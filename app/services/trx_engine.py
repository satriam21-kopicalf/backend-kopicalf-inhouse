"""Dual-lane transactional ingest engine.

Lane A (Historical): continuous monthly chunks oldest-first from BACKFILL_START,
    runs every 25 minutes, 24/7.
Lane B (Daily Process): rolling window T-2 -> T daily, driven by md_sync_schedules.
Real-time lane: T-1 -> T for current day data, runs every 30 minutes.

Both lanes upsert into trx_raw_staging keyed (company_id, entity_type, doc_num)
which makes overlaps structurally impossible to duplicate; the daily
completeness_audit re-pulls any date bucket where API count != staging count.

Verified live 2026-08-16 (CALF scope):
- STOCK_OPNAME      index /inventory/stock-opname          dateFrom/dateTo OK, num=stockOpnameNum
- PURCHASE_ORDER    index /purchase/purchase-order         dateFrom/dateTo OK, num=purchaseNum
- PURCHASE_REQUEST  index /purchase/purchase-request       NO server date filter (full pull + local filter)
- GOODS_RECEIPT     index /inventory/goods-receipt         dateFrom/dateTo OK, num NULL while Pending
- GOODS_DELIVERY    index /inventory/goods-delivery        dateFrom/dateTo OK, num NULL while Pending
"""
import os
import json
import time
import math
import hashlib
import typing
import urllib.parse
from datetime import datetime, timezone, date, timedelta

import redis as redis_lib
from psycopg2.extras import execute_values, RealDictCursor
from app.services.operational_window import is_within_operational_window

from app.core.worker import celery_app
from app.core.db import get_db_connection
from app.services.tasks import (
    ESBClient, _esb_company_token, _extract_page, _is_engine_enabled,
    ESB_FALLBACK_USERNAME, ESB_FALLBACK_PASSWORD, PAGE_SIZE,
    CircuitBreakerOpenException,
)

ESB_API_BASE_URL = os.getenv("ESB_CORE_URL", "https://services.esb.co.id/core")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

BACKFILL_START = os.getenv("BACKFILL_START_DATE", "2026-08-01")   # Historical data start: 2026-08-01
BACKFILL_NIGHT_START = int(os.getenv("BACKFILL_WINDOW_START", "19"))   # WIB
BACKFILL_NIGHT_END = int(os.getenv("BACKFILL_WINDOW_END", "8"))        # WIB
DELTA_WINDOW_DAYS = 2       # T-2 -> T
RATE_LIMIT_SECONDS = 0.5    # between view calls
PAGE_SLEEP_SECONDS = 0.3    # between index pages
MAX_MONTHS_PER_RUN = 12     # backfill fairness: months per task invocation
AUTH_LOCK_TTL = 60          # seconds
COMPANY_LOCK_TTL = 3600     # seconds; renewed per chunk

TRX_INDEX_VIEW: typing.Dict[str, dict] = {
    "STOCK_OPNAME": {
        "index_path": "/inventory/stock-opname",
        "doc_num_field": "stockOpnameNum",
        "doc_date_field": "stockOpnameDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "identity_fields": ["stockOpnameNum"],
    },
    "PURCHASE_ORDER": {
        "index_path": "/purchase/purchase-order",
        "doc_num_field": "purchaseNum",
        "doc_date_field": "purchaseDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "identity_fields": ["purchaseNum"],
    },
    "PURCHASE_REQUEST": {
        "index_path": "/purchase/purchase-request",
        "doc_num_field": "purchaseRequestNum",
        "doc_date_field": "purchaseRequestDate",
        "status_field": "statusName",
        "date_filter": None,  # server ignores date params -> full pull + local filter
        "view": True,
        "identity_fields": ["purchaseRequestNum"],
    },
    "GOODS_RECEIPT": {
        "index_path": "/inventory/goods-receipt",
        "doc_num_field": "goodsReceiptNum",      # NULL while status Pending
        "doc_date_field": "goodsReceiptDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "nullable_doc_num": True,
        "identity_fields": ["refNum", "goodsReceiptDate", "branchID"],
    },
    "GOODS_DELIVERY": {
        "index_path": "/inventory/goods-delivery",
        "doc_num_field": "goodsDeliveryNum",     # NULL while Pending
        "doc_date_field": "goodsDeliveryDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "nullable_doc_num": True,
        "identity_fields": ["referenceNumber", "goodsDeliveryDate", "originBranchID"],
    },
    # ── Sprint 2 batch (verified live 2026-08-16) ──
    "RECEIPT": {
        "index_path": "/receipt",
        "doc_num_field": "receiptNum",
        "doc_date_field": "receiptDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,          # view has receiptDetail[]
        "identity_fields": ["receiptNum"],
    },
    "MEMORIAL_JOURNAL": {
        "index_path": "/accounting/memorial-journal",
        "doc_num_field": "memorialJournalNum",
        "doc_date_field": "memorialJournalDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,          # view has memorialJournalDetails[]
        "identity_fields": ["memorialJournalNum"],
    },
    "ADVANCE_SALES": {
        "index_path": "/sales/advance-sales",
        "doc_num_field": "customerAdvancePaymentNum",
        "doc_date_field": "customerAdvancePaymentDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,          # header-rich view (no details array; header == report needs)
        "identity_fields": ["customerAdvancePaymentNum"],
    },
    "SIMPLE_MANUFACTURING": {
        "index_path": "/production/simple-manufacturing",
        "doc_num_field": "simpleManufacturingNum",   # contains spaces: "SM... - 1" (URL-encode!)
        "doc_date_field": "simpleManufacturingDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "identity_fields": ["simpleManufacturingNum"],
    },
    "DISBURSEMENT": {
        "index_path": "/finance/disbursement",
        "doc_num_field": "disbursementNum",
        "doc_date_field": "disbursementDate",
        "status_field": "statusName",
        "date_filter": None,   # server ignores date params (full count regardless)
        "view": False,         # index row already report-rich (ref, supplier, method, total, overdue)
        "identity_fields": ["disbursementNum"],
    },
    "PRODUCT_SALES": {
        "index_path": "/sales/product-sales",
        "doc_num_field": "productSalesNum",
        "doc_date_field": "productSalesDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "identity_fields": ["productSalesNum"],
    },
    "SALES_PAYMENT": {
        "index_path": "/sales/product-sales-payment",
        "doc_num_field": "salesPaymentNum",
        "doc_date_field": "salesPaymentDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "identity_fields": ["salesPaymentNum"],
    },
    "PRODUCT_SALES_ACTUATION": {
        "index_path": "/sales/product-sales/actuation",
        "doc_num_field": "actuationNum",
        "doc_date_field": "actuationDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "identity_fields": ["actuationNum"],
    },
    "AR_SUSPENSE": {
        "index_path": "/finance/account-receivable-suspense",
        "doc_num_field": "suspenseNum",
        "doc_date_field": "suspenseDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "identity_fields": ["suspenseNum"],
    },
    "AP_SUSPENSE": {
        "index_path": "/finance/account-payable-suspense",
        "doc_num_field": "suspenseNum",
        "doc_date_field": "suspenseDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "identity_fields": ["suspenseNum"],
    },
    "EMPLOYEE_ADVANCE": {
        "index_path": "/employee/employee-advance-payment",
        "doc_num_field": "employeeAdvanceNum",
        "doc_date_field": "employeeAdvanceDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "identity_fields": ["employeeAdvanceNum"],
    },
    "BUDGET_DETAIL": {
        "index_path": "/accounting/budget-detail",
        "doc_num_field": "budgetNum",
        "doc_date_field": "budgetDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "identity_fields": ["budgetNum"],
    },
    "BUDGET_REVISION": {
        "index_path": "/accounting/budget-revision",
        "doc_num_field": "budgetRevisionNum",
        "doc_date_field": "budgetRevisionDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "identity_fields": ["budgetRevisionNum"],
    },
    "PURCHASE_INVOICE": {
        "index_path": "/purchase/purchase-invoices",
        "doc_num_field": "purchaseInvoiceNum",
        "doc_date_field": "purchaseInvoiceDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "identity_fields": ["purchaseInvoiceNum"],
    },
    "PURCHASE_INVOICE_PAYMENT": {
        "index_path": "/purchase/purchase-invoice-payment",
        "doc_num_field": "purchaseInvoicePaymentNum",
        "doc_date_field": "purchaseInvoicePaymentDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "identity_fields": ["purchaseInvoicePaymentNum"],
    },
    "PURCHASE_RETURN": {
        "index_path": "/purchases/purchase-return",
        "doc_num_field": "purchaseReturnNum",
        "doc_date_field": "purchaseReturnDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "identity_fields": ["purchaseReturnNum"],
    },
    "GOODS_RECEIPT_RETURN": {
        "index_path": "/inventory/goods-receipt-return",
        "doc_num_field": "goodsReceiptReturnNum",
        "doc_date_field": "goodsReceiptReturnDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "identity_fields": ["goodsReceiptReturnNum"],
    },
    "GOODS_DELIVERY_RETURN": {
        "index_path": "/inventory/goods-delivery-return",
        "doc_num_field": "goodsDeliveryReturnNum",
        "doc_date_field": "goodsDeliveryReturnDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "identity_fields": ["goodsDeliveryReturnNum"],
    },
    "BILL_OF_MATERIAL": {
        "index_path": "/product/bom",
        "doc_num_field": "bomID",
        "doc_date_field": "bomDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "identity_fields": ["bomID"],
    },
    "ADVANCE_RECAP": {
        "index_path": "/finance/advance-recap",
        "doc_num_field": "advanceRecapNum",
        "doc_date_field": "advanceRecapDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "identity_fields": ["advanceRecapNum"],
    },
    "ITEM_JOURNAL": {
        "index_path": "/inventory/item-journal",
        "doc_num_field": "itemJournalNum",
        "doc_date_field": "itemJournalDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "identity_fields": ["itemJournalNum"],
    },
    "PURCHASE_ORDER_ACTUATION": {
        "index_path": "/purchase/purchase-order-actuation",
        "doc_num_field": "actuationNum",
        "doc_date_field": "actuationDate",
        "status_field": "statusName",
        "date_filter": ("dateFrom", "dateTo"),
        "view": True,
        "identity_fields": ["actuationNum"],
    }
}

