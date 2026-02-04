
import json
import requests as http
import psycopg2
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

from config.settings import settings
from auth.azure_auth import get_current_user, require_auth, AuthUser
from alerts.alert_service import alert_service, AlertType

# ── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Unilever Procurement GPT — API Gateway",
    version="2.0",
    description="Unified gateway with AUTOMATED drift, error, and evaluation pipeline"
)

# ── CORS middleware ──────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Agent base URLs (independent services) ──────────────────────────────────
AGENT_URLS = {
    "spend":  "http://localhost:8001",
    "demand": "http://localhost:8002",
}

# ── Global caches (lazy loaded) ─────────────────────────────────────────────
_drift_detector = None
_error_classifier = None
_ground_truth_cache = None  # {query_text: {query_id, sql, complexity, agent_type}}

def get_drift_detector():
    """Lazy load drift detector (loads embedding model)."""
    global _drift_detector
    if _drift_detector is None:
        from monitoring.drift_detector import DriftDetector
        _drift_detector = DriftDetector()
        logger.info("Drift detector initialized")
    return _drift_detector

def get_error_classifier():
    """Lazy load error classifier."""
    global _error_classifier
    if _error_classifier is None:
        from monitoring.error_classifier import ErrorClassifier
        _error_classifier = ErrorClassifier()
        logger.info("Error classifier initialized")
    return _error_classifier

def get_ground_truth():
    """Load ground truth into cache for fast lookup."""
    global _ground_truth_cache
    if _ground_truth_cache is None:
        try:
            with open("data/ground_truth/all_queries.json") as f:
                gt_list = json.load(f)
            # Index by normalized query text for lookup
            _ground_truth_cache = {}
            for q in gt_list:
                key = q["query_text"].strip().lower()
                _ground_truth_cache[key] = {
                    "query_id": q["query_id"],
                    "sql": q["sql"],
                    "complexity": q["complexity"],
                    "agent_type": q["agent_type"]
                }
            logger.info(f"Ground truth loaded: {len(_ground_truth_cache)} queries")
        except Exception as e:
            logger.warning(f"Could not load ground truth: {e}")
            _ground_truth_cache = {}
    return _ground_truth_cache

def lookup_ground_truth(query_text: str) -> Optional[Dict]:
    """Find ground truth for a query (exact match on normalized text)."""
    gt = get_ground_truth()
    key = query_text.strip().lower()
    return gt.get(key)

# ── DB helper ────────────────────────────────────────────────────────────────
def _db():
    return psycopg2.connect(
        host=settings.DB_HOST, port=settings.DB_PORT,
        database=settings.DB_NAME,
        user=settings.DB_USER, password=settings.DB_PASSWORD
    )

# ── Pydantic request models ──────────────────────────────────────────────────
class QueryRequest(BaseModel):
    query:      str
    agent_type: str = Field(..., description="'spend' or 'demand'")

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

# ── Health ───────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    """Gateway health + downstream agent status."""
    status = {"gateway": "ok", "agents": {}, "automation": "enabled", "auth_enabled": settings.AUTH_ENABLED}
    for name, base in AGENT_URLS.items():
        try:
            r = http.get(f"{base}/health", timeout=3)
            status["agents"][name] = r.json()
        except Exception:
            status["agents"][name] = {"status": "down"}
    return status

# ── Auth info ────────────────────────────────────────────────────────────────
@app.get("/api/v1/auth/me")
async def get_user_info(user: AuthUser = Depends(require_auth)):
    """Get current authenticated user information."""
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
    """Get Azure AD configuration for frontend (public info only)."""
    return {
        "auth_enabled": settings.AUTH_ENABLED,
        "tenant_id": settings.AZURE_AD_TENANT_ID if settings.AUTH_ENABLED else None,
        "client_id": settings.AZURE_AD_CLIENT_ID if settings.AUTH_ENABLED else None,
        "authority": settings.azure_ad_authority if settings.AUTH_ENABLED else None,
        "scopes": [f"api://{settings.AZURE_AD_CLIENT_ID}/access"] if settings.AUTH_ENABLED else []
    }

