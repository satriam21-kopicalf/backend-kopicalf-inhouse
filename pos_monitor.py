#!/usr/bin/env python3
"""
POS Sales Monitor - KOPICALF
Real-time monitoring dashboard for sync status.

Usage:
    python pos_monitor.py              # Monitor current sync (live)
    python pos_monitor.py --summary    # Show DB summary only (no live monitor)
    python pos_monitor.py --counts     # Show daily record counts only

Requirements:
    pip install psycopg2-binary python-dotenv
"""
import sys
import os
import psycopg2
import time
import argparse
import glob
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv()

# ── Colors (ANSI) ──────────────────────────────────────────────────────────
C_RESET  = "\033[0m"
C_RED    = "\033[91m"
C_GREEN  = "\033[92m"
C_YELLOW = "\033[93m"
C_BLUE   = "\033[94m"
C_CYAN   = "\033[96m"
C_BOLD   = "\033[1m"
C_DIM    = "\033[2m"

# ── ASCII fallback for Windows cmd ──────────────────────────────────────────
try:
    result = __import__('subprocess').run(['chcp'], capture_output=True, text=True)
    IS_UTF8 = '65001' in result.stdout
except Exception:
    IS_UTF8 = False

# Use ASCII-safe separators
D_SEP = "="  # Header border
S_SEP = "-"  # Row separator
S_BAR = "#"  # Bar fill (ASCII)

def col(c, text):
    return (c + text + C_RESET) if IS_UTF8 else text

def bar(current: int, total: int, width: int = 20, ok: bool = True) -> str:
    """Draw a progress bar using ASCII characters."""
    if total <= 0:
        return col(C_DIM, "[" + " " * width + "] 0%")
    filled = int(width * current / total)
    part   = int(width * current / total * 4) - filled * 4
    sym    = " .*#" [part]
    bar_s  = S_BAR * filled + sym + "." * max(0, width - filled - 1)
    pct    = min(100, int(100 * current / total))
    color  = C_GREEN if ok else C_YELLOW
    return color + f"[{bar_s}] {pct}%" + C_RESET


# ── DB Helpers ──────────────────────────────────────────────────────────────
def get_db():
    db_url = os.getenv("DB_POOLER_URL")
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    return conn


def get_all_counts() -> dict:
    """Get record counts per day for August 2026."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT DATE(created_date) as dt, COUNT(*) as cnt
        FROM esb_data.report_pos_sales
        WHERE created_date >= '2026-08-01' AND created_date < '2026-09-01'
        GROUP BY DATE(created_date)
        ORDER BY dt
    """)
    result = {row[0]: row[1] for row in cur.fetchall()}
    cur.close()
    conn.close()
    return result


def get_total_august() -> int:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM esb_data.report_pos_sales
        WHERE company_id = 1
          AND sales_date >= '2026-08-01' AND sales_date <= '2026-08-31'
    """)
    total = cur.fetchone()[0]
    cur.close()
    conn.close()
    return total


def get_recent_sync():
    """Get the most recent sync record."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, entity_type, status, records_processed, started_at, completed_at
        FROM public.sync_history
        WHERE entity_type LIKE 'POS%%'
        ORDER BY started_at DESC
        LIMIT 1
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


# ── Display Helpers ──────────────────────────────────────────────────────────
THRESHOLD = 58_000

def fmt_num(n: int) -> str:
    return f"{n:,}" if n else "0"

def status_cell(cnt: int) -> str:
    if cnt >= THRESHOLD:
        return col(C_GREEN, "  OK  ")
    elif cnt > 0:
        pct = int(100 * cnt / THRESHOLD)
        return col(C_YELLOW, f" {pct}% ")
    else:
        return col(C_RED, " EMPTY")


def print_header(title: str):
    W = 72
    print()
    print(col(C_BOLD + C_BLUE, f"  {title}"))
    print(col(C_BLUE, D_SEP * W))


