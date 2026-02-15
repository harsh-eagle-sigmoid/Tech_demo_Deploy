"""
Backfill drift detection for all queries that have been evaluated but have no drift data.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from config.settings import settings
from monitoring.drift_detector import DriftDetector
from loguru import logger

def main():
    conn = psycopg2.connect(
        host=settings.DB_HOST, port=settings.DB_PORT,
        database=settings.DB_NAME, user=settings.DB_USER,
        password=settings.DB_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT q.query_id, q.query_text, q.agent_type
        FROM monitoring.queries q
        LEFT JOIN monitoring.drift_monitoring d ON q.query_id = d.query_id
        WHERE d.query_id IS NULL AND q.status = 'success'
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    logger.info(f"Found {len(rows)} queries needing drift detection")
    
    detector = DriftDetector()
    
    success = 0
    for query_id, query_text, agent_type in rows:
        try:
            result = detector.detect(query_id, query_text, agent_type)
            logger.info(f"{query_id}: drift={result['drift_score']:.3f}, "
                        f"class={result['drift_classification']}, "
                        f"sim={result['similarity_to_baseline']:.3f}")
            success += 1
        except Exception as e:
            logger.error(f"{query_id}: FAILED - {e}")
    
    logger.info(f"Done! {success}/{len(rows)} drift detections completed")

if __name__ == "__main__":
    main()