# ══════════════════════════════════════════════════════════════════════════════
# ██  AUTOMATED QUERY ENDPOINT                                                ██
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/api/v1/query")
async def route_query(req: QueryRequest, user: Optional[AuthUser] = Depends(get_current_user)):
    """
    AUTOMATED PIPELINE:
    1. Call agent → get SQL + results
    2. Auto drift detection → store in DB
    3. Auto error classification (if error) → store in DB
    4. Auto evaluation (if ground truth exists) → store in DB
    5. Return response with all metrics

    Protected by Azure AD when AUTH_ENABLED=true
    """
    if req.agent_type not in AGENT_URLS:
        raise HTTPException(status_code=400, detail="agent_type must be 'spend' or 'demand'")

    # Generate unique query ID for this request
    query_id = f"LIVE-{req.agent_type.upper()}-{uuid.uuid4().hex[:8]}"

    # Log initial query to DB
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO monitoring.queries (query_id, query_text, agent_type, user_id, status)
            VALUES (%s, %s, %s, %s, 'pending')
        """, (query_id, req.query, req.agent_type, user.sub if user else None))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to log query to DB: {e}")

    response = {
        "query_id": query_id,
        "query": req.query,
        "agent_type": req.agent_type,
        "sql": None,
        "results": [],
        "status": "success",
        "error": None,
        # Automated metrics
        "drift": None,
        "error_classification": None,
        "evaluation": None,
        # User info (if authenticated)
        "user": user.name if user else "anonymous"
    }

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1: Call Agent
    # ─────────────────────────────────────────────────────────────────────────
    base = AGENT_URLS[req.agent_type]
    try:
        agent_resp = http.post(f"{base}/query", json={"query": req.query}, timeout=30)
        agent_resp.raise_for_status()
        agent_data = agent_resp.json()

        response["sql"] = agent_data.get("sql")
        response["results"] = agent_data.get("results", [])
        response["status"] = agent_data.get("status", "success")
        response["error"] = agent_data.get("error")

    except http.exceptions.Timeout:
        response["status"] = "error"
        response["error"] = "Agent timed out"
        # ALERT: Agent timeout (potential system issue)
        alert_service.alert_system_down(
            service=f"{req.agent_type.capitalize()} Agent",
            error="Agent request timed out after 30 seconds"
        )
    except Exception as e:
        response["status"] = "error"
        response["error"] = str(e)
        # ALERT: Agent connection failure
        if "Connection refused" in str(e) or "Connection error" in str(e):
            alert_service.alert_system_down(
                service=f"{req.agent_type.capitalize()} Agent",
                error=str(e)
            )

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2: Auto Drift Detection (always runs)
    # ─────────────────────────────────────────────────────────────────────────
    try:
        drift_detector = get_drift_detector()
        drift_result = drift_detector.detect(query_id, req.query, req.agent_type)
        response["drift"] = {
            "score": round(drift_result.get("drift_score", 0), 3),
            "classification": drift_result.get("drift_classification", "unknown"),
            "is_anomaly": drift_result.get("anomaly_flag", False)
        }
        logger.info(f"[{query_id}] Drift: {response['drift']['classification']} ({response['drift']['score']})")

        # ALERT: Send email alert for high drift
        if response["drift"]["classification"].lower() == "high":
            alert_service.alert_high_drift(
                query_id=query_id,
                query_text=req.query,
                drift_score=response["drift"]["score"],
                agent_type=req.agent_type
            )
    except Exception as e:
        logger.error(f"Drift detection failed: {e}")
        response["drift"] = {"error": str(e)}

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3: Auto Error Classification (if error occurred)
    # ─────────────────────────────────────────────────────────────────────────
    if response["status"] == "error" and response["error"]:
        try:
            error_classifier = get_error_classifier()
            error_result = error_classifier.classify(
                query_id=query_id,
                query_text=req.query,
                error_message=response["error"]
            )
            response["error_classification"] = {
                "category": error_result.get("category", "UNKNOWN"),
                "severity": error_result.get("severity", "medium"),
                "suggested_fix": error_result.get("suggested_fix", "")
            }
            logger.info(f"[{query_id}] Error classified: {response['error_classification']['category']}")

            # ALERT: Send email alert for critical errors
            if response["error_classification"]["severity"].lower() == "critical":
                alert_service.alert_critical_error(
                    query_id=query_id,
                    error_category=response["error_classification"]["category"],
                    error_message=response["error"],
                    agent_type=req.agent_type
                )
        except Exception as e:
            logger.error(f"Error classification failed: {e}")
            response["error_classification"] = {"error": str(e)}

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4: Auto Evaluation (if ground truth exists for this query)
    # ─────────────────────────────────────────────────────────────────────────
    if response["sql"] and response["status"] == "success":
        gt = lookup_ground_truth(req.query)
        if gt:
            try:
                from evaluation.evaluator import Evaluator
                evaluator = Evaluator(req.agent_type)
                eval_result = evaluator.evaluate(
                    query_id=query_id,
                    query_text=req.query,
                    generated_sql=response["sql"],
                    ground_truth_sql=gt["sql"],
                    complexity=gt["complexity"]
                )
                evaluator.store_result(eval_result)

                response["evaluation"] = {
                    "result": eval_result["final_result"],
                    "score": round(eval_result["final_score"], 3),
                    "confidence": round(eval_result["confidence"], 3),
                    "scores": {
                        "structural": round(eval_result["scores"].get("structural", 0), 3),
                        "semantic": round(eval_result["scores"].get("semantic", 0), 3),
                        "llm": round(eval_result["scores"].get("llm", 0), 3)
                    },
                    "ground_truth_id": gt["query_id"]
                }
                logger.info(f"[{query_id}] Evaluation: {response['evaluation']['result']} (score={response['evaluation']['score']})")
            except Exception as e:
                logger.error(f"Evaluation failed: {e}")
                response["evaluation"] = {"error": str(e)}
        else:
            response["evaluation"] = {"status": "skipped", "reason": "no ground truth match"}

    return response

# ══════════════════════════════════════════════════════════════════════════════
# ██  MANUAL ENDPOINTS (unchanged)                                            ██
# ══════════════════════════════════════════════════════════════════════════════

# ── POST /api/v1/evaluate ────────────────────────────────────────────────────
@app.post("/api/v1/evaluate")
async def evaluate(req: EvaluateRequest, user: Optional[AuthUser] = Depends(get_current_user)):
    """Run the full 6-step evaluation pipeline manually."""
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

# ── GET /api/v1/metrics ──────────────────────────────────────────────────────
@app.get("/api/v1/metrics")
def get_metrics():
    """Overall + per-agent accuracy metrics from monitoring.evaluations."""
    conn = _db()
    cur  = conn.cursor()

    cur.execute("""
        SELECT COUNT(*),
               SUM(CASE WHEN result = 'PASS' THEN 1 ELSE 0 END),
               AVG(final_score)
        FROM monitoring.evaluations
    """)
    total, passed, avg_score = cur.fetchone()
    total  = total  or 0
    passed = passed or 0

    cur.execute("""
        SELECT agent_type,
               COUNT(*),
               SUM(CASE WHEN result = 'PASS' THEN 1 ELSE 0 END),
               AVG(final_score)
        FROM monitoring.evaluations
        GROUP BY agent_type
    """)
    per_agent = {}
    for row in cur.fetchall():
        t, p = row[1], row[2] or 0
        per_agent[row[0]] = {
            "total":    t,
            "passed":   p,
            "accuracy": round(p / t * 100, 1) if t else 0,
            "avg_score": round(float(row[3]), 3) if row[3] else 0.0
        }

    cur.close()
    conn.close()

    return {
        "overall": {
            "total_evaluations": total,
            "passed":            passed,
            "failed":            total - passed,
            "accuracy":          round(passed / total * 100, 1) if total else 0,
            "avg_score":         round(float(avg_score or 0), 3)
        },
        "per_agent": per_agent
    }

# ── GET /api/v1/drift ────────────────────────────────────────────────────────
@app.get("/api/v1/drift")
def get_drift(agent_type: Optional[str] = Query(None)):
    """Drift distribution, anomaly count, and top high-drift samples."""
    conn = _db()
    cur  = conn.cursor()

    where, params = "", []
    if agent_type:
        prefix = "SPEND" if agent_type == "spend" else "DEMAND"
        where  = " WHERE query_id LIKE %s"
        params = [f"{prefix}%"]

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
        SELECT query_id, drift_score, drift_classification
        FROM monitoring.drift_monitoring
        WHERE LOWER(drift_classification) = 'high' {('AND query_id LIKE %s' if agent_type else '')}
        ORDER BY drift_score DESC LIMIT 5
    """, params if agent_type else [])
    high_samples = [
        {"query_id": r[0], "drift_score": round(float(r[1]), 3), "classification": r[2]}
        for r in cur.fetchall()
    ]

    cur.close()
    conn.close()

    return {
        "distribution":      distribution,
        "total_anomalies":   anomalies,
        "high_drift_samples": high_samples
    }

