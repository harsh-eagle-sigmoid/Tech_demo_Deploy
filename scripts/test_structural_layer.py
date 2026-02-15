
import sys
import os
sys.path.append(os.getcwd())
import time
from evaluation.layers.structural import StructuralLayer
from loguru import logger

# Configure logger to stdout
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")

def test_structural_layer():
    logger.info("Initializing StructuralLayer for 'spend_data'")
    layer = StructuralLayer("spend_data")
    
    test_cases = [
        # 1. Valid Query
        {
            "name": "Valid Query",
            "sql": "SELECT * FROM spend_data.orders LIMIT 5",
            "expected_score": 1.0
        },
        # 2. Syntax Error
        {
            "name": "Syntax Error",
            "sql": "SELEK * FROM spend_data.orders",
            "expected_score": 0.0
        },
        # 3. Invalid Table Schema
        {
            "name": "Invalid Table",
            "sql": "SELECT * FROM spend_data.ghost_table",
            "expected_score": 0.5 # Schema error = 0.5 score in logic
        },
        # 4. Invalid Column
        {
            "name": "Invalid Column",
            "sql": "SELECT ghost_col FROM spend_data.orders",
            "expected_score": 0.5 # Schema error = 0.5
        },
        # 5. Invalid Schema Name
        {
            "name": "Invalid Schema Name",
            "sql": "SELECT * FROM wrong_schema.orders",
            "expected_score": 0.5
        }
    ]
    
    for case in test_cases:
        logger.info(f"--- Testing: {case['name']} ---")
        logger.info(f"SQL: {case['sql']}")
        score = layer.evaluate(case['sql'])
        logger.info(f"Score: {score} (Expected: {case['expected_score']})")
        
        if score == case['expected_score']:
            logger.info("RESULT: PASS")
        else:
            logger.error(f"RESULT: FAIL (Expected {case['expected_score']}, Got {score})")
        
        # Access internal errors if possible via logger (they are logged by layer)
        print("-" * 30)

if __name__ == "__main__":
    test_structural_layer()
