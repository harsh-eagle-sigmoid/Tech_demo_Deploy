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

print("--- Columns in demand_data.sales ---")
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'demand_data' AND table_name = 'sales'
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"{row['column_name']} ({row['data_type']})")

print("\n--- Columns in demand_data.products ---")
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'demand_data' AND table_name = 'products'
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"{row['column_name']} ({row['data_type']})")

print("\n--- Columns in demand_data.supply_chain ---")
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'demand_data' AND table_name = 'supply_chain'
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"{row['column_name']} ({row['data_type']})")

cur.close()
conn.close()
