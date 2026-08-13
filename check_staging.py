import psycopg2
DB_URI = 'postgresql://postgres.hpbmalkmorjwvfrxgszl:Kopicalf2019%23@aws-0-ap-south-1.pooler.supabase.com:5432/postgres'
conn = psycopg2.connect(DB_URI)
cur = conn.cursor()
cur.execute("SELECT conname, pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_class t ON c.conrelid = t.oid WHERE t.relname = 'esb_raw_staging'")
for r in cur.fetchall(): print(r)
