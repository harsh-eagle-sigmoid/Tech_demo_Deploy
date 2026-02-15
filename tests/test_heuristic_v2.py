
import sys
import os
sys.path.append(os.getcwd())
from evaluation.evaluator import Evaluator
from loguru import logger

# Redirect logger to file
logger.add('test_output.txt', format='{message}')

def test_heuristic_eval():
    logger.info('Testing Heuristic Evaluation (Reference-Free)...')
    evaluator = Evaluator('spend')
    
    # Test Query 1: Valid Highest Sales query
    query_text = 'Show me the highest sales product'
    generated_sql = 'SELECT product_id, SUM(sales) FROM spend_data.orders GROUP BY product_id ORDER BY SUM(sales) DESC LIMIT 1'
    
    logger.info(f'Query: {query_text}')
    
    # Evaluate with NO Ground Truth
    result = evaluator.evaluate(
        query_id='test_heuristic_1',
        query_text=query_text,
        generated_sql=generated_sql,
        ground_truth_sql=None
    )
    
    logger.info(f'Result: {result["final_result"]} (Score: {result["final_score"]})')
    logger.info(f'Breakdown: {result["scores"]}')
    
    if result['final_result'] == 'PASS' and result['scores']['structural'] == 1.0:
        logger.success('Test 1 Passed!')
    else:
        logger.error('Test 1 Failed!')

    # Test Query 2: Invalid SQL
    logger.info('\nTesting Invalid SQL...')
    invalid_sql = 'SELECT magic_column FROM non_existent_table'
    result_fail = evaluator.evaluate(
        query_id='test_heuristic_fail',
        query_text='show me magic',
        generated_sql=invalid_sql,
        ground_truth_sql=None
    )
    logger.info(f'Result: {result_fail["final_result"]} (Score: {result_fail["final_score"]})')
    
    if result_fail['scores'].get('structural') == 0.0:
        logger.success('Test 2 Passed (Correctly Failed Structural)!')
    else:
        logger.error('Test 2 Failed!')

if __name__ == '__main__':
    test_heuristic_eval()

