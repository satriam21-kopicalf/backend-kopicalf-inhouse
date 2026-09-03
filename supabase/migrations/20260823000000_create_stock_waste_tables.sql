-- Stock Opname and Waste Management Tables
-- Supports COGS analysis for outlet, hub-wh, and hub-ck branches

-- =============================================
-- STOCK OPNAME TABLES
-- =============================================

CREATE TABLE IF NOT EXISTS esb_data.stock_opname_header (
    id SERIAL PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES esb_data.master_branch(id),
    opname_date DATE NOT NULL,
    period_month VARCHAR(7) NOT NULL, -- YYYY-MM format
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    total_variance_value DECIMAL(15,2) DEFAULT 0,
    item_count INTEGER DEFAULT 0,
    approved_by VARCHAR(100),
    approved_at TIMESTAMP WITH TIME ZONE,
    notes TEXT,
    created_by VARCHAR(100) NOT NULL DEFAULT 'system',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS esb_data.stock_opname_detail (
    id SERIAL PRIMARY KEY,
    header_id INTEGER NOT NULL REFERENCES esb_data.stock_opname_header(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES esb_data.master_product(id),
    system_qty DECIMAL(12,3) NOT NULL DEFAULT 0,
    counted_qty DECIMAL(12,3) NOT NULL DEFAULT 0,
    unit_cost DECIMAL(15,4) NOT NULL DEFAULT 0,
    variance_qty DECIMAL(12,3) NOT NULL DEFAULT 0,
    variance_value DECIMAL(15,4) NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for stock opname
CREATE INDEX IF NOT EXISTS idx_stock_opname_header_branch ON esb_data.stock_opname_header(branch_id);
CREATE INDEX IF NOT EXISTS idx_stock_opname_header_status ON esb_data.stock_opname_header(status);
CREATE INDEX IF NOT EXISTS idx_stock_opname_header_period ON esb_data.stock_opname_header(period_month);
CREATE INDEX IF NOT EXISTS idx_stock_opname_header_created ON esb_data.stock_opname_header(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_stock_opname_detail_header ON esb_data.stock_opname_detail(header_id);
CREATE INDEX IF NOT EXISTS idx_stock_opname_detail_product ON esb_data.stock_opname_detail(product_id);

-- =============================================
-- WASTE TABLES
-- =============================================

CREATE TABLE IF NOT EXISTS esb_data.waste_header (
    id SERIAL PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES esb_data.master_branch(id),
    waste_date DATE NOT NULL,
    period_month VARCHAR(7) NOT NULL, -- YYYY-MM format
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    total_value DECIMAL(15,2) DEFAULT 0,
    item_count INTEGER DEFAULT 0,
    approved_by VARCHAR(100),
    approved_at TIMESTAMP WITH TIME ZONE,
    notes TEXT,
    created_by VARCHAR(100) NOT NULL DEFAULT 'system',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS esb_data.waste_detail (
    id SERIAL PRIMARY KEY,
    header_id INTEGER NOT NULL REFERENCES esb_data.waste_header(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES esb_data.master_product(id),
    qty DECIMAL(12,3) NOT NULL DEFAULT 0,
    unit_cost DECIMAL(15,4) NOT NULL DEFAULT 0,
    total_value DECIMAL(15,4) NOT NULL DEFAULT 0,
    reason VARCHAR(50) NOT NULL, -- expired, damaged, quality, other
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for waste
CREATE INDEX IF NOT EXISTS idx_waste_header_branch ON esb_data.waste_header(branch_id);
CREATE INDEX IF NOT EXISTS idx_waste_header_status ON esb_data.waste_header(status);
CREATE INDEX IF NOT EXISTS idx_waste_header_period ON esb_data.waste_header(period_month);
CREATE INDEX IF NOT EXISTS idx_waste_header_created ON esb_data.waste_header(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_waste_detail_header ON esb_data.waste_detail(header_id);
CREATE INDEX IF NOT EXISTS idx_waste_detail_product ON esb_data.waste_detail(product_id);
CREATE INDEX IF NOT EXISTS idx_waste_detail_reason ON esb_data.waste_detail(reason);

COMMENT ON TABLE esb_data.stock_opname_header IS 'Stock opname header records with approval workflow (draft -> submitted -> approved/rejected)';
COMMENT ON TABLE esb_data.stock_opname_detail IS 'Stock opname line items - each product counted at a branch';
COMMENT ON TABLE esb_data.waste_header IS 'Waste record header with approval workflow';
COMMENT ON TABLE esb_data.waste_detail IS 'Waste line items with reason categorization';
