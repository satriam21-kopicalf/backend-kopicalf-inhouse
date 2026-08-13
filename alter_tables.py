import sys
import psycopg2

def alter_tables():
    conn_str = 'postgresql://postgres.hpbmalkmorjwvfrxgszl:Kopicalf2019#@aws-0-ap-south-1.pooler.supabase.com:5432/postgres'
    conn = psycopg2.connect(conn_str)
    cur = conn.cursor()
    
    queries = [
        # md_products
        "ALTER TABLE md_products ADD COLUMN IF NOT EXISTS product_alias VARCHAR(255);",
        "ALTER TABLE md_products ADD COLUMN IF NOT EXISTS category_id BIGINT;",
        "ALTER TABLE md_products ADD COLUMN IF NOT EXISTS sub_category_id BIGINT;",
        "ALTER TABLE md_products ADD COLUMN IF NOT EXISTS uom_id BIGINT;",
        "ALTER TABLE md_products ADD COLUMN IF NOT EXISTS bom_id BIGINT;",
        "ALTER TABLE md_products ADD COLUMN IF NOT EXISTS pricelist_id BIGINT;",
        "ALTER TABLE md_products ADD COLUMN IF NOT EXISTS min_stock NUMERIC;",
        "ALTER TABLE md_products ADD COLUMN IF NOT EXISTS max_stock NUMERIC;",
        "ALTER TABLE md_products ADD COLUMN IF NOT EXISTS is_track_inventory BOOLEAN;",
        "ALTER TABLE md_products ADD COLUMN IF NOT EXISTS description TEXT;",
        
        # md_branch_products
        "ALTER TABLE md_branch_products ADD COLUMN IF NOT EXISTS product_code VARCHAR(255);",
        "ALTER TABLE md_branch_products ADD COLUMN IF NOT EXISTS product_name VARCHAR(255);",
        "ALTER TABLE md_branch_products ADD COLUMN IF NOT EXISTS branch_name VARCHAR(255);",
        "ALTER TABLE md_branch_products ADD COLUMN IF NOT EXISTS location_id BIGINT;",
        "ALTER TABLE md_branch_products ADD COLUMN IF NOT EXISTS location_name VARCHAR(255);",
        "ALTER TABLE md_branch_products ADD COLUMN IF NOT EXISTS min_stock NUMERIC;",
        "ALTER TABLE md_branch_products ADD COLUMN IF NOT EXISTS max_stock NUMERIC;",
        "ALTER TABLE md_branch_products ADD COLUMN IF NOT EXISTS reserved_stock NUMERIC;",
        
        # md_sub_categories
        "ALTER TABLE md_sub_categories ADD COLUMN IF NOT EXISTS display_order INTEGER;",
        
        # md_pricelists
        "ALTER TABLE md_pricelists ADD COLUMN IF NOT EXISTS price_date TIMESTAMP WITH TIME ZONE;",
        "ALTER TABLE md_pricelists ADD COLUMN IF NOT EXISTS supplier_name VARCHAR(255);",
        "ALTER TABLE md_pricelists ADD COLUMN IF NOT EXISTS product_name VARCHAR(255);",
        "ALTER TABLE md_pricelists ADD COLUMN IF NOT EXISTS product_code VARCHAR(255);",
        "ALTER TABLE md_pricelists ADD COLUMN IF NOT EXISTS unit_name VARCHAR(255);",
        "ALTER TABLE md_pricelists ADD COLUMN IF NOT EXISTS currency VARCHAR(50);",
        "ALTER TABLE md_pricelists ADD COLUMN IF NOT EXISTS expired_date TIMESTAMP WITH TIME ZONE;"
    ]
    
    for q in queries:
        try:
            print(f"Executing: {q}")
            cur.execute(q)
        except Exception as e:
            print(f"Error executing {q}: {e}")
            conn.rollback()
        else:
            conn.commit()
            
    print("Alter tables completed successfully.")
    cur.close()
    conn.close()

if __name__ == '__main__':
    alter_tables()
