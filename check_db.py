import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DB_POOLER_URL")

def check_db():
    print("Connecting to Supabase...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    try:
        cur.execute("SELECT * FROM company_configs;")
        companies = cur.fetchall()
        print(f"Companies: {companies}")
        
        cur.execute("SELECT * FROM sync_history ORDER BY id DESC LIMIT 5;")
        history = cur.fetchall()
        print(f"Sync History (last 5): {history}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    check_db()
