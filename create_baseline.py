import requests
import json

API_URL = "http://localhost:8000/api/v1/baseline/update"

def create_baselines():
    print("📏 Creating Baselines...")
    try:
        with open("data/ground_truth/all_queries.json", "r") as f:
            data = json.load(f)
            
        spend_queries = [q["query_text"] for q in data if q["agent_type"] == "spend"][:50]
        demand_queries = [q["query_text"] for q in data if q["agent_type"] == "demand"][:50]
        
        # Spend Baseline
        if spend_queries:
            requests.post(API_URL, json={"agent_type": "spend", "queries": spend_queries})
            print(f"✅ Spend Baseline Created ({len(spend_queries)} queries)")

        # Demand Baseline
        if demand_queries:
            requests.post(API_URL, json={"agent_type": "demand", "queries": demand_queries})
            print(f"✅ Demand Baseline Created ({len(demand_queries)} queries)")
            
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    create_baselines()
