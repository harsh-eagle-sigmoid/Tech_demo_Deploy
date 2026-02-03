"""
REST API Gateway — Unilever Procurement GPT POC
Single entry point on port 8000.

Routes:
  GET  /health                  → gateway health
  POST /api/v1/query            → proxy to Spend (8001) or Demand (8002) agent
  POST /api/v1/evaluate         → run 6-step evaluation on a query pair
  GET  /api/v1/metrics          → evaluation accuracy metrics from DB
  GET  /api/v1/drift            → drift distribution + anomalies (filter by agent_type)
  GET  /api/v1/errors           → error summary (filter by category)
  GET  /api/v1/errors/{category}→ detailed errors for one category
  POST /api/v1/baseline/update  → rebuild drift baseline for an agent
"""
import requests as http
import psycopg2
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv(dotenv_path="/home/lenovo/Desktop/New_tech_demo/.env")

from config.settings import settings

# ── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Unilever Procurement GPT — API Gateway",
    version="1.0",
    description="Unified gateway: agent proxy + evaluation + monitoring"
)

# ── Agent base URLs (independent services) ──────────────────────────────────
AGENT_URLS = {
    "spend":  "http://localhost:8001",
    "demand": "http://localhost:8002",
}

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
    status = {"gateway": "ok", "agents": {}}
    for name, base in AGENT_URLS.items():
        try:
            r = http.get(f"{base}/health", timeout=3)
            status["agents"][name] = r.json()
        except Exception:
            status["agents"][name] = {"status": "down"}
    return status

# ── POST /api/v1/query — proxy to correct agent ─────────────────────────────
@app.post("/api/v1/query")
def route_query(req: QueryRequest):
    """Route a natural-language query to Spend or Demand agent."""
    if req.agent_type not in AGENT_URLS:
        raise HTTPException(status_code=400, detail="agent_type must be 'spend' or 'demand'")
    base = AGENT_URLS[req.agent_type]
    try:
        resp = http.post(f"{base}/query", json={"query": req.query}, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except http.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Agent timed out")
    except http.exceptions.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

# ── POST /api/v1/evaluate ────────────────────────────────────────────────────
@app.post("/api/v1/evaluate")
def evaluate(req: EvaluateRequest):
    """Run the full 6-step evaluation pipeline and store result."""
    from evaluation.evaluator import Evaluator          # lazy import (heavy)

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

    # Overall
    cur.execute("""
        SELECT COUNT(*),
               SUM(CASE WHEN result = 'PASS' THEN 1 ELSE 0 END),
               AVG(final_score)
        FROM monitoring.evaluations
    """)
    total, passed, avg_score = cur.fetchone()
    total  = total  or 0
    passed = passed or 0

    # Per-agent
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

    # Build optional WHERE for agent_type filter (query_id prefix)
    where, params = "", []
    if agent_type:
        prefix = "SPEND" if agent_type == "spend" else "DEMAND"
        where  = " WHERE query_id LIKE %s"
        params = [f"{prefix}%"]

    # Distribution
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

    # Anomaly count
    cur.execute(f"SELECT COUNT(*) FROM monitoring.drift_monitoring WHERE is_anomaly = true {where.replace('WHERE','AND') if where else ''}", params)
    anomalies = cur.fetchone()[0]

    # Top 5 high-drift samples
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

    # Category summary
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

    # Recent errors (optionally filtered by category)
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

# ── POST /api/v1/baseline/update ─────────────────────────────────────────────
@app.post("/api/v1/baseline/update")
def update_baseline(req: BaselineUpdateRequest):
    """Rebuild the drift-detection baseline for one agent from provided queries."""
    if req.agent_type not in ("spend", "demand"):
        raise HTTPException(status_code=400, detail="agent_type must be 'spend' or 'demand'")
    from monitoring.drift_detector import DriftDetector  # lazy import (loads model)

    dd     = DriftDetector()
    result = dd.create_baseline(req.agent_type, req.queries)
    return {"status": "ok", "result": result}

# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
