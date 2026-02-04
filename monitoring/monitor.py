"""
Monitoring Framework — Main Orchestrator
Single entry point.  Call monitor.run() to:
  1. Build baselines from ground truth (one-time)
  2. Detect drift on any query
  3. Classify any error
  4. Print summary stats from the DB

Usage:
  python -m monitoring.monitor
"""
import json
from typing import Dict, List, Optional
from loguru import logger
from monitoring.drift_detector import DriftDetector
from monitoring.error_classifier import ErrorClassifier
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = int(os.getenv("DB_PORT", "5432"))
DB_NAME     = os.getenv("DB_NAME", "unilever_poc")
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

GROUND_TRUTH_PATH = "data/ground_truth/all_queries.json"


class Monitor:
    """Orchestrates drift detection + error classification."""

    def __init__(self):
        self.drift_detector    = DriftDetector()
        self.error_classifier  = ErrorClassifier()
        logger.info("Monitor initialised — drift detector + error classifier ready")

    # ── Baseline ──────────────────────────────────────────────────────────
    def build_baselines(self, ground_truth_path: str = GROUND_TRUTH_PATH):
        """
        One-time setup: build baselines for spend and demand from ground truth.
        """
        print("\n📐 Building baselines from ground truth...")
        with open(ground_truth_path, "r") as f:
            all_queries = json.load(f)

        spend_texts  = [q["query_text"] for q in all_queries if q["agent_type"] == "spend"]
        demand_texts = [q["query_text"] for q in all_queries if q["agent_type"] == "demand"]

        spend_result  = self.drift_detector.create_baseline("spend",  spend_texts)
        demand_result = self.drift_detector.create_baseline("demand", demand_texts)

        print(f"   Spend  baseline : {len(spend_texts)} queries  → {spend_result}")
        print(f"   Demand baseline : {len(demand_texts)} queries → {demand_result}")

    # ── Monitor a single query ────────────────────────────────────────────
    def monitor_query(self, query_id: str, query_text: str,
                      agent_type: str, status: str,
                      error: Optional[str] = None) -> Dict:
        """
        Run full monitoring on one query:
          - drift detection
          - error classification (if status != success)

        Args:
            query_id: unique query ID
            query_text: natural language query
            agent_type: 'spend' or 'demand'
            status: 'success' or 'error'
            error: error message if status == 'error'

        Returns:
            monitoring result dict
        """
        result = {
            "query_id":   query_id,
            "query_text": query_text,
            "agent_type": agent_type,
            "status":     status,
            "drift":      None,
            "error_class": None
        }

        # Always run drift detection
        result["drift"] = self.drift_detector.detect(query_id, query_text, agent_type)

        # Classify error only if one exists
        if status != "success" and error:
            result["error_class"] = self.error_classifier.classify(
                error_message=error,
                query_id=query_id
            )

        return result

    # ── Batch monitor from agent_outputs ──────────────────────────────────
    def monitor_all(self, agent_outputs_path: str = "data/agent_outputs.json"):
        """
        Run monitoring on every query in agent_outputs.json.
        """
        print("\n📊 Loading agent outputs...")
        with open(agent_outputs_path, "r") as f:
            outputs = json.load(f)
        print(f"   Loaded {len(outputs)} outputs")

        results = []
        for i, out in enumerate(outputs, 1):
            r = self.monitor_query(
                query_id=out["query_id"],
                query_text=out["query_text"],
                agent_type=out["agent_type"],
                status=out["status"],
                error=out.get("error")
            )
            results.append(r)

            if i % 50 == 0:
                print(f"   Monitored {i}/{len(outputs)}...")

        return results

    # ── Stats from DB ─────────────────────────────────────────────────────
    def print_stats(self):
        """Print summary stats from monitoring tables."""
        try:
            conn = psycopg2.connect(
                host=DB_HOST, port=DB_PORT, database=DB_NAME,
                user=DB_USER, password=DB_PASSWORD
            )
            cur = conn.cursor()

            print("\n" + "=" * 60)
            print(" MONITORING STATS")
            print("=" * 60)

            # Drift stats
            cur.execute("""
                SELECT drift_classification, COUNT(*), AVG(drift_score)
                FROM monitoring.drift_monitoring
                GROUP BY drift_classification
                ORDER BY drift_classification
            """)
            print("\n  Drift Distribution:")
            for row in cur.fetchall():
                print(f"    {row[0]:10s} → count={row[1]:4d}  avg_drift={row[2]:.3f}")

            # Error stats
            cur.execute("""
                SELECT error_category, severity, COUNT(*)
                FROM monitoring.errors
                GROUP BY error_category, severity
                ORDER BY error_category, severity
            """)
            print("\n  Error Distribution:")
            for row in cur.fetchall():
                print(f"    {row[0]:22s} [{row[1]:8s}] → {row[2]}")

            # Anomaly count
            cur.execute("SELECT COUNT(*) FROM monitoring.drift_monitoring WHERE is_anomaly = true")
            anomalies = cur.fetchone()[0]
            print(f"\n  Total anomalies detected: {anomalies}")

            cur.close()
            conn.close()

        except Exception as e:
            logger.error(f"Stats error: {e}")


# ── CLI entry point ───────────────────────────────────────────────────────
if __name__ == "__main__":
    monitor = Monitor()

    print("=" * 60)
    print(" MONITORING FRAMEWORK")
    print("=" * 60)

    # Step 1: build baselines (uses ground truth)
    monitor.build_baselines()

    # Step 2: run drift + error monitoring on agent outputs
    print("\n▶  Running monitoring on agent outputs...")
    try:
        results = monitor.monitor_all()
        print(f"   Monitored {len(results)} queries")
    except FileNotFoundError:
        print("   ⚠  agent_outputs.json not found — run agents first")
        print("      (python -m agents.run_agents)")
        results = []

    # Step 3: print DB stats
    monitor.print_stats()

    print("\n✅ Monitoring complete")
