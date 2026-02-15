utf-8import json
import requests
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
def run_load_test():
    print("🚀 Starting Demand Agent Load Test (100 Queries)")
    print("Target: http://localhost:8002/query (Demand Agent)")
    with open("data/ground_truth/all_queries.json") as f:
        all_queries = json.load(f)
    demand_queries = [q for q in all_queries if q.get("agent_type") == ]
    print(f"Found {len(demand_queries)} available Demand queries.")
    target_queries = []
    while len(target_queries) < 100:
        target_queries.extend(demand_queries)
    target_queries = target_queries[:100]
    print(f"Queue size: {len(target_queries)}")
    def send_query(q):
        url = "http://localhost:8002/query"
        try:
            resp = requests.post(url, json={"query": q["query_text"]}, timeout=60)
            return resp.status_code
        except Exception as e:
            return str(e)
    success = 0
    failed = 0
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(send_query, q): q for q in target_queries}
        for i, future in enumerate(as_completed(futures)):
            res = future.result()
            if res == 200:
                success += 1
            else:
                if failed == 0:
                    print(f"❌ First Error: {res}")
                failed += 1
            if (i+1) % 10 == 0:
                print(f"Processed {i+1}/100...")
    duration = time.time() - start_time
    print(f"\n✅ Done in {duration:.2f}s")
    print(f"Success: {success}")
    print(f"Failed: {failed}")
if __name__ == :
    run_load_test()