def print_summary_table(counts: dict):
    W = 72
    print()
    print(f"  {'DATE':<12} {'RECORDS':>10}  {'STATUS':<8} {'BAR':<26}")
    sep = S_SEP
    print(col(C_BLUE, f"  {sep*12} {sep*10}  {sep*8} {sep*26}"))

    ok_days = low_days = empty_days = 0
    for day_num in range(1, 32):
        dt = date(2026, 8, day_num)
        cnt = counts.get(dt, 0)
        if cnt >= THRESHOLD:
            ok_days += 1
        elif cnt > 0:
            low_days += 1
        else:
            empty_days += 1

        cell = status_cell(cnt)
        bar_s = bar(cnt, THRESHOLD, 20, cnt >= THRESHOLD)
        print(f"  {col(C_CYAN, str(dt)):<12} {fmt_num(cnt):>10}  {cell}  {bar_s}")

    print(col(C_BLUE, f"  {sep*12} {sep*10}  {sep*8} {sep*26}"))
    total = sum(counts.values())
    status_line = f'{ok_days} OK / {low_days} LOW / {empty_days} EMPTY'
    print(f"  {col(C_BOLD, 'TOTAL')[:12]:<12} {col(C_BOLD, fmt_num(total)):>10}  "
          f"{col(C_GREEN if ok_days == 31 else C_YELLOW, status_line):<8}")


def parse_progress(line: str):
    """Parse page progress from output like 'Page 145/1826: +20 (total: 2900)'."""
    import re
    m = re.search(r'Page (\d+)/(\d+).*total[:\s]+(\d+)', line)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None


# ── Live Monitor ────────────────────────────────────────────────────────────
def live_monitor(output_file: str, interval: int = 5):
    """Watch the sync output file and display live progress."""
    print_header("POS SALES SYNC - LIVE MONITOR")
    print()
    print(col(C_DIM, "  Watching sync output... (Ctrl+C to stop)\n"))

    last_pos = 0
    day_info = {}       # date -> {api_total, page, max_page, total_rec}
    days_done = []      # dates already completed
    current_day = None
    api_cache = {}      # date -> api_total

    while True:
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\n  Monitor stopped.")
            return

        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                f.seek(last_pos)
                lines = f.readlines()
                last_pos = f.tell()

            new_lines = [l.strip() for l in lines if l.strip()]

            for line in new_lines:
                import re

                # New day started
                if 'Processing' in line and line.count('[') >= 1:
                    m = re.search(r'\[(\d{4}-\d{2}-\d{2})\]', line)
                    if m:
                        new_day = date.fromisoformat(m.group(1))
                        if current_day and current_day not in days_done:
                            days_done.append(current_day)
                        current_day = new_day

                # API total discovered
                if 'API Total:' in line:
                    m = re.search(r'\[(\d{4}-\d{2}-\d{2})\].*API Total[:\s]+(\d+)', line)
                    if m:
                        dt = date.fromisoformat(m.group(1))
                        api_tot = int(m.group(2))
                        api_cache[dt] = api_tot
                        day_info[dt] = {'api_total': api_tot, 'page': 0, 'max_page': 0, 'total_rec': 0}

                # Page progress
                prog = parse_progress(line)
                if prog and current_day:
                    cur_pg, max_pg, tot_rec = prog
                    day_info.setdefault(current_day, {})['page'] = cur_pg
                    day_info.setdefault(current_day, {})['max_page'] = max_pg
                    day_info.setdefault(current_day, {})['total_rec'] = tot_rec

                # Day completed
                if 'Done:' in line:
                    m = re.search(r'\[(\d{4}-\d{2}-\d{2})\]', line)
                    if m:
                        done_dt = date.fromisoformat(m.group(1))
                        if done_dt not in days_done:
                            days_done.append(done_dt)

                # Sync complete
                if 'SYNC COMPLETE' in line:
                    _print_live_table(day_info, api_cache, days_done, current_day)
                    print()
                    print_header("SYNC COMPLETE")
                    print()
                    return

            # Print live table
            if new_lines:
                _print_live_table(day_info, api_cache, days_done, current_day)

        except FileNotFoundError:
            print(col(C_RED, "  ! Output file not found. Is sync running?"))
            time.sleep(interval)
        except Exception as e:
            print(col(C_RED, f"  Error: {e}"))
            time.sleep(interval)


def _print_live_table(day_info, api_cache, days_done, current_day):
    """Print the live progress table using ANSI escape."""
    # Move cursor up to overwrite previous table
    num_rows = max(len(day_info), 1) + 3
    sys.stdout.write("\033[" + str(num_rows) + "A")
    sys.stdout.flush()

    sep = S_SEP
    print()
    print(f"  {col(C_BOLD, 'DATE'):<12} {'API TOTAL':>10} {'DB REC':>10}  {'PAGE':>10}  {'PROGRESS'}")
    print(col(C_BLUE, f"  {sep*12} {sep*10} {sep*10}  {sep*10}  {sep*26}"))

    all_dates = sorted(day_info.keys()) if day_info else ([current_day] if current_day else [])
    for dt in all_dates:
        info = day_info.get(dt, {})
        api_tot = api_cache.get(dt) or 0
        page    = info.get('page', 0)
        max_pg  = info.get('max_page', 0)
        db_rec  = info.get('total_rec', 0)
        is_done = dt in days_done

        if is_done:
            date_s = col(C_GREEN + C_BOLD, f"  {dt}")
            status = col(C_GREEN, "  DONE   ")
        elif page > 0:
            date_s = col(C_CYAN, f"  {dt}")
            status = col(C_YELLOW, f"  {page}/{max_pg}")
        else:
            date_s = col(C_DIM, f"  {dt}")
            status = col(C_DIM, "  WAITING")

        bar_s = bar(db_rec, max(api_tot, 1), 22, is_done) if max_pg > 0 else col(C_DIM, "[                    ] --")
        print(f"  {date_s:<12} {fmt_num(api_tot):>10} {fmt_num(db_rec):>10}  {status}  {bar_s}")

    print()


