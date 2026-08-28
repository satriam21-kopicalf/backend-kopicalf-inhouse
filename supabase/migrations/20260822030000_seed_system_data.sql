-- Seed Data for ESB Data System Tables
-- Populate endpoint_registry and initial sync_schedules from existing hardcoded configuration

-- ============================================
-- Seed Company Configs (8 Kopi Calf Companies)
-- ============================================
INSERT INTO esb_data.company_configs (esb_company_code, company_name, esb_username, esb_password, is_active) VALUES
    ('CALF', 'PT Yuda Prawira Group', 'CALFSUPERADMINOPS', 'admin123', true),
    ('CALF2', 'Calf Central Kitchen', 'CALFSUPERADMINOPS', 'admin123', true),
    ('CALF3', 'PT DAYUPRA SOLUSI PARTNER', 'CALFSUPERADMINOPS', 'admin123', true),
    ('CALF4', 'Coffee Solution Indo', 'CALFSUPERADMINOPS', 'admin123', true),
    ('CALF5', 'Calf COTR', 'CALFSUPERADMINOPS', 'admin123', true),
    ('CALF6', 'Calf Central Kitchen Food', 'CALFSUPERADMINOPS', 'admin123', true),
    ('CALF7', 'Wasgee Tea', 'CALFSUPERADMINOPS', 'admin123', true),
    ('CALF1', 'Calf Roastery', 'CALFSUPERADMINCK', 'calf123!', true)
ON CONFLICT (esb_company_code) DO NOTHING;

