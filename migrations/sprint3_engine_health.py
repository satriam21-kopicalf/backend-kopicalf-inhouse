"""Sprint 3 migration: reconciliation log residual-verification column.

Idempotent: safe to re-run.
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

MIGRATION = """
ALTER TABLE report_reconciliation_log ADD COLUMN IF NOT EXISTS staging_after int;
"""


def main():
    conn = psycopg2.connect(os.getenv("DB_POOLER_URL"))
    try:
        cur = conn.cursor()
        cur.execute(MIGRATION)
        conn.commit()
        print("OK: staging_after column present")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
