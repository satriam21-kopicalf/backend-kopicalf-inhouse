import psycopg2

# Connection to Supabase
conn = psycopg2.connect(
    host="db.hpbmalkmorjwvfrxgszl.supabase.co",
    port=5432,
    dbname="postgres",
    user="postgres",
    password="Kopicalf2019#",
    sslmode="require",
    connect_timeout=30
)
conn.autocommit = True
cur = conn.cursor()

# Read migration file
with open("D:/kopicalf-projection/be-kopicalf-inhouse/supabase/migrations/20260814170700_fix_master_data_sync_issues.sql", "r", encoding="utf-8") as f:
    migration_sql = f.read()

# Execute migration
try:
    cur.execute(migration_sql)
    print("SUCCESS: Migration applied to Supabase")
except Exception as e:
    print(f"ERROR: Migration failed: {e}")

# Verify tables exist
cur.execute("""
    SELECT table_name FROM information_schema.tables 
    WHERE table_name IN ('md_document_templates', 'md_customer_pricelists')
    AND table_schema = 'public'
""")
tables = cur.fetchall()
print(f"Tables found: {[t[0] for t in tables]}")

# Verify new columns in md_pricelists
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'md_pricelists' AND table_schema = 'public'
    AND column_name IN ('price_date', 'supplier_name', 'product_name', 'product_code', 'unit_name', 'currency', 'expired_date')
""")
columns = cur.fetchall()
print(f"md_pricelists new columns: {[c[0] for c in columns]}")

# Verify new columns in md_branch_products
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'md_branch_products' AND table_schema = 'public'
    AND column_name IN ('product_code', 'product_name', 'branch_name', 'location_id', 'location_name', 'min_stock', 'max_stock', 'reserved_stock')
""")
columns = cur.fetchall()
print(f"md_branch_products new columns: {[c[0] for c in columns]}")

cur.close()
conn.close()
