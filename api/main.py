
import json
import os
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
import uuid
from datetime import datetime
import asyncio
from fastapi import FastAPI, HTTPException, Query, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
from auth.api_keys import hash_api_key
from dotenv import load_dotenv
from loguru import logger

# Load environment variables from .env file
load_dotenv()

from config.settings import settings
from auth.azure_auth import get_current_user, require_auth, AuthUser
from alerts.alert_service import alert_service, AlertType

# Initialize FastAPI app for monitoring & observability
app = FastAPI(
    title="Unilever Procurement GPT — Observability Backend",
    version="2.0",
    description="Centralized Observability & Monitoring System (Drift, Eval, Metrics)"
)

# Enable CORS for frontend dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Singleton instances (lazy-loaded to avoid startup delays)
_drift_detector = None
_error_classifier = None
_ground_truth_cache = None
_semantic_matcher = None
db_pool = None

from monitoring.baseline_manager import initialize_baseline_if_needed
from evaluation.semantic_match import SemanticMatcher
import evaluation.semantic_match
from agent_platform.poller import start_polling, stop_polling
from agent_platform.health_checker import start_health_checker, stop_health_checker
from agent_platform.agent_manager import AgentManager
from agent_platform.schema_monitor_scheduler import SchemaMonitorScheduler
from database.init_db import migrate_schema_tables

# ==================== GLOBAL STATE ====================
schema_scheduler = None

# ==================== STARTUP & SHUTDOWN ====================

@app.on_event("startup")
async def startup_event():
    """Initialize DB pool, semantic matcher, and drift baseline on app start."""
    global db_pool, schema_scheduler
    logger.info("Starting up...")

    try:
        # Create PostgreSQL connection pool (min=1, max=20 connections)
        db_pool = pool.SimpleConnectionPool(
            1, 20,
            host=settings.DB_HOST, port=settings.DB_PORT, database=settings.DB_NAME, user=settings.DB_USER, password=settings.DB_PASSWORD
        )
        logger.info("DB Connection Pool initialized")

        # Run schema migrations (idempotent — safe to run every startup)
        migrate_schema_tables()

        # Load semantic matcher in background thread (heavy: loads embeddings)
        async def init_matcher():
            try:
                logger.info("Initializing Semantic Matcher in background...")
                from agent_platform.gt_storage import get_gt_storage
                storage = get_gt_storage()
                data = storage.load("test.json")
                matcher = SemanticMatcher()
                if data is not None:
                    await asyncio.to_thread(matcher.load_from_data, data)
                evaluation.semantic_match._matcher_instance = matcher
                logger.info("Semantic Matcher background initialization complete.")
            except Exception as e:
                logger.error(f"Semantic Matcher initialization failed: {e}")

        asyncio.create_task(init_matcher())

        # Initialize drift baseline if not already present in DB
        asyncio.create_task(asyncio.to_thread(initialize_baseline_if_needed))

        # Start DB poller for registered agents
        asyncio.create_task(start_polling())

        # Start health checker for agent monitoring
        asyncio.create_task(start_health_checker())

        # Start schema monitoring scheduler (every 10 hours)
        try:
            schema_scheduler = SchemaMonitorScheduler()
            schema_scheduler.start()
            logger.info("✅ Schema monitor scheduler started (10-hour interval)")
        except Exception as e:
            logger.error(f"Failed to start schema monitor scheduler: {e}")

    except Exception as e:
        logger.error(f"Startup failed: {e}")

@app.on_event("shutdown")
def shutdown_event():
    """Close all DB connections on app shutdown."""
    global db_pool, schema_scheduler
    stop_polling()
    stop_health_checker()

    # Stop schema monitor scheduler
    if schema_scheduler:
        try:
            schema_scheduler.stop()
            logger.info("Schema monitor scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")

    if db_pool:
        db_pool.closeall()
        logger.info("DB Connection Pool closed")

# ==================== SINGLETON GETTERS (Lazy Init) ====================

def get_drift_detector():
    """Lazy-load drift detector singleton (uses Bedrock Titan embeddings)."""
    global _drift_detector
    if _drift_detector is None:
        from monitoring.drift_detector import DriftDetector
        _drift_detector = DriftDetector()
        logger.info("Drift detector initialized")
    return _drift_detector

def get_error_classifier():
    """Lazy-load error classifier singleton (categorizes SQL/agent errors)."""
    global _error_classifier
    if _error_classifier is None:
        from monitoring.error_classifier import ErrorClassifier
        _error_classifier = ErrorClassifier()
        logger.info("Error classifier initialized")
    return _error_classifier

def get_semantic_matcher():
    """Lazy-load semantic matcher singleton (matches queries to ground truth)."""
    global _semantic_matcher
    if _semantic_matcher is None:
        _semantic_matcher = SemanticMatcher()
        logger.info("Semantic matcher initialized")
    return _semantic_matcher

def get_ground_truth():
    """Load ground truth queries from storage (S3 or local) and initialize semantic matcher."""
    global _ground_truth_cache
    if _ground_truth_cache is None:
        try:
            from agent_platform.gt_storage import get_gt_storage
            storage = get_gt_storage()
            gt_list = storage.load("all_queries.json")

            if gt_list is None:
                raise FileNotFoundError("all_queries.json not found in GT storage")

            # Build lookup cache: normalized query text -> ground truth entry
            _ground_truth_cache = {}
            for q in gt_list:
                key = q["query_text"].strip().lower().rstrip("?.!")
                _ground_truth_cache[key] = {
                    "query_id": q["query_id"],
                    "sql": q["sql"],
                    "complexity": q["complexity"],
                    "agent_type": q["agent_type"]
                }
            logger.info(f"Ground truth loaded: {len(_ground_truth_cache)} queries")

            # Also initialize semantic matcher with ground truth if not ready
            matcher = get_semantic_matcher()
            if not matcher.is_ready:
                matcher.initialize(_ground_truth_cache)
        except Exception as e:
            logger.warning(f"Could not load ground truth: {e}")
            _ground_truth_cache = {}
    return _ground_truth_cache