_redis_client: typing.Optional[redis_lib.Redis] = None


def _redis() -> redis_lib.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def _auth_locked_company_token(company_code: str, username: str, password: str,
                               max_wait: int = 180) -> str:
    """Serialize ESB logins across lanes via a Redis lock (base JWT is single-use
    and concurrent logins invalidate each other)."""
    lock = _redis().lock("esb_auth_lock", timeout=AUTH_LOCK_TTL)
    waited = 0
    while True:
        if lock.acquire(blocking=False):
            try:
                return _esb_company_token(company_code, username, password)
            finally:
                try:
                    lock.release()
                except Exception:
                    pass
        time.sleep(2)
        waited += 2
        if waited >= max_wait:
            return _esb_company_token(company_code, username, password)  # last resort


def _parse_date(val) -> typing.Optional[date]:
    if not val:
        return None
    s = str(val)[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _is_backfill_allowed(now_jkt: typing.Optional[datetime] = None) -> bool:
    # Lane A runs 24/7, no time restriction
    return True


# ─────────────────────────────────────────────────────────────────────────
# Company-level backfill lock: one backfill task per company at a time.
# ESB company tokens are invalidated by concurrent same-company logins, and
# chunk work for one company is sequential anyway — parallelism comes from
# running DIFFERENT companies concurrently (worker concurrency > 1).
# ─────────────────────────────────────────────────────────────────────────

def _company_lock(company_id: int):
    return _redis().lock(f"bf_company_{company_id}", timeout=COMPANY_LOCK_TTL)


def _company_locked(company_id: int) -> bool:
    return _redis().exists(f"bf_company_{company_id}") > 0


def _month_chunks(start: date, until: date):
    """Yield (month_start, month_end) from start until 'until', oldest-first."""
    cur = date(start.year, start.month, 1)
    while cur <= until:
        next_m = date(cur.year + (cur.month == 12), (cur.month % 12) + 1, 1)
        yield cur, min(next_m - timedelta(days=1), until)
        cur = next_m


# ─────────────────────────────────────────────────────────────────────────
# Watermark helpers
# ─────────────────────────────────────────────────────────────────────────

def _get_watermark(cur, company_id: int, entity: str, lane: str):
    cur.execute("SELECT watermark_date, status FROM sync_watermarks WHERE company_id=%s AND entity_type=%s AND lane=%s",
                (company_id, entity, lane))
    return cur.fetchone()


def _set_watermark(cur, company_id: int, entity: str, lane: str,
                   watermark_date, status: str):
    cur.execute("""
        INSERT INTO sync_watermarks (company_id, entity_type, lane, watermark_date, status, updated_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON CONFLICT (company_id, entity_type, lane) DO UPDATE SET
            watermark_date = COALESCE(EXCLUDED.watermark_date, sync_watermarks.watermark_date),
            status = EXCLUDED.status, updated_at = NOW()
    """, (company_id, entity, lane, watermark_date, status))


def _stale_running_cleanup(cur):
    """Reset watermarks stuck in 'running' > 3h (dead worker / killed task)."""
    cur.execute("""
        UPDATE sync_watermarks SET status = 'idle', updated_at = NOW()
        WHERE status = 'running' AND updated_at < NOW() - INTERVAL '3 hours'
    """)


def _advance_delta_watermark(cur, company_id: int, entity: str, new_date):
    """Delta watermark is monotonic: never moves backwards."""
    cur.execute("""
        INSERT INTO sync_watermarks (company_id, entity_type, lane, watermark_date, status, updated_at)
        VALUES (%s, %s, 'delta', %s, 'idle', NOW())
        ON CONFLICT (company_id, entity_type, lane) DO UPDATE SET
            watermark_date = GREATEST(COALESCE(EXCLUDED.watermark_date, sync_watermarks.watermark_date),
                                      COALESCE(sync_watermarks.watermark_date, '1900-01-01'::date)),
            status = 'idle', updated_at = NOW()
    """, (company_id, entity, new_date))


# ─────────────────────────────────────────────────────────────────────────
# Core pull: index (server- or client-filtered) -> optional view -> upsert
# ─────────────────────────────────────────────────────────────────────────

def _iter_index_rows(client: ESBClient, cfg: dict, date_from: date, date_to: date):
    """Yield index rows whose doc_date falls in [date_from, date_to].

    date_filter set  -> server-side filter, every row is in range (still verified).
    date_filter None -> full pagination, rows filtered locally by doc_date.
    """
    page = 1
    total_pages = 1
    while page <= total_pages:
        params: typing.Dict[str, typing.Any] = {"page": page, "limit": PAGE_SIZE}
        if cfg["date_filter"]:
            params[cfg["date_filter"][0]] = date_from.isoformat()
            params[cfg["date_filter"][1]] = date_to.isoformat()
        body = client.get(cfg["index_path"], params=params)
        rows, total_pages = _extract_page(body, "envelope")
        for row in rows:
            if cfg["index_path"] == "/sales/product-sales" and page == 1:
                import logging
                logging.error(f"DEBUG PRODUCT_SALES ROW: {row}")
            row_date = _parse_date(row.get(cfg["doc_date_field"]))
            if row_date and date_from <= row_date <= date_to:
                yield row
        page += 1
        time.sleep(PAGE_SLEEP_SECONDS)


def _doc_key(cfg: dict, row: dict) -> typing.Tuple[str, bool]:
    """Return (doc_num, is_surrogate).

    Surrogate = digest of the FULL index row. Identity fields alone are NOT
    unique for GR/GD: several documents (e.g. partial receipts) can share one
    refNum + date + branch, so identity-only digests collided and promotions
    deleted unrelated pending docs (verified live 2026-08-16: GR CALF 09/10
    Aug kept losing its Pending docs every delta run)."""
    num = row.get(cfg["doc_num_field"])
    if num:
        return str(num), False
    digest = hashlib.md5(json.dumps(row, default=str, sort_keys=True).encode()).hexdigest()[:16]
    return f"SUR:{digest}", True


def _surrogate_group_key(cfg: dict, row: dict) -> tuple:
    """Identity group for reconcile: (ref, date, branch)."""
    ref = str(row.get(cfg["identity_fields"][0]) or "")
    d = str(row.get(cfg["identity_fields"][1]) or "")[:10]
    bf = cfg["identity_fields"][2] if len(cfg["identity_fields"]) > 2 else None
    b = str(row.get(bf)) if bf else ""
    return (ref, d, b)


def _reconcile_surrogates(cur, company_id: int, entity: str, cfg: dict,
                          date_from: date, date_to: date,
                          pending_counts: typing.Dict[tuple, int]):
    """Post-window invariant: for each identity group, staging keeps exactly as
    many SUR rows as the index currently shows Pending (null-numbered) docs.
    Extra/older SUR rows (docs that have since become numbered, or rows stored
    under the pre-Sprint-3 identity digest) are removed oldest-first."""
    if not cfg.get("nullable_doc_num"):
        return
    cur.execute("""
        SELECT ctid, payload->>%s AS ref, payload->>%s AS d, payload->>%s AS bid, synced_at
        FROM trx_raw_staging
        WHERE company_id = %s AND entity_type = %s AND doc_num LIKE 'SUR:%%'
          AND doc_date BETWEEN %s AND %s
    """, (cfg["identity_fields"][0], cfg["identity_fields"][1],
          cfg["identity_fields"][2] if len(cfg["identity_fields"]) > 2 else "statusName",
          company_id, entity, date_from, date_to))
    groups: typing.Dict[tuple, list] = {}
    for r in cur.fetchall():
        key = (str(r["ref"] or ""), str(r["d"] or "")[:10], str(r["bid"] or ""))
        groups.setdefault(key, []).append(r)
    doomed: typing.List[typing.Any] = []
    for key, rows in groups.items():
        keep = pending_counts.get(key, 0)
        rows.sort(key=lambda r: r["synced_at"] or datetime.min.replace(tzinfo=timezone.utc))
        doomed.extend(r["ctid"] for r in rows[:max(0, len(rows) - keep)])
    if doomed:
        cur.execute("DELETE FROM trx_raw_staging WHERE ctid = ANY(%s::tid[])",
                    ([str(c) for c in doomed],))
    return len(doomed)


def pull_trx_window(company_id: int, client: ESBClient, entity: str,
                    date_from: date, date_to: date,
                    lane: str = "delta", skip_if_synced: bool = False) -> dict:
    """Pull one date window for one entity into trx_raw_staging. Idempotent.
    skip_if_synced: skip view fetch for docs already staged (full-scan backfill
    optimization; index row is still upserted so status stays fresh)."""
    cfg = TRX_INDEX_VIEW[entity]
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    stats: typing.Dict[str, typing.Any] = {"pulled": 0, "views": 0, "surrogate": 0, "promoted": 0}
    pending_counts: typing.Dict[tuple, int] = {}
    try:
        cur.execute(
            "INSERT INTO sync_history (entity_type, status, company_id) VALUES (%s, %s, %s) RETURNING id",
            (f"TRX_{entity}", "STARTED", company_id))
        _row = cur.fetchone()
        history_id = _row["id"] if _row else None
        conn.commit()

        _set_watermark(cur, company_id, entity, lane, None, "running")
        conn.commit()

        has_error = False
        error_msg = ""
        for row in _iter_index_rows(client, cfg, date_from, date_to):
            try:
                doc_num, surrogate = _doc_key(cfg, row)
                doc_date = _parse_date(row.get(cfg["doc_date_field"]))
                status_val = row.get(cfg["status_field"])

                payload = dict(row)
                if cfg["view"] and not surrogate:
                    if skip_if_synced and not surrogate:
                        cur.execute(
                            "SELECT 1 FROM trx_raw_staging WHERE company_id=%s AND entity_type=%s AND doc_num=%s",
                            (company_id, entity, doc_num))
                        if cur.fetchone():
                            stats["skipped"] = stats.get("skipped", 0) + 1
                            continue
                    try:
                        time.sleep(RATE_LIMIT_SECONDS)
                        encoded = urllib.parse.quote(str(doc_num), safe="")
                        body = client.get(f"{cfg['index_path']}/{encoded}")
                        result = body.get("result")
                        if isinstance(result, dict) and result:
                            payload = result
                            stats["views"] += 1
                    except CircuitBreakerOpenException:
                        raise
                    except Exception:
                        # view failed -> keep index row as payload (header-only)
                        payload = dict(row)
                        payload["_view_error"] = True

                execute_values(cur, """
                    INSERT INTO trx_raw_staging (company_id, entity_type, doc_num, doc_date, status, payload, synced_at)
                    VALUES %s ON CONFLICT (company_id, entity_type, doc_num) DO UPDATE SET
                        doc_date = EXCLUDED.doc_date, status = EXCLUDED.status,
                        payload = EXCLUDED.payload, synced_at = EXCLUDED.synced_at
                """, [(company_id, entity, doc_num, doc_date, status_val,
                       json.dumps(payload, default=str), datetime.now(timezone.utc))])
                if surrogate and cfg.get("nullable_doc_num"):
                    gk = _surrogate_group_key(cfg, row)
                    pending_counts[gk] = pending_counts.get(gk, 0) + 1
                stats["surrogate" if surrogate else "pulled"] += 1
                conn.commit()
            except CircuitBreakerOpenException:
                has_error, error_msg = True, "Circuit breaker opened during TRX pull."
                break
            except Exception as row_err:
                cur.execute(
                    "INSERT INTO dlq_logs (entity_type, raw_payload, error_reason) VALUES (%s, %s, %s)",
                    (f"TRX_{entity}", json.dumps(row, default=str), str(row_err)))
                conn.commit()

        if not has_error:
            removed = _reconcile_surrogates(cur, company_id, entity, cfg,
                                            date_from, date_to, pending_counts)
            if removed:
                stats["surrogate_removed"] = removed
            conn.commit()

        status = "FAILED" if has_error else "SUCCESS"
        cur.execute(
            "UPDATE sync_history SET status=%s, records_processed=%s, error_message=%s, completed_at=%s WHERE id=%s",
            (status, stats["pulled"], error_msg, datetime.now(timezone.utc), history_id))
        if lane == "delta":
            _advance_delta_watermark(cur, company_id, entity,
                                     date_to if not has_error else None)
        else:
            _set_watermark(cur, company_id, entity, lane,
                           date_to if not has_error else None,
                           "failed" if has_error else "idle")
        conn.commit()
        stats["status"] = status
        return stats
    finally:
        cur.close()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────
# Lane B: delta sync (rolling T-2 -> T)
# ─────────────────────────────────────────────────────────────────────────

def _due_trx_entities(cur) -> list:
    cur.execute("""
        SELECT entity_type FROM md_sync_schedules
        WHERE enabled = true AND entity_type LIKE 'TRX_%%'
          AND (last_synced_at IS NULL OR last_synced_at + (interval_minutes || ' minutes')::interval <= NOW())
    """)
    return [r["entity_type"][4:] for r in cur.fetchall()]


@celery_app.task(bind=True, name="app.services.trx_engine.delta_sync_trx")
def delta_sync_trx(self):
    """Daily delta for all companies (sequential) for TRX entities that are due."""
    if not is_within_operational_window():
        return "Outside operational window (03:00-08:00 WIB) - delta sync skipped"
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if not _is_engine_enabled(cur):
            return "Engine disabled; delta skipped"
        _stale_running_cleanup(cur)
        conn.commit()
        due = _due_trx_entities(cur)
        if not due:
            return "No TRX entities due"

        cur.execute("""
            SELECT id, esb_company_code, esb_username, esb_password
            FROM company_configs WHERE is_active = true AND esb_company_code IS NOT NULL
        """)
        companies = cur.fetchall()

        today = date.today()
        window_from = today - timedelta(days=DELTA_WINDOW_DAYS)
        results = {}
        for co in companies:
            if not _is_engine_enabled(cur):
                break
            code = co["esb_company_code"]
            username = co["esb_username"] or ESB_FALLBACK_USERNAME
            password = co["esb_password"] or ESB_FALLBACK_PASSWORD
            if not (username and password):
                continue
            try:
                token = _auth_locked_company_token(code, username, password)
                client = ESBClient(token, code, username, password)
            except Exception as auth_err:
                cur.execute(
                    "INSERT INTO sync_history (entity_type, status, company_id, error_message, completed_at) VALUES (%s,%s,%s,%s,%s)",
                    ("TRX_AUTH", "FAILED", co["id"], str(auth_err), datetime.now(timezone.utc)))
                conn.commit()
                continue
            for entity in due:
                if entity not in TRX_INDEX_VIEW:
                    continue
                try:
                    cfg = TRX_INDEX_VIEW[entity]
                    if cfg["date_filter"] is None:
                        # No server date filter: full re-pull upsert (index-only or
                        # skip_if_synced views). Window args are local filters only.
                        stats = pull_trx_window(co["id"], client, entity, window_from, today,
                                                lane="delta", skip_if_synced=True)
                    else:
                        stats = pull_trx_window(co["id"], client, entity, window_from, today, lane="delta")
                    results[f"{code}:{entity}"] = stats.get("pulled", 0)
                except Exception as e:
                    results[f"{code}:{entity}"] = f"ERROR: {e}"
        # mark schedule rows synced
        for entity in due:
            cur.execute("UPDATE md_sync_schedules SET last_synced_at = NOW(), updated_at = NOW() WHERE entity_type = %s",
                        (f"TRX_{entity}",))
        conn.commit()
        return results
    finally:
        cur.close()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────
# Lane A: Historical (monthly chunks, 24/7 every 25 min, checkpoint resume)
# Lane C: Real-time (T-0 current day, every 5 minutes)
# ─────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────
# Lane C: Real-time sync (T-0, every 5 minutes)
# ─────────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="app.services.trx_engine.realtime_sync_trx")
def realtime_sync_trx(self):
    """Real-time sync for all companies: pulls T-0 (current day) data every 5 minutes.
    This ensures today's transactions are available immediately without waiting for
    the daily delta or historical backfill lanes."""
    if not is_within_operational_window():
        return "Outside operational window (03:00-08:00 WIB) - realtime sync skipped"
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if not _is_engine_enabled(cur):
            return "Engine disabled; realtime skipped"
        _stale_running_cleanup(cur)
        conn.commit()

        cur.execute("""
            SELECT id, esb_company_code, esb_username, esb_password
            FROM company_configs WHERE is_active = true AND esb_company_code IS NOT NULL
        """)
        companies = cur.fetchall()

        today = date.today()
        results = {}
        for co in companies:
            if not _is_engine_enabled(cur):
                break
            code = co["esb_company_code"]
            username = co["esb_username"] or ESB_FALLBACK_USERNAME
            password = co["esb_password"] or ESB_FALLBACK_PASSWORD
            if not (username and password):
                continue
            try:
                token = _auth_locked_company_token(code, username, password)
                client = ESBClient(token, code, username, password)
            except Exception as auth_err:
                cur.execute(
                    "INSERT INTO sync_history (entity_type, status, company_id, error_message, completed_at) VALUES (%s,%s,%s,%s,%s)",
                    ("TRX_REALTIME_AUTH", "FAILED", co["id"], str(auth_err), datetime.now(timezone.utc)))
                conn.commit()
                continue
            # Pull all TRX entities for today only
            for entity in TRX_INDEX_VIEW:
                try:
                    cfg = TRX_INDEX_VIEW[entity]
                    # For entities without server-side date filter, pull full index
                    # For others, pull only today's date range
                    if cfg["date_filter"] is None:
                        stats = pull_trx_window(co["id"], client, entity, today, today,
                                                lane="realtime", skip_if_synced=True)
                    else:
                        stats = pull_trx_window(co["id"], client, entity, today, today, lane="realtime")
                    results[f"{code}:{entity}"] = stats.get("pulled", 0)
                except Exception as e:
                    results[f"{code}:{entity}"] = f"ERROR: {e}"
        return results
    finally:
        cur.close()
        conn.close()


@celery_app.task(bind=True, name="app.services.trx_engine.backfill_entity")
def backfill_entity(self, company_id: int, entity: str):
    """Process up to MAX_MONTHS_PER_RUN months for one (company, entity), then
    re-enqueue itself while work remains. Lane A runs continuously 24/7."""
    if not is_within_operational_window():
        return "Outside operational window (03:00-08:00 WIB) - backfill paused"
    
    if entity not in TRX_INDEX_VIEW:
        return f"Unknown entity {entity}"
    # Phase 1 priorities: COGS + usage ratio analysis entities
    # Added 2026-09-02: ITEM_JOURNAL, PURCHASE_INVOICE, GOODS_RECEIPT, GOODS_DELIVERY,
    # PURCHASE_ORDER, SIMPLE_MANUFACTURING, PURCHASE_RETURN, GOODS_RECEIPT_RETURN, STOCK_OPNAME
    priority_entities = (
        # Sales transactions (COGS analysis)
        "PRODUCT_SALES",
        # Purchase transactions (COGS purchase cost)
        "PURCHASE_INVOICE",
        "GOODS_RECEIPT",
        "PURCHASE_ORDER",
        "PURCHASE_RETURN",
        "GOODS_RECEIPT_RETURN",
        # Manufacturing (COGS production cost)
        "SIMPLE_MANUFACTURING",
        # Inventory movements (usage ratio)
        "ITEM_JOURNAL",
        "GOODS_DELIVERY",
        "STOCK_OPNAME",
        # Report (GR Recap - already active)
        "RPT_GOODS_RECEIPT_RECAPITULATION",
    )
    if entity not in priority_entities:
        return f"Temporarily paused non-priority TRX entity {entity}"
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if not _is_engine_enabled(cur):
            return "Engine disabled; backfill paused"
        if not _is_backfill_allowed():
            return "Outside night window; backfill will resume via router"

        cur.execute("SELECT esb_company_code, esb_username, esb_password FROM company_configs WHERE id = %s",
                    (company_id,))
        co = cur.fetchone()
        if not co:
            return f"Company {company_id} not found"
        code = co["esb_company_code"]
        username = co["esb_username"] or ESB_FALLBACK_USERNAME
        password = co["esb_password"] or ESB_FALLBACK_PASSWORD

        lock = _company_lock(company_id)
        if not lock.acquire(blocking=False):
            # Another task is already backfilling this company -> retry later.
            backfill_entity.apply_async((company_id, entity), countdown=600)
            return f"{code}:{entity} busy (company lock held); re-enqueued +10min"

        today = date.today()
        converge_to = today - timedelta(days=DELTA_WINDOW_DAYS)  # delta lane owns T-2..T

        cfg = TRX_INDEX_VIEW[entity]
        client = ESBClient(_auth_locked_company_token(code, username, password),
                           code, username, password)

        # FULL-SCAN MODE: entities without server-side date filtering cannot be
        # backfilled month-by-month (every chunk would re-page the full index).
        # One full pass instead; delta lane keeps it fresh afterwards.
        if cfg["date_filter"] is None:
            wm = _get_watermark(cur, company_id, entity, "backfill")
            if wm and wm["status"] == "done":
                return f"{code}:{entity} full-scan already done"
            _set_watermark(cur, company_id, entity, "backfill", None, "running")
            conn.commit()
            start_val = _parse_date(BACKFILL_START)
            assert start_val is not None and converge_to is not None
            stats = pull_trx_window(company_id, client, entity,
                                    date_from=start_val, date_to=converge_to,
                                    lane="backfill", skip_if_synced=True)
            if stats.get("status") == "FAILED":
                _set_watermark(cur, company_id, entity, "backfill", None, "failed")
                conn.commit()
                return f"{code}:{entity} full-scan FAILED; retry next night"
            _set_watermark(cur, company_id, entity, "backfill", converge_to, "done")
            conn.commit()
            return f"{code}:{entity} full-scan complete: {stats.get('pulled')} pulled, {stats.get('skipped', 0)} skipped"

        wm = _get_watermark(cur, company_id, entity, "backfill")
        start_from = BACKFILL_START
        if wm and wm["watermark_date"]:
            nxt = wm["watermark_date"] + timedelta(days=1)
            start_from = nxt.isoformat()
        start = _parse_date(start_from)
        assert start is not None and converge_to is not None

        chunks = list(_month_chunks(start, converge_to))
        if not chunks:
            _set_watermark(cur, company_id, entity, "backfill", converge_to, "done")
            conn.commit()
            return f"{code}:{entity} backfill converged"

        processed = 0
        for (m_start, m_end) in chunks:
            if processed >= MAX_MONTHS_PER_RUN or not _is_backfill_allowed():
                break
            if not _is_engine_enabled(cur):
                _set_watermark(cur, company_id, entity, "backfill", None, "paused")
                conn.commit()
                return f"{code}:{entity} paused (engine disabled)"
            stats = pull_trx_window(company_id, client, entity, m_start, m_end, lane="backfill")
            if stats.get("status") == "FAILED":
                _set_watermark(cur, company_id, entity, "backfill", None, "failed")
                conn.commit()
                return f"{code}:{entity} month {m_start} FAILED; will retry next night"
            _set_watermark(cur, company_id, entity, "backfill", m_end, "running")
            conn.commit()
            processed += 1
            try:
                lock.reacquire()   # keep TTL fresh for the next chunk
            except Exception:
                pass

        remaining = list(_month_chunks((m_end + timedelta(days=1)) if processed else start, converge_to))
        if remaining and _is_backfill_allowed():
            try:
                lock.release()    # hand the company over to the chained task
            except Exception:
                pass
            backfill_entity.delay(company_id, entity)  # round-robin fairness
            return f"{code}:{entity} processed {processed} month(s); re-enqueued"
        if not remaining:
            _set_watermark(cur, company_id, entity, "backfill", converge_to, "done")
            conn.commit()
            return f"{code}:{entity} backfill converged"
        return f"{code}:{entity} processed {processed} month(s); window closed"
    finally:
        try:
            if 'lock' in locals() and lock.locked() and lock.local.token:
                lock.release()
        except Exception:
            pass
        cur.close()
        conn.close()


@celery_app.task(name="app.services.trx_engine.backfill_router")
def backfill_router():
    """Lane A router: dispatches historical backfill every 25 minutes for every
    company x entity not yet converged."""
    if not is_within_operational_window():
        return "Outside operational window (03:00-08:00 WIB) - backfill router skipped"
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if not _is_engine_enabled(cur):
            return "Engine disabled"
        _stale_running_cleanup(cur)
        conn.commit()
        # CALF-first round-robin: PT Yuda Prawira Group (id=1) dispatched first,
        # remaining companies follow in stable id order; the per-company lock
        # (bf_company_{id}) lets the top-N companies run in parallel.
        cur.execute("""
            SELECT id FROM company_configs
            WHERE is_active = true AND esb_company_code IS NOT NULL
            ORDER BY (id = 1) DESC, id
        """)
        companies = [r["id"] for r in cur.fetchall()]
        today = date.today()
        converge_to = today - timedelta(days=DELTA_WINDOW_DAYS)
        dispatched = []
        for company_id in companies:
            company_pending = 0

            # Count pending entities for this company
            for entity in TRX_INDEX_VIEW:
                wm = _get_watermark(cur, company_id, entity, "backfill")
                if not wm or not wm["watermark_date"] or wm["watermark_date"] < converge_to:
                    company_pending += 1
            for entity in RPT_DIRECT:
                wm = _get_watermark(cur, company_id, entity, "backfill")
                if not wm or wm.get("status") != "done":
                    company_pending += 1

            # If the company is locked (actively running), skip it and continue to next company
            # This ensures all unlocked companies get processed even if some are running
            if _company_locked(company_id):
                print(f"Company {company_id} is locked, skipping to next company...")
                continue

            # If we reach here, the company is NOT locked.
            # Let's dispatch pending entities for this company.
            for entity in TRX_INDEX_VIEW:
                wm = _get_watermark(cur, company_id, entity, "backfill")
                if not wm or not wm["watermark_date"] or wm["watermark_date"] < converge_to:
                    if wm and wm["status"] == "running" and wm.get("updated_at") \
                            and (datetime.now(timezone.utc) - wm["updated_at"]).total_seconds() < 6 * 3600:
                        continue
                    backfill_entity.delay(company_id, entity)
                    dispatched.append(f"{company_id}:{entity}")

            for entity in RPT_DIRECT:
                wm = _get_watermark(cur, company_id, entity, "backfill")
                if not wm or wm.get("status") != "done":
                    rpt_backfill_entity.delay(company_id, entity)
                    dispatched.append(f"{company_id}:{entity}")
                
        return f"Dispatched {len(dispatched)}: {dispatched}"
    finally:
        cur.close()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────
# Completeness audit (self-healing)
# ─────────────────────────────────────────────────────────────────────────

def _api_bucket_counts(client: ESBClient, cfg: dict, buckets: list) -> dict:
    """Count API index rows per date bucket. For server-filtered entities this is
    one small request per bucket; for unfilterable entities (PURCHASE_REQUEST)
    the full index is pulled ONCE and grouped locally."""
    counts = {b: 0 for b in buckets}
    bucket_set = {b.isoformat() for b in buckets}
    if cfg["date_filter"]:
        for b in buckets:
            rows = _iter_index_rows(client, cfg, b, b)
            counts[b] = sum(1 for _ in rows)
    else:
        for row in _iter_index_rows_all(client, cfg):
            d = _parse_date(row.get(cfg["doc_date_field"]))
            if d and d.isoformat() in bucket_set:
                counts[d] += 1
    return counts


def _iter_index_rows_all(client: ESBClient, cfg: dict):
    """Full pagination without any date filtering."""
    page = 1
    total_pages = 1
    while page <= total_pages:
        body = client.get(cfg["index_path"], params={"page": page, "limit": PAGE_SIZE})
        rows, total_pages = _extract_page(body, "envelope")
        for row in rows:
            yield row
        page += 1
        time.sleep(PAGE_SLEEP_SECONDS)


@celery_app.task(name="app.services.trx_engine.completeness_audit")
def completeness_audit():
    """Daily 07:15 WIB: compare API index count vs staging count for each SETTLED
    date bucket [T-7, T-3]; mismatched buckets are re-pulled immediately.

    Settled = the engine claims coverage of the bucket: either the backfill
    watermark has passed it, or the bucket falls inside the delta window
    (T-2..T). Buckets in between (backfill not converged yet) are logged as
    PENDING_BACKFILL without re-pull — the nightly backfill owns them."""
    if not is_within_operational_window():
        return "Outside operational window (03:00-08:00 WIB) - completeness audit skipped"
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if not _is_engine_enabled(cur):
            return "Engine disabled"
        cur.execute("""
            SELECT id, esb_company_code, esb_username, esb_password
            FROM company_configs WHERE is_active = true AND esb_company_code IS NOT NULL
        """)
        companies = cur.fetchall()
        today = date.today()
        buckets = [today - timedelta(days=d) for d in range(7, 2, -1)]  # T-7..T-3
        delta_floor = today - timedelta(days=DELTA_WINDOW_DAYS)
        summary = {}
        for co in companies:
            code = co["esb_company_code"]
            username = co["esb_username"] or ESB_FALLBACK_USERNAME
            password = co["esb_password"] or ESB_FALLBACK_PASSWORD
            if not (username and password):
                continue
            try:
                token = _auth_locked_company_token(code, username, password)
                client = ESBClient(token, code, username, password)
            except Exception:
                continue
            for entity, cfg in TRX_INDEX_VIEW.items():
                bf_wm = _get_watermark(cur, co["id"], entity, "backfill")
                bf_date = bf_wm["watermark_date"] if bf_wm else None
                # pre-check coverage per bucket: settled only when backfill passed
                # the bucket or the bucket is inside the delta window
                settled_buckets = [b for b in buckets
                                   if (bf_date and b <= bf_date) or b >= delta_floor]
                pending_buckets = [b for b in buckets if b not in settled_buckets]
                for b in pending_buckets:
                    cur.execute("""
                        INSERT INTO report_reconciliation_log (company_id, entity_type, bucket_date, api_count, staging_count, status)
                        VALUES (%s, %s, %s, NULL, NULL, 'PENDING_BACKFILL')
                    """, (co["id"], entity, b))
                    conn.commit()
                if not settled_buckets:
                    continue
                try:
                    api_counts = _api_bucket_counts(client, cfg, settled_buckets)
                except Exception:
                    continue
                for bucket, api_count in api_counts.items():
                    cur.execute(
                        "SELECT count(*) AS n FROM trx_raw_staging WHERE company_id=%s AND entity_type=%s AND doc_date=%s",
                        (co["id"], entity, bucket))
                    row = cur.fetchone()
                    staging_count = row["n"] if row else 0
                    status = "MATCH" if api_count == staging_count else "MISMATCH"
                    cur.execute("""
                        INSERT INTO report_reconciliation_log (company_id, entity_type, bucket_date, api_count, staging_count, status)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (co["id"], entity, bucket, api_count, staging_count, status))
                    conn.commit()
                    if status == "MISMATCH":
                        try:
                            pull_trx_window(co["id"], client, entity, bucket, bucket, lane="delta")
                            cur.execute(
                                "SELECT count(*) AS n FROM trx_raw_staging WHERE company_id=%s AND entity_type=%s AND doc_date=%s",
                                (co["id"], entity, bucket))
                            row = cur.fetchone()
                            after = row["n"] if row else 0
                            cur.execute("""
                                INSERT INTO report_reconciliation_log (company_id, entity_type, bucket_date, api_count, staging_count, status, staging_after)
                                VALUES (%s, %s, %s, %s, %s, 'REPOILED', %s)
                            """, (co["id"], entity, bucket, api_count, staging_count, after))
                            conn.commit()
                        except Exception:
                            pass
                    key = f"{code}:{entity}"
                    s = summary.setdefault(key, {"match": 0, "mismatch": 0})
                    s["match" if status == "MATCH" else "mismatch"] += 1
        return summary
    finally:
        cur.close()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────
# Direct period-based reports -> report_raw_staging (period-shaped table)
# ─────────────────────────────────────────────────────────────────────────

RPT_DIRECT: typing.Dict[str, dict] = {
    "RPT_STOCK_MOVEMENT": {
        "path": "/report/stock-movement",
        "params_for": lambda d: {"startPeriod": d.isoformat(), "endPeriod": d.isoformat()},
        "window_days": 7,   # T-7 -> T daily refresh
    },
    "RPT_SALES_PAYMENT_SUMMARY": {
        "path": "/report/sales-payment-summary",
        "params_for": lambda d: {"salesDate": d.isoformat()},
        "window_days": 2,   # yesterday + today
    },
    # ── Priority Reports (Sprint 4) ──────────────────────────────────────────
    # Goods Receipt Recapitulation Report - Rekapitulasi penerimaan barang
    "RPT_GOODS_RECEIPT_RECAPITULATION": {
        "path": "/report/goods-receipt-recapitulation",
        "params_for": lambda d: {"dateFrom": d.isoformat(), "dateTo": d.isoformat()},
        "window_days": 2,   # yesterday + today (T-2 -> T)
    },
}


def _iter_rpt_rows(client: ESBClient, cfg: dict, d: date):
    """Yield rows of a direct report for one date bucket (envelope-paginated).
    sales-payment-summary returns a plain list (not envelope): handled by
    _extract_page's array fallback inside envelope branch check."""
    page = 1
    total_pages = 1
    while page <= total_pages:
        params = {"page": page, "limit": PAGE_SIZE}
        params.update(cfg["params_for"](d))
        body = client.get(cfg["path"], params=params)
        result = body.get("result")
        if isinstance(result, dict):
            rows = result.get("data") or []
            count = result.get("count", 0)
            total_pages = max(1, math.ceil((count or len(rows)) / PAGE_SIZE))
        else:
            rows = result or []
            total_pages = 1
        for r in rows:
            yield r
        page += 1
        time.sleep(PAGE_SLEEP_SECONDS)


@celery_app.task(name="app.services.trx_engine.sync_direct_reports")
def sync_direct_reports():
    """DEEP refresh (daily 06:00 WIB): dispatch one per-company report task per
    active company (parallel). Each report entity uses its configured
    window_days (T-7 for stock movement, T-2 for sales-payment summary)."""
    if not is_within_operational_window():
        return "Outside operational window (03:00-08:00 WIB) - direct reports skipped"
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if not _is_engine_enabled(cur):
            return "Engine disabled"
        cur.execute("""
            SELECT id FROM company_configs WHERE is_active = true AND esb_company_code IS NOT NULL
            ORDER BY (id = 1) DESC, id
        """)
        ids = [r["id"] for r in cur.fetchall()]
        for company_id in ids:
            sync_direct_reports_company.delay(company_id, None)   # None = cfg window (deep)
        return f"Dispatched deep report sync for {len(ids)} companies"
    finally:
        cur.close()
        conn.close()


@celery_app.task(name="app.services.trx_engine.sync_direct_reports_delta")
def sync_direct_reports_delta():
    """LIVE delta (every 30 min): dispatch per-company report tasks with a small
    T-1..T window so fresh data lands without re-pulling the whole T-7 range."""
    if not is_within_operational_window():
        return "Outside operational window (03:00-08:00 WIB) - direct reports delta skipped"
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if not _is_engine_enabled(cur):
            return "Engine disabled"
        cur.execute("""
            SELECT id FROM company_configs WHERE is_active = true AND esb_company_code IS NOT NULL
            ORDER BY (id = 1) DESC, id
        """)
        ids = [r["id"] for r in cur.fetchall()]
        for company_id in ids:
            sync_direct_reports_company.delay(company_id, 1)      # T-1..T only
        return f"Dispatched delta report sync for {len(ids)} companies"
    finally:
        cur.close()
        conn.close()


@celery_app.task(name="app.services.trx_engine.sync_direct_reports_company")
def sync_direct_reports_company(company_id: int, window_days: typing.Optional[int]):
    """Pull direct period-based reports for ONE company into report_raw_staging
    (idempotent on the existing period+branch unique key). window_days=None
    uses each entity's configured window (deep); an int overrides it (delta)."""
    if not is_within_operational_window():
        return "Outside operational window (03:00-08:00 WIB) - direct reports company sync skipped"
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if not _is_engine_enabled(cur):
            return "Engine disabled"
        cur.execute("SELECT id, esb_company_code, esb_username, esb_password FROM company_configs WHERE id = %s",
                    (company_id,))
        co = cur.fetchone()
        if not co:
            return f"Company {company_id} not found"
        code = co["esb_company_code"]
        username = co["esb_username"] or ESB_FALLBACK_USERNAME
        password = co["esb_password"] or ESB_FALLBACK_PASSWORD
        if not (username and password):
            return f"{code}: no credentials"
        try:
            token = _auth_locked_company_token(code, username, password)
            client = ESBClient(token, code, username, password)
        except Exception as e:
            return f"{code}: auth failed {str(e)[:120]}"
        today = date.today()
        results = {}
        for entity, cfg in RPT_DIRECT.items():
            cur.execute(
                "INSERT INTO sync_history (entity_type, status, company_id) VALUES (%s, %s, %s) RETURNING id",
                (entity, "STARTED", co["id"]))
            _row = cur.fetchone()
            history_id = _row["id"] if _row else None
            conn.commit()
            pulled, has_error, err = 0, False, ""
            back_days = cfg["window_days"] if window_days is None else window_days
            for back in range(back_days, -1, -1):
                d = today - timedelta(days=back)
                try:
                    rows = list(_iter_rpt_rows(client, cfg, d))
                except Exception as e:
                    has_error, err = True, str(e)[:200]
                    break
                # Group lines by branch so storage fits the period+branch
                # unique key of report_raw_staging (one row per branch/day).
                by_branch: typing.Dict[str, list] = {}
                for r in rows:
                    b_code = str(r.get("branchCode") or r.get("branchName") or "")[:50]
                    by_branch.setdefault(b_code, []).append(r)
                for b_code, lines in by_branch.items():
                    cur.execute("""
                        INSERT INTO report_raw_staging (company_id, report_type, period_start, period_end, branch_esb_id, raw_data, source_params, fetched_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (company_id, report_type, period_start, period_end, branch_esb_id) DO UPDATE SET
                            raw_data = EXCLUDED.raw_data, fetched_at = EXCLUDED.fetched_at
                    """, (co["id"], entity, d, d, b_code,
                          json.dumps({"salesDate": d.isoformat(), "lines": lines}, default=str),
                          json.dumps({k: v for k, v in cfg["params_for"](d).items()}, default=str),
                          datetime.now(timezone.utc)))
                    pulled += len(lines)
                conn.commit()
            status = "FAILED" if has_error else "SUCCESS"
            cur.execute(
                "UPDATE sync_history SET status=%s, records_processed=%s, error_message=%s, completed_at=%s WHERE id=%s",
                (status, pulled, err, datetime.now(timezone.utc), history_id))
            conn.commit()
            results[entity] = pulled if not has_error else f"ERROR {err}"
        return {code: results}
    finally:
        cur.close()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────
# Sprint 3: historical backfill for direct period-based reports
# (RPT_STOCK_MOVEMENT, nightly, per company, company-locked)
# ─────────────────────────────────────────────────────────────────────────

RPT_BACKFILL_CHUNK_DAYS = 15   # days per task invocation (fairness)


@celery_app.task(name="app.services.trx_engine.rpt_backfill_entity")
def rpt_backfill_entity(company_id: int, entity: str = "RPT_STOCK_MOVEMENT"):
    """Historical backfill of a direct report into report_raw_staging.

    Walks day-by-day from the checkpoint (or BACKFILL_START / the earliest
    already-stored period) forward to T-{window_days}, RPT_BACKFILL_CHUNK_DAYS
    per invocation, then re-enqueues itself. Lane A runs continuously 24/7.
    Uses the same per-company Redis lock as TRX backfill."""
    if not is_within_operational_window():
        return "Outside operational window (03:00-08:00 WIB) - RPT backfill paused"
    
    cfg = RPT_DIRECT.get(entity)
    if not cfg:
        return f"Unknown RPT entity {entity}"
    # Phase 1 priorities: all report entities needed for analysis
    # Added 2026-09-02: RPT_STOCK_MOVEMENT, RPT_SALES_PAYMENT_SUMMARY
    priority_entities = (
        "PRODUCT_SALES",
        "RPT_GOODS_RECEIPT_RECAPITULATION",
        "RPT_STOCK_MOVEMENT",
        "RPT_SALES_PAYMENT_SUMMARY",
    )
    if entity not in priority_entities:
        return f"Temporarily paused non-priority RPT entity {entity}"
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    lock = None
    try:
        if not _is_engine_enabled(cur):
            return "Engine disabled; RPT backfill paused"
        if not _is_backfill_allowed():
            return "Outside night window; RPT backfill will resume via router"
        cur.execute("SELECT esb_company_code, esb_username, esb_password FROM company_configs WHERE id = %s",
                    (company_id,))
        co = cur.fetchone()
        if not co:
            return f"Company {company_id} not found"
        code = co["esb_company_code"]
        username = co["esb_username"] or ESB_FALLBACK_USERNAME
        password = co["esb_password"] or ESB_FALLBACK_PASSWORD

        # Use a separate lock for RPT so it can run parallel to TRX for the same company
        lock = _redis().lock(f"bf_company_rpt_{company_id}", timeout=600)
        if not lock.acquire(blocking=False):
            rpt_backfill_entity.apply_async((company_id, entity), countdown=600)
            return f"{code}:{entity} busy (RPT company lock held); re-enqueued +10min"

        today = date.today()
        converge_to = today - timedelta(days=cfg["window_days"])  # delta refresh owns the rest

        wm = _get_watermark(cur, company_id, entity, "backfill")
        start = _parse_date(BACKFILL_START)
        assert start is not None and converge_to is not None
        if wm and wm["watermark_date"]:
            start = wm["watermark_date"] + timedelta(days=1)
        else:
            # resume from the earliest staged period if it is newer than BACKFILL_START
            cur.execute("""SELECT min(period_start) AS d FROM report_raw_staging
                           WHERE company_id = %s AND report_type = %s""", (company_id, entity))
            row = cur.fetchone()
            if row and row["d"]:
                start = min(start, row["d"])

        end = min(start + timedelta(days=RPT_BACKFILL_CHUNK_DAYS - 1), converge_to)
        if start > converge_to:
            _set_watermark(cur, company_id, entity, "backfill", converge_to, "done")
            conn.commit()
            return f"{code}:{entity} RPT backfill converged"

        token = _auth_locked_company_token(code, username, password)
        client = ESBClient(token, code, username, password)

        pulled = 0
        has_error, err = False, ""
        _set_watermark(cur, company_id, entity, "backfill", None, "running")
        conn.commit()
        d = start
        while d <= end and _is_backfill_allowed():
            try:
                rows = list(_iter_rpt_rows(client, cfg, d))
            except Exception as e:
                has_error, err = True, str(e)[:200]
                break
            by_branch: typing.Dict[str, list] = {}
            for r in rows:
                b_code = str(r.get("branchCode") or r.get("branchName") or "")[:50]
                by_branch.setdefault(b_code, []).append(r)
            for b_code, lines in by_branch.items():
                cur.execute("""
                    INSERT INTO report_raw_staging (company_id, report_type, period_start, period_end, branch_esb_id, raw_data, source_params, fetched_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (company_id, report_type, period_start, period_end, branch_esb_id) DO UPDATE SET
                        raw_data = EXCLUDED.raw_data, fetched_at = EXCLUDED.fetched_at
                """, (company_id, entity, d, d, b_code,
                      json.dumps({"salesDate": d.isoformat(), "lines": lines}, default=str),
                      json.dumps({k: v for k, v in cfg["params_for"](d).items()}, default=str),
                      datetime.now(timezone.utc)))
                pulled += len(lines)
            conn.commit()
            try:
                lock.reacquire()
            except Exception:
                pass
            d += timedelta(days=1)

        if has_error:
            _set_watermark(cur, company_id, entity, "backfill", None, "failed")
            conn.commit()
            return f"{code}:{entity} RPT backfill FAILED at {d}: {err}"
        _set_watermark(cur, company_id, entity, "backfill", end, "running")
        conn.commit()

        if end < converge_to and _is_backfill_allowed():
            try:
                lock.release()
            except Exception:
                pass
            rpt_backfill_entity.delay(company_id, entity)
            return f"{code}:{entity} RPT backfill {start}..{end} ({pulled} lines); re-enqueued"
        if end >= converge_to:
            _set_watermark(cur, company_id, entity, "backfill", converge_to, "done")
            conn.commit()
            return f"{code}:{entity} RPT backfill converged"
        return f"{code}:{entity} RPT backfill {start}..{end} ({pulled} lines); window closed"
    finally:
        try:
            if lock is not None and lock.local.token:
                lock.release()
        except Exception:
            pass
        cur.close()
        conn.close()
