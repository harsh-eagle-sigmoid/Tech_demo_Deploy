#!/usr/bin/env python3
"""
Re-evaluate existing queries with result validation to populate output scores.
Run this to update old evaluations with the new result validation layer.
"""
import sys
sys.path.insert(0, '/home/lenovo/New_tech_demo')

import psycopg2
from config.settings import settings
from evaluation.evaluator import Evaluator
from loguru import logger

def main():
    conn = psycopg2.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD
    )
    cur = conn.cursor()

    # Get queries that need re-evaluation (have ground truth but no result validation)
    cur.execute("""
        SELECT q.query_id, q.query_text, q.generated_sql, q.agent_type,
               e.ground_truth_sql
        FROM monitoring.queries q
        JOIN monitoring.evaluations e ON q.query_id = e.query_id
        WHERE e.ground_truth_sql IS NOT NULL
          AND (e.evaluation_data->'steps'->'result_validation' IS NULL)
        ORDER BY q.created_at DESC
        LIMIT 10
    """)

    queries = cur.fetchall()
    cur.close()
    conn.close()

    if not queries:
        print("No queries need re-evaluation")
        return

    print(f"Found {len(queries)} queries to re-evaluate with result validation\n")

    for i, (query_id, query_text, generated_sql, agent_type, gt_sql) in enumerate(queries, 1):
        print(f"[{i}/{len(queries)}] Re-evaluating: {query_text[:60]}...")

        # Map agent type to evaluator type
        eval_agent_type = agent_type.lower().replace(' ', '_').replace('_agent', '')
        if 'marketing' in eval_agent_type:
            eval_agent_type = 'marketing'
        elif 'spend' in eval_agent_type:
            eval_agent_type = 'spend'
        elif 'demand' in eval_agent_type:
            eval_agent_type = 'demand'

        try:
            evaluator = Evaluator(agent_type=eval_agent_type)
            result = evaluator.evaluate(
                query_id=query_id,
                query_text=query_text,
                generated_sql=generated_sql,
                ground_truth_sql=gt_sql
            )

            if 'scores' in result and 'result_validation' in result['scores']:
                score = result['scores']['result_validation']
                print(f"   ✓ Output Score: {score:.2%}")
            else:
                print(f"   ⚠ No output score (likely no DB URL)")

        except Exception as e:
            print(f"   ✗ Error: {str(e)[:100]}")

    print(f"\n✓ Re-evaluation complete! Check dashboard for output scores.")

if __name__ == "__main__":
    main()
