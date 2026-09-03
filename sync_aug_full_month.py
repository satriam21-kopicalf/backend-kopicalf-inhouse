#!/usr/bin/env python3
"""
POS Sales Full Sync - ALL August 2026 (2026-08-01 to 2026-08-31)
- Syncs ALL dates, with force-resync for LOW-count days
- No data loss: UPSERT on row_hash means duplicates are impossible
- Per-day DB connection (prevents connection drop from losing batch)
- Every page commit ensures partial progress survives crashes
- Target: 58-70k records/day
"""
import sys
import os
import psycopg2
import httpx
import base64
import hashlib
import json
import time
from datetime import date, timedelta, datetime
from dotenv import load_dotenv

# Force unbuffered output
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)

load_dotenv()

# Config
OMS_BASE_URL = "https://esbcore.co.id"
OMS_USERNAME = "CALFSUPERADMINOPS"
OMS_PASSWORD = "abc123"
COMPANY_CODE = "CALF"
COMPANY_ID = 1
DATE_FROM = "2026-08-01"
DATE_TO = "2026-08-31"

DB_TIMEOUT = "30min"
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5
LOW_COUNT_THRESHOLD = 58000  # Below this = force re-sync


def generate_row_hash(r: dict) -> str:
    return hashlib.md5(json.dumps(r, sort_keys=True, default=str).encode()).hexdigest()


def get_db():
    db_url = os.getenv("DB_POOLER_URL")
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute(f"SET statement_timeout = '{DB_TIMEOUT}'")
    return conn, cur


def get_api_client():
    creds = base64.b64encode((OMS_USERNAME + ":" + OMS_PASSWORD).encode()).decode()
    return httpx.Client(
        base_url=OMS_BASE_URL,
        headers={"Authorization": "Basic " + creds, "Content-Type": "application/json"},
        timeout=120
    )


def get_existing_counts():
    """Get record counts per day from DB."""
    conn, cur = get_db()
    try:
        cur.execute("""
            SELECT DATE(created_date) as dt, COUNT(*) as cnt
            FROM esb_data.report_pos_sales
            WHERE created_date >= '2026-08-01' AND created_date < '2026-09-01'
            GROUP BY DATE(created_date)
            ORDER BY dt
        """)
        counts = {row[0]: row[1] for row in cur.fetchall()}
    finally:
        cur.close()
        conn.close()
    return counts


def upsert_batch(cur, records):
    """Upsert a batch of records. UPSERT = no duplicates possible."""
    if not records:
        return
    sql = '''
        INSERT INTO esb_data.report_pos_sales
        (company_id, sales_num, bill_num, sales_date, branch_code, branch_name, batch_id,
         menu_code, menu_name, menu_category_name, menu_category_detail_name, qty, price,
         original_price, discount, discount_value, subtotal, other_tax, service_charge,
         tax, vat, total, notes, cancel_notes, status_id, status_name, created_by,
         created_date, extras, raw_data, id_esb, row_hash)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (row_hash) DO UPDATE SET
            synced_at = NOW(), updated_at = NOW(),
            sales_num = EXCLUDED.sales_num,
            menu_code = EXCLUDED.menu_code,
            id_esb = EXCLUDED.id_esb
    '''
    cur.executemany(sql, records)


def process_rows(rows, company_id):
    """Convert API rows to DB records."""
    records = []
    for r in rows:
        raw_data = json.dumps(r, default=str)
        row_hash = generate_row_hash(r)
        records.append((
            company_id,
            r.get('salesNum'),
            r.get('billNum'),
            r.get('salesDate'),
            r.get('branchCode'),
            r.get('branchName'),
            r.get('batchID'),
            r.get('menuCode'),
            r.get('menuName'),
            r.get('menuCategoryName'),
            r.get('menuCategoryDetailName'),
            r.get('qty') or 0,
            r.get('price') or 0,
            r.get('originalPrice') or 0,
            r.get('discount') or 0,
            r.get('discountValue') or 0,
            r.get('subTotal') or 0,
            r.get('otherTax') or 0,
            r.get('serviceCharge') or 0,
            r.get('tax') or 0,
            r.get('vat') or 0,
            r.get('total') or 0,
            r.get('notes'),
            r.get('cancelNotes'),
            r.get('statusID'),
            r.get('statusName'),
            r.get('createdBy'),
            r.get('createdDate'),
            json.dumps(r.get('extras') or [], default=str),
            raw_data,
            r.get('menuID') or r.get('id'),
            row_hash,
        ))
    return records


