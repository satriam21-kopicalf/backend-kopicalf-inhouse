-- SCC manual-input & stock-system support for company CALF
-- 1) stock opname: period type (daily_packaging/weekly/monthly) + detail extras
ALTER TABLE esb_data.stock_opname_header
    ADD COLUMN IF NOT EXISTS period_type VARCHAR(20) DEFAULT 'monthly';

ALTER TABLE esb_data.stock_opname_detail
    ADD COLUMN IF NOT EXISTS movements JSONB,
    ADD COLUMN IF NOT EXISTS photos JSONB;

-- 2) waste details: photo evidence
ALTER TABLE esb_data.waste_detail
    ADD COLUMN IF NOT EXISTS photos JSONB;

-- 3) manual stock adjustments (Stock System editable matrix overrides)
CREATE TABLE IF NOT EXISTS esb_data.stock_system_adjustment (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL DEFAULT 1,
    branch_id INTEGER NOT NULL REFERENCES esb_data.master_branch(id),
    product_id INTEGER NOT NULL REFERENCES esb_data.master_product(id),
    adjust_date DATE NOT NULL,
    qty NUMERIC(12,3) NOT NULL DEFAULT 0,
    note TEXT,
    created_by VARCHAR(100) DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (company_id, branch_id, product_id, adjust_date)
);

CREATE INDEX IF NOT EXISTS idx_ssa_branch_product
    ON esb_data.stock_system_adjustment (branch_id, product_id, adjust_date DESC);
