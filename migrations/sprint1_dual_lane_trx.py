r"""Sprint 1 migration: dual-lane TRX engine tables.

Run: venv\Scripts\python.exe migrations\sprint1_dual_lane_trx.py
Idempotent: safe to re-run.
"""
import psycopg2
import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DSN = os.getenv("DB_POOLER_URL") or os.getenv("DB_DIRECT_URL")

MIGRATION = """
-- Doc-based staging for index->view transactional entities (dual-lane upsert target)
CREATE TABLE IF NOT EXISTS trx_raw_staging (
  id BIGSERIAL PRIMARY KEY,
  company_id INT NOT NULL,
  entity_type TEXT NOT NULL,
  doc_num TEXT NOT NULL,
  doc_date DATE,
  status TEXT,
  payload JSONB NOT NULL,
  synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_trx_staging_doc UNIQUE (company_id, entity_type, doc_num)
);
CREATE INDEX IF NOT EXISTS idx_trx_staging_docdate ON trx_raw_staging (company_id, entity_type, doc_date);
CREATE INDEX IF NOT EXISTS idx_trx_staging_synced ON trx_raw_staging (company_id, entity_type, synced_at);

-- Dual-lane checkpoint state per (company, entity, lane)
CREATE TABLE IF NOT EXISTS sync_watermarks (
  company_id INT NOT NULL,
  entity_type TEXT NOT NULL,
  lane TEXT NOT NULL,                -- 'backfill' | 'delta'
  watermark_date DATE,               -- backfill: last completed month-end; delta: last success date
  status TEXT NOT NULL DEFAULT 'idle', -- idle|running|paused|done|failed
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, entity_type, lane)
);

-- Async export job tracking (Sprint 3 consumer, schema now)
CREATE TABLE IF NOT EXISTS export_files (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id INT NOT NULL,
  requested_by TEXT,
  report_slug TEXT NOT NULL,
  params JSONB,
  file_path TEXT,
  status TEXT NOT NULL DEFAULT 'pending', -- pending|running|ready|failed
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);

-- Completeness audit results (self-healing reconciliation)
CREATE TABLE IF NOT EXISTS report_reconciliation_log (
  id BIGSERIAL PRIMARY KEY,
  company_id INT NOT NULL,
  entity_type TEXT NOT NULL,
  bucket_date DATE NOT NULL,
  api_count INT,
  staging_count INT,
  status TEXT NOT NULL,              -- MATCH|MISMATCH|REPOILED
  checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_recon_lookup ON report_reconciliation_log (company_id, entity_type, bucket_date);

-- Delta lane schedule rows (picked up by existing 5-min router)
INSERT INTO md_sync_schedules (entity_type, interval_minutes, enabled, description) VALUES
  ('TRX_STOCK_OPNAME', 1440, true, 'Delta sync stock opname (T-2 window)'),
  ('TRX_PURCHASE_REQUEST', 1440, true, 'Delta sync purchase request (T-2 window)'),
  ('TRX_PURCHASE_ORDER', 1440, true, 'Delta sync purchase order (T-2 window)'),
  ('TRX_GOODS_RECEIPT', 1440, true, 'Delta sync goods receipt (T-2 window)'),
  ('TRX_GOODS_DELIVERY', 1440, true, 'Delta sync goods delivery (T-2 window)')
ON CONFLICT (entity_type) DO NOTHING;
"""


def main():
    if not DSN:
        print("DATABASE_URL / SUPABASE_DB_URL not set in .env")
        sys.exit(1)
    conn = psycopg2.connect(DSN)
    try:
        cur = conn.cursor()
        cur.execute(MIGRATION)
        conn.commit()
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='trx_raw_staging'")
        print("trx_raw_staging cols:", [r[0] for r in cur.fetchall()])
        cur.execute("SELECT entity_type, interval_minutes, enabled FROM md_sync_schedules WHERE entity_type LIKE 'TRX_%' ORDER BY 1")
        print("TRX schedules:", cur.fetchall())
        print("Migration OK")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
