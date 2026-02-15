import os
import psycopg2
from psycopg2.extras import RealDictCursor

# DB Config
DB_NAME = "unilever_poc"
DB_USER = "postgres"
DB_PASS = "postgres"
DB_HOST = "localhost"
DB_PORT = "5432"

conn = psycopg2.connect(
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASS,
    host=DB_HOST,
    port=DB_PORT
)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("--- All Time Accuracy ---")
cur.execute("""
    SELECT 
        e.agent_type, 
        COUNT(*) as total, 
        SUM(CASE WHEN e.result = 'PASS' THEN 1 ELSE 0 END) as passed,
        ROUND(AVG(CASE WHEN e.result = 'PASS' THEN 100.0 ELSE 0.0 END), 2) as accuracy
    FROM monitoring.evaluations e
    GROUP BY e.agent_type
""")
for row in cur.fetchall():
    print(f"Agent: {row['agent_type']} | Total: {row['total']} | Passed: {row['passed']} | Accuracy: {row['accuracy']}%")

print("\n--- Last 50 Queries Accuracy (Recent Run) ---")
agents = ['spend', 'demand']
for agent in agents:
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN result = 'PASS' THEN 1 ELSE 0 END) as passed,
            ROUND(AVG(CASE WHEN result = 'PASS' THEN 100.0 ELSE 0.0 END), 2) as accuracy
        FROM (
            SELECT e.result
            FROM monitoring.evaluations e
            JOIN monitoring.queries q ON e.query_id = q.query_id
            WHERE q.agent_type = %s
            ORDER BY q.created_at DESC
            LIMIT 50
        ) as recent
    """, (agent,))
    row = cur.fetchone()
    if row and row['total'] > 0:
        print(f"Agent: {agent} | Recent 50 - Total: {row['total']} | Passed: {row['passed']} | Accuracy: {row['accuracy']}%")
    else:
        print(f"Agent: {agent} | Recent 50 - No data found")

cur.close()
conn.close()
