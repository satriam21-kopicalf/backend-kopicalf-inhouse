import psycopg2
DB_URI = 'postgresql://postgres.hpbmalkmorjwvfrxgszl:Kopicalf2019%23@aws-0-ap-south-1.pooler.supabase.com:5432/postgres'
conn = psycopg2.connect(DB_URI)
conn.autocommit = True
cur = conn.cursor()
cur.execute("DELETE FROM company_configs WHERE company_name = 'System Analyst ESB'")
print('Deleted System Analyst ESB')
cur.close()
conn.close()
