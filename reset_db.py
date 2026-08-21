import psycopg2
from psycopg2.extras import RealDictCursor
import sys

# Using Pooler URL in case IPv6 is blocked inside docker
DB_URL = "postgresql://postgres.hpbmalkmorjwvfrxgszl:Kopicalf2019#@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"

def main():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get all table names
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        tables = [r['table_name'] for r in cur.fetchall()]
        
        excluded_tables = {'company_configs', 'alembic_version', 'spatial_ref_sys'}
        tables_to_truncate = [t for t in tables if t not in excluded_tables]
        
        if not tables_to_truncate:
            print("No tables to truncate.")
            return
            
        print(f"Truncating {len(tables_to_truncate)} tables: {', '.join(tables_to_truncate)}")
        # Use CASCADE to handle foreign key dependencies
        truncate_sql = f"TRUNCATE TABLE {', '.join(tables_to_truncate)} CASCADE;"
        
        cur.execute(truncate_sql)
        conn.commit()
        
        print("Successfully wiped database tables (except company_configs).")
    except Exception as e:
        print(f"Error resetting database: {e}")
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()
