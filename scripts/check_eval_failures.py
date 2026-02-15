import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(dbname="unilever_poc", user="postgres", password="postgres", host="localhost")
cur = conn.cursor(cursor_factory=RealDictCursor)

print("--- Recent Failed Evaluations (Last 10) ---")
cur.execute("""
    SELECT q.query_text, e.result, e.reasoning, e.generated_sql
    FROM monitoring.evaluations e
    JOIN monitoring.queries q ON e.query_id = q.query_id
    WHERE e.agent_type = 'demand' AND e.result = 'FAIL'
    ORDER BY e.created_at DESC
    LIMIT 10
""")
for row in cur.fetchall():
    print(f"Query: {row['query_text']}")
    print(f"Result: {row['result']}")
    print(f"Reasoning: {row['reasoning']}")
    print(f"SQL: {row['generated_sql']}")
    print("-" * 40)

conn.close()
