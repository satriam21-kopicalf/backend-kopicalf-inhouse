"""
Data migration script from be-kopicalf-inhouse to backend-kopicalf-inhouse.
This script migrates data from public.md_* tables to esb_data.master_* tables.
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_source_connection():
    """Get connection to source database (be-kopicalf-inhouse)."""
    # This would be the source database connection
    # For now, using the same connection as target for testing
    db_url = os.getenv('DB_POOLER_URL') or os.getenv('DATABASE_URL')
    if not db_url:
        raise ValueError("Database URL not found in environment variables.")
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

def get_target_connection():
    """Get connection to target database (backend-kopicalf-inhouse with esb_data schema)."""
    db_url = os.getenv('DB_POOLER_URL') or os.getenv('DATABASE_URL')
    if not db_url:
        raise ValueError("Database URL not found in environment variables.")
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor, options="-c search_path=esb_data,public")

def migrate_master_data():
    """Migrate master data from public.md_* to esb_data.master_* tables."""
    print("Starting master data migration...")
    
    target_conn = get_target_connection()
    target_cur = target_conn.cursor()
    
    try:
        # Define migration mappings
        migrations = [
            {
                "source": "md_outlets",
                "target": "master_branch",
                "mapping": """
                    INSERT INTO esb_data.master_branch 
                    (esb_id, company_id, name, branch_code, is_active, location_name, stock, available_stock, raw_data)
                    SELECT esb_id, company_id, name, branch_code, is_active, location_name, stock, available_stock, raw_data
                    FROM public.md_outlets
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        name = EXCLUDED.name, branch_code = EXCLUDED.branch_code, is_active = EXCLUDED.is_active,
                        location_name = EXCLUDED.location_name, stock = EXCLUDED.stock, available_stock = EXCLUDED.available_stock,
                        raw_data = EXCLUDED.raw_data, updated_at = NOW()
                """
            },
            {
                "source": "md_products", 
                "target": "master_product",
                "mapping": """
                    INSERT INTO esb_data.master_product 
                    (esb_id, company_id, name, product_code, bom_name, category_name, sub_category_name, category_type_name, flag_active, raw_data)
                    SELECT esb_id, company_id, name, product_code, bom_name, category_name, sub_category_name, category_type_name, flag_active, raw_data
                    FROM public.md_products
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        name = EXCLUDED.name, product_code = EXCLUDED.product_code, bom_name = EXCLUDED.bom_name,
                        category_name = EXCLUDED.category_name, sub_category_name = EXCLUDED.sub_category_name,
                        category_type_name = EXCLUDED.category_type_name, flag_active = EXCLUDED.flag_active, 
                        raw_data = EXCLUDED.raw_data, updated_at = NOW()
                """
            },
            {
                "source": "md_categories",
                "target": "master_category", 
                "mapping": """
                    INSERT INTO esb_data.master_category
                    (esb_id, company_id, code, name, type_name, flag_active, category_type_id, notes, raw_data)
                    SELECT esb_id, company_id, code, name, type_name, flag_active, category_type_id, notes, raw_data
                    FROM public.md_categories
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        code = EXCLUDED.code, name = EXCLUDED.name, type_name = EXCLUDED.type_name,
                        flag_active = EXCLUDED.flag_active, category_type_id = EXCLUDED.category_type_id,
                        notes = EXCLUDED.notes, raw_data = EXCLUDED.raw_data, updated_at = NOW()
                """
            },
            {
                "source": "md_sub_categories",
                "target": "master_sub_category",
                "mapping": """
                    INSERT INTO esb_data.master_sub_category
                    (esb_id, company_id, category_esb_id, code, name, flag_active, dead_stock_threshold, notes, raw_data)
                    SELECT esb_id, company_id, category_esb_id, code, name, flag_active, dead_stock_threshold, notes, raw_data
                    FROM public.md_sub_categories
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        category_esb_id = EXCLUDED.category_esb_id, code = EXCLUDED.code, name = EXCLUDED.name,
                        flag_active = EXCLUDED.flag_active, dead_stock_threshold = EXCLUDED.dead_stock_threshold,
                        notes = EXCLUDED.notes, raw_data = EXCLUDED.raw_data, updated_at = NOW()
                """
            },
            {
                "source": "md_units",
                "target": "master_unit",
                "mapping": """
                    INSERT INTO esb_data.master_unit
                    (esb_id, company_id, code, name, flag_active, raw_data)
                    SELECT esb_id, company_id, code, name, flag_active, raw_data
                    FROM public.md_units
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        code = EXCLUDED.code, name = EXCLUDED.name, flag_active = EXCLUDED.flag_active, 
                        raw_data = EXCLUDED.raw_data, updated_at = NOW()
                """
            },
            {
                "source": "md_pricelists",
                "target": "master_pricelist",
                "mapping": """
                    INSERT INTO esb_data.master_pricelist
                    (esb_id, company_id, product_esb_id, branch_esb_id, price, flag_active, price_date, supplier_name, 
                     product_name, product_code, unit_name, currency, expired_date, pricelist_num, product_detail_esb_id, 
                     uom_id, currency_id, applicable_branch, raw_data)
                    SELECT esb_id, company_id, product_esb_id, branch_esb_id, price, flag_active, price_date, supplier_name,
                           product_name, product_code, unit_name, currency, expired_date, pricelist_num, product_detail_esb_id,
                           uom_id, currency_id, applicable_branch, raw_data
                    FROM public.md_pricelists
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        product_esb_id = EXCLUDED.product_esb_id, branch_esb_id = EXCLUDED.branch_esb_id,
                        price = EXCLUDED.price, flag_active = EXCLUDED.flag_active, price_date = EXCLUDED.price_date,
                        supplier_name = EXCLUDED.supplier_name, product_name = EXCLUDED.product_name,
                        product_code = EXCLUDED.product_code, unit_name = EXCLUDED.unit_name, currency = EXCLUDED.currency,
                        expired_date = EXCLUDED.expired_date, pricelist_num = EXCLUDED.pricelist_num,
                        product_detail_esb_id = EXCLUDED.product_detail_esb_id, uom_id = EXCLUDED.uom_id,
                        currency_id = EXCLUDED.currency_id, applicable_branch = EXCLUDED.applicable_branch,
                        raw_data = EXCLUDED.raw_data, updated_at = NOW()
                """
            },
            {
                "source": "md_suppliers",
                "target": "master_supplier",
                "mapping": """
                    INSERT INTO esb_data.master_supplier
                    (esb_id, company_id, name, type, supplier_category, status, address, contact_person, cell_phone,
                     due_date, category_esb_id, lock_vat, vat_subject, raw_data)
                    SELECT esb_id, company_id, name, type, supplier_category, status, address, contact_person, cell_phone,
                           due_date, category_esb_id, lock_vat, vat_subject, raw_data
                    FROM public.md_suppliers
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        name = EXCLUDED.name, supplier_category = EXCLUDED.supplier_category, status = EXCLUDED.status,
                        address = EXCLUDED.address, contact_person = EXCLUDED.contact_person, cell_phone = EXCLUDED.cell_phone,
                        due_date = EXCLUDED.due_date, category_esb_id = EXCLUDED.category_esb_id,
                        lock_vat = EXCLUDED.lock_vat, vat_subject = EXCLUDED.vat_subject, raw_data = EXCLUDED.raw_data, updated_at = NOW()
                """
            },
            {
                "source": "md_customers",
                "target": "master_customer",
                "mapping": """
                    INSERT INTO esb_data.master_customer
                    (esb_id, company_id, name, code, category_esb_id, category_name, payment_due_days, address, 
                     pic_name, pic_phone, flag_active, lock_vat, raw_data)
                    SELECT esb_id, company_id, name, code, category_esb_id, category_name, payment_due_days, address,
                           pic_name, pic_phone, flag_active, lock_vat, raw_data
                    FROM public.md_customers
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        name = EXCLUDED.name, code = EXCLUDED.code, category_esb_id = EXCLUDED.category_esb_id,
                        category_name = EXCLUDED.category_name, payment_due_days = EXCLUDED.payment_due_days,
                        address = EXCLUDED.address, pic_name = EXCLUDED.pic_name, pic_phone = EXCLUDED.pic_phone,
                        flag_active = EXCLUDED.flag_active, lock_vat = EXCLUDED.lock_vat, raw_data = EXCLUDED.raw_data, updated_at = NOW()
                """
            },
            {
                "source": "md_boms",
                "target": "master_bill_of_material",
                "mapping": """
                    INSERT INTO esb_data.master_bill_of_material
                    (esb_id, company_id, product_esb_id, code, name, output_qty, flag_active, bom_type_id, 
                     bom_type_name, product_name, uom_name, raw_data)
                    SELECT esb_id, company_id, product_esb_id, code, name, output_qty, flag_active, bom_type_id,
                           bom_type_name, product_name, uom_name, raw_data
                    FROM public.md_boms
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        product_esb_id = EXCLUDED.product_esb_id, code = EXCLUDED.code, name = EXCLUDED.name,
                        output_qty = EXCLUDED.output_qty, flag_active = EXCLUDED.flag_active, bom_type_id = EXCLUDED.bom_type_id,
                        bom_type_name = EXCLUDED.bom_type_name, product_name = EXCLUDED.product_name, uom_name = EXCLUDED.uom_name,
                        raw_data = EXCLUDED.raw_data, updated_at = NOW()
                """
            },
            {
                "source": "md_document_templates",
                "target": "master_document_template",
                "mapping": """
                    INSERT INTO esb_data.master_document_template
                    (esb_id, company_id, name, document_type, template_code, flag_active, raw_data)
                    SELECT esb_id, company_id, name, document_type, template_code, flag_active, raw_data
                    FROM public.md_document_templates
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        name = EXCLUDED.name, document_type = EXCLUDED.document_type, template_code = EXCLUDED.template_code,
                        flag_active = EXCLUDED.flag_active, raw_data = EXCLUDED.raw_data, updated_at = NOW()
                """
            },
            {
                "source": "md_purposes",
                "target": "master_purpose",
                "mapping": """
                    INSERT INTO esb_data.master_purpose
                    (esb_id, company_id, name, account, coa_no, applied_to, flag_active, raw_data)
                    SELECT esb_id, company_id, name, account, coa_no, applied_to, flag_active, raw_data
                    FROM public.md_purposes
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        name = EXCLUDED.name, account = EXCLUDED.account, coa_no = EXCLUDED.coa_no,
                        applied_to = EXCLUDED.applied_to, flag_active = EXCLUDED.flag_active, raw_data = EXCLUDED.raw_data, updated_at = NOW()
                """
            },
            {
                "source": "md_cost_centers",
                "target": "master_cost_center",
                "mapping": """
                    INSERT INTO esb_data.master_cost_center
                    (esb_id, company_id, code, name, flag_active, raw_data)
                    SELECT esb_id, company_id, code, name, flag_active, raw_data
                    FROM public.md_cost_centers
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        code = EXCLUDED.code, name = EXCLUDED.name, flag_active = EXCLUDED.flag_active,
                        raw_data = EXCLUDED.raw_data, updated_at = NOW()
                """
            },
            {
                "source": "md_coas",
                "target": "master_charts_of_account",
                "mapping": """
                    INSERT INTO esb_data.master_charts_of_account
                    (esb_id, company_id, coa_no, coa_level, description, currency, branch_esb_id, flag_active, raw_data)
                    SELECT esb_id, company_id, coa_no, coa_level, description, currency, branch_esb_id, flag_active, raw_data
                    FROM public.md_coas
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        coa_no = EXCLUDED.coa_no, coa_level = EXCLUDED.coa_level, description = EXCLUDED.description,
                        currency = EXCLUDED.currency, branch_esb_id = EXCLUDED.branch_esb_id, flag_active = EXCLUDED.flag_active,
                        raw_data = EXCLUDED.raw_data, updated_at = NOW()
                """
            },
            {
                "source": "md_projects",
                "target": "master_project",
                "mapping": """
                    INSERT INTO esb_data.master_project
                    (esb_id, company_id, name, code, flag_active, raw_data)
                    SELECT esb_id, company_id, name, code, flag_active, raw_data
                    FROM public.md_projects
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        name = EXCLUDED.name, code = EXCLUDED.code, flag_active = EXCLUDED.flag_active,
                        raw_data = EXCLUDED.raw_data, updated_at = NOW()
                """
            },
            {
                "source": "md_users",
                "target": "master_user",
                "mapping": """
                    INSERT INTO esb_data.master_user
                    (esb_id, company_id, username, full_name, role_id, role_desc, flag_active, raw_data)
                    SELECT esb_id, company_id, username, full_name, role_id, role_desc, flag_active, raw_data
                    FROM public.md_users
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        username = EXCLUDED.username, full_name = EXCLUDED.full_name, role_id = EXCLUDED.role_id,
                        role_desc = EXCLUDED.role_desc, flag_active = EXCLUDED.flag_active, raw_data = EXCLUDED.raw_data, updated_at = NOW()
                """
            },
            {
                "source": "md_customer_categories",
                "target": "master_customer_category",
                "mapping": """
                    INSERT INTO esb_data.master_customer_category
                    (esb_id, company_id, name, flag_active, raw_data)
                    SELECT esb_id, company_id, name, flag_active, raw_data
                    FROM public.md_customer_categories
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        name = EXCLUDED.name, flag_active = EXCLUDED.flag_active, raw_data = EXCLUDED.raw_data, updated_at = NOW()
                """
            },
            {
                "source": "md_supplier_categories",
                "target": "master_supplier_category",
                "mapping": """
                    INSERT INTO esb_data.master_supplier_category
                    (esb_id, company_id, name, flag_active, raw_data)
                    SELECT esb_id, company_id, name, flag_active, raw_data
                    FROM public.md_supplier_categories
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        name = EXCLUDED.name, flag_active = EXCLUDED.flag_active, raw_data = EXCLUDED.raw_data, updated_at = NOW()
                """
            },
            {
                "source": "md_customer_pricelists",
                "target": "master_customer_pricelist",
                "mapping": """
                    INSERT INTO esb_data.master_customer_pricelist
                    (esb_id, company_id, customer_name, product_name, product_code, uom_name, currency_name,
                     price, price_date, expire_date, flag_active, raw_data)
                    SELECT esb_id, company_id, customer_name, product_name, product_code, uom_name, currency_name,
                           price, price_date, expire_date, flag_active, raw_data
                    FROM public.md_customer_pricelists
                    ON CONFLICT (company_id, esb_id) DO UPDATE SET
                        customer_name = EXCLUDED.customer_name, product_name = EXCLUDED.product_name,
                        product_code = EXCLUDED.product_code, uom_name = EXCLUDED.uom_name,
                        currency_name = EXCLUDED.currency_name, price = EXCLUDED.price, price_date = EXCLUDED.price_date,
                        expire_date = EXCLUDED.expire_date, flag_active = EXCLUDED.flag_active, raw_data = EXCLUDED.raw_data, updated_at = NOW()
                """
            }
        ]
        
        success_count = 0
        for migration in migrations:
            try:
                print(f"Migrating {migration['source']} -> {migration['target']}...")
                target_cur.execute(migration['mapping'])
                target_conn.commit()
                print(f"Success: {migration['source']} -> {migration['target']}")
                success_count += 1
            except Exception as e:
                print(f"Failed {migration['source']} -> {migration['target']}: {str(e)}")
                target_conn.rollback()
        
        print(f"\nMaster data migration completed: {success_count}/{len(migrations)} tables migrated successfully")
        return success_count == len(migrations)
        
    finally:
        target_conn.close()

def migrate_report_data():
    """Migrate report data from trx_raw_staging to esb_data.report_* tables."""
    print("Starting report data migration...")
    
    target_conn = get_target_connection()
    target_cur = target_conn.cursor()
    
    try:
        # Migrate GOODS_RECEIPT to report_goods_receipt_recapitulation
        print("Migrating GOODS_RECEIPT data...")
        target_cur.execute("""
            INSERT INTO esb_data.report_goods_receipt_recapitulation
            (company_id, report_date, branch_esb_id, receipt_number, receipt_date, branch_name, supplier_name,
             supplier_code, purchase_order_num, warehouse_name, total_amount, total_tax, total_discount,
             net_amount, status, status_name, item_count, payment_terms, notes, created_by, approved_by, 
             approved_date, raw_data, synced_at, updated_at)
            SELECT 
                company_id,
                (payload->>'goodsReceiptDate')::date as report_date,
                (payload->>'branchID') as branch_esb_id,
                payload->>'goodsReceiptNum' as receipt_number,
                (payload->>'goodsReceiptDate')::date as receipt_date,
                payload->>'branchName' as branch_name,
                payload->>'supplierName' as supplier_name,
                payload->>'supplierCode' as supplier_code,
                payload->>'purchaseOrderNum' as purchase_order_num,
                payload->>'warehouseName' as warehouse_name,
                COALESCE((payload->>'totalAmount')::numeric, 0) as total_amount,
                COALESCE((payload->>'totalTax')::numeric, 0) as total_tax,
                COALESCE((payload->>'totalDiscount')::numeric, 0) as total_discount,
                COALESCE((payload->>'netAmount')::numeric, 0) as net_amount,
                payload->>'status' as status,
                payload->>'statusName' as status_name,
                COALESCE(jsonb_array_length(payload->'goodsReceiptDetails'), 0) as item_count,
                payload->>'paymentTerms' as payment_terms,
                payload->>'notes' as notes,
                payload->>'createdBy' as created_by,
                payload->>'approvedBy' as approved_by,
                (payload->>'approvedDate')::date as approved_date,
                payload as raw_data,
                synced_at,
                NOW()
            FROM public.trx_raw_staging
            WHERE entity_type = 'GOODS_RECEIPT'
            ON CONFLICT (company_id, report_date, branch_esb_id, receipt_number) DO UPDATE SET
                receipt_date = EXCLUDED.receipt_date, branch_name = EXCLUDED.branch_name, supplier_name = EXCLUDED.supplier_name,
                total_amount = EXCLUDED.total_amount, total_tax = EXCLUDED.total_tax, total_discount = EXCLUDED.total_discount,
                net_amount = EXCLUDED.net_amount, status = EXCLUDED.status, status_name = EXCLUDED.status_name,
                item_count = EXCLUDED.item_count, raw_data = EXCLUDED.raw_data, updated_at = NOW()
        """)
        gr_count = target_cur.rowcount
        target_conn.commit()
        print(f"Migrated {gr_count} goods receipt records")
        
        # Migrate PRODUCT_SALES to report_sales_recapitulation_detail
        print("Migrating PRODUCT_SALES data...")
        target_cur.execute("""
            INSERT INTO esb_data.report_sales_recapitulation_detail
            (company_id, report_date, branch_esb_id, transaction_number, transaction_date, branch_name, customer_name,
             customer_code, customer_category, salesperson_name, payment_method, payment_method_type, subtotal,
             total_tax, total_discount, total_amount, paid_amount, balance_amount, item_count, status, status_name,
             order_type, delivery_type, notes, created_by, approved_by, approved_date, raw_data, synced_at, updated_at)
            SELECT 
                company_id,
                (payload->>'productSalesDate')::date as report_date,
                (payload->>'branchID')::text as branch_esb_id,
                payload->>'productSalesNum' as transaction_number,
                (payload->>'productSalesDate')::date as transaction_date,
                payload->>'branchName' as branch_name,
                payload->>'customerName' as customer_name,
                (payload->>'customerID')::text as customer_code,
                NULL as customer_category,
                payload->>'salesRepName' as salesperson_name,
                NULL as payment_method,
                NULL as payment_method_type,
                0 as subtotal,
                0 as total_tax,
                0 as total_discount,
                COALESCE((payload->>'productSalesTotal')::numeric, 0) as total_amount,
                0 as paid_amount,
                0 as balance_amount,
                COALESCE(jsonb_array_length(payload->'productSalesDetails'), 0) as item_count,
                (payload->>'statusID')::text as status,
                payload->'printData'->>'statusName' as status_name,
                payload->>'productSalesTypeName' as order_type,
                NULL as delivery_type,
                payload->>'additionalInfo' as notes,
                payload->>'createdBy' as created_by,
                payload->>'authorizedBy' as approved_by,
                (payload->>'authorizedDate')::date as approved_date,
                payload as raw_data,
                synced_at,
                NOW()
            FROM public.trx_raw_staging
            WHERE entity_type = 'PRODUCT_SALES'
            ON CONFLICT (company_id, report_date, branch_esb_id, transaction_number) DO UPDATE SET
                transaction_date = EXCLUDED.transaction_date, branch_name = EXCLUDED.branch_name, customer_name = EXCLUDED.customer_name,
                subtotal = EXCLUDED.subtotal, total_tax = EXCLUDED.total_tax, total_discount = EXCLUDED.total_discount,
                total_amount = EXCLUDED.total_amount, paid_amount = EXCLUDED.paid_amount, balance_amount = EXCLUDED.balance_amount,
                item_count = EXCLUDED.item_count, status = EXCLUDED.status, status_name = EXCLUDED.status_name,
                raw_data = EXCLUDED.raw_data, updated_at = NOW()
        """)
        sales_count = target_cur.rowcount
        target_conn.commit()
        print(f"Migrated {sales_count} sales records")
        
        print(f"Report data migration completed: {gr_count + sales_count} records migrated")
        return True
        
    except Exception as e:
        print(f"Failed report data migration: {str(e)}")
        target_conn.rollback()
        return False
    finally:
        target_conn.close()

def validate_migration():
    """Validate that data migration was successful."""
    print("Validating migration...")
    
    target_conn = get_target_connection()
    target_cur = target_conn.cursor()
    
    try:
        # Compare row counts between source and target
        validation_queries = [
            ("Branch", "SELECT COUNT(*) FROM public.md_outlets", "SELECT COUNT(*) FROM esb_data.master_branch"),
            ("Product", "SELECT COUNT(*) FROM public.md_products", "SELECT COUNT(*) FROM esb_data.master_product"),
            ("Category", "SELECT COUNT(*) FROM public.md_categories", "SELECT COUNT(*) FROM esb_data.master_category"),
            ("Customer", "SELECT COUNT(*) FROM public.md_customers", "SELECT COUNT(*) FROM esb_data.master_customer"),
            ("Supplier", "SELECT COUNT(*) FROM public.md_suppliers", "SELECT COUNT(*) FROM esb_data.master_supplier"),
            ("Goods Receipt", "SELECT COUNT(*) FROM public.trx_raw_staging WHERE entity_type = 'GOODS_RECEIPT'", 
             "SELECT COUNT(*) FROM esb_data.report_goods_receipt_recapitulation"),
            ("Sales", "SELECT COUNT(*) FROM public.trx_raw_staging WHERE entity_type = 'PRODUCT_SALES'",
             "SELECT COUNT(*) FROM esb_data.report_sales_recapitulation_detail")
        ]
        
        all_valid = True
        for name, source_query, target_query in validation_queries:
            target_cur.execute(source_query)
            source_count = target_cur.fetchone()['count']
            
            target_cur.execute(target_query)
            target_count = target_cur.fetchone()['count']
            
            if source_count == target_count:
                print(f"Valid: {name} - {source_count} records")
            else:
                print(f"Mismatch: {name} - Source: {source_count}, Target: {target_count}")
                all_valid = False
        
        return all_valid
        
    finally:
        target_conn.close()

def main():
    """Main migration execution."""
    print("Starting Data Migration from be-kopicalf-inhouse to backend-kopicalf-inhouse")
    print("=" * 80)
    
    # Migrate master data
    master_success = migrate_master_data()
    
    # Migrate report data  
    report_success = migrate_report_data()
    
    # Validate migration
    print("\n" + "=" * 80)
    print("Running validation...")
    validation_success = validate_migration()
    
    # Summary
    print("\n" + "=" * 80)
    print("Migration Summary:")
    print(f"  Master data: {'Success' if master_success else 'Failed'}")
    print(f"  Report data: {'Success' if report_success else 'Failed'}")
    print(f"  Validation: {'Success' if validation_success else 'Failed'}")
    
    if master_success and report_success and validation_success:
        print("\nMigration completed successfully!")
    else:
        print("\nMigration completed with some issues. Please check the errors above.")

if __name__ == "__main__":
    main()