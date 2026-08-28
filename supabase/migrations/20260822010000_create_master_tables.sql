-- Master Data Tables in esb_data schema
-- All tables follow consistent structure: company_id, esb_id, normalized_name, raw_data, synced_at, updated_at

-- ============================================
-- 1. master_branch (from md_outlets)
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.master_branch (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    name TEXT,
    branch_code TEXT,
    is_active BOOLEAN DEFAULT true,
    location_name TEXT,
    stock INTEGER DEFAULT 0,
    available_stock INTEGER DEFAULT 0,
    normalized_name TEXT,  -- Alias from master_normalization
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_branch_company ON esb_data.master_branch(company_id);
CREATE INDEX IF NOT EXISTS idx_master_branch_esb_id ON esb_data.master_branch(esb_id);
CREATE INDEX IF NOT EXISTS idx_master_branch_normalized ON esb_data.master_branch(normalized_name) WHERE normalized_name IS NOT NULL;

-- ============================================
-- 2. master_product (from md_products)
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.master_product (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    name TEXT,
    product_code TEXT,
    bom_name TEXT,
    category_name TEXT,
    sub_category_name TEXT,
    category_type_name TEXT,
    flag_active BOOLEAN DEFAULT true,
    normalized_name TEXT,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_product_company ON esb_data.master_product(company_id);
CREATE INDEX IF NOT EXISTS idx_master_product_esb_id ON esb_data.master_product(esb_id);
CREATE INDEX IF NOT EXISTS idx_master_product_code ON esb_data.master_product(product_code) WHERE product_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_master_product_normalized ON esb_data.master_product(normalized_name) WHERE normalized_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_master_product_category ON esb_data.master_product(category_name) WHERE category_name IS NOT NULL;

-- ============================================
-- 3. master_category (from md_categories)
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.master_category (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    code TEXT,
    name TEXT,
    type_name TEXT,
    flag_active BOOLEAN DEFAULT true,
    category_type_id INTEGER,
    notes TEXT,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_category_company ON esb_data.master_category(company_id);
CREATE INDEX IF NOT EXISTS idx_master_category_esb_id ON esb_data.master_category(esb_id);
CREATE INDEX IF NOT EXISTS idx_master_category_code ON esb_data.master_category(code) WHERE code IS NOT NULL;

-- ============================================
-- 4. master_sub_category (from md_sub_categories)
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.master_sub_category (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    category_esb_id TEXT,
    code TEXT,
    name TEXT,
    flag_active BOOLEAN DEFAULT true,
    dead_stock_threshold INTEGER,
    notes TEXT,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_sub_category_company ON esb_data.master_sub_category(company_id);
CREATE INDEX IF NOT EXISTS idx_master_sub_category_esb_id ON esb_data.master_sub_category(esb_id);
CREATE INDEX IF NOT EXISTS idx_master_sub_category_category ON esb_data.master_sub_category(category_esb_id) WHERE category_esb_id IS NOT NULL;

-- ============================================
-- 5. master_unit (from md_units)
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.master_unit (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    code TEXT,
    name TEXT,
    flag_active BOOLEAN DEFAULT true,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_unit_company ON esb_data.master_unit(company_id);
CREATE INDEX IF NOT EXISTS idx_master_unit_esb_id ON esb_data.master_unit(esb_id);
CREATE INDEX IF NOT EXISTS idx_master_unit_code ON esb_data.master_unit(code) WHERE code IS NOT NULL;

-- ============================================
-- 6. master_pricelist (from md_pricelists)
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.master_pricelist (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    product_esb_id TEXT,
    branch_esb_id TEXT,
    price NUMERIC(15,2) DEFAULT 0,
    flag_active BOOLEAN DEFAULT true,
    price_date DATE,
    supplier_name TEXT,
    product_name TEXT,
    product_code TEXT,
    unit_name TEXT,
    currency TEXT,
    expired_date DATE,
    pricelist_num TEXT,
    product_detail_esb_id TEXT,
    uom_id TEXT,
    currency_id TEXT,
    applicable_branch JSONB DEFAULT '{}',
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_pricelist_company ON esb_data.master_pricelist(company_id);
CREATE INDEX IF NOT EXISTS idx_master_pricelist_esb_id ON esb_data.master_pricelist(esb_id);
CREATE INDEX IF NOT EXISTS idx_master_pricelist_product ON esb_data.master_pricelist(product_esb_id) WHERE product_esb_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_master_pricelist_branch ON esb_data.master_pricelist(branch_esb_id) WHERE branch_esb_id IS NOT NULL;

-- ============================================
-- 7. master_bill_of_material (from md_boms)
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.master_bill_of_material (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    product_esb_id TEXT,
    code TEXT,
    name TEXT,
    output_qty NUMERIC(10,2) DEFAULT 1.0,
    flag_active BOOLEAN DEFAULT true,
    bom_type_id INTEGER,
    bom_type_name TEXT,
    product_name TEXT,
    uom_name TEXT,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_bom_company ON esb_data.master_bill_of_material(company_id);
CREATE INDEX IF NOT EXISTS idx_master_bom_esb_id ON esb_data.master_bill_of_material(esb_id);
CREATE INDEX IF NOT EXISTS idx_master_bom_product ON esb_data.master_bill_of_material(product_esb_id) WHERE product_esb_id IS NOT NULL;

-- ============================================
-- 8. master_cost_center (from md_cost_centers)
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.master_cost_center (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    code TEXT,
    name TEXT,
    flag_active BOOLEAN DEFAULT true,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_cost_center_company ON esb_data.master_cost_center(company_id);
CREATE INDEX IF NOT EXISTS idx_master_cost_center_esb_id ON esb_data.master_cost_center(esb_id);

-- ============================================
-- 9. master_purpose (from md_purposes)
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.master_purpose (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    name TEXT,
    account TEXT,
    coa_no TEXT,
    applied_to JSONB DEFAULT '[]',
    flag_active BOOLEAN DEFAULT true,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_purpose_company ON esb_data.master_purpose(company_id);
CREATE INDEX IF NOT EXISTS idx_master_purpose_esb_id ON esb_data.master_purpose(esb_id);

-- ============================================
-- 10. master_customer (from md_customers)
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.master_customer (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    name TEXT,
    code TEXT,
    category_esb_id TEXT,
    category_name TEXT,
    payment_due_days INTEGER DEFAULT 0,
    address TEXT,
    pic_name TEXT,
    pic_phone TEXT,
    flag_active BOOLEAN DEFAULT true,
    lock_vat BOOLEAN DEFAULT false,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_customer_company ON esb_data.master_customer(company_id);
CREATE INDEX IF NOT EXISTS idx_master_customer_esb_id ON esb_data.master_customer(esb_id);
CREATE INDEX IF NOT EXISTS idx_master_customer_code ON esb_data.master_customer(code) WHERE code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_master_customer_category ON esb_data.master_customer(category_esb_id) WHERE category_esb_id IS NOT NULL;

-- ============================================
-- 11. master_supplier (from md_suppliers)
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.master_supplier (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    name TEXT,
    type TEXT,
    supplier_category TEXT,
    status TEXT,
    address TEXT,
    contact_person TEXT,
    cell_phone TEXT,
    due_date INTEGER,
    category_esb_id TEXT,
    lock_vat BOOLEAN DEFAULT false,
    vat_subject BOOLEAN DEFAULT false,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_supplier_company ON esb_data.master_supplier(company_id);
CREATE INDEX IF NOT EXISTS idx_master_supplier_esb_id ON esb_data.master_supplier(esb_id);
CREATE INDEX IF NOT EXISTS idx_master_supplier_category ON esb_data.master_supplier(category_esb_id) WHERE category_esb_id IS NOT NULL;

-- ============================================
-- 12. master_supplier_category (from md_supplier_categories)
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.master_supplier_category (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    name TEXT,
    flag_active BOOLEAN DEFAULT true,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_supplier_category_company ON esb_data.master_supplier_category(company_id);
CREATE INDEX IF NOT EXISTS idx_master_supplier_category_esb_id ON esb_data.master_supplier_category(esb_id);

-- ============================================
-- 13. master_customer_category (from md_customer_categories)
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.master_customer_category (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    name TEXT,
    flag_active BOOLEAN DEFAULT true,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_customer_category_company ON esb_data.master_customer_category(company_id);
CREATE INDEX IF NOT EXISTS idx_master_customer_category_esb_id ON esb_data.master_customer_category(esb_id);

-- ============================================
-- 14. master_charts_of_account (from md_coas)
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.master_charts_of_account (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    coa_no TEXT,
    coa_level INTEGER,
    description TEXT,
    currency TEXT,
    branch_esb_id TEXT,
    flag_active BOOLEAN DEFAULT false,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_coa_company ON esb_data.master_charts_of_account(company_id);
CREATE INDEX IF NOT EXISTS idx_master_coa_esb_id ON esb_data.master_charts_of_account(esb_id);
CREATE INDEX IF NOT EXISTS idx_master_coa_no ON esb_data.master_charts_of_account(coa_no) WHERE coa_no IS NOT NULL;

-- ============================================
-- 15. master_user (from md_users)
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.master_user (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    username TEXT,
    full_name TEXT,
    role_id TEXT,
    role_desc TEXT,
    flag_active BOOLEAN DEFAULT true,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_user_company ON esb_data.master_user(company_id);
CREATE INDEX IF NOT EXISTS idx_master_user_esb_id ON esb_data.master_user(esb_id);
CREATE INDEX IF NOT EXISTS idx_master_user_username ON esb_data.master_user(username) WHERE username IS NOT NULL;

-- ============================================
-- 16. master_project (from md_projects)
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.master_project (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    name TEXT,
    code TEXT,
    flag_active BOOLEAN DEFAULT true,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_project_company ON esb_data.master_project(company_id);
CREATE INDEX IF NOT EXISTS idx_master_project_esb_id ON esb_data.master_project(esb_id);

-- ============================================
-- 17. master_customer_pricelist (from md_customer_pricelists)
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.master_customer_pricelist (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    customer_name TEXT,
    product_name TEXT,
    product_code TEXT,
    uom_name TEXT,
    currency_name TEXT,
    price NUMERIC(15,2) DEFAULT 0,
    price_date DATE,
    expire_date DATE,
    flag_active BOOLEAN DEFAULT true,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_customer_pricelist_company ON esb_data.master_customer_pricelist(company_id);
CREATE INDEX IF NOT EXISTS idx_master_customer_pricelist_esb_id ON esb_data.master_customer_pricelist(esb_id);

-- ============================================
-- 18. master_document_template (from md_document_templates)
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.master_document_template (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    name TEXT,
    document_type TEXT,
    template_code TEXT,
    flag_active BOOLEAN DEFAULT true,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_document_template_company ON esb_data.master_document_template(company_id);
CREATE INDEX IF NOT EXISTS idx_master_document_template_esb_id ON esb_data.master_document_template(esb_id);

-- ============================================
-- 19. master_product_detail (from md_product_details)
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.master_product_detail (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    product_esb_id TEXT,
    uom_id TEXT,
    metric_id TEXT,
    uom_name TEXT,
    qty NUMERIC(10,2),
    base_price NUMERIC(15,2),
    sku TEXT,
    is_base BOOLEAN DEFAULT false,
    is_stock BOOLEAN DEFAULT false,
    is_purchase BOOLEAN DEFAULT false,
    is_transfer BOOLEAN DEFAULT false,
    is_sales BOOLEAN DEFAULT false,
    flag_active BOOLEAN DEFAULT true,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_product_detail_company ON esb_data.master_product_detail(company_id);
CREATE INDEX IF NOT EXISTS idx_master_product_detail_esb_id ON esb_data.master_product_detail(esb_id);
CREATE INDEX IF NOT EXISTS idx_master_product_detail_product ON esb_data.master_product_detail(product_esb_id) WHERE product_esb_id IS NOT NULL;

-- ============================================
-- 20. master_tax (from ACC_TAX)
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.master_tax (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    name TEXT,
    rate NUMERIC(5,2),
    code TEXT,
    flag_active BOOLEAN DEFAULT true,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_tax_company ON esb_data.master_tax(company_id);
CREATE INDEX IF NOT EXISTS idx_master_tax_esb_id ON esb_data.master_tax(esb_id);

-- ============================================
-- Additional master tables for undocumented entities
-- ============================================

-- 21. master_cashflow_category (from ACC_CASHFLOW_CAT)
CREATE TABLE IF NOT EXISTS esb_data.master_cashflow_category (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    name TEXT,
    code TEXT,
    flag_active BOOLEAN DEFAULT true,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_cashflow_company ON esb_data.master_cashflow_category(company_id);
CREATE INDEX IF NOT EXISTS idx_master_cashflow_esb_id ON esb_data.master_cashflow_category(esb_id);

-- 22. master_approval_flow (from ACC_APPROVAL_FLOW)
CREATE TABLE IF NOT EXISTS esb_data.master_approval_flow (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    esb_id TEXT NOT NULL,
    name TEXT,
    description TEXT,
    flag_active BOOLEAN DEFAULT true,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, esb_id)
);

CREATE INDEX IF NOT EXISTS idx_master_approval_flow_company ON esb_data.master_approval_flow(company_id);
CREATE INDEX IF NOT EXISTS idx_master_approval_flow_esb_id ON esb_data.master_approval_flow(esb_id);

-- ============================================
-- Add updated_at triggers for all master tables
-- ============================================

-- Trigger function already exists in esb_data schema from previous migration
-- Apply triggers to all master tables (fixed syntax)
DROP TRIGGER IF EXISTS update_master_branch_updated_at ON esb_data.master_branch;
CREATE TRIGGER update_master_branch_updated_at BEFORE UPDATE ON esb_data.master_branch
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_master_product_updated_at ON esb_data.master_product;
CREATE TRIGGER update_master_product_updated_at BEFORE UPDATE ON esb_data.master_product
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_master_category_updated_at ON esb_data.master_category;
CREATE TRIGGER update_master_category_updated_at BEFORE UPDATE ON esb_data.master_category
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_master_sub_category_updated_at ON esb_data.master_sub_category;
CREATE TRIGGER update_master_sub_category_updated_at BEFORE UPDATE ON esb_data.master_sub_category
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_master_unit_updated_at ON esb_data.master_unit;
CREATE TRIGGER update_master_unit_updated_at BEFORE UPDATE ON esb_data.master_unit
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_master_pricelist_updated_at ON esb_data.master_pricelist;
CREATE TRIGGER update_master_pricelist_updated_at BEFORE UPDATE ON esb_data.master_pricelist
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_master_supplier_updated_at ON esb_data.master_supplier;
CREATE TRIGGER update_master_supplier_updated_at BEFORE UPDATE ON esb_data.master_supplier
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_master_customer_updated_at ON esb_data.master_customer;
CREATE TRIGGER update_master_customer_updated_at BEFORE UPDATE ON esb_data.master_customer
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_master_bill_of_material_updated_at ON esb_data.master_bill_of_material;
CREATE TRIGGER update_master_bill_of_material_updated_at BEFORE UPDATE ON esb_data.master_bill_of_material
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_master_document_template_updated_at ON esb_data.master_document_template;
CREATE TRIGGER update_master_document_template_updated_at BEFORE UPDATE ON esb_data.master_document_template
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_master_purpose_updated_at ON esb_data.master_purpose;
CREATE TRIGGER update_master_purpose_updated_at BEFORE UPDATE ON esb_data.master_purpose
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_master_cost_center_updated_at ON esb_data.master_cost_center;
CREATE TRIGGER update_master_cost_center_updated_at BEFORE UPDATE ON esb_data.master_cost_center
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_master_charts_of_account_updated_at ON esb_data.master_charts_of_account;
CREATE TRIGGER update_master_charts_of_account_updated_at BEFORE UPDATE ON esb_data.master_charts_of_account
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_master_project_updated_at ON esb_data.master_project;
CREATE TRIGGER update_master_project_updated_at BEFORE UPDATE ON esb_data.master_project
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_master_user_updated_at ON esb_data.master_user;
CREATE TRIGGER update_master_user_updated_at BEFORE UPDATE ON esb_data.master_user
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_master_customer_category_updated_at ON esb_data.master_customer_category;
CREATE TRIGGER update_master_customer_category_updated_at BEFORE UPDATE ON esb_data.master_customer_category
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_master_supplier_category_updated_at ON esb_data.master_supplier_category;
CREATE TRIGGER update_master_supplier_category_updated_at BEFORE UPDATE ON esb_data.master_supplier_category
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_master_customer_pricelist_updated_at ON esb_data.master_customer_pricelist;
CREATE TRIGGER update_master_customer_pricelist_updated_at BEFORE UPDATE ON esb_data.master_customer_pricelist
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_master_tax_updated_at ON esb_data.master_tax;
CREATE TRIGGER update_master_tax_updated_at BEFORE UPDATE ON esb_data.master_tax
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_master_cashflow_category_updated_at ON esb_data.master_cashflow_category;
CREATE TRIGGER update_master_cashflow_category_updated_at BEFORE UPDATE ON esb_data.master_cashflow_category
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_master_approval_flow_updated_at ON esb_data.master_approval_flow;
CREATE TRIGGER update_master_approval_flow_updated_at BEFORE UPDATE ON esb_data.master_approval_flow
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA esb_data TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA esb_data TO postgres;

-- Add comments for documentation
COMMENT ON TABLE esb_data.master_branch IS 'Branch/outlet master data from ESB /branch endpoint';
COMMENT ON TABLE esb_data.master_product IS 'Product master data from ESB /product endpoint';
COMMENT ON TABLE esb_data.master_category IS 'Product category master data from ESB /product/category endpoint';
COMMENT ON TABLE esb_data.master_sub_category IS 'Product sub-category master data from ESB /product/sub-category endpoint';
COMMENT ON TABLE esb_data.master_unit IS 'Unit of measurement master data from ESB /units endpoint';
COMMENT ON TABLE esb_data.master_pricelist IS 'Pricing master data from ESB /pricelist endpoint';
COMMENT ON TABLE esb_data.master_bill_of_material IS 'BOM master data from ESB /product/bom endpoint';
COMMENT ON TABLE esb_data.master_cost_center IS 'Cost center master data from ESB /cost-center endpoint';
COMMENT ON TABLE esb_data.master_purpose IS 'Accounting purpose master data from ESB /purpose endpoint';
COMMENT ON TABLE esb_data.master_customer IS 'Customer master data from ESB /customer endpoint';
COMMENT ON TABLE esb_data.master_supplier IS 'Supplier master data from ESB /supplier endpoint';
COMMENT ON TABLE esb_data.master_supplier_category IS 'Supplier category master data from ESB /supplier/category endpoint';
COMMENT ON TABLE esb_data.master_customer_category IS 'Customer category master data from ESB /customer/category endpoint';
COMMENT ON TABLE esb_data.master_charts_of_account IS 'Chart of accounts master data from ESB /accounting/coa endpoint (undocumented)';
COMMENT ON TABLE esb_data.master_user IS 'User master data from ESB /user endpoint (undocumented)';
COMMENT ON TABLE esb_data.master_project IS 'Project master data from ESB /project endpoint (undocumented)';
COMMENT ON TABLE esb_data.master_customer_pricelist IS 'Customer-specific pricing from ESB /customer-pricelist endpoint';
COMMENT ON TABLE esb_data.master_document_template IS 'Document template master data from ESB /document-template endpoint';
COMMENT ON TABLE esb_data.master_product_detail IS 'Product detail variants from ESB /product/{id} endpoint';
COMMENT ON TABLE esb_data.master_tax IS 'Tax configuration from ESB /tax endpoint (undocumented)';
COMMENT ON TABLE esb_data.master_cashflow_category IS 'Cash flow category from ESB /cash-flow-category endpoint (undocumented)';
COMMENT ON TABLE esb_data.master_approval_flow IS 'Approval flow configuration from ESB /approval-flow endpoint (undocumented)';
