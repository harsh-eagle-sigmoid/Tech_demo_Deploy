
import sys
import os
sys.path.append(os.getcwd())
import time
from evaluation.evaluator import Evaluator
from loguru import logger

# Redirect logger to stdout with color
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")

def run_batch():
    logger.info("Starting Batch Evaluation of 10 Queries...")
    evaluator = Evaluator("spend")

    test_queries = [
        # 1. Valid Reference-Free Query
        {
            "id": "q1",
            "text": "Show me the top 5 highest sales products",
            "sql": "SELECT product_id, SUM(sales) FROM spend_data.orders GROUP BY product_id ORDER BY SUM(sales) DESC LIMIT 5",
            "gt": None
        },
        # 2. Valid Simple Query
        {
            "id": "q2",
            "text": "List all product categories",
            "sql": "SELECT DISTINCT category FROM spend_data.products",
            "gt": None  # Assuming no GT
        },
        # 3. Invalid Table Name (Structural Fail)
        {
            "id": "q3",
            "text": "Show me magic data",
            "sql": "SELECT * FROM magic_table",
            "gt": None
        },
        # 4. Missing Column (Structural Fail)
        {
            "id": "q4",
            "text": "Show me vendor rating",
            "sql": "SELECT vendor_rating FROM spend_data.orders", # Column doesn't exist
            "gt": None 
        },
        # 5. Intent Check (Highest)
        {
            "id": "q5",
            "text": "What is the maximum profit?",
            "sql": "SELECT MAX(profit) FROM spend_data.orders",
            "gt": None
        },
        # 6. Intent Mismatch (Missing MAX)
        {
            "id": "q6",
            "text": "What is the maximum profit?",
            "sql": "SELECT profit FROM spend_data.orders LIMIT 1", # Missing MAX/ORDER BY
            "gt": None
        },
        # 7. Pattern Fail (No LIMIT on large table)
        {
            "id": "q7",
            "text": "Download all orders",
            "sql": "SELECT * FROM spend_data.orders", # Missing LIMIT
            "gt": None
        },
        # 8. Pattern Fail (LIMIT without ORDER BY)
        {
            "id": "q8",
            "text": "Give me any 5 orders",
            "sql": "SELECT * FROM spend_data.orders LIMIT 5", # Missing ORDER BY (nondeterministic)
            "gt": None
        },
        # 9. Complex Valid Query
        {
            "id": "q9",
            "text": "Show monthly sales for 2023",
            "sql": "SELECT DATE_TRUNC('month', order_date), SUM(sales) FROM spend_data.orders WHERE order_date >= '2023-01-01' GROUP BY 1 ORDER BY 1",
            "gt": None
        },
        # 10. Drift (Low Quality Query Text)
        {
            "id": "q10",
            "text": "asdf jkl;", # Nonsense query
            "sql": "SELECT * FROM spend_data.products LIMIT 1",
            "gt": None
        }
    ]

    for q in test_queries:
        logger.info(f"\n--- Running Query {q['id']}: '{q['text']}' ---")
        start_time = time.time()
        
        # We manually skip GT lookup for this test script by passing ground_truth_sql=None
        # But Evaluator might still try to look up if we don't pass it.
        # Actually evaluate() takes ground_truth_sql as argument. If None, it tries lookup.
        # To FORCE heuristic, we must ensure lookup fails or pass logic.
        # But evaluate() lookup happens if ground_truth_sql is None.
        # Wait, if I pass `ground_truth_sql=None`, evaluate() proceeds to lookup.
        # I cannot disable lookup easily without mocking.
        # But for these made-up queries, lookup should fail (return None).
        
        result = evaluator.evaluate(
            query_id=q['id'],
            query_text=q['text'],
            generated_sql=q['sql']
        )
        
        duration = time.time() - start_time
        logger.info(f"Result: {result.get('final_result', 'UNKNOWN')} | Score: {result.get('final_score', 0.0):.2f} | Reasoning: {result.get('reasoning')} | Time: {duration:.2f}s")
        if 'scores' in result:
             logger.info(f"Breakdown: {result['scores']}")

if __name__ == "__main__":
    run_batch()