def sync_date(client, target_date, force=False):
    """Sync one day. Opens its own DB connection per day."""
    date_str = target_date.isoformat()
    day_start = datetime.now()

    conn, cur = get_db()
    try:
        # Check existing count
        if not force:
            cur.execute("""
                SELECT COUNT(*) FROM esb_data.report_pos_sales
                WHERE DATE(created_date) = %s
            """, (date_str,))
            existing = cur.fetchone()[0]
            if existing >= LOW_COUNT_THRESHOLD:
                print(f"  [{date_str}] OK: {existing:,} records (>= {LOW_COUNT_THRESHOLD:,}) - skipping")
                conn.close()
                return 0, 0

        body = {
            "companyCode": COMPANY_CODE,
            "filterSalesDateFrom": date_str,
            "filterSalesDateTo": date_str
        }

        day_lines = 0
        page = 1
        max_pages = None
        total_records = 0
        commits_ok = 0
        commits_fail = 0
        pages_since_refresh = 0
        CONN_REFRESH_EVERY = 50  # Close+reopen DB conn every N pages to avoid pool timeout

        while True:
            url = "/external/general/sales-menu"
            if page > 1:
                url = f"/external/general/sales-menu?page={page}"

            # Refresh DB connection periodically to avoid pool timeout
            pages_since_refresh += 1
            if pages_since_refresh >= CONN_REFRESH_EVERY:
                pages_since_refresh = 0
                try:
                    conn.close()
                except Exception:
                    pass
                conn, cur = get_db()

            # API call with retries
            r = None
            for attempt in range(RETRY_ATTEMPTS):
                try:
                    r = client.post(url, json=body)
                    if r.status_code == 200:
                        break
                    print(f"  [{date_str}] HTTP {r.status_code}, retry {attempt+1}/{RETRY_ATTEMPTS}")
                    time.sleep(RETRY_DELAY)
                except Exception as e:
                    print(f"  [{date_str}] API Error: {e}, retry {attempt+1}/{RETRY_ATTEMPTS}")
                    time.sleep(RETRY_DELAY)
                    client = get_api_client()

            if r is None or r.status_code != 200:
                print(f"  [{date_str}] FAILED after {RETRY_ATTEMPTS} attempts")
                break

            rows = r.json()
            if not rows or not isinstance(rows, list):
                break

            if max_pages is None:
                total_count = r.headers.get('x-pagination-total-count', '0')
                page_count = r.headers.get('x-pagination-page-count', '0')
                max_pages = int(page_count)
                print(f"  [{date_str}] API Total: {total_count}, Pages: {max_pages}")

            # Process and COMMIT EVERY PAGE
            records = process_rows(rows, COMPANY_ID)
            success = False
            for attempt in range(RETRY_ATTEMPTS):
                try:
                    upsert_batch(cur, records)
                    conn.commit()
                    day_lines += len(records)
                    total_records += len(records)
                    commits_ok += 1
                    success = True
                    break
                except Exception as e:
                    print(f"  [{date_str}] DB Error: {e}")
                    conn.rollback()
                    commits_fail += 1
                    time.sleep(RETRY_DELAY)
                    try:
                        conn.close()
                    except Exception:
                        pass
                    conn, cur = get_db()
                    pages_since_refresh = 0

            # Print progress: first 5, every 10, last
            if success:
                if page <= 5 or page % 10 == 0 or page == max_pages:
                    print(f"  [{date_str}] Page {page}/{max_pages}: +{len(records)} (total: {total_records})")

            current_page = int(r.headers.get('x-pagination-current-page', page))
            if current_page >= max_pages:
                break
            page += 1

        elapsed = (datetime.now() - day_start).total_seconds()
        print(f"  [{date_str}] Done: {total_records} records in {elapsed:.1f}s (commits: {commits_ok} ok, {commits_fail} fail)")

    finally:
        try:
            conn.close()
        except Exception:
            pass

    return 0, day_lines


