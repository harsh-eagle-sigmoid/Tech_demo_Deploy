
import json
# Trigger Hot Reload
import os
import requests as http
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
import uuid
from datetime import datetime
import decimal
import asyncio
from fastapi import FastAPI, HTTPException, Query, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

from config.settings import settings
from auth.azure_auth import get_current_user, require_auth, AuthUser
from alerts.alert_service import alert_service, AlertType

app = FastAPI(
    title="Unilever Procurement GPT — Observability Backend",
    version="2.0",
    description="Centralized Observability & Monitoring System (Drift, Eval, Metrics)"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


AGENT_URLS = {
    "spend":  "http://localhost:8001",
    "demand": "http://localhost:8002",
}



_drift_detector = None
_error_classifier = None
_ground_truth_cache = None
_semantic_matcher = None
db_pool = None





from monitoring.baseline_manager import initialize_baseline_if_needed
from evaluation.semantic_match import SemanticMatcher
import evaluation.semantic_match

@app.on_event("startup")
async def startup_event():
    global db_pool
    logger.info("Starting up...")
    
    
    try:
        db_pool = pool.SimpleConnectionPool(
            1, 20,
            host=settings.DB_HOST, port=settings.DB_PORT, database=settings.DB_NAME, user=settings.DB_USER, password=settings.DB_PASSWORD
        )

        logger.info("DB Connection Pool initialized")
        
       
        async def init_matcher():
            try:
                msg = "Initializing Semantic Matcher in background..."
                logger.info(msg)
                matcher = SemanticMatcher()
                
                await asyncio.to_thread(matcher.load_from_file, "data/ground_truth/test.json")
                evaluation.semantic_match._matcher_instance = matcher
                logger.info("Semantic Matcher background initialization complete.")
            except Exception as e:
                logger.error(f"Semantic Matcher initialization failed: {e}")

        asyncio.create_task(init_matcher())
        
        
        asyncio.create_task(asyncio.to_thread(initialize_baseline_if_needed))
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")

@app.on_event("shutdown")
def shutdown_event():
    global db_pool
    if db_pool:
        db_pool.closeall()
        logger.info("DB Connection Pool closed")

def get_drift_detector():

    global _drift_detector
    if _drift_detector is None:
        from monitoring.drift_detector import DriftDetector
        _drift_detector = DriftDetector()
        logger.info("Drift detector initialized")
    return _drift_detector

def get_error_classifier():
    
    global _error_classifier
    if _error_classifier is None:
        from monitoring.error_classifier import ErrorClassifier
        _error_classifier = ErrorClassifier()
        logger.info("Error classifier initialized")
    return _error_classifier

def get_semantic_matcher():
    
    global _semantic_matcher
    if _semantic_matcher is None:
        _semantic_matcher = SemanticMatcher()
        logger.info("Semantic matcher initialized")
    return _semantic_matcher

def get_ground_truth():
    
    global _ground_truth_cache
    if _ground_truth_cache is None:
        try:
            with open("data/ground_truth/all_queries.json") as f:
                gt_list = json.load(f)
            
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
            
            
            matcher = get_semantic_matcher()
            if not matcher.is_ready:
                matcher.initialize(_ground_truth_cache)
        except Exception as e:
            logger.warning(f"Could not load ground truth: {e}")
            _ground_truth_cache = {}
    return _ground_truth_cache

def lookup_ground_truth(query_text: str) -> Optional[Dict]:
    
    gt = get_ground_truth()
    key = query_text.strip().lower().rstrip("?.!")
    match = gt.get(key)
    if match:
        return match
        
    
    matcher = get_semantic_matcher()
    if matcher.is_ready:
        semantic_match = matcher.find_match(query_text, threshold=0.85)
        if semantic_match:
            return semantic_match
            
    return None


@contextmanager
def get_db():
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        db_pool.putconn(conn)


class QueryRequest(BaseModel):
    query:      str
    agent_type: str = Field(..., description="'spend' or 'demand'")

class IngestRequest(BaseModel):
    query_text: str
    agent_type: str
    status: str
    sql: Optional[str] = None
    error: Optional[str] = None
    execution_time_ms: Optional[float] = 0.0

class EvaluateRequest(BaseModel):
    query_id:         str
    query_text:       str
    agent_type:       str
    generated_sql:    str
    ground_truth_sql: str
    complexity:       str = "unknown"

class BaselineUpdateRequest(BaseModel):
    agent_type: str = Field(..., description="'spend' or 'demand'")
    queries:    List[str]

class SqlExecuteRequest(BaseModel):
    sql: str
    agent_type: str

class ContextRequest(BaseModel):
    query: str
    limit: int = 3


@app.post("/api/v1/query")
async def query_agent(req: QueryRequest, user: Optional[AuthUser] = Depends(get_current_user)):
    
    # 1. Check Ground Truth / Semantic Match (Optimization)
    gt = lookup_ground_truth(req.query)
    if gt:
        logger.info(f"Ground truth match found for: {req.query}")
        return {
            "query": req.query,
            "sql": gt["sql"],
            "results": [], 
            "status": "success",
            "source": "ground_truth"
        }

    # 2. Forward to Agent
    target_url = AGENT_URLS.get(req.agent_type)
    if not target_url:
        raise HTTPException(status_code=400, detail=f"Unknown agent type: {req.agent_type}")
    
    try:
        # Forward the request to the agent
        logger.info(f"Forwarding query to {req.agent_type} agent at {target_url}...")
        resp = http.post(f"{target_url}/query", json={"query": req.query}, timeout=60)
        
        if resp.status_code != 200:
            logger.error(f"Agent returned {resp.status_code}: {resp.text}")
            raise HTTPException(status_code=resp.status_code, detail=f"Agent Error: {resp.text}")
            
        return resp.json()
        
    except http.exceptions.RequestException as e:
        logger.error(f"Failed to reach agent: {e}")
        raise HTTPException(status_code=503, detail="Agent Unavailable")


@app.get("/health")
def health():
    
    status = {"gateway": "ok", "agents": {}, "automation": "enabled", "auth_enabled": settings.AUTH_ENABLED}
    for name, base in AGENT_URLS.items():
        try:
            r = http.get(f"{base}/health", timeout=3)
            status["agents"][name] = r.json()
        except Exception:
            status["agents"][name] = {"status": "down"}
    return status


@app.get("/api/v1/auth/me")
async def get_user_info(user: AuthUser = Depends(require_auth)):
    
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
    
    return {
        "auth_enabled": settings.AUTH_ENABLED,
        "tenant_id": settings.AZURE_AD_TENANT_ID if settings.AUTH_ENABLED else None,
        "client_id": settings.AZURE_AD_CLIENT_ID if settings.AUTH_ENABLED else None,
        "authority": settings.azure_ad_authority if settings.AUTH_ENABLED else None,
        "scopes": [f"api://{settings.AZURE_AD_CLIENT_ID}/access"] if settings.AUTH_ENABLED else []
    }


def process_ingest_background(query_id: str, req: IngestRequest):
    
    try:
        drift_detector = get_drift_detector()
        result = drift_detector.detect(query_id, req.query_text, req.agent_type)
        
        # Trigger Alert on High Drift
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

    
    if req.status == "error" and req.error:
        try:
            error_classifier = get_error_classifier()
            error_classifier.classify(req.error, query_id)
        except Exception as e:
            logger.error(f"Error classify failed: {e}")

    
    if req.sql and req.status == "success":
        
        try:
            from evaluation.evaluator import Evaluator
            evaluator = Evaluator(req.agent_type)
            eval_result = evaluator.evaluate(
                query_id=query_id,
                query_text=req.query_text,
                generated_sql=req.sql,
                ground_truth_sql=None
            )
            evaluator.store_result(eval_result)
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            
            try:
                error_classifier = get_error_classifier()
                
                error_classifier.classify(str(e), query_id)
            except Exception as e2:
                logger.error(f"Failed to classify error: {e2}")

@app.post("/api/v1/monitor/ingest")
async def ingest_telemetry(req: IngestRequest, background_tasks: BackgroundTasks):
    
    query_id = f"ASYNC-{req.agent_type.upper()}-{uuid.uuid4().hex[:8]}"
    logger.info(f"[{query_id}] Ingesting telemetry: {req.query_text}")

    
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

    
    background_tasks.add_task(process_ingest_background, query_id, req)

    return {"status": "ingested", "query_id": query_id}




@app.post("/api/v1/evaluate")
async def evaluate(req: EvaluateRequest, user: Optional[AuthUser] = Depends(get_current_user)):
    
    from evaluation.evaluator import Evaluator

    evaluator = Evaluator(req.agent_type)
    result    = evaluator.evaluate(
        query_id=req.query_id,
        query_text=req.query_text,
        generated_sql=req.generated_sql,
        ground_truth_sql=req.ground_truth_sql,
        complexity=req.complexity
    )
    evaluator.store_result(result)

    return {
        "query_id":   result["query_id"],
        "result":     result["final_result"],
        "final_score": result["final_score"],
        "confidence": result["confidence"],
        "scores":     result["scores"],
        "reasoning":  result.get("steps", {}).get("llm_judge", {}).get("reasoning", "")
    }

@app.post("/api/v1/debug/execute")
def execute_sql(req: SqlExecuteRequest):
    
    if not req.sql.strip().upper().startswith("SELECT"):
        raise HTTPException(status_code=400, detail="Only SELECT statements are allowed for debugging.")

    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(req.sql)
            if cur.description:
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                results = []
                for row in rows[:50]:
                    item = {}
                    for i, col in enumerate(columns):
                        val = row[i]
                        if isinstance(val, (datetime, decimal.Decimal)):
                            val = str(val)
                        item[col] = val
                    results.append(item)
                return {"status": "success", "results": results}
            return {"status": "success", "results": []}
        except Exception as e:
            logger.error(f"Debug execution failed: {e}")
            return {"status": "error", "error": str(e)}
        finally:
            cur.close()


@app.get("/api/v1/metrics")
def get_metrics(agent_type: Optional[str] = Query(None)):
    
    with get_db() as conn:
        cur  = conn.cursor()

        
        where_eval = ""
        where_query = "WHERE execution_time_ms IS NOT NULL"
        params_eval = []
        params_query = []
        
        if agent_type:
            where_eval = "WHERE agent_type = %s"
            where_query += " AND agent_type = %s"
            params_eval = [agent_type]
            params_query = [agent_type]

        
        cur.execute(f"""
            SELECT COUNT(*),
                   SUM(CASE WHEN result = 'PASS' THEN 1 ELSE 0 END),
                   AVG(final_score)
            FROM monitoring.evaluations
            {where_eval}
        """, params_eval)
        total, passed, avg_score = cur.fetchone()
        
        
        cur.execute(f"SELECT AVG(execution_time_ms) FROM monitoring.queries {where_query}", params_query)
        row_global_lat = cur.fetchone()
        avg_latency = row_global_lat[0] if row_global_lat and row_global_lat[0] else 0.0

        total  = total  or 0
        passed = passed or 0

        
        cur.execute(f"""
            SELECT agent_type,
                   COUNT(*),
                   SUM(CASE WHEN result = 'PASS' THEN 1 ELSE 0 END),
                   AVG(final_score)
            FROM monitoring.evaluations
            {where_eval}
            GROUP BY agent_type
        """, params_eval)
        
        per_agent = {}
        eval_rows = cur.fetchall()
        
        for row in eval_rows:
            agent = row[0]
            t, p = row[1], row[2] or 0
            
            cur.execute("SELECT AVG(execution_time_ms) FROM monitoring.queries WHERE agent_type = %s AND execution_time_ms IS NOT NULL", (agent,))
            row_lat = cur.fetchone()
            agent_lat = row_lat[0] if row_lat and row_lat[0] else 0.0

            per_agent[agent] = {
                "total":    t,
                "passed":   p,
                "accuracy": round(p / t * 100, 1) if t else 0,
                "avg_score": round(float(row[3]), 3) if row[3] else 0.0,
                "avg_latency": round(float(agent_lat), 1)
            }
        
        
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
        
        
        trend_map = {}
        for row in cur.fetchall():
            time_str, agent_typ, acc = row
            if time_str not in trend_map:
                trend_map[time_str] = {"time": time_str, "Spend": None, "Demand": None}
            
            
            key = "Spend" if agent_typ == "spend" else "Demand"
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
            "avg_latency":       round(float(avg_latency), 1)
        },
        "per_agent": per_agent,
        "trend": trend_data
    }


