import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv(dotenv_path="d:\\kopicalf-projection\\be-kopicalf-inhouse\\.env")

def test():
    db_url = os.getenv('DB_POOLER_URL')
    print("DB URL:", db_url)
    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    
    # Check if sync_history is a table or view
    cur.execute("""
        SELECT table_name, table_type 
        FROM information_schema.tables 
        WHERE table_name = 'sync_history'
    """)
    print("Table info:", cur.fetchall())

    # Check columns
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'sync_history'
    """)
    print("Columns:", cur.fetchall())
    
    # Try an insert inside a transaction that rolls back
    try:
        cur.execute("BEGIN;")
        cur.execute(
            "INSERT INTO sync_history (entity_type, status, company_id) VALUES (%s, %s, %s) RETURNING id",
            ("TEST", "STARTED", 1) # Assuming company_id 1 exists
        )
        row = cur.fetchone()
        print("Inserted row:", row)
        cur.execute("ROLLBACK;")
    except Exception as e:
        print("Insert Error:", repr(e))
        cur.execute("ROLLBACK;")
        
    conn.close()

if __name__ == '__main__':
    test()