# ==================== DB HELPER ====================

@contextmanager
def get_db():
    """Get a DB connection from pool, auto-return on exit."""
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        db_pool.putconn(conn)

# ==================== REQUEST MODELS ====================

class IngestRequest(BaseModel):
    """Telemetry payload sent by agents after processing a user query."""
    query_text: str
    agent_type: str            # 'spend' or 'demand'
    status: str                # 'success' or 'error'
    sql: Optional[str] = None  # Generated SQL (only if status=success)
    error: Optional[str] = None  # Error message (only if status=error)
    execution_time_ms: Optional[float] = 0.0

class EvaluateRequest(BaseModel):
    """Direct evaluation request with ground truth SQL provided."""
    query_id:         str
    query_text:       str
    agent_type:       str
    generated_sql:    str
    ground_truth_sql: str
    complexity:       str = "unknown"

class BaselineUpdateRequest(BaseModel):
    """Request to update drift detection baseline with new queries."""
    agent_type: str = Field(..., description="'spend' or 'demand'")
    queries:    List[str]

# ==================== HEALTH & AUTH ENDPOINTS ====================

@app.get("/health")
def health():
    """Health check - verifies database connectivity."""
    db_status = "ok"
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
    except Exception:
        db_status = "down"

    return {
        "status": "ok",
        "database": db_status,
        "auth_enabled": settings.AUTH_ENABLED
    }

@app.get("/api/v1/auth/me")
async def get_user_info(user: AuthUser = Depends(require_auth)):
    """Return authenticated user info from Azure AD JWT token."""
    return {
        "authenticated": True,
        "sub": user.sub,
        "name": user.name,
        "email": user.email,
        "roles": user.roles,
        "tenant_id": user.tenant_id
    }

@app.get("/api/v1/auth/config")
def get_auth_config():
    """Return Azure AD config for frontend MSAL initialization."""
    return {
        "auth_enabled": settings.AUTH_ENABLED,
        "tenant_id": settings.AZURE_AD_TENANT_ID if settings.AUTH_ENABLED else None,
        "client_id": settings.AZURE_AD_CLIENT_ID if settings.AUTH_ENABLED else None,
        "authority": settings.azure_ad_authority if settings.AUTH_ENABLED else None,
        "scopes": [f"api://{settings.AZURE_AD_CLIENT_ID}/access"] if settings.AUTH_ENABLED else []
    }

# ==================== CORE PIPELINE: INGEST & PROCESS ====================

def process_ingest_background(query_id: str, req: IngestRequest):
    """
    Background processing pipeline (runs after ingest response is sent):
    1. Drift Detection (only if agent succeeded)
    2. Evaluation (if SQL generated successfully) — includes conditional error classification
    3. Legacy Error Classification (if agent returned an error before SQL generation)
    """
    # Step 1: Drift Detection — skip for error queries (no SQL to compare)
    if req.status != "error":
        try:
            drift_detector = get_drift_detector()
            # Compare query embedding against baseline centroid
            result = drift_detector.detect(query_id, req.query_text, req.agent_type)

            # Send email alert if drift is high
            if result.get("drift_classification") == "high":
                logger.warning(f"High Drift Detected for {query_id}. Sending alert...")
                alert_service.alert_high_drift(
                    query_id=query_id,
                    query_text=req.query_text,
                    drift_score=result["drift_score"],
                    agent_type=req.agent_type
                )
        except Exception as e:
            logger.error(f"Drift check failed: {e}")

    # Step 2: Evaluation — run 3-step (if ground truth found) or 4-layer heuristic
    if req.sql and req.status == "success":
        try:
            from evaluation.evaluator import Evaluator
            evaluator = Evaluator(req.agent_type)
            eval_result = evaluator.evaluate(
                query_id=query_id,
                query_text=req.query_text,
                generated_sql=req.sql,
                ground_truth_sql=None  # Evaluator will search for ground truth via semantic matcher
            )

            # Only store here if evaluate() didn't already store (error classification path stores internally)
            if "error_classification" not in eval_result:
                evaluator.store_result(eval_result)

        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            # Classify the evaluation exception itself as an error
            try:
                error_classifier = get_error_classifier()
                error_classifier.classify(str(e), query_id)
            except Exception as e2:
                logger.error(f"Failed to classify error: {e2}")

    # Step 3: Legacy error classification — for agent-level failures (no SQL generated)
    if req.status == "error" and req.error:
        try:
            error_classifier = get_error_classifier()
            error_classifier.classify(req.error, query_id)
        except Exception as e:
            logger.error(f"Error classify failed: {e}")

