-- Report Data Tables in esb_data schema
-- Focus on priority reports: Goods Receipt Recapitulation & Sales Recapitulation Detail
-- Other report tables created but will be populated in future phases

-- ============================================
-- PRIORITY REPORT 1: Goods Receipt Recapitulation
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.report_goods_receipt_recapitulation (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    report_date DATE NOT NULL,
    branch_esb_id TEXT,
    receipt_number TEXT,
    receipt_date DATE,
    branch_name TEXT,
    supplier_name TEXT,
    supplier_code TEXT,
    purchase_order_num TEXT,
    warehouse_name TEXT,
    total_amount NUMERIC(15,2) DEFAULT 0,
    total_tax NUMERIC(15,2) DEFAULT 0,
    total_discount NUMERIC(15,2) DEFAULT 0,
    net_amount NUMERIC(15,2) DEFAULT 0,
    status TEXT,
    status_name TEXT,
    item_count INTEGER DEFAULT 0,
    payment_terms TEXT,
    notes TEXT,
    created_by TEXT,
    approved_by TEXT,
    approved_date DATE,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, report_date, branch_esb_id, receipt_number)
);

-- Indexes for Goods Receipt Recapitulation
CREATE INDEX IF NOT EXISTS idx_report_goods_receipt_company_date ON esb_data.report_goods_receipt_recapitulation(company_id, report_date);
CREATE INDEX IF NOT EXISTS idx_report_goods_receipt_branch ON esb_data.report_goods_receipt_recapitulation(branch_esb_id) WHERE branch_esb_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_report_goods_receipt_supplier ON esb_data.report_goods_receipt_recapitulation(supplier_name) WHERE supplier_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_report_goods_receipt_status ON esb_data.report_goods_receipt_recapitulation(status) WHERE status IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_report_goods_receipt_number ON esb_data.report_goods_receipt_recapitulation(receipt_number) WHERE receipt_number IS NOT NULL;

-- ============================================
-- PRIORITY REPORT 2: Sales Recapitulation Detail
-- ============================================
CREATE TABLE IF NOT EXISTS esb_data.report_sales_recapitulation_detail (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    report_date DATE NOT NULL,
    branch_esb_id TEXT,
    transaction_number TEXT,
    transaction_date DATE,
    branch_name TEXT,
    customer_name TEXT,
    customer_code TEXT,
    customer_category TEXT,
    salesperson_name TEXT,
    payment_method TEXT,
    payment_method_type TEXT,
    subtotal NUMERIC(15,2) DEFAULT 0,
    total_tax NUMERIC(15,2) DEFAULT 0,
    total_discount NUMERIC(15,2) DEFAULT 0,
    total_amount NUMERIC(15,2) DEFAULT 0,
    paid_amount NUMERIC(15,2) DEFAULT 0,
    balance_amount NUMERIC(15,2) DEFAULT 0,
    item_count INTEGER DEFAULT 0,
    status TEXT,
    status_name TEXT,
    order_type TEXT,
    delivery_type TEXT,
    notes TEXT,
    created_by TEXT,
    approved_by TEXT,
    approved_date DATE,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, report_date, branch_esb_id, transaction_number)
);

-- Indexes for Sales Recapitulation Detail
CREATE INDEX IF NOT EXISTS idx_report_sales_detail_company_date ON esb_data.report_sales_recapitulation_detail(company_id, report_date);
CREATE INDEX IF NOT EXISTS idx_report_sales_detail_branch ON esb_data.report_sales_recapitulation_detail(branch_esb_id) WHERE branch_esb_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_report_sales_detail_customer ON esb_data.report_sales_recapitulation_detail(customer_name) WHERE customer_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_report_sales_detail_payment ON esb_data.report_sales_recapitulation_detail(payment_method) WHERE payment_method IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_report_sales_detail_status ON esb_data.report_sales_recapitulation_detail(status) WHERE status IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_report_sales_detail_number ON esb_data.report_sales_recapitulation_detail(transaction_number) WHERE transaction_number IS NOT NULL;

-- ============================================
-- ADDITIONAL REPORT TABLES (Future Implementation)
-- ============================================

