import json
import requests
import time
from concurrent.futures import ThreadPoolExecutor

def run_demand_sim():
    print("🚀 Starting 50-Query Demand Simulation")
    
    # Load Queries
    with open("data/ground_truth/test.json") as f:
        all_queries = json.load(f)

    demand_queries = [q for q in all_queries if q.get("agent_type") == "demand"]
    print(f"Loaded {len(demand_queries)} unique Demand queries.")

    # Expand/Sample to 50
    target_queries = (demand_queries * 10)[:50]
    print(f"Queued {len(target_queries)} Demand queries.")

    passed = 0
    total = 0

    def send_query(query_obj):
        url = "http://localhost:8000/api/v1/query"
        payload = {
            "query": query_obj["query_text"],
            "agent_type": "demand"
        }
        try:
            resp = requests.post(url, json=payload, timeout=30)
            data = resp.json()
            # Check Evaluation Result
            # API returns { ..., "evaluation": { "result": "PASS", ... } }
            # Wait. Does API return evaluation?
            # It returns "status": "success", "data": ...
            # The Evaluation is Async in background usually?
            # Let's check api/main.py response structure.
            # But we can check "sql" presence.
            return data
        except Exception as e:
            return {"status": "error", "error": str(e)}

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(send_query, q): q for q in target_queries}
        
        for future in futures:
            res = future.result()
            total += 1
            if total % 10 == 0:
                print(f"[{total}/50] Processed")

    print("✅ Simulation Complete!")
    print("Check Dashboard for Score.")
    
    # We can also check DB for recent accuracy
    import psycopg2
    conn = psycopg2.connect('dbname=unilever_poc user=postgres password=postgres host=localhost port=5432')
    cur = conn.cursor()
    cur.execute("SELECT count(*), sum(case when result='PASS' then 1 else 0 end) FROM monitoring.evaluations WHERE agent_type='demand' AND created_at > NOW() - INTERVAL '5 minutes'")
    cnt, pass_cnt = cur.fetchone()
    if cnt and cnt > 0:
        print(f"Recent Accuracy (Last 5 mins): {pass_cnt}/{cnt} = {pass_cnt/cnt:.2%}")
    else:
        print("No evaluations found in last 5 mins.")

if __name__ == "__main__":
    run_demand_sim()
