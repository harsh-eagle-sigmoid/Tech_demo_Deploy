import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(dbname="unilever_poc", user="postgres", password="postgres", host="localhost")
cur = conn.cursor(cursor_factory=RealDictCursor)

print("--- Columns in monitoring.evaluations ---")
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'monitoring' AND table_name = 'evaluations'
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"{row['column_name']} ({row['data_type']})")

conn.close()
