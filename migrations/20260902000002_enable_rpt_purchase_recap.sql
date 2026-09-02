-- Migration: Enable RPT_PURCHASE_RECAPITULATION endpoint and add unique constraint
-- Created: 2026-09-02
-- Purpose: Activate the Purchase Recapitulation report for sync

-- 1. Activate the endpoint in endpoint_registry
UPDATE esb.endpoint_registry
SET is_active = true
WHERE entity = 'RPT_PURCHASE_RECAPITULATION';

-- 2. Add unique constraint on report_purchase_recapitulation
--    (one row per company/date/purchase_order_num)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_report_purchase_recap_company_date_po'
    ) THEN
        ALTER TABLE esb_data.report_purchase_recapitulation
            ADD CONSTRAINT uq_report_purchase_recap_company_date_po
            UNIQUE (company_id, report_date, purchase_order_num);
    END IF;
END
$$;
