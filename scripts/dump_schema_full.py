
import sys
import os
sys.path.append(os.getcwd())
import psycopg2
from config.settings import settings

def analyze_schema():
    try:
        conn = psycopg2.connect(host=settings.DB_HOST, port=settings.DB_PORT, database=settings.DB_NAME, user=settings.DB_USER, password=settings.DB_PASSWORD)
        cur = conn.cursor()
        
        # Get all schemas (excluding system ones)
        cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')")
        schemas = [row[0] for row in cur.fetchall()]
        
        print("=== Database Schema Analysis (Read-Only) ===\n")
        
        for schema in schemas:
            print(f"--- Schema: {schema} ---")
            
            # Get Tables
            cur.execute(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema}' AND table_type = 'BASE TABLE'")
            tables = [row[0] for row in cur.fetchall()]
            
            if not tables:
                print("  (No tables)")
                # Check for Views?
                cur.execute(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema}' AND table_type = 'VIEW'")
                views = [row[0] for row in cur.fetchall()]
                if views:
                    print("  Views:", views)
                continue

            for table in tables:
                print(f"\n  Table: {table}")
                
                # Get Columns
                cur.execute(f"""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_schema = '{schema}' AND table_name = '{table}'
                    ORDER BY ordinal_position
                """)
                columns = cur.fetchall()
                for col in columns:
                    print(f"    - {col[0]} ({col[1]}), Nullable: {col[2]}")
                
                # Get Foreign Keys
                cur.execute(f"""
                    SELECT
                        kcu.column_name, 
                        ccu.table_schema AS foreign_table_schema,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name 
                    FROM 
                        information_schema.key_column_usage AS kcu
                        JOIN information_schema.referential_constraints AS rc 
                        ON kcu.constraint_name = rc.constraint_name
                        JOIN information_schema.constraint_column_usage AS ccu 
                        ON rc.unique_constraint_name = ccu.constraint_name
                    WHERE kcu.table_schema = '{schema}' AND kcu.table_name = '{table}'
                """)
                fks = cur.fetchall()
                if fks:
                    print("    Foreign Keys:")
                    for fk in fks:
                        print(f"      -> {fk[0]} references {fk[1]}.{fk[2]}({fk[3]})")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_schema()
