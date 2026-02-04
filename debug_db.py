import psycopg2
from config.settings import settings

def debug_db():
    conn = psycopg2.connect(
        host=settings.DB_HOST,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("--- Queries ---")
    cur.execute("SELECT query_id, agent_type, created_at FROM monitoring.queries ORDER BY created_at DESC LIMIT 5")
    for row in cur.fetchall():
        print(row)
        
    print("\n--- Evaluations ---")
    cur.execute("SELECT query_id, result, final_score FROM monitoring.evaluations LIMIT 5")
    rows = cur.fetchall()
    print(f"Total Evaluations: {len(rows)}")
    for row in rows:
        print(row)
        
    print("\n--- Join Test ---")
    cur.execute("""
        SELECT q.query_id, e.result 
        FROM monitoring.queries q 
        LEFT JOIN monitoring.evaluations e ON q.query_id = e.query_id 
        WHERE q.query_id = %s
    """, (rows[0][0] if rows else "DUMMY",))
    print(cur.fetchall())
    
    conn.close()

if __name__ == "__main__":
    debug_db()
