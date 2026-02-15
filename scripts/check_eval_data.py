#!/usr/bin/env python3
"""
Check if evaluations table has data
"""
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", 5432),
    database=os.getenv("DB_NAME", "unilever_poc"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "postgres")
)

cur = conn.cursor()

# Check count
cur.execute("SELECT COUNT(*) FROM monitoring.evaluations")
count = cur.fetchone()[0]
print(f"Total evaluations in DB: {count}")

# Show latest 3
cur.execute("""
    SELECT query_id, result, confidence, created_at 
    FROM monitoring.evaluations 
    ORDER BY created_at DESC 
    LIMIT 3
""")
rows = cur.fetchall()
print(f"\nLatest 3 evaluations:")
for row in rows:
    print(f"  - {row[0]}: {row[1]} (conf: {row[2]:.2f}) at {row[3]}")

cur.close()
conn.close()
