"""
platform/poller.py

Async background poller — connects to each registered agent's DB,
fetches new rows from their query_log table, and runs the evaluation pipeline.

Called at FastAPI startup via:
    asyncio.create_task(start_polling())
"""

import asyncio
import uuid
from datetime import datetime

import psycopg2
import psycopg2.extras
from loguru import logger

from config.settings import settings
from agent_platform.agent_manager import AgentManager, _fw_conn

_stop_flag = False


def stop_polling():
    global _stop_flag
    _stop_flag = True
    logger.info("Poller shutdown requested.")


async def start_polling():
    """Infinite loop — runs every 5 seconds, dispatches due agents."""
    global _stop_flag
    _stop_flag = False
    logger.info("DB Poller started.")

    while not _stop_flag:
        try:
            await asyncio.to_thread(_poll_cycle)
        except Exception as e:
            logger.error(f"Poller cycle error: {e}")
        await asyncio.sleep(5)

    logger.info("DB Poller stopped.")


def _poll_cycle():
    """Single poll cycle — synchronous, runs in a thread pool."""
    mgr = AgentManager()
    agents = mgr.get_all_agents()

    now = datetime.now()

    for agent in agents:
        if agent["status"] != "active":
            continue

        last_polled = agent.get("last_polled_at")
        interval    = agent.get("poll_interval_s", 30)

        # Check if agent is due for polling
        if last_polled is not None:
            # Strip timezone info for comparison (DB stores naive local time)
            if last_polled.tzinfo is not None:
                last_polled = last_polled.replace(tzinfo=None)
            elapsed = (now - last_polled).total_seconds()
            if elapsed < interval:
                continue

        agent_id   = agent["agent_id"]
        agent_name = agent["agent_name"]

        try:
            _poll_agent(agent_id, agent_name, agent["db_url"], mgr)
            # Update last_polled_at
            conn = _fw_conn()
            cur  = conn.cursor()
            cur.execute(
                "UPDATE platform.agents SET last_polled_at = NOW() WHERE agent_id = %s",
                (agent_id,)
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Poll failed for agent '{agent_name}': {e}")
            mgr.update_agent_status(agent_id, "error", str(e))


def _poll_agent(agent_id: int, agent_name: str, db_url: str, mgr: AgentManager):
    """Fetch new query_log rows for one agent and evaluate each."""
    # Get query log config + current watermark
    config = _get_log_config(agent_id)
    if not config:
        return  # No query_log table — agent uses SDK for ingestion

    schema_name   = config["schema_name"]
    table_name    = config["table_name"]
    qt_col        = config["query_text_column"]
    sql_col       = config["sql_column"]
    ts_col        = config["timestamp_column"]
    status_col    = config.get("status_column")
    error_col     = config.get("error_column")
    watermark     = config.get("last_seen_timestamp")

    # Build SELECT — always include ts + qt + sql; optionally status/error
    extra_cols = ""
    if status_col:
        extra_cols += f", {status_col}"
    if error_col:
        extra_cols += f", {error_col}"

    if watermark is None:
        where_clause = "TRUE"
        params = ()
    else:
        where_clause = f"{ts_col} > %s"
        params = (watermark,)

    query = (
        f"SELECT {ts_col}, {qt_col}, {sql_col}{extra_cols} "
        f"FROM {schema_name}.{table_name} "
        f"WHERE {where_clause} "
        f"ORDER BY {ts_col} ASC "
        f"LIMIT 100"
    )

    try:
        ext_conn = psycopg2.connect(db_url)
        ext_cur  = ext_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        ext_cur.execute(query, params)
        rows = ext_cur.fetchall()
        ext_cur.close()
        ext_conn.close()
    except Exception as e:
        logger.error(f"Failed to fetch from agent '{agent_name}' DB: {e}")
        raise

    if not rows:
        return

    logger.info(f"Poller: {len(rows)} new rows from agent '{agent_name}'")

    new_watermark = watermark
    for row in rows:
        ts          = row[ts_col]
        query_text  = row[qt_col]
        generated_sql = row[sql_col]
        status      = row[status_col] if status_col and status_col in row else "success"
        error_msg   = row[error_col]  if error_col  and error_col  in row else None

        query_id = f"POLL-{agent_name}-{uuid.uuid4().hex[:8]}"

        _store_and_evaluate(
            query_id=query_id,
            query_text=query_text,
            agent_name=agent_name,
            generated_sql=generated_sql,
            status=status,
            error=error_msg,
        )

        if ts and (new_watermark is None or ts > new_watermark):
            new_watermark = ts

    # Update watermark
    if new_watermark != watermark:
        _update_watermark(agent_id, new_watermark)


def _get_log_config(agent_id: int) -> dict | None:
    """Fetch query_log_config for an agent."""
    try:
        conn = _fw_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM platform.query_log_config WHERE agent_id = %s",
            (agent_id,)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"_get_log_config failed: {e}")
        return None


def _update_watermark(agent_id: int, ts):
    """Persist the new watermark timestamp."""
    try:
        conn = _fw_conn()
        cur  = conn.cursor()
        cur.execute(
            "UPDATE platform.query_log_config SET last_seen_timestamp = %s WHERE agent_id = %s",
            (ts, agent_id)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"_update_watermark failed: {e}")


def _store_and_evaluate(
    query_id: str,
    query_text: str,
    agent_name: str,
    generated_sql: str,
    status: str,
    error: str | None,
):
    """
    Insert the polled query into monitoring.queries and run the evaluation pipeline.
    Mirrors the process_ingest_background logic from api/main.py.
    """
    try:
        # 1. Insert into monitoring.queries
        conn = _fw_conn()
        cur  = conn.cursor()
        cur.execute(
            """INSERT INTO monitoring.queries
                   (query_id, query_text, agent_type, generated_sql, status)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (query_id) DO NOTHING""",
            (query_id, query_text, agent_name, generated_sql, status)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"_store_and_evaluate: DB insert failed: {e}")
        return

    # Step 2: Drift Detection (only for successful queries with SQL)
    if status != "error" and generated_sql:
        try:
            from monitoring.drift_detector import DriftDetector
            drift_detector = DriftDetector()
            drift_detector.detect(query_id, query_text, agent_name)
        except Exception as e:
            logger.error(f"_store_and_evaluate: drift detection failed for {query_id}: {e}")

    if not generated_sql or status == "error":
        return

    # Step 3: Run evaluation pipeline
    try:
        from evaluation.evaluator import Evaluator
        evaluator = Evaluator(agent_type=agent_name)
        result = evaluator.evaluate(
            query_text=query_text,
            generated_sql=generated_sql,
            query_id=query_id,
        )

        # Store result — evaluate() only stores internally for heuristic/error paths,
        # the 3-step LLM path (ground truth found) does NOT store, so we must do it here.
        if "error_classification" not in result:
            evaluator.store_result(result)

        logger.info(
            f"Polled query evaluated: query_id={query_id} "
            f"result={result.get('final_result')} score={result.get('final_score')}"
        )
    except Exception as e:
        logger.error(f"_store_and_evaluate: evaluation failed for {query_id}: {e}")
