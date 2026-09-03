import psycopg2
import sys

try:
    print("Connecting to Supabase database...")
    conn = psycopg2.connect(
        host='db.hpbmalkmorjwvfrxgszl.supabase.co',
        port=5432,
        database='postgres',
        user='postgres',
        password='Kopicalf2019#'
    )
    cur = conn.cursor()

    # Check schemas
    cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('esb_data', 'public')")
    schemas = cur.fetchall()
    print('\nAvailable schemas:')
    for s in schemas:
        print(f'  - {s[0]}')

    # Check if master tables exist
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'esb_data' AND table_name LIKE 'master_%%'
    """)
    master_tables = cur.fetchall()
    print('\nMaster tables in esb_data:')
    if master_tables:
        for t in master_tables:
            print(f'  - {t[0]}')
    else:
        print('  (none found)')

    # Check public schema tables
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name LIKE 'master_%%'
    """)
    public_master_tables = cur.fetchall()
    print('\nMaster tables in public:')
    if public_master_tables:
        for t in public_master_tables:
            print(f'  - {t[0]}')
    else:
        print('  (none found)')

    cur.close()
    conn.close()
    print('\nConnection successful!')
except Exception as e:
    print(f'Error: {e}')
    sys.exit(1)