-- Stock Movement Report (Documented in ESB)
CREATE TABLE IF NOT EXISTS esb_data.report_stock_movement (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    report_date DATE NOT NULL,
    branch_esb_id TEXT,
    product_code TEXT,
    product_name TEXT,
    branch_name TEXT,
    location TEXT,
    uom_name TEXT,
    transaction_type TEXT,
    reference_number TEXT,
    document_code TEXT,
    document_date DATE,
    value_per_unit NUMERIC(15,2) DEFAULT 0,
    qty_in NUMERIC(15,2) DEFAULT 0,
    amount_in NUMERIC(15,2) DEFAULT 0,
    qty_out NUMERIC(15,2) DEFAULT 0,
    amount_out NUMERIC(15,2) DEFAULT 0,
    qty_balance NUMERIC(15,2) DEFAULT 0,
    amount_balance NUMERIC(15,2) DEFAULT 0,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_report_stock_movement_company_date ON esb_data.report_stock_movement(company_id, report_date);
CREATE INDEX IF NOT EXISTS idx_report_stock_movement_product ON esb_data.report_stock_movement(product_code) WHERE product_code IS NOT NULL;

-- Sales Payment Summary Report
CREATE TABLE IF NOT EXISTS esb_data.report_sales_payment_summary (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    report_date DATE NOT NULL,
    branch_esb_id TEXT,
    branch_name TEXT,
    payment_method_type TEXT,
    payment_method_name TEXT,
    transaction_type TEXT,
    payment_count INTEGER DEFAULT 0,
    payment_amount NUMERIC(15,2) DEFAULT 0,
    mdr NUMERIC(15,2) DEFAULT 0,
    net_after_mdr NUMERIC(15,2) DEFAULT 0,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_report_sales_payment_company_date ON esb_data.report_sales_payment_summary(company_id, report_date);
CREATE INDEX IF NOT EXISTS idx_report_sales_payment_branch ON esb_data.report_sales_payment_summary(branch_esb_id) WHERE branch_esb_id IS NOT NULL;

-- Daily Sales Payment Recapitulation Report
CREATE TABLE IF NOT EXISTS esb_data.report_daily_sales_payment_recapitulation (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    report_date DATE NOT NULL,
    branch_esb_id TEXT,
    branch_name TEXT,
    payment_method_type TEXT,
    payment_method_name TEXT,
    transaction_type TEXT,
    payment_count INTEGER DEFAULT 0,
    payment_amount NUMERIC(15,2) DEFAULT 0,
    mdr NUMERIC(15,2) DEFAULT 0,
    net_after_mdr NUMERIC(15,2) DEFAULT 0,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_report_daily_sales_payment_company_date ON esb_data.report_daily_sales_payment_recapitulation(company_id, report_date);

-- Stock Opname Report
CREATE TABLE IF NOT EXISTS esb_data.report_stock_opname (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    report_date DATE NOT NULL,
    branch_esb_id TEXT,
    stock_opname_num TEXT,
    stock_opname_date DATE,
    branch_name TEXT,
    location_name TEXT,
    purpose_name TEXT,
    product_name TEXT,
    product_code TEXT,
    category_name TEXT,
    sub_category_name TEXT,
    uom_name TEXT,
    stock_qty NUMERIC(15,2) DEFAULT 0,
    opname_qty NUMERIC(15,2) DEFAULT 0,
    diff_qty NUMERIC(15,2) DEFAULT 0,
    hpp NUMERIC(15,2) DEFAULT 0,
    diff_value NUMERIC(15,2) DEFAULT 0,
    status_name TEXT,
    additional_info TEXT,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_report_stock_opname_company_date ON esb_data.report_stock_opname(company_id, report_date);

-- Transfer Report
CREATE TABLE IF NOT EXISTS esb_data.report_transfer (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    report_date DATE NOT NULL,
    branch_esb_id TEXT,
    transfer_num TEXT,
    transfer_date DATE,
    branch_name TEXT,
    source_warehouse TEXT,
    destination_warehouse TEXT,
    product_name TEXT,
    product_code TEXT,
    uom_name TEXT,
    qty NUMERIC(15,2) DEFAULT 0,
    hpp NUMERIC(15,2) DEFAULT 0,
    total NUMERIC(15,2) DEFAULT 0,
    status_name TEXT,
    notes TEXT,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_report_transfer_company_date ON esb_data.report_transfer(company_id, report_date);

-- Purchase Recapitulation Report
CREATE TABLE IF NOT EXISTS esb_data.report_purchase_recapitulation (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    report_date DATE NOT NULL,
    branch_esb_id TEXT,
    purchase_order_num TEXT,
    purchase_order_date DATE,
    supplier_name TEXT,
    supplier_code TEXT,
    branch_name TEXT,
    department_name TEXT,
    total_amount NUMERIC(15,2) DEFAULT 0,
    total_tax NUMERIC(15,2) DEFAULT 0,
    total_discount NUMERIC(15,2) DEFAULT 0,
    net_amount NUMERIC(15,2) DEFAULT 0,
    status_name TEXT,
    notes TEXT,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_report_purchase_recap_company_date ON esb_data.report_purchase_recapitulation(company_id, report_date);

-- Menu COGS Report
CREATE TABLE IF NOT EXISTS esb_data.report_menu_cogs (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    report_date DATE NOT NULL,
    branch_esb_id TEXT,
    branch_name TEXT,
    menu_name TEXT,
    menu_code TEXT,
    category_name TEXT,
    sales_qty NUMERIC(15,2) DEFAULT 0,
    sales_amount NUMERIC(15,2) DEFAULT 0,
    material_cost NUMERIC(15,2) DEFAULT 0,
    labor_cost NUMERIC(15,2) DEFAULT 0,
    overhead_cost NUMERIC(15,2) DEFAULT 0,
    total_cogs NUMERIC(15,2) DEFAULT 0,
    cogs_percentage NUMERIC(5,2) DEFAULT 0,
    gross_profit NUMERIC(15,2) DEFAULT 0,
    gross_profit_percentage NUMERIC(5,2) DEFAULT 0,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_report_menu_cogs_company_date ON esb_data.report_menu_cogs(company_id, report_date);

-- Bill of Material Report
CREATE TABLE IF NOT EXISTS esb_data.report_bill_of_material (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    report_date DATE NOT NULL,
    branch_esb_id TEXT,
    bom_num TEXT,
    bom_date DATE,
    branch_name TEXT,
    product_name TEXT,
    product_code TEXT,
    uom_name TEXT,
    material_name TEXT,
    material_code TEXT,
    material_uom TEXT,
    qty NUMERIC(15,2) DEFAULT 0,
    hpp NUMERIC(15,2) DEFAULT 0,
    total NUMERIC(15,2) DEFAULT 0,
    status_name TEXT,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_report_bom_company_date ON esb_data.report_bill_of_material(company_id, report_date);

-- ============================================
-- Add updated_at triggers for all report tables
-- ============================================

DROP TRIGGER IF EXISTS update_report_goods_receipt_recapitulation_updated_at ON esb_data.report_goods_receipt_recapitulation;
CREATE TRIGGER update_report_goods_receipt_recapitulation_updated_at BEFORE UPDATE ON esb_data.report_goods_receipt_recapitulation
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();
DROP TRIGGER IF EXISTS update_report_sales_recapitulation_detail_updated_at ON esb_data.report_sales_recapitulation_detail;
CREATE TRIGGER update_report_sales_recapitulation_detail_updated_at BEFORE UPDATE ON esb_data.report_sales_recapitulation_detail
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();
DROP TRIGGER IF EXISTS update_report_stock_movement_updated_at ON esb_data.report_stock_movement;
CREATE TRIGGER update_report_stock_movement_updated_at BEFORE UPDATE ON esb_data.report_stock_movement
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();
DROP TRIGGER IF EXISTS update_report_sales_payment_summary_updated_at ON esb_data.report_sales_payment_summary;
CREATE TRIGGER update_report_sales_payment_summary_updated_at BEFORE UPDATE ON esb_data.report_sales_payment_summary
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();
DROP TRIGGER IF EXISTS update_report_daily_sales_payment_recapitulation_updated_at ON esb_data.report_daily_sales_payment_recapitulation;
CREATE TRIGGER update_report_daily_sales_payment_recapitulation_updated_at BEFORE UPDATE ON esb_data.report_daily_sales_payment_recapitulation
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();
DROP TRIGGER IF EXISTS update_report_stock_opname_updated_at ON esb_data.report_stock_opname;
CREATE TRIGGER update_report_stock_opname_updated_at BEFORE UPDATE ON esb_data.report_stock_opname
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();
DROP TRIGGER IF EXISTS update_report_transfer_updated_at ON esb_data.report_transfer;
CREATE TRIGGER update_report_transfer_updated_at BEFORE UPDATE ON esb_data.report_transfer
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();
DROP TRIGGER IF EXISTS update_report_purchase_recapitulation_updated_at ON esb_data.report_purchase_recapitulation;
CREATE TRIGGER update_report_purchase_recapitulation_updated_at BEFORE UPDATE ON esb_data.report_purchase_recapitulation
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();
DROP TRIGGER IF EXISTS update_report_menu_cogs_updated_at ON esb_data.report_menu_cogs;
CREATE TRIGGER update_report_menu_cogs_updated_at BEFORE UPDATE ON esb_data.report_menu_cogs
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();
DROP TRIGGER IF EXISTS update_report_bill_of_material_updated_at ON esb_data.report_bill_of_material;
CREATE TRIGGER update_report_bill_of_material_updated_at BEFORE UPDATE ON esb_data.report_bill_of_material
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA esb_data TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA esb_data TO postgres;

-- Add comments for documentation
COMMENT ON TABLE esb_data.report_goods_receipt_recapitulation IS 'Priority Report: Goods receipt summary from ESB /report/goods-receipt-recapitulation (undocumented)';
COMMENT ON TABLE esb_data.report_sales_recapitulation_detail IS 'Priority Report: Sales detail from ESB /sales/product-sales (aggregated)';
COMMENT ON TABLE esb_data.report_stock_movement IS 'Stock movement report from ESB /report/stock-movement (documented)';
COMMENT ON TABLE esb_data.report_sales_payment_summary IS 'Sales payment summary from ESB /report/sales-payment-summary (undocumented)';
COMMENT ON TABLE esb_data.report_daily_sales_payment_recapitulation IS 'Daily sales payment recapitulation (undocumented)';
COMMENT ON TABLE esb_data.report_stock_opname IS 'Stock opname report (undocumented)';
COMMENT ON TABLE esb_data.report_transfer IS 'Inventory transfer report (undocumented)';
COMMENT ON TABLE esb_data.report_purchase_recapitulation IS 'Purchase order recapitulation (undocumented)';
COMMENT ON TABLE esb_data.report_menu_cogs IS 'Menu Cost of Goods Sold report (undocumented)';
COMMENT ON TABLE esb_data.report_bill_of_material IS 'Bill of Material usage report (undocumented)';
