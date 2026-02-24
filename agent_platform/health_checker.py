"""
agent_platform/health_checker.py

Async background task — pings each agent's /health endpoint every 30 seconds.
Detects telemetry gaps (agent up but SDK not sending data).
Updates platform.agents with health_status and last_health_check_at.

Health states:
    healthy   — agent is up and telemetry is flowing
    unhealthy — agent health check failed (agent down)
    sdk_issue — agent is up but no telemetry received recently
    unknown   — no agent_url configured or never checked
"""

import asyncio

import requests as http_requests
import psycopg2.extras
from loguru import logger

from config.settings import settings
from agent_platform.agent_manager import _fw_conn

_stop_flag = False


def stop_health_checker():
    global _stop_flag
    _stop_flag = True
    logger.info("Health Checker shutdown requested.")


async def start_health_checker():
    """Infinite loop — runs every HEALTH_CHECK_INTERVAL_S seconds."""
    global _stop_flag
    _stop_flag = False
    logger.info("Health Checker started.")

    while not _stop_flag:
        try:
            await asyncio.to_thread(_health_check_cycle)
        except Exception as e:
            logger.error(f"Health check cycle error: {e}")
        await asyncio.sleep(settings.HEALTH_CHECK_INTERVAL_S)

    logger.info("Health Checker stopped.")


def _health_check_cycle():
    """Single cycle — synchronous, runs in thread pool."""
    try:
        conn = _fw_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM platform.agents WHERE status = 'active'")
        agents = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Health checker: failed to fetch agents: {e}")
        return

    for agent in agents:
        agent_id = agent["agent_id"]
        agent_name = agent["agent_name"]
        agent_url = agent.get("agent_url")
        prev_status = agent.get("health_status", "unknown")

        if not agent_url:
            _update_health(agent_id, "unknown", "No agent_url configured")
            continue

        # Step 1: Ping /health
        is_up = _ping_health(agent_url)

        if not is_up:
            new_status = "unhealthy"
            detail = "Health check failed — agent unreachable"
            _update_health(agent_id, new_status, detail)

            # Alert only on transition (not every cycle)
            if prev_status != "unhealthy":
                logger.warning(f"Agent '{agent_name}' is now UNHEALTHY")
            continue

        # Step 2: Check telemetry gap
        has_telemetry = _has_recent_telemetry(
            agent_name, settings.TELEMETRY_GAP_THRESHOLD_M
        )

        if has_telemetry:
            _update_health(agent_id, "healthy", None)
            if prev_status != "healthy":
                logger.info(f"Agent '{agent_name}' is now HEALTHY")
        else:
            new_status = "sdk_issue"
            detail = f"Agent is up but no telemetry in last {settings.TELEMETRY_GAP_THRESHOLD_M} minutes"
            _update_health(agent_id, new_status, detail)

            if prev_status != "sdk_issue":
                logger.warning(f"Agent '{agent_name}' has SDK ISSUE — no telemetry")


def _ping_health(agent_url: str) -> bool:
    """GET base_url/health with a 5-second timeout.

    agent_url may include a path (e.g. http://localhost:8001/query),
    so we extract the base (scheme + host + port) for the health check.
    """
    try:
        from urllib.parse import urlparse
        parsed = urlparse(agent_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        url = f"{base_url}/health"
        resp = http_requests.get(url, timeout=5)
        return resp.status_code < 400
    except Exception:
        return False


def _has_recent_telemetry(agent_name: str, threshold_minutes: int) -> bool:
    """Check if monitoring.queries has a row for this agent within the threshold."""
    try:
        conn = _fw_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT EXISTS(
                SELECT 1 FROM monitoring.queries
                WHERE agent_type = %s
                AND created_at > NOW() - make_interval(mins => %s)
            )""",
            (agent_name, threshold_minutes)
        )
        result = cur.fetchone()[0]
        cur.close()
        conn.close()
        return result
    except Exception as e:
        logger.error(f"_has_recent_telemetry failed: {e}")
        return True  # Assume OK on DB failure to avoid false positives


def _update_health(agent_id: int, health_status: str, detail: str | None):
    """Write health_status and last_health_check_at to platform.agents."""
    try:
        conn = _fw_conn()
        cur = conn.cursor()
        cur.execute(
            """UPDATE platform.agents
               SET health_status = %s,
                   health_detail = %s,
                   last_health_check_at = NOW()
               WHERE agent_id = %s""",
            (health_status, detail, agent_id)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"_update_health failed: {e}")