# ── Summary Mode ────────────────────────────────────────────────────────────
def show_summary():
    counts = get_all_counts()

    print_header("KOPICALF - POS SALES MONITOR (2026-08-01 to 31)")
    print(f"  {col(C_CYAN, 'Generated:')} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_summary_table(counts)

    print()
    recent = get_recent_sync()
    if recent:
        ts = recent[4].strftime('%Y-%m-%d %H:%M:%S') if recent[4] else 'N/A'
        st = col(C_GREEN if recent[2] == 'SUCCESS' else C_YELLOW, recent[2])
        print(f"  {col(C_CYAN, 'Last Sync:')}   {ts}  {st}  {(recent[3] or 0):,} records")

    print()
    print(col(C_BLUE, D_SEP * 72))


# ── Counts Only Mode ────────────────────────────────────────────────────────
def show_counts():
    counts = get_all_counts()
    sep = S_SEP
    print()
    print(f"  {'DATE':<12} {'RECORDS':>10}  {'STATUS'}")
    print(col(C_BLUE, f"  {sep*12} {sep*10}"))
    for day_num in range(1, 32):
        dt = date(2026, 8, day_num)
        cnt = counts.get(dt, 0)
        print(f"  {col(C_CYAN, str(dt)):<12} {fmt_num(cnt):>10}  {status_cell(cnt)}")
    print(col(C_BLUE, f"  {sep*12} {sep*10}"))
    print(f"  {col(C_BOLD, 'TOTAL'):<12} {col(C_BOLD, fmt_num(sum(counts.values()))):>10}")
    print()


# ── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="POS Sales Monitor - KOPICALF",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pos_monitor.py              # Live monitoring of sync process
  python pos_monitor.py --summary   # Show full DB summary + table
  python pos_monitor.py --counts    # Show daily record counts only
        """
    )
    parser.add_argument('--summary', action='store_true',
                        help='Show full DB summary (no live monitor)')
    parser.add_argument('--counts', action='store_true',
                        help='Show daily record counts only')
    parser.add_argument('--output', default='sync_output.txt',
                        help='Path to sync output file (default: sync_output.txt)')
    parser.add_argument('--interval', type=int, default=5,
                        help='Refresh interval in seconds (default: 5)')
    args = parser.parse_args()

    if args.counts:
        show_counts()
    elif args.summary:
        show_summary()
    else:
        # Find sync output file
        base_dir = os.path.dirname(os.path.abspath(__file__))
        possible = [
            args.output,
            os.path.join(base_dir, args.output),
            os.path.join(os.getcwd(), args.output),
        ]

        # Also check temp task output dirs
        temp = os.environ.get('TEMP', '')
        if temp:
            for pattern in [f'{temp}/claude/**/tasks/*.output']:
                possible.extend(glob.glob(pattern))

        output_file = None
        for p in possible:
            if os.path.exists(p):
                output_file = p
                break

        if not output_file:
            # Find most recently modified .output
            candidates = []
            for root in [temp, os.getcwd(), base_dir]:
                if not os.path.exists(root):
                    continue
                for f in glob.glob(f'{root}/**/*.output', recursive=True):
                    try:
                        if time.time() - os.path.getmtime(f) < 7200:
                            candidates.append((os.path.getmtime(f), f))
                    except Exception:
                        pass
            if candidates:
                candidates.sort(reverse=True)
                output_file = candidates[0][1]

        if output_file:
            print(f"  Watching: {col(C_CYAN, output_file)}")
            live_monitor(output_file, args.interval)
        else:
            print(col(C_YELLOW, "  No sync output found. Run sync_aug_full_month.py first,"))
            print(f"  or use {col(C_CYAN, '--summary')} to show current DB status.\n")
            show_summary()
