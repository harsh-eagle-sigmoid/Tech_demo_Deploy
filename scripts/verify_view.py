import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(dbname="unilever_poc", user="postgres", password="postgres", host="localhost")
cur = conn.cursor(cursor_factory=RealDictCursor)

print("--- View ---")
cur.execute("""
    SELECT table_name 
    FROM information_schema.views 
    WHERE table_schema = 'demand_data' AND table_name = 'product_profitability'
""")
for row in cur.fetchall():
    print(f"View Found: {row['table_name']}")

print("--- Columns ---")
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_schema = 'demand_data' AND table_name = 'product_profitability'
""")
for row in cur.fetchall():
    print(f"{row['column_name']} ({row['data_type']})")

conn.close()
