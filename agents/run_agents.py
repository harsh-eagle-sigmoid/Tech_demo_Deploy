"""
Independent Agent Runner — HTTP version
Calls agents via HTTP (they run on Desktop independently).
  Spend Agent  → http://localhost:8001/query
  Demand Agent → http://localhost:8002/query

Before running this, start both agents:
  cd ~/Desktop && python -m spend_agent.run
  cd ~/Desktop && python -m demand_agent.run
"""
import json
import requests
from loguru import logger

SPEND_URL  = "http://localhost:8001/query"
DEMAND_URL = "http://localhost:8002/query"


def _call_agent(url: str, query_text: str) -> dict:
    """POST a query to a running agent, return its response."""
    try:
        resp = requests.post(url, json={"query": query_text}, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"query": query_text, "sql": None, "results": [], "status": "error", "error": str(e)}


def run_agents(ground_truth_path: str = "data/ground_truth/all_queries.json",
               output_path: str = "data/agent_outputs.json"):
    """
    Load ground truth queries, send each to the correct agent over HTTP,
    collect agent's own generated SQL, save to output file.
    """
    logger.add("logs/run_agents.log", rotation="10 MB")

    print("=" * 80)
    print(" INDEPENDENT AGENT RUNNER  (HTTP)")
    print(" Spend  → localhost:8001 | Demand → localhost:8002")
    print("=" * 80)

    # ── Health check both agents ──────────────────────────────────────────
    print("\n🏓 Checking agents are running...")
    for label, base in [("Spend", "http://localhost:8001"), ("Demand", "http://localhost:8002")]:
        try:
            r = requests.get(f"{base}/health", timeout=5)
            print(f"   {label} Agent : {r.json()}")
        except Exception:
            print(f"   {label} Agent : ❌ NOT running — start it first")
            return

    # ── Load ground truth (only query_text used, NOT its SQL) ────────────
    print(f"\n📂 Loading queries from {ground_truth_path}...")
    with open(ground_truth_path, "r") as f:
        ground_truth = json.load(f)
    print(f"   Loaded {len(ground_truth)} queries")

    # ── Send each query to correct agent via HTTP ────────────────────────
    outputs = []
    success = 0
    fail    = 0

    print(f"\n▶  Sending {len(ground_truth)} queries to agents...\n")

    for i, gt in enumerate(ground_truth, 1):
        query_id   = gt["query_id"]
        query_text = gt["query_text"]
        agent_type = gt["agent_type"]

        url    = SPEND_URL if agent_type == "spend" else DEMAND_URL
        result = _call_agent(url, query_text)

        outputs.append({
            "query_id":            query_id,
            "query_text":          query_text,
            "agent_type":          agent_type,
            "complexity":          gt["complexity"],
            "agent_generated_sql": result.get("sql"),
            "status":              result.get("status", "error"),
            "error":               result.get("error")
        })

        if result.get("status") == "success":
            success += 1
        else:
            fail += 1
            print(f"   ⚠  [{query_id}] {query_text[:50]}… → {result.get('error','')[:60]}")

        if i % 50 == 0:
            print(f"   ✓ {i}/{len(ground_truth)} done  ({success} ok, {fail} failed)")

    # ── Save ──────────────────────────────────────────────────────────────
    print(f"\n💾 Saving agent outputs to {output_path}...")
    with open(output_path, "w") as f:
        json.dump(outputs, f, indent=2)

    print("\n" + "=" * 80)
    print(" AGENT RUN COMPLETE")
    print("=" * 80)
    print(f"   Total queries : {len(outputs)}")
    print(f"   Succeeded     : {success}")
    print(f"   Failed        : {fail}")
    print(f"   Success rate  : {success / len(outputs) * 100:.1f}%")
    print(f"   Output file   : {output_path}")
    print(f"\n   Next step: run evaluation/test_evaluator.py")
    print("=" * 80)


if __name__ == "__main__":
    run_agents()
