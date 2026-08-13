import psycopg2, os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(os.getenv('DB_POOLER_URL'))
cur = conn.cursor()

tables = [
    ('md_products', 'SELECT COUNT(*) FROM md_products'),
    ('md_categories', 'SELECT COUNT(*) FROM md_categories'),
    ('md_sub_categories', 'SELECT COUNT(*) FROM md_sub_categories'),
    ('md_units', 'SELECT COUNT(*) FROM md_units'),
    ('md_pricelists', 'SELECT COUNT(*) FROM md_pricelists'),
    ('md_branch_products', 'SELECT COUNT(*) FROM md_branch_products'),
    ('md_boms', 'SELECT COUNT(*) FROM md_boms'),
    ('esb_raw_staging (CUSTOMER_PRICELIST)', "SELECT COUNT(*) FROM esb_raw_staging WHERE entity_type = 'CUSTOMER_PRICELIST'"),
    ('dlq_logs total', 'SELECT COUNT(*) FROM dlq_logs'),
]

for label, q in tables:
    cur.execute(q)
    print(f"  {label}: {cur.fetchone()[0]}")

print("\n--- Sync History (latest per entity) ---")
cur.execute("""
    SELECT DISTINCT ON (entity_type) entity_type, status, records_processed, error_message
    FROM sync_history
    WHERE entity_type IN ('PRODUCT','CATEGORY','PRODUCT_SUB_CATEGORY','PRODUCT_UNIT','PRICELIST','BRANCH_PRODUCT','BOM','CUSTOMER_PRICELIST')
    ORDER BY entity_type, id DESC
""")
for r in cur.fetchall():
    flag = "OK" if r[1] == "SUCCESS" else ("..." if r[1] == "STARTED" else "FAIL")
    print(f"  [{flag}] {r[0]}: {r[1]} ({r[2]} records) {r[3][:80] if r[3] else ''}")

cur.close(); conn.close()
