
import psycopg2
from config.settings import settings
try:
    conn = psycopg2.connect(host=settings.DB_HOST, port=settings.DB_PORT, database=settings.DB_NAME, user=settings.DB_USER, password=settings.DB_PASSWORD)
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'spend_data'")
    rows = cur.fetchall()
    print(f'Tables in spend_data schema: {rows}')
    
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    rows_public = cur.fetchall()
    print(f'Tables in public schema: {rows_public}')
except Exception as e:
    print(e)

