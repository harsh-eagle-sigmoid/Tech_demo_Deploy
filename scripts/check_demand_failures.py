import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json

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

print("--- Top Error Categories (Last 50 Failures) ---")
cur.execute("""
    SELECT error_category, COUNT(*) as count
    FROM monitoring.errors e
    JOIN monitoring.queries q ON e.query_id = q.query_id
    WHERE q.agent_type = 'demand'
    GROUP BY error_category
    ORDER BY count DESC
    LIMIT 5
""")
for row in cur.fetchall():
    print(f"Category: {row['error_category']} | Count: {row['count']}")

print("\n--- Recent Failed Queries (Last 5) ---")
cur.execute("""
    SELECT q.query_text, q.generated_sql, e.error_message, e.last_seen
    FROM monitoring.errors e
    JOIN monitoring.queries q ON e.query_id = q.query_id
    WHERE q.agent_type = 'demand'
    ORDER BY e.last_seen DESC
    LIMIT 5
""")
for row in cur.fetchall():
    print(f"Time: {row['last_seen']}")
    print(f"Query: {row['query_text']}")
    print(f"SQL: {row['generated_sql']}")
    print(f"Error: {row['error_message']}")
    print("-" * 40)

cur.close()
conn.close()
