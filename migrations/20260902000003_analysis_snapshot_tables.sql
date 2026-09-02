-- Migration: Create analysis snapshot tables for COGS ratio and usage ratio
-- Created: 2026-09-02
-- Purpose: Pre-compute expensive COGS/usage calculations for fast dashboard queries
-- Refresh: Daily after delta sync completes (Celery queue: queue_report)

-- ─────────────────────────────────────────────────────────────────────────
-- analysis_cogs_snapshot: Branch-level COGS metrics per period
-- Replaces ad-hoc query in cogs_ratio.py with a materialized snapshot
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS esb_data.analysis_cogs_snapshot (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    branch_id INTEGER,
    branch_esb_id TEXT,
    branch_code TEXT,
    branch_name TEXT,
    branch_type TEXT,
    period DATE NOT NULL,           -- first day of month (YYYY-MM-01)
    period_label TEXT NOT NULL,    -- 'YYYY-MM' display label
    revenue NUMERIC(15, 2) DEFAULT 0,
    cogs NUMERIC(15, 2) DEFAULT 0,
    cogs_ratio NUMERIC(6, 2) DEFAULT 0,   -- cogs / revenue * 100
    target_cogs_ratio NUMERIC(6, 2) DEFAULT 65.0,
    gap NUMERIC(6, 2) DEFAULT 0,          -- cogs_ratio - target
    teoretis_usage NUMERIC(15, 2) DEFAULT 0,
    actual_usage NUMERIC(15, 2) DEFAULT 0,
    usage_ratio NUMERIC(6, 2) DEFAULT 0,  -- actual / teoretis * 100
    flagged BOOLEAN DEFAULT FALSE,
    trend TEXT DEFAULT 'flat',             -- 'up' | 'flat' | 'down'
    last_updated TIMESTAMPTZ,
    refreshed_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_cogs_snapshot_company_branch_period
        UNIQUE (company_id, branch_id, period)
);
COMMENT ON TABLE esb_data.analysis_cogs_snapshot IS
    'Pre-computed COGS ratio metrics per branch per month. Refresh daily via refresh_cogs_snapshot().';

CREATE INDEX IF NOT EXISTS idx_cogs_snapshot_company_period
    ON esb_data.analysis_cogs_snapshot(company_id, period);
CREATE INDEX IF NOT EXISTS idx_cogs_snapshot_branch
    ON esb_data.analysis_cogs_snapshot(branch_id);
CREATE INDEX IF NOT EXISTS idx_cogs_snapshot_flagged
    ON esb_data.analysis_cogs_snapshot(company_id, flagged) WHERE flagged = TRUE;

-- Trigger to auto-update refreshed_at
CREATE OR REPLACE FUNCTION esb_data._touch_cogs_snapshot()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.refreshed_at = NOW(); RETURN NEW; END;
$$;

DROP TRIGGER IF EXISTS touch_cogs_snapshot ON esb_data.analysis_cogs_snapshot;
CREATE TRIGGER touch_cogs_snapshot
    BEFORE UPDATE ON esb_data.analysis_cogs_snapshot
    FOR EACH ROW EXECUTE FUNCTION esb_data._touch_cogs_snapshot();


-- ─────────────────────────────────────────────────────────────────────────
-- analysis_usage_ratio: Branch-level material usage ratio per period
-- Tracks how actual material consumption compares to BOM-theoretical amounts
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS esb_data.analysis_usage_ratio (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    branch_id INTEGER,
    branch_esb_id TEXT,
    branch_code TEXT,
    branch_name TEXT,
    branch_type TEXT,
    period DATE NOT NULL,
    period_label TEXT NOT NULL,
    product_id INTEGER,
    product_esb_id TEXT,
    product_code TEXT,
    product_name TEXT,
    category_name TEXT,
    teoretis_qty NUMERIC(15, 4) DEFAULT 0,
    actual_qty NUMERIC(15, 4) DEFAULT 0,
    teoretis_cost NUMERIC(15, 2) DEFAULT 0,
    actual_cost NUMERIC(15, 2) DEFAULT 0,
    usage_ratio NUMERIC(6, 2) DEFAULT 0,   -- actual_qty / teoretis_qty * 100
    efficiency_pct NUMERIC(6, 2) DEFAULT 0,  -- (1 - abs deviation) * 100
    flagged BOOLEAN DEFAULT FALSE,         -- TRUE when usage_ratio > 110 or < 90
    last_updated TIMESTAMPTZ,
    refreshed_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_usage_ratio_company_branch_product_period
        UNIQUE (company_id, branch_id, product_id, period)
);
COMMENT ON TABLE esb_data.analysis_usage_ratio IS
    'Pre-computed material usage ratio per product per branch per month. Refresh daily via refresh_usage_ratio().';

CREATE INDEX IF NOT EXISTS idx_usage_ratio_company_period
    ON esb_data.analysis_usage_ratio(company_id, period);
CREATE INDEX IF NOT EXISTS idx_usage_ratio_branch
    ON esb_data.analysis_usage_ratio(branch_id);
CREATE INDEX IF NOT EXISTS idx_usage_ratio_flagged
    ON esb_data.analysis_usage_ratio(company_id, flagged) WHERE flagged = TRUE;

-- Trigger to auto-update refreshed_at
CREATE OR REPLACE FUNCTION esb_data._touch_usage_ratio()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.refreshed_at = NOW(); RETURN NEW; END;
$$;

DROP TRIGGER IF EXISTS touch_usage_ratio ON esb_data.analysis_usage_ratio;
CREATE TRIGGER touch_usage_ratio
    BEFORE UPDATE ON esb_data.analysis_usage_ratio
    FOR EACH ROW EXECUTE FUNCTION esb_data._touch_usage_ratio();
