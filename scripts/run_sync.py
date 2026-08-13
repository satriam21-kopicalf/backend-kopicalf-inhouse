"""
Script untuk menjalankan sinkronisasi master data secara manual (development/testing).
Tidak digunakan di production — production menggunakan Celery task.
"""
import os
import sys
import httpx
from datetime import datetime, timezone
from dotenv import load_dotenv

# Tambah project root ke path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from app.core.db import get_db_connection
from app.services.tasks import sync_company_data
from psycopg2.extras import DictCursor

def run_sync():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    try:
        cur.execute("SELECT id, esb_token FROM company_configs WHERE is_active = true LIMIT 1")
        company = cur.fetchone()
        if not company:
            print("No active company found.")
            return

        company_id = company['id']

        # Ambil token dinamis dari ESB
        esb_user = os.getenv("ESB_CORE_USERNAME")
        esb_pass = os.getenv("ESB_CORE_PASSWORD")
        esb_url = os.getenv("ESB_CORE_URL", "https://services.esb.co.id/core")
        esb_token = company['esb_token']

        if esb_user and esb_pass:
            try:
                res = httpx.post(f"{esb_url}/auth/login",
                                 json={"username": esb_user, "password": esb_pass},
                                 timeout=15.0)
                if res.status_code == 200:
                    esb_token = res.json().get("result", {}).get("accessToken", esb_token)
                    print(f"Token fetched: {esb_token[:12]}...")
            except Exception as e:
                print(f"Warning: Could not fetch dynamic token: {e}")

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        historical_start = "2026-07-01"

        print(f"Starting sync for company_id={company_id}...")
        sync_company_data(company_id, esb_token, historical_start, today_str)
        print("Sync complete.")

    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    run_sync()