@app.post("/api/v1/monitor/ingest")
async def ingest_telemetry(request: Request, req: IngestRequest, background_tasks: BackgroundTasks):
    """Main entry point — agents send telemetry here after each query. Requires API key."""
    # Validate API key
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    key_hash = hash_api_key(api_key)
    mgr = AgentManager()
    agent = mgr.get_agent_by_api_key_hash(key_hash)
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Generate unique query ID with agent type prefix
    query_id = f"ASYNC-{agent['agent_name'].upper()}-{uuid.uuid4().hex[:8]}"
    req.agent_type = agent["agent_name"]
    logger.info(f"[{query_id}] Ingesting telemetry: {req.query_text}")

    # Store raw query record in monitoring.queries table
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO monitoring.queries (query_id, query_text, agent_type, status, generated_sql, execution_time_ms)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (query_id, req.query_text, req.agent_type, req.status, req.sql, req.execution_time_ms))
            conn.commit()
            cur.close()
    except Exception as e:
        logger.error(f"DB Insert failed: {e}")
        raise HTTPException(status_code=500, detail=f"Database Ingest Failed: {str(e)}")

    # Queue drift + evaluation + error classification as background task
    background_tasks.add_task(process_ingest_background, query_id, req)

    return {"status": "ingested", "query_id": query_id}

# ==================== METRICS ENDPOINT ====================

@app.get("/api/v1/metrics")
def get_metrics(agent_type: Optional[str] = Query(None)):
    """Return overall and per-agent evaluation metrics with accuracy trend."""
    with get_db() as conn:
        cur = conn.cursor()

        # Build optional agent_type filter
        where_eval = ""
        where_query = "WHERE execution_time_ms IS NOT NULL"
        params_eval = []
        params_query = []

        if agent_type:
            where_eval = "WHERE agent_type = %s"
            where_query += " AND agent_type = %s"
            params_eval = [agent_type]
            params_query = [agent_type]

        # Fetch overall stats: total evaluations, passed count, avg score, component scores
        cur.execute(f"""
            SELECT COUNT(*),
                   SUM(CASE WHEN result = 'PASS' THEN 1 ELSE 0 END),
                   AVG(final_score),
                   AVG(structural_score),
                   AVG(semantic_score),
                   AVG(llm_score),
                   AVG((evaluation_data->'scores'->>'result_validation')::float)
            FROM monitoring.evaluations
            {where_eval}
        """, params_eval)
        row = cur.fetchone()
        total, passed, avg_score = row[0], row[1], row[2]
        avg_structural = row[3]
        avg_semantic = row[4]
        avg_llm = row[5]
        avg_result_validation = row[6]

        # Fetch global average latency from queries table
        cur.execute(f"SELECT AVG(execution_time_ms) FROM monitoring.queries {where_query}", params_query)
        row_global_lat = cur.fetchone()
        avg_latency = row_global_lat[0] if row_global_lat and row_global_lat[0] else 0.0

        total = total or 0
        passed = passed or 0

        # Fetch per-agent breakdown: total, passed, accuracy, avg_score, latency, component scores
        cur.execute(f"""
            SELECT agent_type,
                   COUNT(*),
                   SUM(CASE WHEN result = 'PASS' THEN 1 ELSE 0 END),
                   AVG(final_score),
                   AVG(structural_score),
                   AVG(semantic_score),
                   AVG(llm_score),
                   AVG((evaluation_data->'scores'->>'result_validation')::float)
            FROM monitoring.evaluations
            {where_eval}
            GROUP BY agent_type
        """, params_eval)

        per_agent = {}
        eval_rows = cur.fetchall()

        for row in eval_rows:
            agent = row[0]
            t, p = row[1], row[2] or 0

            # Get per-agent average latency
            cur.execute("SELECT AVG(execution_time_ms) FROM monitoring.queries WHERE agent_type = %s AND execution_time_ms IS NOT NULL", (agent,))
            row_lat = cur.fetchone()
            agent_lat = row_lat[0] if row_lat and row_lat[0] else 0.0

            per_agent[agent] = {
                "total":    t,
                "passed":   p,
                "accuracy": round(p / t * 100, 1) if t else 0,
                "avg_score": round(float(row[3]), 3) if row[3] else 0.0,
                "avg_latency": round(float(agent_lat), 1),
                "component_scores": {
                    "structural": round(float(row[4] or 0), 3),
                    "semantic": round(float(row[5] or 0), 3),
                    "llm_judge": round(float(row[6] or 0), 3),
                    "result_validation": round(float(row[7] or 0), 3) if row[7] else None
                }
            }

        # Fetch 7-day accuracy trend grouped by day and agent type
        where_trend = "WHERE q.created_at > NOW() - INTERVAL '7 days'"
        params_trend = []
        if agent_type:
            where_trend += " AND q.agent_type = %s"
            params_trend = [agent_type]

        cur.execute(f"""
            SELECT
                to_char(date_trunc('day', q.created_at), 'Mon DD') as time_str,
                q.agent_type,
                AVG(CASE WHEN e.result='PASS' THEN 100.0 ELSE 0.0 END) as acc
            FROM monitoring.queries q
            JOIN monitoring.evaluations e ON q.query_id = e.query_id
            {where_trend}
            GROUP BY 1, 2
            ORDER BY min(q.created_at)
        """, params_trend)

        # Build trend data — dynamic agent keys from query results
        trend_map = {}
        for row in cur.fetchall():
            time_str, agent_typ, acc = row
            if time_str not in trend_map:
                trend_map[time_str] = {"time": time_str}
            key = agent_typ.capitalize()
            trend_map[time_str][key] = round(float(acc), 1)

        trend_data = list(trend_map.values())
        cur.close()

    return {
        "overall": {
            "total_evaluations": total,
            "passed":            passed,
            "failed":            total - passed,
            "accuracy":          round(passed / total * 100, 1) if total else 0,
            "avg_score":         round(float(avg_score or 0), 3),
            "avg_latency":       round(float(avg_latency), 1),
            "component_scores": {
                "structural": round(float(avg_structural or 0), 3),
                "semantic": round(float(avg_semantic or 0), 3),
                "llm_judge": round(float(avg_llm or 0), 3),
                "result_validation": round(float(avg_result_validation or 0), 3) if avg_result_validation else None
            }
        },
        "per_agent": per_agent,
        "trend": trend_data
    }

