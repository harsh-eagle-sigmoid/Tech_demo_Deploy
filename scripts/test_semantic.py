utf-8import sys
import os
sys.path.append(os.getcwd())
from api.semantic_match import SemanticMatcher
from api.main import get_ground_truth
from loguru import logger
logger.info("Loading matcher...")
matcher = SemanticMatcher()
import json
with open("data/ground_truth/all_queries.json") as f:
    gt_list = json.load(f)
gt_data = {}
for q in gt_list:
    key = q["query_text"].strip().lower().rstrip("?.!")
    gt_data[key] = q
matcher.initialize(gt_data)
test_queries = [
    "Show me every customer in the South region",           
    "Most profitable region",                               
    "Region with max profit",                               
    "High demand low stock products",                       
    "Products with big demand and small stock",             
    "Count of tech products",                               
    "Number of products inside Technology",                 
    "Where are suppliers located?",                         
    "Whch region has heighest profit?",                     
    "Top selling items",                                    
]
print(f"\n--- Testing {len(test_queries)} Variants ---")
for q in test_queries:
    print(f"\nInput: '{q}'")
    query_vec = matcher.model.encode(q)
    best_score = -1.0
    best_text = ""
    import numpy as np
    q_norm = np.linalg.norm(query_vec)
    for vec, entry in matcher.index:
        v_norm = np.linalg.norm(vec)
        score = np.dot(query_vec, vec) / (q_norm * v_norm)
        if score > best_score:
            best_score = score
            best_text = entry['query_text']
    print(f"Best Score: {best_score:.3f} -> '{best_text}'")
    if best_score >= 0.85:
        print(f"✅ MATCHED (Threshold 0.85)")
    else:
        print(f"❌ NO MATCH (Threshold 0.85)")