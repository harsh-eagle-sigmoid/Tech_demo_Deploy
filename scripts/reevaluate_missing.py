"""
Re-evaluate queries that are missing evaluations in monitoring.evaluations.
This fixes the issue where background evaluation failed silently during ingest.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from config.settings import settings
from evaluation.evaluator import Evaluator
from loguru import logger

def get_unevaluated_queries():
    """Find queries with no corresponding evaluation."""
    conn = psycopg2.connect(
        host=settings.DB_HOST, port=settings.DB_PORT,
        database=settings.DB_NAME, user=settings.DB_USER,
        password=settings.DB_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT q.query_id, q.query_text, q.agent_type, q.generated_sql
        FROM monitoring.queries q
        LEFT JOIN monitoring.evaluations e ON q.query_id = e.query_id
        WHERE e.query_id IS NULL
          AND q.status = 'success'
          AND q.generated_sql IS NOT NULL
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def main():
    queries = get_unevaluated_queries()
    logger.info(f"Found {len(queries)} unevaluated queries")
    
    success = 0
    failed = 0
    
    for query_id, query_text, agent_type, generated_sql in queries:
        try:
            logger.info(f"Evaluating {query_id}: {query_text[:60]}...")
            evaluator = Evaluator(agent_type)
            result = evaluator.evaluate(
                query_id=query_id,
                query_text=query_text,
                generated_sql=generated_sql,
                ground_truth_sql=None
            )
            
            # store_result is called inside evaluate for heuristic path,
            # but not for the GT path if we call evaluate standalone
            # Make sure it's stored
            if result.get("final_result") != "ERROR":
                evaluator.store_result(result)
                logger.info(f"  -> {result['final_result']} (score={result['final_score']:.2f}, conf={result['confidence']:.2f})")
                success += 1
            else:
                logger.error(f"  -> ERROR: {result.get('error', 'unknown')}")
                failed += 1
                
        except Exception as e:
            logger.error(f"  -> EXCEPTION: {e}")
            failed += 1
    
    logger.info(f"\nDone! Success: {success}, Failed: {failed}")

if __name__ == "__main__":
    main()
