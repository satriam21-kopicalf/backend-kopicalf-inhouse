import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()
conn = psycopg2.connect(os.getenv('DB_POOLER_URL'))
cur = conn.cursor()
cur.execute("INSERT INTO company_configs (company_name, is_active, esb_token) VALUES ('Dummy', true, 'dummy_token')")
conn.commit()
cur.close()
conn.close()
print("Config added")
