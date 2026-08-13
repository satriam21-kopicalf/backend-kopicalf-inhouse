import psycopg2
conn = psycopg2.connect('postgresql://postgres.hpbmalkmorjwvfrxgszl:Kopicalf2019%23@aws-0-ap-south-1.pooler.supabase.com:5432/postgres')
cur = conn.cursor()
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'md_products'")
for r in cur.fetchall():
    print(r)
