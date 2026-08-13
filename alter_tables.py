import sys
import psycopg2

def alter_tables():
    conn_str = 'postgresql://postgres.hpbmalkmorjwvfrxgszl:Kopicalf2019#@aws-0-ap-south-1.pooler.supabase.com:5432/postgres'
    conn = psycopg2.connect(conn_str)
    cur = conn.cursor()
    
    queries = [
        # md_products — extra fields (optional, may not exist in API list)
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

        # md_branch_products — sesuai response stock-location aktual
        "ALTER TABLE md_branch_products ADD COLUMN IF NOT EXISTS product_detail_id BIGINT;",
        "ALTER TABLE md_branch_products ADD COLUMN IF NOT EXISTS product_code VARCHAR(255);",
        "ALTER TABLE md_branch_products ADD COLUMN IF NOT EXISTS product_name VARCHAR(255);",
        "ALTER TABLE md_branch_products ADD COLUMN IF NOT EXISTS branch_name VARCHAR(255);",
        "ALTER TABLE md_branch_products ADD COLUMN IF NOT EXISTS location_id BIGINT;",
        "ALTER TABLE md_branch_products ADD COLUMN IF NOT EXISTS location_name VARCHAR(255);",
        "ALTER TABLE md_branch_products ADD COLUMN IF NOT EXISTS min_stock NUMERIC;",
        "ALTER TABLE md_branch_products ADD COLUMN IF NOT EXISTS max_stock NUMERIC;",
        "ALTER TABLE md_branch_products ADD COLUMN IF NOT EXISTS reserved_stock NUMERIC;",
        "ALTER TABLE md_branch_products ADD COLUMN IF NOT EXISTS uom_name VARCHAR(100);",
        "ALTER TABLE md_branch_products ADD COLUMN IF NOT EXISTS qty NUMERIC;",
        "ALTER TABLE md_branch_products ADD COLUMN IF NOT EXISTS dropdown_product VARCHAR(500);",

        # md_sub_categories — display_order + nullable category
        "ALTER TABLE md_sub_categories ADD COLUMN IF NOT EXISTS display_order INTEGER;",
        "ALTER TABLE md_sub_categories ADD COLUMN IF NOT EXISTS notes TEXT;",
        "ALTER TABLE md_sub_categories ADD COLUMN IF NOT EXISTS dead_stock_threshold INTEGER;",
        "ALTER TABLE md_sub_categories ALTER COLUMN category_esb_id DROP NOT NULL;",

        # md_categories — notes + categoryTypeID
        "ALTER TABLE md_categories ADD COLUMN IF NOT EXISTS notes TEXT;",
        "ALTER TABLE md_categories ADD COLUMN IF NOT EXISTS category_type_id BIGINT;",

        # md_units — tambah metric fields
        "ALTER TABLE md_units ADD COLUMN IF NOT EXISTS metric_id BIGINT;",
        "ALTER TABLE md_units ADD COLUMN IF NOT EXISTS metric_name VARCHAR(100);",
        "ALTER TABLE md_units ADD COLUMN IF NOT EXISTS notes TEXT;",

        # md_pricelists — sesuai response aktual
        "ALTER TABLE md_pricelists ADD COLUMN IF NOT EXISTS price_date TIMESTAMP WITH TIME ZONE;",
        "ALTER TABLE md_pricelists ADD COLUMN IF NOT EXISTS supplier_name VARCHAR(255);",
        "ALTER TABLE md_pricelists ADD COLUMN IF NOT EXISTS product_name VARCHAR(255);",
        "ALTER TABLE md_pricelists ADD COLUMN IF NOT EXISTS product_code VARCHAR(255);",
        "ALTER TABLE md_pricelists ADD COLUMN IF NOT EXISTS unit_name VARCHAR(255);",
        "ALTER TABLE md_pricelists ADD COLUMN IF NOT EXISTS currency VARCHAR(50);",
        "ALTER TABLE md_pricelists ADD COLUMN IF NOT EXISTS expired_date TIMESTAMP WITH TIME ZONE;",
        "ALTER TABLE md_pricelists ADD COLUMN IF NOT EXISTS product_detail_id BIGINT;",
        "ALTER TABLE md_pricelists ADD COLUMN IF NOT EXISTS pricelist_num VARCHAR(100);",
        "ALTER TABLE md_pricelists ADD COLUMN IF NOT EXISTS supplier_id BIGINT;",
        "ALTER TABLE md_pricelists ADD COLUMN IF NOT EXISTS uom_id BIGINT;",

        # md_boms — tambah fields yang ada di response
        "ALTER TABLE md_boms ADD COLUMN IF NOT EXISTS bom_type_id BIGINT;",
        "ALTER TABLE md_boms ADD COLUMN IF NOT EXISTS bom_type_name VARCHAR(100);",
        "ALTER TABLE md_boms ADD COLUMN IF NOT EXISTS product_name VARCHAR(255);",
        "ALTER TABLE md_boms ADD COLUMN IF NOT EXISTS uom_name VARCHAR(100);",
        "ALTER TABLE md_boms ADD COLUMN IF NOT EXISTS notes TEXT;",
        "ALTER TABLE md_boms ALTER COLUMN product_esb_id DROP NOT NULL;",
        # md_branch_products — branch_esb_id & product_esb_id bisa NULL (response tidak berisi branchID)
        "ALTER TABLE md_branch_products ALTER COLUMN branch_esb_id DROP NOT NULL;",
        "ALTER TABLE md_branch_products ALTER COLUMN product_esb_id DROP NOT NULL;",
        # sync_history — drop FK ke company_configs agar tidak error saat data direset
        "ALTER TABLE sync_history DROP CONSTRAINT IF EXISTS sync_history_company_id_fkey;",
    ]
    
    for q in queries:
        try:
            print(f"Executing: {q[:80]}...")
            cur.execute(q)
        except Exception as e:
            print(f"  Warning: {e}")
            conn.rollback()
        else:
            conn.commit()
            
    print("\nAlter tables completed successfully.")
    cur.close()
    conn.close()

if __name__ == '__main__':
    alter_tables()
