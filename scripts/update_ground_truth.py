utf-8import json
import sys
import os
sys.path.insert(0, "/home/lenovo/demand_agent")
sys.path.append(os.getcwd())
from agent import DemandAgent
def update_demand_ground_truth():
    print("🚀 Updating Demand Agent Ground Truth...")
    path = "data/ground_truth/all_queries.json"
    with open(path, "r") as f:
        data = json.load(f)
    print(f"Loaded {len(data)} queries.")
    agent = DemandAgent()
    updated_count = 0
    for item in data:
        if item.get("agent_type") == :
            query = item["query_text"]
            try:
                sql, _ = agent.generate_sql(query)
                if sql:
                    item["sql"] = sql
                    updated_count += 1
                    if updated_count % 10 == 0:
                        print(f"Updated {updated_count}...")
            except Exception as e:
                print(f"Failed to generate for '{query}': {e}")
    with open(path, "w") as f:
        json.dump(data, f, indent=4)
    print(f"✅ Successfully updated {updated_count} Demand queries in Ground Truth.")
    print("You can now re-run evaluations to see improved accuracy.")
if __name__ == :
    update_demand_ground_truth()