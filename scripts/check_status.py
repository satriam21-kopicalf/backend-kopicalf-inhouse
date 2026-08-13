from app.core.db import get_db_connection
conn = get_db_connection()
cur = conn.cursor()
cur.execute("SELECT entity_type, status, error_message, records_processed FROM sync_history WHERE entity_type IN ('PRODUCT', 'BRANCH_PRODUCT', 'PRICELIST', 'CUSTOMER_PRICELIST', 'BOM')")
for row in cur.fetchall():
    print(row)
cur.close()
conn.close()
