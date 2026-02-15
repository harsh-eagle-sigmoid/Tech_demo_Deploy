#!/usr/bin/env python3
"""
Fix the missing UNIQUE constraint on monitoring.evaluations(query_id)
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

# Check if constraint exists
print("Checking current constraints on monitoring.evaluations...")
cur.execute("""
    SELECT constraint_name, constraint_type 
    FROM information_schema.table_constraints 
    WHERE table_schema = 'monitoring' 
    AND table_name = 'evaluations'
""")
constraints = cur.fetchall()
print(f"Current constraints: {constraints}")

# Check if query_id is indexed/unique
cur.execute("""
    SELECT indexname, indexdef
    FROM pg_indexes
    WHERE schemaname = 'monitoring'
    AND tablename = 'evaluations'
""")
indexes = cur.fetchall()
print(f"Current indexes: {indexes}")

# Add UNIQUE constraint on query_id if it doesn't exist
print("\nAdding UNIQUE constraint on query_id...")
try:
    cur.execute("""
        ALTER TABLE monitoring.evaluations
        ADD CONSTRAINT evaluations_query_id_unique UNIQUE (query_id)
    """)
    conn.commit()
    print("✅ UNIQUE constraint added successfully!")
except Exception as e:
    print(f"❌ Error adding constraint: {e}")
    conn.rollback()

cur.close()
conn.close()
print("\nDone!")
