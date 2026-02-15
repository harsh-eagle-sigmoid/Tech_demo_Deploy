import json

def verify():
    print("Loading data/ground_truth/all_queries.json...")
    try:
        with open("data/ground_truth/all_queries.json", "r") as f:
            all_queries = json.load(f)
    except FileNotFoundError:
        print("File not found.")
        return

    print(f"Total Queries in File: {len(all_queries)}")

    spend_queries = [q for q in all_queries if q.get("agent_type") == "spend"]
    demand_queries = [q for q in all_queries if q.get("agent_type") == "demand"]
    other_queries = [q for q in all_queries if q.get("agent_type") not in ["spend", "demand"]]

    print(f"Spend Queries (Count): {len(spend_queries)}")
    print(f"Demand Queries (Count): {len(demand_queries)}")
    print(f"Other Queries (Count): {len(other_queries)}")

    print("\n--- Sample Spend Query ---")
    if spend_queries:
        print(json.dumps(spend_queries[0], indent=2))
        if spend_queries[0].get("agent_type") != "spend":
            print("❌ ERROR: Spend List contains non-spend query!")

    print("\n--- Sample Demand Query ---")
    if demand_queries:
        print(json.dumps(demand_queries[0], indent=2))
        if demand_queries[0].get("agent_type") != "demand":
            print("❌ ERROR: Demand List contains non-demand query!")

    if other_queries:
        print("\n--- Sample Other Query ---")
        print(json.dumps(other_queries[0], indent=2))

if __name__ == "__main__":
    verify()
