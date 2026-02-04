import requests
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor

# API Gateway URL
API_URL = "http://localhost:8000/api/v1/query"

def run_simulation():
    print("🚀 Starting Dashboard Population Simulation...")
    
    # Load Ground Truth queries
    try:
        with open("data/ground_truth/all_queries.json", "r") as f:
            queries = json.load(f)
    except FileNotFoundError:
        print("❌ Could not find ground truth file. Using dummy data.")
        queries = [
            {"query_text": "What is total sales?", "agent_type": "spend"},
            {"query_text": "Show me top customers", "agent_type": "spend"},
            {"query_text": "Check inventory levels", "agent_type": "demand"}
        ]

    # Select a mix of Spend and Demand queries
    selected_queries = queries[:300]
    print(f"📋 Selected {len(selected_queries)} queries to run.")

    def send_query(q):
        try:
            payload = {
                "query": q["query_text"],
                "agent_type": q["agent_type"]
            }
            # Simulate real user typing speed / traffic
            time.sleep(random.uniform(0.1, 1.0))
            
            response = requests.post(API_URL, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                eval_data = data.get("evaluation", {})
                status = "✅ PASS" if eval_data.get("result") == "PASS" else "⚠️ FAIL"
                print(f"[{status}] {q['query_text'][:40]}... (Drift: {data.get('drift', {}).get('score', 0)})")
                if "result" not in eval_data:
                     print(f"   -> Eval Debug: {eval_data}")
            else:
                print(f"❌ Error {response.status_code}: {q['query_text'][:30]}...")
        except Exception as e:
            print(f"❌ Exception: {e}")

    # Run in parallel to speed up
    with ThreadPoolExecutor(max_workers=3) as executor:
        executor.map(send_query, selected_queries)

    print("\n✅ Simulation Complete!")
    print("Graphs should now be populated at http://localhost:3000")

if __name__ == "__main__":
    run_simulation()