# ── GET /api/v1/errors ───────────────────────────────────────────────────────
@app.get("/api/v1/errors")
def get_errors(category: Optional[str] = Query(None), limit: int = Query(20)):
    """Error summary grouped by category + recent errors list."""
    conn = _db()
    cur  = conn.cursor()

    cur.execute("""
        SELECT error_category, severity, COUNT(*)
        FROM monitoring.errors
        GROUP BY error_category, severity
        ORDER BY error_category
    """)
    categories = {}
    for row in cur.fetchall():
        cat = row[0]
        if cat not in categories:
            categories[cat] = {"count": 0, "severities": {}}
        categories[cat]["count"]            += row[2]
        categories[cat]["severities"][row[1]] = row[2]

    q      = "SELECT query_id, error_category, error_message, severity FROM monitoring.errors"
    params = []
    if category:
        q     += " WHERE error_category = %s"
        params.append(category)
    q += " ORDER BY first_seen DESC LIMIT %s"
    params.append(limit)
    cur.execute(q, params)
    recent = [
        {"query_id": r[0], "category": r[1], "message": r[2], "severity": r[3]}
        for r in cur.fetchall()
    ]

    cur.close()
    conn.close()

    return {
        "total_errors": sum(c["count"] for c in categories.values()),
        "categories":   categories,
        "recent_errors": recent
    }

