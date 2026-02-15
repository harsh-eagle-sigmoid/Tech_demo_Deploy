import requests
import json

queries = [
    "Who are the top 3 suppliers by best performance?",
    "Show me monthly sales trend of 'Eco-Friendly Detergent' for 2024",
    "Identify high risk suppliers with lead time > 15 days"
]

print("--- Testing Demand Agent ---")
for q in queries:
    print(f"\nQUERY: {q}")
    try:
        resp = requests.post("http://localhost:8002/query", json={"query": q})
        data = resp.json()
        if data.get("status") == "success":
            print(f"SQL: {data.get('sql')}")
        else:
            print(f"ERROR: {data.get('error')}")
    except Exception as e:
        print(f"EXCEPTION: {e}")
print("\n--- End Test ---")
