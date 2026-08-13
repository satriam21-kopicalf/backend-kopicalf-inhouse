import psycopg2
import os
from dotenv import load_dotenv

def truncate_db():
    load_dotenv()
    db_url = os.getenv('DB_POOLER_URL')
    if not db_url:
        print("Error: Database URL not found.")
        return

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # Fetch all tables in the public schema
        cur.execute("""
            SELECT tablename 
            FROM pg_catalog.pg_tables 
            WHERE schemaname = 'public' 
            AND tablename != 'engine_settings';
        """)
        
        tables = [row[0] for row in cur.fetchall()]
        if not tables:
            print("No tables to truncate.")
            return

        print(f"Truncating tables: {', '.join(tables)}")
        cur.execute(f"TRUNCATE TABLE {', '.join(tables)} CASCADE;")
        
        conn.commit()
        cur.close()
        conn.close()
        print("All data successfully deleted (except engine_settings).")
    except Exception as e:
        print(f"Failed to truncate database: {e}")

if __name__ == '__main__':
    truncate_db()
