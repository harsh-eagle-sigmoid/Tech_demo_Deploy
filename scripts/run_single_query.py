
import sys
import os
sys.path.append(os.getcwd())
import time
from evaluation.evaluator import Evaluator
from loguru import logger

# Configure logger to stdout
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")

def run_query():
    evaluator = Evaluator("spend")
    
    query_text = "What is total shipping cost for 2020"
    generated_sql = """SELECT SUM(shipping_cost) as total_shipping_cost 
FROM spend_data.orders 
WHERE year = 2020"""
    
    import uuid
    query_id = f"manual_test_{str(uuid.uuid4())[:8]}"
    
    logger.info(f"Running Query: '{query_text}' with ID: {query_id}")
    logger.info(f"SQL: {generated_sql}")
    
    result = evaluator.evaluate(
        query_id=query_id,
        query_text=query_text,
        generated_sql=generated_sql
    )
    
    logger.info(f"Result: {result.get('final_result')} | Score: {result.get('final_score')}")
    if 'scores' in result:
        logger.info(f"Breakdown: {result['scores']}")
    if result.get('reasoning'):
        logger.info(f"Reasoning: {result['reasoning']}")

if __name__ == "__main__":
    run_query()