# ==================== DRIFT ENDPOINT ====================

@app.get("/api/v1/drift")
def get_drift(agent_type: Optional[str] = Query(None)):
    """Return drift distribution, anomalies, high-drift samples, and trend."""
    with get_db() as conn:
        cur = conn.cursor()

        # Filter by agent_type via JOIN with monitoring.queries (works for any agent name)
        agent_where = "WHERE LOWER(q.agent_type) = LOWER(%s)" if agent_type else ""
        agent_and   = "AND LOWER(q.agent_type) = LOWER(%s)" if agent_type else ""
        params      = [agent_type] if agent_type else []

        # Get drift classification distribution (low/medium/high counts + avg score)
        cur.execute(f"""
            SELECT LOWER(d.drift_classification), COUNT(*), AVG(d.drift_score)
            FROM monitoring.drift_monitoring d
            JOIN monitoring.queries q ON d.query_id = q.query_id
            {agent_where}
            GROUP BY LOWER(d.drift_classification)
            ORDER BY LOWER(d.drift_classification)
        """, params)
        distribution = {
            row[0]: {"count": row[1], "avg_drift_score": round(float(row[2]), 3)}
            for row in cur.fetchall()
        }

        # Count total anomalies (flagged by drift detector)
        cur.execute(f"""
            SELECT COUNT(*) FROM monitoring.drift_monitoring d
            JOIN monitoring.queries q ON d.query_id = q.query_id
            WHERE d.is_anomaly = true {agent_and}
        """, params)
        anomalies = cur.fetchone()[0]

        # Get top 20 high-drift queries with details
        cur.execute(f"""
            SELECT d.query_id, d.drift_score, d.drift_classification, q.query_text, q.generated_sql, q.agent_type
            FROM monitoring.drift_monitoring d
            LEFT JOIN monitoring.queries q ON d.query_id = q.query_id
            WHERE LOWER(d.drift_classification) = 'high' {agent_and}
            ORDER BY d.drift_score DESC LIMIT 20
        """, params)
        high_samples = [
            {
                "query_id": r[0],
                "drift_score": round(float(r[1]), 3),
                "classification": r[2],
                "query_text": r[3] or "Unknown",
                "sql": r[4] or "Not Available (No Eval)",
                "agent_type": r[5] or "spend"
            }
            for r in cur.fetchall()
        ]

        # Get daily drift score trend
        cur.execute(f"""
            SELECT date_trunc('day', q.created_at) as date, AVG(d.drift_score)
            FROM monitoring.drift_monitoring d
            JOIN monitoring.queries q ON d.query_id = q.query_id
            {agent_where}
            GROUP BY 1
            ORDER BY 1
        """, params)

        trend = []
        for row in cur.fetchall():
            trend.append({
                "date": row[0].strftime("%b %d") if row[0] else "Unknown",
                "avg_score": round(float(row[1]), 3) if row[1] else 0.0
            })

        cur.close()

    return {
        "distribution":      distribution,
        "total_anomalies":   anomalies,
        "high_drift_samples": high_samples,
        "trend":             trend
    }

# ==================== EXECUTE SQL ENDPOINT ====================

class ExecuteSqlRequest(BaseModel):
    sql: str
    agent_type: str

