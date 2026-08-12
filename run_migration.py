import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

migration_file = 'supabase/migrations/20260812120000_phase1_engine_and_master_data.sql'

with open(migration_file, 'r') as f:
    sql = f.read()

conn = psycopg2.connect(os.getenv('DB_POOLER_URL'))
cur = conn.cursor()

try:
    cur.execute(sql)
    conn.commit()
    print("Migration executed successfully.")
except Exception as e:
    conn.rollback()
    print(f"Error executing migration: {e}")
finally:
    cur.close()
    conn.close()
