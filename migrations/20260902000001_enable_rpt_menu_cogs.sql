-- Migration: Enable RPT_MENU_COGS endpoint and add unique constraint
-- Created: 2026-09-02
-- Purpose: Activate the Menu COGS report endpoint for sync

-- 1. Activate the endpoint in endpoint_registry
UPDATE esb_data.endpoint_registry
SET is_active = true
WHERE entity = 'RPT_MENU_COGS';

-- 2. Add unique constraint on report_menu_cogs so upserts work correctly
--    (one row per company/date/branch/menu)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_report_menu_cogs_company_date_branch_menu'
    ) THEN
        ALTER TABLE esb_data.report_menu_cogs
            ADD CONSTRAINT uq_report_menu_cogs_company_date_branch_menu
            UNIQUE (company_id, report_date, branch_esb_id, menu_code);
    END IF;
END
$$;