@app.post("/api/v1/execute-sql")
def execute_sql_endpoint(req: ExecuteSqlRequest):
    """Safely execute a read-only SQL query on the agent's database and return results."""
    from evaluation.output_validators.query_executor import QueryExecutor

    # Get agent's db_url from platform registry
    try:
        mgr = AgentManager()
        agent = mgr.get_agent_by_name(req.agent_type)
        if not agent or not agent.get("db_url"):
            raise HTTPException(status_code=404, detail=f"Agent '{req.agent_type}' not found or has no DB URL")
        db_url = agent["db_url"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load agent: {str(e)}")

    executor = QueryExecutor(timeout_seconds=10, max_rows=100)
    result = executor.execute(req.sql, db_url)

    if not result.success:
        return {"status": "error", "error": result.error, "results": []}

    # Convert rows to list of dicts for frontend table rendering
    columns = result.columns or []
    rows_as_dicts = [
        {columns[i]: (str(v) if v is not None else None) for i, v in enumerate(row)}
        for row in (result.rows or [])
    ]

    return {
        "status": "success",
        "results": rows_as_dicts,
        "row_count": result.row_count,
        "execution_time_ms": round(result.execution_time_ms or 0, 2)
    }

# ==================== ERRORS ENDPOINT ====================

@app.get("/api/v1/errors")
def get_errors(category: Optional[str] = Query(None), limit: int = Query(20), agent_type: Optional[str] = Query(None)):
    """Return error summary by category and recent error list."""
    with get_db() as conn:
        cur = conn.cursor()

        # Build optional join/filter for agent_type
        summary_join = ""
        summary_where = ""
        summary_params = []

        if agent_type:
            summary_join = "JOIN monitoring.queries q ON e.query_id = q.query_id"
            summary_where = "WHERE q.agent_type = %s"
            summary_params = [agent_type]

        # Get error count grouped by category and severity
        cur.execute(f"""
            SELECT e.error_category, e.severity, COUNT(*)
            FROM monitoring.errors e
            {summary_join}
            {summary_where}
            GROUP BY e.error_category, e.severity
            ORDER BY e.error_category
        """, tuple(summary_params))

        categories = {}
        for row in cur.fetchall():
            cat = row[0]
            if cat not in categories:
                categories[cat] = {"count": 0, "severities": {}}
            categories[cat]["count"]            += row[2]
            categories[cat]["severities"][row[1]] = row[2]

        # Get recent errors with optional category/agent_type filter
        q_sql = """
            SELECT e.query_id, e.error_category, e.error_message, e.severity, q.query_text
            FROM monitoring.errors e
            LEFT JOIN monitoring.queries q ON e.query_id = q.query_id
        """
        params = []
        wheres = []

        if category:
            wheres.append("e.error_category = %s")
            params.append(category)

        if agent_type:
            wheres.append("q.agent_type = %s")
            params.append(agent_type)

        if wheres:
            q_sql += " WHERE " + " AND ".join(wheres)

        q_sql += " ORDER BY e.first_seen DESC LIMIT %s"
        params.append(limit)

        cur.execute(q_sql, tuple(params))
        recent = [
            {
                "query_id": r[0],
                "category": r[1],
                "message": r[2],
                "severity": r[3],
                "query_text": r[4] or "Unknown"
            }
            for r in cur.fetchall()
        ]

        cur.close()

    return {
        "total_errors": sum(c["count"] for c in categories.values()),
        "categories":   categories,
        "recent_errors": recent
    }

@app.get("/api/v1/errors/{category}")
def get_errors_by_category(category: str):
    """Return all errors for a specific error category."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT query_id, error_message, severity, suggested_fix, first_seen
            FROM monitoring.errors
            WHERE error_category = %s
            ORDER BY first_seen DESC
        """, (category,))
        errors = [
            {
                "query_id":      r[0],
                "message":       r[1],
                "severity":      r[2],
                "suggested_fix": r[3],
                "first_seen":    str(r[4])
            }
            for r in cur.fetchall()
        ]
        cur.close()
    return {"category": category, "count": len(errors), "errors": errors}

# ==================== HISTORY ENDPOINT ====================

@app.get("/api/v1/history")
def get_history(limit: int = 50, agent_type: Optional[str] = Query(None)):
    """Return recent query history with evaluation, error, and drift data joined."""
    with get_db() as conn:
        cur = conn.cursor()

        # Filter: exclude queries with no SQL or error status
        where_clause = "WHERE q.generated_sql IS NOT NULL AND q.generated_sql != '' AND q.generated_sql != '-- No SQL Generated' AND q.status != 'error'"
        params = []
        if agent_type:
            where_clause += " AND LOWER(q.agent_type) = LOWER(%s)"
            params.append(agent_type)

        params.append(limit)

        # Join queries with evaluations, errors, and drift for full picture
        cur.execute(f"""
            SELECT DISTINCT ON (q.created_at, q.query_id)
                q.query_text,
                e.result,
                e.confidence,
                r.error_category,
                q.agent_type,
                q.created_at,
                q.query_id,
                d.drift_score,
                d.drift_classification,
                (e.evaluation_data->'scores'->>'result_validation')::float
            FROM monitoring.queries q
            LEFT JOIN monitoring.evaluations e ON q.query_id = e.query_id
            LEFT JOIN monitoring.errors r ON q.query_id = r.query_id
            LEFT JOIN monitoring.drift_monitoring d ON q.query_id = d.query_id
            {where_clause}
            ORDER BY q.created_at DESC, q.query_id
            LIMIT %s
        """, tuple(params))

        rows = cur.fetchall()
        cur.close()

    # Format each row into a frontend-friendly dict
    history = []
    for row in rows:
        history.append({
            "prompt": row[0],
            "correctness_verdict": row[1] or "N/A",
            "evaluation_confidence": row[2] if row[2] is not None else 0.0,
            "error_bucket": row[3] or "None",
            "dataset": row[4],
            "timestamp": str(row[5]),
            "query_id": row[6],
            "drift_score": row[7] if row[7] is not None else 0.0,
            "drift_level": row[8] or "N/A",
            "output_score": row[9] if row[9] is not None else None
        })
    return history

# ==================== BASELINE ENDPOINT ====================

@app.post("/api/v1/baseline/update")
def update_baseline(req: BaselineUpdateRequest):
    """Manually update drift detection baseline with new representative queries."""
    # Dynamic allowed-agents check from platform.agents + legacy fallback
    try:
        mgr = AgentManager()
        registered = {a["agent_name"] for a in mgr.get_all_agents()}
        allowed = registered | {"spend", "demand"}
    except Exception:
        allowed = {"spend", "demand"}

    if req.agent_type not in allowed:
        raise HTTPException(status_code=400, detail=f"Unknown agent_type '{req.agent_type}'")

    dd = get_drift_detector()
    result = dd.create_baseline(req.agent_type, req.queries)
    return {"status": "ok", "result": result}

# ==================== ALERTS ENDPOINT ====================