@app.get("/api/v1/drift")
def get_drift(agent_type: Optional[str] = Query(None)):
    
    with get_db() as conn:
        cur  = conn.cursor()

        where, params = "", []
        if agent_type:
            
            keyword = "SPEND" if agent_type.lower() == "spend" else "DEMAND"
            where  = " WHERE query_id LIKE %s"
            params = [f"%{keyword}%"]

        cur.execute(f"""
            SELECT LOWER(drift_classification), COUNT(*), AVG(drift_score)
            FROM monitoring.drift_monitoring {where}
            GROUP BY LOWER(drift_classification)
            ORDER BY LOWER(drift_classification)
        """, params)
        distribution = {
            row[0]: {"count": row[1], "avg_drift_score": round(float(row[2]), 3)}
            for row in cur.fetchall()
        }

        cur.execute(f"SELECT COUNT(*) FROM monitoring.drift_monitoring WHERE is_anomaly = true {where.replace('WHERE','AND') if where else ''}", params)
        anomalies = cur.fetchone()[0]

        cur.execute(f"""
            SELECT d.query_id, d.drift_score, d.drift_classification, q.query_text, q.generated_sql, q.agent_type
            FROM monitoring.drift_monitoring d
            LEFT JOIN monitoring.queries q ON d.query_id = q.query_id
            WHERE LOWER(d.drift_classification) = 'high' {('AND d.query_id LIKE %s' if agent_type else '')}
            ORDER BY d.drift_score DESC LIMIT 20
        """, params if agent_type else [])
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

        # Trend Logic
        cur.execute(f"""
            SELECT date_trunc('day', q.created_at) as date, AVG(d.drift_score)
            FROM monitoring.drift_monitoring d
            JOIN monitoring.queries q ON d.query_id = q.query_id
            {where.replace('query_id', 'd.query_id')}
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


@app.get("/api/v1/errors")
def get_errors(category: Optional[str] = Query(None), limit: int = Query(20), agent_type: Optional[str] = Query(None)):
    
    with get_db() as conn:
        cur  = conn.cursor()

        
        summary_join = ""
        summary_where = ""
        summary_params = []
        
        if agent_type:
            summary_join = "JOIN monitoring.queries q ON e.query_id = q.query_id"
            summary_where = "WHERE q.agent_type = %s"
            summary_params = [agent_type]

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
    
    with get_db() as conn:
        cur  = conn.cursor()
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


@app.get("/api/v1/history")
def get_history(limit: int = 50, agent_type: Optional[str] = Query(None)):
    
    with get_db() as conn:
        cur = conn.cursor()
        
        where_clause = ""
        params = []
        if agent_type:
            
            where_clause = "WHERE LOWER(q.agent_type) = LOWER(%s)"
            params.append(agent_type)
        
        
        params.append(limit)

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
                d.drift_classification
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
            "drift_level": row[8] or "N/A"
        })
    return history


@app.post("/api/v1/baseline/update")
def update_baseline(req: BaselineUpdateRequest):
    
    if req.agent_type not in ("spend", "demand"):
        raise HTTPException(status_code=400, detail="agent_type must be 'spend' or 'demand'")

    dd = get_drift_detector()
    result = dd.create_baseline(req.agent_type, req.queries)
    return {"status": "ok", "result": result}



@app.get("/api/v1/alerts")
def get_alerts():
    
    alerts = []
    
    with get_db() as conn:
        cur = conn.cursor()

        
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

@app.get("/api/v1/monitor/runs/{query_id}")
def get_run_details(query_id: str):
    
    with get_db() as conn:
        cur = conn.cursor()
        
       
        cur.execute("""
            SELECT 
                q.query_id, q.query_text, q.agent_type, q.status, q.generated_sql as q_sql, q.created_at,
                e.result, e.confidence, e.final_score, e.reasoning, e.generated_sql as e_sql, e.evaluation_data,
                d.drift_score, d.drift_classification
            FROM monitoring.queries q
            LEFT JOIN monitoring.evaluations e ON q.query_id = e.query_id
            LEFT JOIN monitoring.drift_monitoring d ON q.query_id = d.query_id
            WHERE q.query_id = %s
        """, (query_id,))
        
        row = cur.fetchone()
        
        if not row:
             raise HTTPException(status_code=404, detail="Run not found")
             
        # Unwrap evaluation_data if exists
        eval_data = row[11] if row[11] else {}
        scores_breakdown = eval_data.get("scores", {})

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
                "scores": scores_breakdown
            },
            "drift": {
                "score": row[12] if row[12] is not None else 0.0,
                "status": row[13] or "unknown"
            },
            "intent": None 
        }
        
    return data



@app.post("/api/v1/context/retrieve")
def retrieve_context(req: ContextRequest):
    
    matcher = get_semantic_matcher()
    
    
    if not matcher.is_ready:
        matcher.initialize(get_ground_truth())

    if matcher.is_ready:
        
        match = matcher.find_match(req.query, threshold=0.5)
        if match:
            return {"examples": [match]}
            
    return {"examples": []}

@app.get("/api/v1/agents/summary")
def get_agents_summary():
    
    summary = []
    
    with get_db() as conn:
        cur = conn.cursor()
        
    
        agents = ["spend", "demand"]
        
        for agent in agents:
            try:
                
                cur.execute("SELECT COUNT(*) FROM monitoring.queries WHERE agent_type = %s", (agent,))
                total_reqs = cur.fetchone()[0]
                
                
                cur.execute("""
                    SELECT AVG(execution_time_ms) 
                    FROM monitoring.queries 
                    WHERE agent_type = %s AND execution_time_ms IS NOT NULL
                """, (agent,))
                row_lat = cur.fetchone()
                avg_lat = row_lat[0] if row_lat and row_lat[0] else 0.0
                
                
                cur.execute("""
                    SELECT 
                        count(*) filter (where result='PASS') * 100.0 / nullif(count(*), 0)
                    FROM monitoring.evaluations 
                    WHERE agent_type = %s
                """, (agent,))
                row_acc = cur.fetchone()
                accuracy = row_acc[0] if row_acc and row_acc[0] else 0.0
                
                status = "Healthy" 
                if accuracy < 80 and total_reqs > 5: status = "Degraded"

                summary.append({
                    "id": agent,
                    "name": f"{agent.capitalize()} GPT",
                    "description": "Spend analytics and supplier intelligence" if agent == 'spend' else "Demand forecasting and market analytics",
                    "status": status,
                    "accuracy": round(float(accuracy), 1),
                    "requests": total_reqs,
                    "latency_s": round(float(avg_lat) / 1000.0, 2)
                })
            except Exception as e:
                logger.error(f"Summary failed for {agent}: {e}")
                
    return summary


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
