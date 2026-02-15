utf-8import requests
import json
import time
API_URL = "http://localhost:8000/api/v1/query"
TEST_QUERIES = [
    "Which products have stock below 20?",
    "Calculate the average profit margin for Electronics products",
    "Show me suppliers with high defect rates (>5%) in the East region",
    "Which products had no sales in Q1 2024?"
]
def test_demand_agent():
    print("Testing Demand Agent Accuracy Improvement...")
    passed = 0
    for query in TEST_QUERIES:
        print(f"\nQUERY: {query}")
        try:
            resp = requests.post(API_URL, json={"query": query, "agent_type": "demand"}, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                sql = data.get("sql")
                results = data.get("results")
                if sql:
                    print(f"✅ Generated SQL: {sql}")
                    if results:
                        print(f"✅ Executed Successfully: {len(results)} rows returned.")
                        passed += 1
                    else:
                        print("⚠️ SQL Generated but No Results (Logic might be wrong or no data).")
                        passed += 1 
                else:
                    print(f"❌ Failed to Generate SQL. Error: {data.get('error')}")
            else:
                print(f"❌ API Error: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"❌ Request Failed: {e}")
    print(f"\nSUMMARY: {passed}/{len(TEST_QUERIES)} Passed.")
if __name__ == :
    test_demand_agent()