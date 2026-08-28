-- Create esb_data schema for isolated ESB data management
CREATE SCHEMA IF NOT EXISTS esb_data;

-- Set search_path to prioritize esb_data for ESB operations
-- This allows queries to find tables in esb_data first, then fall back to public
SET search_path TO esb_data, public;

-- ============================================
-- System Tables in esb_data schema
-- ============================================

-- 1. company_configs: Store 8 Kopi Calf companies with ESB credentials
-- Migrated from public.company_configs with added static_token support
CREATE TABLE IF NOT EXISTS esb_data.company_configs (
    id SERIAL PRIMARY KEY,
    esb_company_code TEXT NOT NULL UNIQUE,
    company_name TEXT NOT NULL,
    esb_username TEXT,
    esb_password TEXT,
    static_token TEXT,  -- Optional: pre-generated token to speed up auth
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for active companies lookup
CREATE INDEX IF NOT EXISTS idx_company_configs_active ON esb_data.company_configs(esb_company_code) WHERE is_active = true;

-- 2. endpoint_registry: Dynamic endpoint configuration
-- Replaces hardcoded MASTER_ENDPOINTS and OPTIONAL_ENDPOINTS in tasks.py
CREATE TABLE IF NOT EXISTS esb_data.endpoint_registry (
    id SERIAL PRIMARY KEY,
    entity TEXT NOT NULL UNIQUE,  -- BRANCH, PRODUCT, CATEGORY, etc.
    path TEXT NOT NULL,  -- API path like /branch, /product
    id_field TEXT NOT NULL,  -- Field used for unique ID (branchID, productID, etc.)
    response_shape TEXT NOT NULL,  -- 'array' or 'envelope'
    is_active BOOLEAN DEFAULT true,
    is_documented BOOLEAN DEFAULT false,  -- TRUE if in official ESB docs
    category TEXT NOT NULL,  -- 'master' or 'report'
    module TEXT,  -- Product, POS, Accounting, etc.
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for endpoint lookups
CREATE INDEX IF NOT EXISTS idx_endpoint_registry_active ON esb_data.endpoint_registry(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_endpoint_registry_category ON esb_data.endpoint_registry(category);
CREATE INDEX IF NOT EXISTS idx_endpoint_registry_documented ON esb_data.endpoint_registry(is_documented) WHERE is_documented = true;

-- 3. sync_schedules: Per-company, per-endpoint scheduling
-- Replaces md_sync_schedules with more granular control
CREATE TABLE IF NOT EXISTS esb_data.sync_schedules (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES esb_data.company_configs(id) ON DELETE CASCADE,
    endpoint_id INTEGER REFERENCES esb_data.endpoint_registry(id) ON DELETE CASCADE,
    module TEXT NOT NULL,  -- 'master' or 'report'
    cron_expr TEXT NOT NULL,  -- Cron expression: "0 2 * * *" = 2 AM daily
    enabled BOOLEAN DEFAULT true,
    last_run TIMESTAMPTZ,
    next_run TIMESTAMPTZ,
    date_from DATE,  -- For historical backfill
    date_to DATE,  -- For date range limited syncs
    custom_params JSONB DEFAULT '{}',  -- Additional parameters per schedule
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, endpoint_id)
);

-- Indexes for schedule lookups
CREATE INDEX IF NOT EXISTS idx_sync_schedules_enabled ON esb_data.sync_schedules(enabled, next_run) WHERE enabled = true;
CREATE INDEX IF NOT EXISTS idx_sync_schedules_company ON esb_data.sync_schedules(company_id);
CREATE INDEX IF NOT EXISTS idx_sync_schedules_module ON esb_data.sync_schedules(module);

-- 4. master_normalization: Alias normalization for Company, Branch, Product
-- Handles messy names from ESB source with standardized aliases
CREATE TABLE IF NOT EXISTS esb_data.master_normalization (
    id SERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,  -- 'COMPANY', 'BRANCH', 'PRODUCT'
    esb_id TEXT NOT NULL,  -- Original ID from ESB
    company_id INTEGER REFERENCES esb_data.company_configs(id) ON DELETE CASCADE,
    normalized_name TEXT NOT NULL,  -- Clean, standardized name
    original_name TEXT,  -- Store original for reference
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_type, esb_id, company_id)
);

-- Indexes for normalization lookups
CREATE INDEX IF NOT EXISTS idx_master_normalization_entity ON esb_data.master_normalization(entity_type, esb_id);
CREATE INDEX IF NOT EXISTS idx_master_normalization_company ON esb_data.master_normalization(company_id);
CREATE INDEX IF NOT EXISTS idx_master_normalization_active ON esb_data.master_normalization(is_active) WHERE is_active = true;

-- Grant permissions for application user
GRANT USAGE ON SCHEMA esb_data TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA esb_data TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA esb_data TO postgres;

-- Add updated_at trigger function if not exists
CREATE OR REPLACE FUNCTION esb_data.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers to all tables with updated_at
DROP TRIGGER IF EXISTS update_company_configs_updated_at ON esb_data.company_configs;
CREATE TRIGGER update_company_configs_updated_at BEFORE UPDATE ON esb_data.company_configs
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_endpoint_registry_updated_at ON esb_data.endpoint_registry;
CREATE TRIGGER update_endpoint_registry_updated_at BEFORE UPDATE ON esb_data.endpoint_registry
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_sync_schedules_updated_at ON esb_data.sync_schedules;
CREATE TRIGGER update_sync_schedules_updated_at BEFORE UPDATE ON esb_data.sync_schedules
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

DROP TRIGGER IF EXISTS update_master_normalization_updated_at ON esb_data.master_normalization;
CREATE TRIGGER update_master_normalization_updated_at BEFORE UPDATE ON esb_data.master_normalization
    FOR EACH ROW EXECUTE FUNCTION esb_data.update_updated_at_column();

-- Comment for documentation
COMMENT ON SCHEMA esb_data IS 'Isolated schema for ESB data management - master data, reports, and system configuration';
COMMENT ON TABLE esb_data.company_configs IS 'Configuration for 8 Kopi Calf companies with ESB API credentials';
COMMENT ON TABLE esb_data.endpoint_registry IS 'Dynamic endpoint registry replacing hardcoded configuration';
COMMENT ON TABLE esb_data.sync_schedules IS 'Per-company, per-endpoint scheduling with cron expressions';
COMMENT ON TABLE esb_data.master_normalization IS 'Alias normalization for Company, Branch, Product entities';
