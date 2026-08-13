import psycopg2
DB_URI = 'postgresql://postgres.hpbmalkmorjwvfrxgszl:Kopicalf2019%23@aws-0-ap-south-1.pooler.supabase.com:5432/postgres'
conn = psycopg2.connect(DB_URI)
cur = conn.cursor()
cur.execute("SELECT entity_type, COUNT(*) FROM esb_raw_staging GROUP BY entity_type")
for r in cur.fetchall(): print(r)