-- ============================================
-- Seed Endpoint Registry from MASTER_ENDPOINTS + OPTIONAL_ENDPOINTS
-- ============================================
INSERT INTO esb_data.endpoint_registry (entity, path, id_field, response_shape, is_active, is_documented, category, module, description) VALUES
    -- Documented Master Endpoints
    ('BRANCH', '/branch', 'branchID', 'array', true, true, 'master', 'Company', 'Branch/outlet master data'),
    ('PRODUCT', '/product', 'productID', 'envelope', true, true, 'master', 'Product', 'Product master data'),
    ('CATEGORY', '/product/category', 'categoryID', 'envelope', true, true, 'master', 'Product', 'Product category master data'),
    ('PRODUCT_SUB_CATEGORY', '/product/sub-category', 'subCategoryID', 'envelope', true, true, 'master', 'Product', 'Product sub-category master data'),
    ('PRODUCT_UNIT', '/units', 'uomID', 'envelope', true, true, 'master', 'Product', 'Unit of measurement master data'),
    ('PRICELIST', '/pricelist', 'ID', 'envelope', true, true, 'master', 'Product', 'Pricing master data'),
    ('SUPPLIER', '/supplier', 'supplierID', 'envelope', true, true, 'master', 'Partner', 'Supplier master data'),
    ('CUSTOMER', '/customer', 'customerID', 'envelope', true, true, 'master', 'Partner', 'Customer master data'),
    ('BOM', '/product/bom', 'bomID', 'envelope', true, true, 'master', 'Product', 'Bill of materials master data'),
    ('DOCUMENT_TEMPLATE', '/document-template', 'requestTemplateID', 'envelope', true, true, 'master', 'Company', 'Document template master data'),
    ('ACC_PURPOSE', '/purpose', 'purposeID', 'envelope', true, true, 'master', 'Accounting', 'Accounting purpose master data'),
    ('ACC_COST_CENTER', '/cost-center', 'ID', 'array', true, true, 'master', 'Accounting', 'Cost center master data'),
    
    -- Undocumented Master Endpoints (but still pulling)
    ('ACC_COA', '/accounting/coa', 'coaNo', 'array', true, false, 'master', 'Accounting', 'Chart of accounts master data (undocumented)'),
    ('COMP_PROJECT', '/project', 'ID', 'array', true, false, 'master', 'Company', 'Project master data (undocumented)'),
    ('COMP_USER', '/user', 'username', 'envelope', true, false, 'master', 'Company', 'User master data (undocumented)'),
    ('PARTNER_CUST_CAT', '/customer/category', 'customerCategoryID', 'array', true, false, 'master', 'Partner', 'Customer category master data (undocumented)'),
    ('PARTNER_SUPP_CAT', '/supplier/category', 'supplierCategoryID', 'array', true, false, 'master', 'Partner', 'Supplier category master data (undocumented)'),
    ('CUSTOMER_PRICELIST', '/customer-pricelist', 'ID', 'envelope', true, false, 'master', 'Partner', 'Customer-specific pricing (documented)'),
    
    -- Optional Endpoints (low priority, but keep pulling)
    ('ACC_TAX', '/tax', 'taxID', 'envelope', true, false, 'master', 'Accounting', 'Tax configuration (undocumented)'),
    ('ACC_CASHFLOW_CAT', '/cash-flow-category', 'ID', 'envelope', true, false, 'master', 'Accounting', 'Cash flow category (undocumented)'),
    ('ACC_APPROVAL_FLOW', '/approval-flow', 'ID', 'envelope', true, false, 'master', 'Accounting', 'Approval flow configuration (undocumented)'),
    
    -- Report Endpoints (Priority)
    ('RPT_STOCK_MOVEMENT', '/report/stock-movement', 'ID', 'envelope', true, true, 'report', 'Inventory', 'Stock movement report (documented)'),
    ('RPT_SALES_PAYMENT_SUMMARY', '/report/sales-payment-summary', 'ID', 'envelope', true, false, 'report', 'Sales', 'Sales payment summary (undocumented)'),
    ('RPT_GOODS_RECEIPT_RECAPITULATION', '/report/goods-receipt-recapitulation', 'ID', 'envelope', true, false, 'report', 'Inventory', 'Goods receipt recapitulation (undocumented)'),
    
    -- Additional Report Endpoints (Future)
    ('RPT_DAILY_SALES_PAYMENT', '/report/daily-sales-payment-recapitulation', 'ID', 'envelope', false, false, 'report', 'Sales', 'Daily sales payment recapitulation (undocumented)'),
    ('RPT_STOCK_OPNAME', '/report/stock-opname', 'ID', 'envelope', false, false, 'report', 'Inventory', 'Stock opname report (undocumented)'),
    ('RPT_TRANSFER', '/report/transfer', 'ID', 'envelope', false, false, 'report', 'Inventory', 'Transfer report (undocumented)'),
    ('RPT_PURCHASE_RECAPITULATION', '/report/purchase-recapitulation', 'ID', 'envelope', false, false, 'report', 'Purchasing', 'Purchase order recapitulation (undocumented)'),
    ('RPT_MENU_COGS', '/report/menu-cogs', 'ID', 'envelope', false, false, 'report', 'Sales', 'Menu COGS report (undocumented)'),
    ('RPT_BOM', '/report/bill-of-material', 'ID', 'envelope', false, false, 'report', 'Inventory', 'Bill of material report (undocumented)')
ON CONFLICT (entity) DO NOTHING;

-- ============================================
-- Seed Sync Schedules (Initial Default Schedules)
-- ============================================

-- Get company IDs and endpoint IDs for schedule creation
DO $$
DECLARE
    company_record RECORD;
    endpoint_record RECORD;
    schedule_count INTEGER := 0;