@app.get("/api/v1/alerts")
def get_alerts():
    """Generate real-time alerts based on accuracy degradation and high drift."""
    alerts = []

    with get_db() as conn:
        cur = conn.cursor()

        # Check if avg score of last 50 evaluations drops below 90%
        cur.execute("""
            SELECT AVG(final_score), COUNT(*)
            FROM (SELECT final_score FROM monitoring.evaluations ORDER BY created_at DESC LIMIT 50) sub
        """)
        row = cur.fetchone()
        avg_score = float(row[0]) if row and row[0] is not None else 1.0
        count = row[1] if row else 0

        if count > 5 and avg_score < 0.90:
             alerts.append({
                "id": str(uuid.uuid4()),
                "title": "Evaluation Accuracy Degradation",
                "severity": "warning",
                "message": f"Accuracy dropped to {round(avg_score*100, 1)}% (Threshold: 90%)",
                "reason": f"Based on last {count} evaluations.",
                "timestamp": datetime.now().isoformat()
             })

        # Check for high-drift queries in last 24 hours
        cur.execute("""
            SELECT COUNT(*) FROM monitoring.drift_monitoring d
            JOIN monitoring.queries q ON d.query_id = q.query_id
            WHERE d.drift_classification = 'high'
            AND q.created_at > NOW() - INTERVAL '24 hours'
        """)
        high_drift_count = cur.fetchone()[0]

        if high_drift_count > 0:
            alerts.append({
                "id": str(uuid.uuid4()),
                "title": "High Drift Detected",
                "severity": "critical" if high_drift_count > 3 else "warning",
                "message": f"{high_drift_count} High Drift queries detected in last 24h.",
                "reason": "User queries deviate significantly from the baseline.",
                "timestamp": datetime.now().isoformat()
            })

        cur.close()

    return alerts

# ==================== RUN DETAILS ENDPOINT ====================

@app.get("/api/v1/monitor/runs/{query_id}")
def get_run_details(query_id: str):
    """Return full evaluation details for a specific query (used by dashboard expand view)."""
    with get_db() as conn:
        cur = conn.cursor()

        # Join query, evaluation, and drift data for complete picture
        cur.execute("""
            SELECT
                q.query_id, q.query_text, q.agent_type, q.status, q.generated_sql as q_sql, q.created_at,
                e.result, e.confidence, e.final_score, e.reasoning, e.generated_sql as e_sql, e.evaluation_data,
                d.drift_score, d.drift_classification,
                e.structural_score, e.semantic_score, e.llm_score
            FROM monitoring.queries q
            LEFT JOIN monitoring.evaluations e ON q.query_id = e.query_id
            LEFT JOIN monitoring.drift_monitoring d ON q.query_id = d.query_id
            WHERE q.query_id = %s
        """, (query_id,))

        row = cur.fetchone()

        if not row:
             raise HTTPException(status_code=404, detail="Run not found")

        # Parse JSONB evaluation_data (psycopg2 auto-parses JSONB to dict)
        eval_data = row[11] if row[11] else {}
        scores_breakdown = eval_data.get("scores", {})

        # Rename drift_quality -> drift for frontend compatibility
        if "drift_quality" in scores_breakdown and "drift" not in scores_breakdown:
            scores_breakdown["drift"] = scores_breakdown.pop("drift_quality")

        # Fallback: build scores from individual columns if evaluation_data has no scores
        if not scores_breakdown and row[14] is not None:
            scores_breakdown = {
                "structural": float(row[14] or 0),
                "semantic": float(row[15] or 0),
                "llm": float(row[16] or 0)
            }

        data = {
            "query_id": row[0],
            "user_prompt": row[1],
            "agent_type": row[2],
            "status": row[3],
            "generated_sql": row[10] if row[10] else row[4],
            "timestamp": row[5].isoformat() if row[5] else None,
            "evaluation": {
                "verdict": row[6] or "PENDING",
                "confidence": row[7] or 0.0,
                "score": row[8] or 0.0,
                "reasoning": row[9],
                "scores": scores_breakdown,
                "result_validation": eval_data.get("result_validation"),  # NEW: Include result validation details
                "steps": eval_data.get("steps", {}),  # NEW: Include evaluation steps
                "ground_truth_sql": eval_data.get("ground_truth_sql")  # NEW: Include ground truth SQL
            },
            "drift": {
                "score": row[12] if row[12] is not None else 0.0,
                "status": row[13] or "unknown"
            },
            "intent": None
        }

    return data

# ==================== AGENTS SUMMARY ENDPOINT ====================

