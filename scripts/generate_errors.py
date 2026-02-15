from monitoring.error_classifier import ErrorClassifier
import uuid
import random
import time
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def generate_errors():
    print("💥 Generating 15 System Errors for Dashboard...")
    classifier = ErrorClassifier()
    
    # DB Connection to insert dummy queries
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        database=os.getenv("DB_NAME", "unilever_poc"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres")
    )
    
    errors = [
        ("SQL_GENERATION", "syntax error at or near 'FROM'"),
        ("SQL_GENERATION", "invalid sql statement: SELECT * FROM WHERE"),
        ("SQL_GENERATION", "could not parse generated SQL"),
        ("CONTEXT_RETRIEVAL", "relation 'public.users' does not exist"),
        ("CONTEXT_RETRIEVAL", "column 'profit_margin' does not exist"),
        ("CONTEXT_RETRIEVAL", "schema 'finance' does not exist"),
        ("INTEGRATION", "connection refused to agent"),
        ("INTEGRATION", "timeout waiting for agent response"),
        ("INTEGRATION", "http error 503 service unavailable"),
        ("DATA_ERROR", "no rows returned for query"),
        ("DATA_ERROR", "empty result set"),
        ("AGENT_LOGIC", "incorrect join logic detected"),
        ("AGENT_LOGIC", "missing filter condition"),
        ("SQL_GENERATION", "unexpected token 'LIMIT'"),
        ("INTEGRATION", "max retries exceeded for url"),
    ]
    
    cur = conn.cursor()
    
    for i, (cat, msg) in enumerate(errors):
        query_id = f"ERR-TEST-{uuid.uuid4().hex[:8]}"
        
        # 1. Insert Dummy Query
        try:
            cur.execute("""
                INSERT INTO monitoring.queries (query_id, query_text, agent_type, status)
                VALUES (%s, %s, %s, %s)
            """, (query_id, f"Simulated error query {i+1}", "spend", "error"))
            conn.commit()
            
            # 2. Trigger Error Classification (which inserts into errors)
            print(f"[{i+1}/15] Triggering: {msg}")
            classifier.classify(msg, query_id)
            time.sleep(0.1)
        except Exception as e:
            print(f"❌ Failed to insert dummy query: {e}")
            conn.rollback()

    cur.close()
    conn.close()
    print("✅ Done! Check Errors Tab.")

if __name__ == "__main__":
    generate_errors()
