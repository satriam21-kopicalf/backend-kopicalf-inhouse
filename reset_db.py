import sys
import psycopg2

def reset_database():
    conn_str = 'postgresql://postgres.hpbmalkmorjwvfrxgszl:Kopicalf2019#@aws-0-ap-south-1.pooler.supabase.com:5432/postgres'
    try:
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor()
        
        # Get all public tables except spatial_ref_sys or postgis internal tables if any
        cur.execute("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public';
        """)
        
        tables = cur.fetchall()
        
        for table in tables:
            table_name = table[0]
            print(f"Truncating and resetting identity for table: {table_name}")
            try:
                cur.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE;")
            except Exception as e:
                print(f"Skipping {table_name}: {e}")
                conn.rollback()
            else:
                conn.commit()
                
        print("Database reset successfully. IDs will start from 1 again.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Failed to connect or reset database: {e}")

if __name__ == '__main__':
    reset_database()
