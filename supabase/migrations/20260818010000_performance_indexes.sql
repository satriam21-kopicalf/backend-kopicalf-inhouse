-- Performance optimization indexes
-- Added: 2026-08-18

-- Index for esb_raw_staging lookups (used by fetchLiveEsbData)
CREATE INDEX IF NOT EXISTS idx_esb_raw_staging_lookup
ON public.esb_raw_staging(company_id, entity_type);

-- Index for sync_watermarks (used by trx_status)
CREATE INDEX IF NOT EXISTS idx_sync_watermarks_company
ON public.sync_watermarks(company_id, entity_type, lane);

-- Index for sync_history lookups (used by master_summary)
CREATE INDEX IF NOT EXISTS idx_sync_history_entity
ON public.sync_history(entity_type, completed_at DESC);

-- Index for md_sync_schedules lookups
CREATE INDEX IF NOT EXISTS idx_md_sync_schedules_entity
ON public.md_sync_schedules(entity_type);

-- Composite index for report_raw_staging with branch filter
CREATE INDEX IF NOT EXISTS idx_report_raw_staging_branch
ON public.report_raw_staging(company_id, report_type, period_start, branch_esb_id);

-- Index for export_files status tracking
CREATE INDEX IF NOT EXISTS idx_export_files_status
ON public.export_files(status, created_at);

-- Index for trx_raw_staging with branchID filter (JSON payload)
-- Note: This is a workaround since we filter on payload->>'branchID'
-- For better performance, consider adding a separate branch_esb_id column
CREATE INDEX IF NOT EXISTS idx_trx_staging_branch
ON public.trx_raw_staging(company_id, entity_type, doc_date)
WHERE payload->>'branchID' IS NOT NULL;
