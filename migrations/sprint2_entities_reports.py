"""Sprint 2 migration: schedule rows for new TRX entities + direct reports.

Idempotent: safe to re-run.
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

MIGRATION = """
INSERT INTO md_sync_schedules (entity_type, interval_minutes, enabled, description) VALUES
  ('TRX_RECEIPT', 1440, true, 'Delta sync receipt (T-2 window)'),
  ('TRX_MEMORIAL_JOURNAL', 1440, true, 'Delta sync memorial journal (T-2 window)'),
  ('TRX_ADVANCE_SALES', 1440, true, 'Delta sync customer advance sales (T-2 window)'),
  ('TRX_SIMPLE_MANUFACTURING', 1440, true, 'Delta sync simple manufacturing (T-2 window)'),
  ('TRX_DISBURSEMENT', 1440, true, 'Full re-pull disbursement (no server date filter)'),
  ('RPT_STOCK_MOVEMENT', 1440, true, 'Direct report stock movement (T-7 window, beat 06:00)'),
  ('RPT_SALES_PAYMENT_SUMMARY', 1440, true, 'Direct report sales payment summary (beat 06:00)')
ON CONFLICT (entity_type) DO NOTHING;
"""


def main():
    conn = psycopg2.connect(os.getenv("DB_POOLER_URL"))
    try:
        cur = conn.cursor()
        cur.execute(MIGRATION)
        conn.commit()
        cur.execute("SELECT entity_type, enabled FROM md_sync_schedules WHERE entity_type LIKE 'TRX_%' OR entity_type LIKE 'RPT_%' ORDER BY 1")
        for r in cur.fetchall():
            print(r)
        print("OK")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
