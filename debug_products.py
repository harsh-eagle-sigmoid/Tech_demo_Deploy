
import psycopg2
from config.settings import settings
conn = psycopg2.connect(host=settings.DB_HOST, port=settings.DB_PORT, database=settings.DB_NAME, user=settings.DB_USER, password=settings.DB_PASSWORD)
cur = conn.cursor()
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'spend_data' AND table_name = 'products'")
print(cur.fetchall())