@app.get("/api/v1/agents/summary")
def get_agents_summary():
    """Return summary card data for each agent (accuracy, requests, latency, status)."""
    summary = []

    # Build dynamic agent list from platform.agents only — no hardcoded fallback
    try:
        mgr = AgentManager()
        registered = mgr.get_all_agents()
        agents = [a["agent_name"] for a in registered]
    except Exception:
        agents = []

    with get_db() as conn:
        cur = conn.cursor()

        for agent in agents:
            try:
                # Get total request count for this agent
                cur.execute("SELECT COUNT(*) FROM monitoring.queries WHERE agent_type = %s", (agent,))
                total_reqs = cur.fetchone()[0]

                # Get average latency for this agent
                cur.execute("""
                    SELECT AVG(execution_time_ms)
                    FROM monitoring.queries
                    WHERE agent_type = %s AND execution_time_ms IS NOT NULL
                """, (agent,))
                row_lat = cur.fetchone()
                avg_lat = row_lat[0] if row_lat and row_lat[0] else 0.0

                # Calculate accuracy (pass rate) for this agent
                cur.execute("""
                    SELECT
                        count(*) filter (where result='PASS') * 100.0 / nullif(count(*), 0)
                    FROM monitoring.evaluations
                    WHERE agent_type = %s
                """, (agent,))
                row_acc = cur.fetchone()
                accuracy = row_acc[0] if row_acc and row_acc[0] else 0.0

                # Get registered agent record from platform.agents
                reg = next((a for a in (registered if registered else []) if a["agent_name"] == agent), None)

                # Use real health check status from DB
                reg_health = reg.get("health_status", "unknown") if reg else "unknown"
                status_map = {
                    "healthy": "Healthy",
                    "unhealthy": "Unhealthy",
                    "sdk_issue": "SDK Issue",
                    "unknown": "Unknown",
                }
                status = status_map.get(reg_health, "Unknown")
                # Override: also flag degraded accuracy
                if status == "Healthy" and accuracy < 80 and total_reqs > 5:
                    status = "Degraded"
                display = reg["display_name"] if reg else f"{agent.capitalize()} GPT"
                description = reg["description"] if reg and reg.get("description") else (
                    "Spend analytics and supplier intelligence" if agent == 'spend'
                    else "Demand forecasting and market analytics"
                )

                summary.append({
                    "id": agent,
                    "agent_id": reg["agent_id"] if reg else None,
                    "name": display,
                    "description": description,
                    "status": status,
                    "accuracy": round(float(accuracy), 1),
                    "requests": total_reqs,
                    "latency_s": round(float(avg_lat) / 1000.0, 2),
                    "gt_status": reg.get("gt_status", "pending") if reg else "pending",
                    "gt_error": reg.get("gt_error") if reg else None,
                    "gt_query_count": reg.get("gt_query_count") if reg else None,
                    "gt_retry_count": reg.get("gt_retry_count", 0) if reg else 0,
                    "schema_version": reg.get("schema_version", 1) if reg else 1,
                    "last_schema_scan_at": str(reg.get("last_schema_scan_at")) if reg and reg.get("last_schema_scan_at") else None,
                    "schema_change_count": reg.get("schema_change_count", 0) if reg else 0,
                })
            except Exception as e:
                logger.error(f"Summary failed for {agent}: {e}")

    return summary


@app.get("/api/v1/agents/health")
def get_agents_health():
    """Return health status for all registered agents."""
    mgr = AgentManager()
    agents = mgr.get_all_agents()
    return [
        {
            "agent_id": a["agent_id"],
            "agent_name": a["agent_name"],
            "health_status": a.get("health_status", "unknown"),
            "health_detail": a.get("health_detail"),
            "last_health_check_at": str(a.get("last_health_check_at")) if a.get("last_health_check_at") else None,
            "agent_url": a.get("agent_url"),
        }
        for a in agents
    ]


# ==================== AGENT MANAGEMENT ENDPOINTS ====================

class RegisterAgentRequest(BaseModel):
    agent_name: str
    db_url: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    agent_url: Optional[str] = None
    poll_interval_s: int = 30


