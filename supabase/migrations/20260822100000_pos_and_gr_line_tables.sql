-- Line-level POS sales tables (OMS gateway) + GR line-level restructure
-- Based on ERP sample exports (Sales Recapitulation Detail, Goods Receipt Recapitulation)

-- 1) POS Sales Head (OMS /external/general/sales-head)
CREATE TABLE IF NOT EXISTS esb_data.report_pos_sales_head (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    sales_num TEXT NOT NULL,
    parent_link_sales_num TEXT,
    bill_num TEXT,
    sales_date DATE NOT NULL,
    sales_date_in TIMESTAMPTZ,
    sales_date_out TIMESTAMPTZ,
    branch_code TEXT,
    branch_name TEXT,
    member_code TEXT,
    member_name TEXT,
    table_name TEXT,
    visit_purpose_name TEXT,
    pax_total INTEGER,
    subtotal NUMERIC(15,2) DEFAULT 0,
    discount_total NUMERIC(15,2) DEFAULT 0,
    menu_discount_total NUMERIC(15,2) DEFAULT 0,
    promotion_discount NUMERIC(15,2) DEFAULT 0,
    other_tax_total NUMERIC(15,2) DEFAULT 0,
    vat_total NUMERIC(15,2) DEFAULT 0,
    grand_total NUMERIC(15,2) DEFAULT 0,
    voucher_total NUMERIC(15,2) DEFAULT 0,
    rounding_total NUMERIC(15,2) DEFAULT 0,
    payment_total NUMERIC(15,2) DEFAULT 0,
    status_id INTEGER,
    status_name TEXT,
    created_by TEXT,
    payments JSONB DEFAULT '[]',
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, sales_num)
);

CREATE INDEX IF NOT EXISTS idx_pos_head_company_date ON esb_data.report_pos_sales_head(company_id, sales_date);
CREATE INDEX IF NOT EXISTS idx_pos_head_branch ON esb_data.report_pos_sales_head(branch_code);

-- 2) POS Sales Menu lines (OMS /external/general/sales-menu)
CREATE TABLE IF NOT EXISTS esb_data.report_pos_sales (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    sales_num TEXT NOT NULL,
    bill_num TEXT,
    sales_date DATE NOT NULL,
    branch_code TEXT,
    branch_name TEXT,
    batch_id INTEGER,
    menu_code TEXT,
    menu_name TEXT,
    menu_category_name TEXT,
    menu_category_detail_name TEXT,
    qty NUMERIC(15,2) DEFAULT 0,
    price NUMERIC(15,2) DEFAULT 0,
    original_price NUMERIC(15,2) DEFAULT 0,
    discount NUMERIC(15,2) DEFAULT 0,
    discount_value NUMERIC(15,2) DEFAULT 0,
    subtotal NUMERIC(15,2) DEFAULT 0,
    other_tax NUMERIC(15,2) DEFAULT 0,
    service_charge NUMERIC(15,2) DEFAULT 0,
    tax NUMERIC(15,2) DEFAULT 0,
    vat NUMERIC(15,2) DEFAULT 0,
    total NUMERIC(15,2) DEFAULT 0,
    notes TEXT,
    cancel_notes TEXT,
    status_id INTEGER,
    status_name TEXT,
    created_by TEXT,
    created_date TIMESTAMPTZ,
    extras JSONB DEFAULT '[]',
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    id_esb BIGINT,
    UNIQUE(company_id, sales_num, menu_code, menu_category_detail_name, id_esb)
);

CREATE INDEX IF NOT EXISTS idx_pos_sales_company_date ON esb_data.report_pos_sales(company_id, sales_date);
CREATE INDEX IF NOT EXISTS idx_pos_sales_branch ON esb_data.report_pos_sales(branch_code);
CREATE INDEX IF NOT EXISTS idx_pos_sales_menu ON esb_data.report_pos_sales(menu_code);

-- 3) Goods Receipt Recapitulation: restructure to LINE-level (matches ERP export)
DROP TABLE IF EXISTS esb_data.report_goods_receipt_recapitulation;
CREATE TABLE esb_data.report_goods_receipt_recapitulation (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    report_date DATE NOT NULL,
    branch_name TEXT,
    receipt_number TEXT NOT NULL,
    receipt_date DATE,
    reference_number TEXT,
    transaction_type TEXT,
    origin_name TEXT,
    origin_location TEXT,
    destination_name TEXT,
    destination_location TEXT,
    cost_center_name TEXT,
    project_name TEXT,
    category_name TEXT,
    sub_category_name TEXT,
    product_name TEXT,
    product_code TEXT,
    uom_name TEXT,
    qty NUMERIC(15,2) DEFAULT 0,
    converted_qty NUMERIC(15,2) DEFAULT 0,
    returned_qty NUMERIC(15,2) DEFAULT 0,
    expired_date DATE,
    status_name TEXT,
    additional_info TEXT,
    raw_data JSONB DEFAULT '{}',
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, report_date, receipt_number, product_code, sub_category_name)
);

CREATE INDEX IF NOT EXISTS idx_report_gr_company_date ON esb_data.report_goods_receipt_recapitulation(company_id, report_date);
CREATE INDEX IF NOT EXISTS idx_report_gr_product ON esb_data.report_goods_receipt_recapitulation(product_code);

DROP TRIGGER IF EXISTS update_report_goods_receipt_recapitulation_updated_at ON esb_data.report_goods_receipt_recapitulation;
CREATE TRIGGER update_report_goods_receipt_recapitulation_updated_at BEFORE UPDATE ON esb_data.report_goods_receipt_recapitulation
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();
DROP TRIGGER IF EXISTS update_report_pos_sales_head_updated_at ON esb_data.report_pos_sales_head;
CREATE TRIGGER update_report_pos_sales_head_updated_at BEFORE UPDATE ON esb_data.report_pos_sales_head
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();
DROP TRIGGER IF EXISTS update_report_pos_sales_updated_at ON esb_data.report_pos_sales;
CREATE TRIGGER update_report_pos_sales_updated_at BEFORE UPDATE ON esb_data.report_pos_sales
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA esb_data TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA esb_data TO postgres;
