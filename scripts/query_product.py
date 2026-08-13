import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.getenv('DB_POOLER_URL'))
cur = conn.cursor()
cur.execute("SELECT entity_type, status, error_message FROM sync_history WHERE entity_type = 'PRODUCT' ORDER BY id DESC LIMIT 5")
for r in cur.fetchall():
    print(r)
