from monitoring.error_classifier import ErrorClassifier
import psycopg2
from config.settings import settings

def backfill():
    print("🛠 Backfilling Errors from Evaluations...")
    classifier = ErrorClassifier()
    
    conn = psycopg2.connect(
        host=settings.DB_HOST, port=settings.DB_PORT, database=settings.DB_NAME,
        user=settings.DB_USER, password=settings.DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Get all FAIL evaluations that are not in errors table
    cur.execute("""
        SELECT e.query_id, e.reasoning 
        FROM monitoring.evaluations e
        LEFT JOIN monitoring.errors r ON e.query_id = r.query_id
        WHERE e.result = 'FAIL' AND r.query_id IS NULL
    """)
    rows = cur.fetchall()
    print(f"Found {len(rows)} failed evaluations missing from errors table.")
    
    for row in rows:
        qid, reasoning = row
        reasoning = reasoning or "Logic Error"
        classifier.classify(reasoning, qid)
        print(f" -> Classified {qid}")
        
    conn.close()
    print("✅ Backfill Complete!")

if __name__ == "__main__":
    backfill()