@app.post("/api/v1/agents/register", status_code=201)
def register_agent(req: RegisterAgentRequest, background_tasks: BackgroundTasks):
    """Register a new agent. Triggers schema discovery as a background task."""
    mgr = AgentManager()
    try:
        agent = mgr.register_agent(
            agent_name=req.agent_name,
            db_url=req.db_url,
            display_name=req.display_name,
            description=req.description,
            agent_url=req.agent_url,
            poll_interval_s=req.poll_interval_s,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Kick off discovery + baseline creation in background
    background_tasks.add_task(mgr.discover_and_configure, agent["agent_id"])
    background_tasks.add_task(initialize_baseline_if_needed)

    api_key = agent.get("api_key", "")
    agent_name = agent.get("agent_name", "agent")
    return {
        "message": "Agent registered. Schema discovery started.",
        "agent": agent,
        "sdk_install": "pip install agent-observe-sdk",
        "sdk_snippet": (
            f"from agent_observe_sdk import Observer\n"
            f"observer = Observer(api_key='{api_key}')\n\n"
            f"# Wrap your agent's query function — 1 line, no decorator needed\n"
            f"agent.process_query = observer.wrap(agent.process_query)"
        ),
    }


@app.get("/api/v1/agents")
def list_agents():
    """List all registered agents from platform.agents."""
    mgr = AgentManager()
    return mgr.get_all_agents()


@app.get("/api/v1/agents/{agent_id}")
def get_agent(agent_id: int):
    """Get agent details + discovered schema summary."""
    mgr = AgentManager()
    agent = mgr.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    schema_info = mgr.get_agent_schema_info(agent_id)
    return {"agent": agent, "schema_info": schema_info}


@app.delete("/api/v1/agents/{agent_id}")
def delete_agent(agent_id: int):
    """Delete an agent and cascade to discovered_schemas / query_log_config."""
    mgr = AgentManager()
    deleted = mgr.delete_agent(agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"message": f"Agent {agent_id} deleted."}


@app.post("/api/v1/agents/{agent_id}/refresh")
def refresh_agent(agent_id: int, background_tasks: BackgroundTasks):
    """Re-discover schema for an agent (background task)."""
    mgr = AgentManager()
    if not mgr.get_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    background_tasks.add_task(mgr.discover_and_configure, agent_id)
    return {"message": "Schema re-discovery started."}


@app.post("/api/v1/agents/{agent_id}/retry-ground-truth")
def retry_ground_truth(agent_id: int, background_tasks: BackgroundTasks):
    """Manually retry ground truth generation for an agent (background task)."""
    mgr = AgentManager()
    agent = mgr.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Check current status
    gt_status = agent.get('gt_status', 'pending')
    if gt_status == 'in_progress':
        raise HTTPException(status_code=400, detail="Ground truth generation already in progress")

    # Trigger retry in background
    background_tasks.add_task(mgr.retry_ground_truth_generation, agent_id)
    return {"message": "Ground truth generation retry started."}


@app.get("/api/v1/agents/{agent_id}/ground-truth-status")
def get_ground_truth_status(agent_id: int):
    """Get ground truth generation status for an agent."""
    mgr = AgentManager()
    agent = mgr.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {
        "agent_id": agent_id,
        "gt_status": agent.get("gt_status", "pending"),
        "gt_error": agent.get("gt_error"),
        "gt_generated_at": str(agent.get("gt_generated_at")) if agent.get("gt_generated_at") else None,
        "gt_query_count": agent.get("gt_query_count"),
        "gt_retry_count": agent.get("gt_retry_count", 0),
        "gt_last_retry_at": str(agent.get("gt_last_retry_at")) if agent.get("gt_last_retry_at") else None,
    }


@app.post("/api/v1/agents/{agent_id}/scan-schema-changes")
def scan_schema_changes(agent_id: int, background_tasks: BackgroundTasks):
    """
    Manually trigger schema change detection and incremental GT generation.
    Runs as background task.
    """
    mgr = AgentManager()
    agent = mgr.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Run in background
    background_tasks.add_task(mgr.scan_schema_changes, agent_id)

    return {
        "message": "Schema change scan started",
        "agent_id": agent_id,
        "agent_name": agent.get("agent_name")
    }


@app.get("/api/v1/agents/{agent_id}/schema-changes")
def get_schema_changes(agent_id: int, limit: int = 50):
    """Get schema change history for an agent"""
    mgr = AgentManager()
    agent = mgr.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    changes = mgr.get_schema_changes_history(agent_id, limit)

    return {
        "agent_id": agent_id,
        "agent_name": agent.get("agent_name"),
        "schema_version": agent.get("schema_version", 1),
        "last_scan": str(agent.get("last_schema_scan_at")) if agent.get("last_schema_scan_at") else None,
        "total_changes": len(changes),
        "changes": changes
    }


@app.get("/api/v1/agents/{agent_id}/schema-status")
def get_schema_status(agent_id: int):
    """Get schema monitoring status for an agent"""
    mgr = AgentManager()
    agent = mgr.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {
        "agent_id": agent_id,
        "schema_version": agent.get("schema_version", 1),
        "last_schema_scan_at": str(agent.get("last_schema_scan_at")) if agent.get("last_schema_scan_at") else None,
        "schema_change_count": agent.get("schema_change_count", 0),
        "gt_query_count": agent.get("gt_query_count", 0)
    }


@app.get("/api/v1/agents/{agent_id}/data-quality")
def get_data_quality_issues(agent_id: int):
    """Get all data quality issues for an agent."""
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("""
                SELECT *
                FROM platform.data_quality_issues
                WHERE agent_id = %s
                ORDER BY
                    CASE severity
                        WHEN 'critical' THEN 1
                        WHEN 'warning' THEN 2
                        WHEN 'info' THEN 3
                    END,
                    discovered_at DESC
            """, (agent_id,))
            issues = [dict(r) for r in cur.fetchall()]
            cur.close()

        # Group by severity
        return {
            "agent_id": agent_id,
            "total_issues": len(issues),
            "critical": len([i for i in issues if i['severity'] == 'critical']),
            "warnings": len([i for i in issues if i['severity'] == 'warning']),
            "info": len([i for i in issues if i['severity'] == 'info']),
            "issues": issues
        }
    except Exception as e:
        logger.error(f"Failed to get data quality issues: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/agents/{agent_id}/revalidate")
def revalidate_database(agent_id: int, background_tasks: BackgroundTasks):
    """Trigger database validation for an agent."""
    mgr = AgentManager()
    agent = mgr.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    background_tasks.add_task(mgr._run_database_validation, agent_id)
    return {"message": "Database validation started"}


@app.post("/api/v1/agents/{agent_id}/regenerate-key")
def regenerate_key(agent_id: int):
    """Regenerate API key for an agent. Returns the new key (show once)."""
    mgr = AgentManager()
    try:
        full_key, prefix = mgr.regenerate_api_key(agent_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "api_key": full_key,
        "api_key_prefix": prefix,
        "message": "Key regenerated. Store it securely — it will not be shown again.",
    }


# ==================== SDK INGEST ENDPOINT ====================

@app.post("/api/v1/monitor/ingest/sdk")
async def ingest_sdk_telemetry(
    request: Request,
    req: IngestRequest,
    background_tasks: BackgroundTasks,
):
    """SDK telemetry ingest — authenticated via X-API-Key, agent_type auto-resolved."""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    key_hash = hash_api_key(api_key)
    mgr = AgentManager()
    agent = mgr.get_agent_by_api_key_hash(key_hash)
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Override agent_type with the registered agent name
    req.agent_type = agent["agent_name"]

    query_id = f"SDK-{agent['agent_name'].upper()}-{uuid.uuid4().hex[:8]}"
    logger.info(f"[{query_id}] SDK ingest: {req.query_text[:80]}")

    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO monitoring.queries
                    (query_id, query_text, agent_type, status, generated_sql, execution_time_ms)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (query_id, req.query_text, req.agent_type, req.status,
                  req.sql, req.execution_time_ms))
            conn.commit()
            cur.close()
    except Exception as e:
        logger.error(f"SDK ingest DB insert failed: {e}")
        raise HTTPException(status_code=500, detail="Ingest failed")

    background_tasks.add_task(process_ingest_background, query_id, req)
    return {"status": "ingested", "query_id": query_id}


# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