def main():
    import argparse
    parser = argparse.ArgumentParser(description='POS Sales Sync - August 2026 Full')
    parser.add_argument('--force', action='store_true', help='Force re-sync ALL dates')
    parser.add_argument('--days', help='Comma-separated specific dates (YYYY-MM-DD)')
    args = parser.parse_args()

    print("=" * 80)
    print("POS SALES FULL SYNC - AUGUST 2026 (FULL MONTH)")
    print("=" * 80)
    print(f"Period: {DATE_FROM} to {DATE_TO}")
    print(f"Company: {COMPANY_CODE} (ID: {COMPANY_ID})")
    print(f"Threshold: {LOW_COUNT_THRESHOLD:,} records/day")
    print(f"DB Timeout: {DB_TIMEOUT}")
    print(f"Commit: EVERY page")
    print("=" * 80)

    start_time = datetime.now()
    print(f"\nStarted at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Check existing counts
    print("Checking existing DB counts...")
    existing = get_existing_counts()

    # Determine which dates to sync
    if args.days:
        dates = [date.fromisoformat(d) for d in args.days.split(',')]
        force_all = True
    elif args.force:
        current = date.fromisoformat(DATE_FROM)
        end = date.fromisoformat(DATE_TO)
        dates = []
        while current <= end:
            dates.append(current)
            current += timedelta(days=1)
        force_all = True
    else:
        current = date.fromisoformat(DATE_FROM)
        end = date.fromisoformat(DATE_TO)
        dates = []
        while current <= end:
            dates.append(current)
            current += timedelta(days=1)
        force_all = False

    # Show what will be synced
    print(f"\n{'Date':<12} {'Before':>10} {'Action':<15}")
    print("-" * 40)
    for d in dates:
        cnt = existing.get(d, 0)
        if force_all:
            action = "FORCE SYNC"
        elif cnt >= LOW_COUNT_THRESHOLD:
            action = "skip (OK)"
        elif cnt > 0:
            action = f"re-sync ({cnt:,})"
        else:
            action = "SYNC (new)"
        print(f"{d.isoformat():<12} {cnt:>10,} {action:<15}")

    print(f"\nTotal dates to process: {len(dates)}")

    client = get_api_client()
    total_lines = 0

    for i, target_date in enumerate(dates):
        is_last = (i == len(dates) - 1)
        cnt_before = existing.get(target_date, 0)

        # Determine if force needed
        force = force_all or cnt_before < LOW_COUNT_THRESHOLD

        print(f"\n[{i+1}/{len(dates)}] Processing {target_date}...")
        try:
            heads, lines = sync_date(client, target_date, force=force)
            total_lines += lines
        except Exception as e:
            print(f"  [{target_date}] Fatal error: {e}")
            client = get_api_client()
            continue

        # Small delay between days
        if not is_last:
            time.sleep(2)

    client.close()

    # Final summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Get updated counts
    existing_after = get_existing_counts()

    print("\n" + "=" * 80)
    print("SYNC COMPLETE")
    print("=" * 80)
    print(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Finished: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration: {duration:.0f} seconds ({duration/60:.1f} minutes)")
    print(f"Total Lines: {total_lines:,}")
    print("\nFinal Counts:")
    print(f"{'Date':<12} {'Records':>10} {'Status'}")
    print("-" * 40)
    for d in dates:
        cnt = existing_after.get(d, 0)
        if cnt >= LOW_COUNT_THRESHOLD:
            status = "OK"
        elif cnt > 0:
            status = "LOW"
        else:
            status = "EMPTY"
        print(f"{d.isoformat():<12} {cnt:>10,} {status}")
    print("=" * 80)


if __name__ == "__main__":
    main()
