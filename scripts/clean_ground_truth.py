
import json
import os

FILE_PATH = "data/ground_truth/all_queries.json"
QUERY_TEXT = "Which products need reordering?"

def clean_gt():
    if not os.path.exists(FILE_PATH):
        print(f"File not found: {FILE_PATH}")
        return

    with open(FILE_PATH, 'r') as f:
        data = json.load(f)

    initial_count = len(data)
    new_data = [item for item in data if item.get('query_text') != QUERY_TEXT]
    final_count = len(new_data)
    
    removed = initial_count - final_count
    
    if removed > 0:
        with open(FILE_PATH, 'w') as f:
            json.dump(new_data, f, indent=2)
        print(f"Removed {removed} entries for '{QUERY_TEXT}'.")
    else:
        print(f"No entries found for '{QUERY_TEXT}'.")

if __name__ == "__main__":
    clean_gt()