BEGIN
    -- Create default schedules for all active companies and documented master endpoints
    FOR company_record IN 
        SELECT id, esb_company_code FROM esb_data.company_configs WHERE is_active = true
    LOOP
        -- Master data schedules: every 30 minutes for all documented endpoints
        FOR endpoint_record IN 
            SELECT id, entity FROM esb_data.endpoint_registry 
            WHERE is_active = true AND is_documented = true AND category = 'master'
        LOOP
            INSERT INTO esb_data.sync_schedules (company_id, endpoint_id, module, cron_expr, enabled, date_from, date_to)
            VALUES (
                company_record.id,
                endpoint_record.id,
                'master',
                '*/30 * * * *',  -- Every 30 minutes
                true,
                '2024-01-01',    -- Historical data
                CURRENT_DATE     -- Up to current date
            )
            ON CONFLICT (company_id, endpoint_id) DO NOTHING;
            
            schedule_count := schedule_count + 1;
        END LOOP;
        
        -- Priority Report 1: Goods Receipt Recapitulation - 2 AM daily
        INSERT INTO esb_data.sync_schedules (company_id, endpoint_id, module, cron_expr, enabled, date_from, date_to)
        SELECT 
            company_record.id,
            id,
            'report',
            '0 2 * * *',  -- 2 AM daily
            true,
            '2024-01-01',
            CURRENT_DATE
        FROM esb_data.endpoint_registry 
        WHERE entity = 'RPT_GOODS_RECEIPT_RECAPITULATION'
        ON CONFLICT (company_id, endpoint_id) DO NOTHING;
        
        schedule_count := schedule_count + 1;
        
        -- Priority Report 2: Sales Payment Summary - 2:30 AM daily
        INSERT INTO esb_data.sync_schedules (company_id, endpoint_id, module, cron_expr, enabled, date_from, date_to)
        SELECT 
            company_record.id,
            id,
            'report',
            '30 2 * * *',  -- 2:30 AM daily
            true,
            '2024-01-01',
            CURRENT_DATE
        FROM esb_data.endpoint_registry 
        WHERE entity = 'RPT_SALES_PAYMENT_SUMMARY'
        ON CONFLICT (company_id, endpoint_id) DO NOTHING;
        
        schedule_count := schedule_count + 1;
        
        -- Stock Movement Report - 3 AM daily (documented endpoint)
        INSERT INTO esb_data.sync_schedules (company_id, endpoint_id, module, cron_expr, enabled, date_from, date_to)
        SELECT 
            company_record.id,
            id,
            'report',
            '0 3 * * *',  -- 3 AM daily
            true,
            '2024-01-01',
            CURRENT_DATE
        FROM esb_data.endpoint_registry 
        WHERE entity = 'RPT_STOCK_MOVEMENT'
        ON CONFLICT (company_id, endpoint_id) DO NOTHING;
        
        schedule_count := schedule_count + 1;
    END LOOP;
    
    RAISE NOTICE 'Created % default sync schedules', schedule_count;
END $$;

-- ============================================
-- Seed Master Normalization (Optional Examples)
-- ============================================
INSERT INTO esb_data.master_normalization (entity_type, esb_id, company_id, normalized_name, original_name, is_active) VALUES
    -- Example branch normalizations (adjust based on actual data)
    ('BRANCH', '1', 1, 'Cabang Utama', 'Main Store', true),
    ('BRANCH', '2', 1, 'Cabang Jakarta', 'Jakarta Store', true),
    ('BRANCH', '3', 1, 'Cabang Bandung', 'Bandung Outlet', true),
    
    -- Example product normalizations
    ('PRODUCT', 'PROD001', 1, 'Kopi Arabika Premium', 'Arabica Coffee Premium', true),
    ('PRODUCT', 'PROD002', 1, 'Kopi Robusta Standard', 'Robusta Coffee Standard', true),
    
    -- Example company normalizations (though companies are already clean)
    ('COMPANY', '1', 1, 'PT Yuda Prawira Group', 'PT Yuda Prawira Group', true)
ON CONFLICT (entity_type, esb_id, company_id) DO NOTHING;

-- ============================================
-- Verification Queries
-- ============================================

-- Check companies seeded
SELECT 'Companies seeded:' as info, COUNT(*) as count FROM esb_data.company_configs WHERE is_active = true;

-- Check endpoints seeded
SELECT 'Endpoints seeded:' as info, COUNT(*) as count FROM esb_data.endpoint_registry WHERE is_active = true;

-- Check schedules created
SELECT 'Sync schedules created:' as info, COUNT(*) as count FROM esb_data.sync_schedules WHERE enabled = true;

-- Check normalization examples
SELECT 'Normalization examples:' as info, COUNT(*) as count FROM esb_data.master_normalization WHERE is_active = true;

-- Show schedule distribution by company
SELECT 
    cc.esb_company_code,
    COUNT(ss.id) as schedule_count,
    COUNT(CASE WHEN ss.module = 'master' THEN 1 END) as master_schedules,
    COUNT(CASE WHEN ss.module = 'report' THEN 1 END) as report_schedules
FROM esb_data.company_configs cc
LEFT JOIN esb_data.sync_schedules ss ON cc.id = ss.company_id AND ss.enabled = true
WHERE cc.is_active = true
GROUP BY cc.id, cc.esb_company_code
ORDER BY cc.esb_company_code;
