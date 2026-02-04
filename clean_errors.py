import psycopg2
from config.settings import settings

def clean_errors():
    print("🧹 Cleaning Logic Errors from Errors Table (Reverting Backfill)...")
    
    conn = psycopg2.connect(
        host=settings.DB_HOST, port=settings.DB_PORT, database=settings.DB_NAME,
        user=settings.DB_USER, password=settings.DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Delete 'AGENT_LOGIC' errors (which were backfilled)
    cur.execute("DELETE FROM monitoring.errors WHERE error_category = 'AGENT_LOGIC'")
    deleted = cur.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"✅ Deleted {deleted} rows. Errors tab should now be empty (except systems errors).")

if __name__ == "__main__":
    clean_errors()