# ── GET /api/v1/errors/{category} ────────────────────────────────────────────
@app.get("/api/v1/errors/{category}")
def get_errors_by_category(category: str):
    """All errors for a specific category with suggested fixes."""
    conn = _db()
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
    conn.close()
    return {"category": category, "count": len(errors), "errors": errors}

# ── GET /api/v1/history ────────────────────────────────────────────────────
@app.get("/api/v1/history")
def get_history(limit: int = 50):
    """Get history of execution runs with evaluation and error details."""
    conn = _db()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            q.query_text,
            e.result,
            e.confidence,
            r.error_category,
            q.agent_type,
            q.created_at,
            q.query_id
        FROM monitoring.queries q
        LEFT JOIN monitoring.evaluations e ON q.query_id = e.query_id
        LEFT JOIN monitoring.errors r ON q.query_id = r.query_id
        ORDER BY q.created_at DESC
        LIMIT %s
    """, (limit,))
    
    rows = cur.fetchall()
    cur.close()
    conn.close()

    history = []
    for row in rows:
        history.append({
            "prompt": row[0],
            "correctness_verdict": row[1] or "N/A",
            "evaluation_confidence": row[2] if row[2] is not None else 0.0,
            "error_bucket": row[3] or "None",
            "dataset": row[4],  # agent_type
            "timestamp": str(row[5]),
            "query_id": row[6]
        })
    return history

# ── POST /api/v1/baseline/update ─────────────────────────────────────────────
@app.post("/api/v1/baseline/update")
def update_baseline(req: BaselineUpdateRequest):
    """Rebuild the drift-detection baseline for one agent."""
    if req.agent_type not in ("spend", "demand"):
        raise HTTPException(status_code=400, detail="agent_type must be 'spend' or 'demand'")

    dd = get_drift_detector()
    result = dd.create_baseline(req.agent_type, req.queries)
    return {"status": "ok", "result": result}

# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
