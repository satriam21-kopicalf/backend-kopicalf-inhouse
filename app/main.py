import typing
from typing import Any
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="CALF Ecosystem Backend")

# Include routers
from app.routers import stock_waste
app.include_router(stock_waste.router)

# Allow CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "calf-backend"}

@app.get("/api/v1/trx/status")
async def trx_status():
    """Dual-lane TRX engine status: watermarks per company x entity x lane,
    staging counts, and the latest reconciliation results."""
    from app.core.db import get_db_connection
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT w.company_id, c.esb_company_code, c.company_name, w.entity_type, w.lane,
                   w.watermark_date, w.status, w.updated_at
            FROM sync_watermarks w
            JOIN company_configs c ON c.id = w.company_id
            ORDER BY w.company_id, w.entity_type, w.lane
        """)
        watermarks = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT company_id, entity_type, count(*) AS row_count,
                   min(doc_date) AS earliest, max(doc_date) AS latest, max(synced_at) AS last_sync
            FROM trx_raw_staging GROUP BY company_id, entity_type ORDER BY 1, 2
        """)
        staging = [dict(r) for r in cur.fetchall()]

        # Direct period-based reports (line counts live inside raw_data JSON lines[])
        cur.execute("""
            SELECT company_id, report_type AS entity_type, count(*) AS row_count,
                   min(period_start) AS earliest, max(period_start) AS latest,
                   max(fetched_at) AS last_sync,
                   coalesce(sum(json_array_length(raw_data::json->'lines')), 0) AS line_count
            FROM report_raw_staging
            WHERE report_type LIKE 'RPT_%'
            GROUP BY company_id, report_type ORDER BY 1, 2
        """)
        for r in cur.fetchall():
            d = dict(r)
            d["row_count"] = d.pop("line_count") or d["row_count"]
            staging.append(d)

        cur.execute("""
            SELECT company_id, entity_type, status, count(*) AS n
            FROM report_reconciliation_log
            WHERE checked_at > NOW() - INTERVAL '24 hours'
            GROUP BY company_id, entity_type, status
        """)
        recon = [dict(r) for r in cur.fetchall()]

        return {"watermarks": watermarks, "staging": staging, "reconciliation_24h": recon}
    finally:
        cur.close()
        conn.close()

@app.post("/api/v1/trx/delta/run")
async def trx_delta_run():
    """Manually trigger the TRX delta lane (respects due-gating inside the task)."""
    from app.core.worker import celery_app
    celery_app.send_task("app.services.trx_engine.delta_sync_trx")
    return {"status": "triggered"}

@app.post("/api/v1/trx/backfill/run")
async def trx_backfill_run(company_id: int | None = None, entity: str | None = None):
    """Manually enqueue backfill for one (company, entity), or all when omitted.
    Tasks self-gate on the night window; use force=true to bypass for smoke tests."""
    from app.core.db import get_db_connection
    from app.core.worker import celery_app
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if company_id and entity:
            celery_app.send_task("app.services.trx_engine.backfill_entity",
                                 kwargs={"company_id": company_id, "entity": entity})
            return {"status": "triggered", "company_id": company_id, "entity": entity}
        celery_app.send_task("app.services.trx_engine.backfill_router")
        return {"status": "triggered", "message": "backfill_router dispatched"}
    finally:
        cur.close()
        conn.close()

@app.post("/api/v1/trx/direct-reports/run")
async def trx_direct_reports_run():
    """Manually trigger the direct period-based reports sync."""
    from app.core.worker import celery_app
    celery_app.send_task("app.services.trx_engine.sync_direct_reports")
    return {"status": "triggered"}


@app.get("/api/v1/reports/summary")
async def reports_summary():
    """Per-report staging stats: row counts, period coverage, and last sync â€”
    powers the LIVE badges on the Reporting menu."""
    from app.core.db import get_db_connection
    from app.services.reports import REPORTS
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        out = []
        for slug, spec in REPORTS.items():
            if spec["source"] == "rpt":
                cur.execute("""
                    SELECT count(*) AS rows,
                           coalesce(sum(json_array_length(raw_data::json->'lines')), 0) AS lines,
                           min(period_start) AS earliest, max(period_start) AS latest,
                           max(fetched_at) AS last_sync,
                           count(DISTINCT company_id) AS companies
                    FROM report_raw_staging WHERE report_type = %s
                """, (spec["entity"],))
                r = typing.cast(typing.Any, cur.fetchone())
                row_count = r["lines"] or r["rows"] or 0
            else:
                cur.execute("""
                    SELECT count(*) AS rows, NULL::bigint AS lines,
                           min(doc_date) AS earliest, max(doc_date) AS latest,
                           max(synced_at) AS last_sync,
                           count(DISTINCT company_id) AS companies
                    FROM trx_raw_staging WHERE entity_type = %s
                """, (spec["entity"],))
                r = typing.cast(typing.Any, cur.fetchone())
                row_count = r["rows"] or 0
            out.append({
                "slug": slug, "title": spec["title"], "source": spec["source"],
                "row_count": row_count,
                "staging_rows": r["rows"] or 0,
                "companies": r["companies"] or 0,
                "period_from": r["earliest"], "period_to": r["latest"],
                "last_sync": r["last_sync"],
                "live": (r["rows"] or 0) > 0,
            })
        return {"reports": out}
    finally:
        cur.close()
        conn.close()

@app.get("/api/v1/reports")
async def list_reports():
    from app.services.reports import REPORTS
    return [{"slug": slug, "title": spec["title"], "source": spec["source"]}
            for slug, spec in REPORTS.items()]

@app.get("/api/v1/reports/categories")
async def list_report_categories():
    """Get all report categories with their metadata."""
    from app.services.reports import list_reports_by_category, REPORT_CATEGORIES
    return {
        "categories": REPORT_CATEGORIES,
        "grouped_reports": list_reports_by_category(),
    }

@app.get("/api/v1/reports/tiers")
async def list_report_tiers():
    """Get all reports grouped by tier (T1=direct trx, T2=aggregated)."""
    from app.services.reports import list_reports_by_tier
    return {
        "tiers": {
            "T1": {
                "label": "Direct ERP Data",
                "description": "Real-time transaction data from ESB",
                "color": "#3b82f6",  # blue
            },
            "T2": {
                "label": "CALF-Aggregated",
                "description": "Pre-computed reports from ESB",
                "color": "#10b981",  # green
            },
        },
        "reports_by_tier": list_reports_by_tier(),
    }


@app.get("/api/v1/reports/available")
async def get_available_reports(company_id: int = 1):
    """Reports that currently hold consumed data (rows > 0) for a company."""
    from app.services.reports import available_reports
    return available_reports(company_id)


@app.get("/api/v1/reports/{slug}/metadata")
async def get_report_metadata(slug: str):
    """Get full metadata for a specific report."""
    from app.services.reports import get_report_metadata
    metadata = get_report_metadata(slug)
    if not metadata:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Report not found: {slug}")
    return metadata

@app.get("/api/v1/reports/{slug}")
async def get_report(slug: str, company_id: int, date_from: str, date_to: str,
                     branch_esb_id: str | None = None, limit: int = 200, offset: int = 0):
    from datetime import date
    from app.services.reports import run_report
    try:
        return run_report(slug, company_id, branch_esb_id,
                          date.fromisoformat(date_from), date.fromisoformat(date_to),
                          limit=min(limit, 1000), offset=offset)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/v1/exports")
async def create_export(body: dict):
    """body: {slug, company_id, date_from, date_to, branch_esb_id?, branch_label?, requested_by?}"""
    import uuid
    from app.core.db import get_db_connection
    from app.core.worker import celery_app
    from app.services.reports import REPORTS
    slug = body.get("slug")
    if slug not in REPORTS:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Unknown report: {slug}")
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        export_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO export_files (id, company_id, requested_by, report_slug, params, status)
            VALUES (%s, %s, %s, %s, %s, 'pending')
        """, (export_id, body.get("company_id"), body.get("requested_by"), slug,
              __import__("json").dumps({k: body[k] for k in
                                        ("date_from", "date_to", "branch_esb_id", "branch_label") if body.get(k) is not None})))
        conn.commit()
        celery_app.send_task("app.services.export_engine.generate_export",
                             kwargs={"export_id": export_id})
        return {"export_id": export_id, "status": "pending"}
    finally:
        cur.close()
        conn.close()

@app.get("/api/v1/exports/{export_id}")
async def get_export(export_id: str):
    from app.core.db import get_db_connection
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT status, file_path, error_message FROM export_files WHERE id = %s", (export_id,))
        row = cur.fetchone()
        if not row:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="export not found")
        status, file_path, error_message = row
        result = {"status": status}
        if status == "ready" and file_path:
            from app.services.export_engine import make_signed_url
            result["download_url"] = make_signed_url(file_path)
        if error_message:
            result["error"] = error_message
        return result
    finally:
        cur.close()
        conn.close()

from pydantic import BaseModel

class SyncTriggerRequest(BaseModel):
    company_id: int
    module: str
    entities: typing.Optional[typing.List[str]] = None
    date_from: typing.Optional[str] = None
    date_to: typing.Optional[str] = None

@app.post("/sync/trigger")
async def trigger_sync(req: SyncTriggerRequest):
    from app.core.db import get_db_connection
    from app.services.tasks import sync_company_data
    from app.services.trx_engine import backfill_entity, rpt_backfill_entity
    from fastapi import HTTPException
    
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT esb_company_code, esb_username, esb_password FROM company_configs WHERE id = %s", (req.company_id,))
        co = cur.fetchone()
        if not co:
            raise HTTPException(status_code=404, detail="Company not found")
        
        if req.module == "master":
            if req.entities:
                ents = req.entities
            else:
                cur.execute("""
                    SELECT er.entity FROM esb_data.sync_schedules ss
                    JOIN esb_data.endpoint_registry er ON er.id = ss.endpoint_id
                    WHERE ss.company_id = %s AND ss.enabled = true AND ss.module = 'master'
                """, (req.company_id,))
                ents = [r[0] for r in cur.fetchall()]
            sync_company_data.delay(req.company_id, co[0], co[1], co[2], ents)
            return {"status": "triggered", "message": f"Master sync triggered for company {req.company_id}", "entities": ents}
            
        elif req.module == "trx":
            ents = req.entities if req.entities else ["PRODUCT_SALES"]
            for ent in ents:
                backfill_entity.delay(req.company_id, ent)
            return {"status": "triggered", "message": f"TRX backfill triggered for company {req.company_id}", "entities": ents}

        elif req.module == "rpt":
            ents = req.entities if req.entities else ["RPT_GOODS_RECEIPT_RECAPITULATION"]
            for ent in ents:
                rpt_backfill_entity.delay(req.company_id, ent)
            return {"status": "triggered", "message": f"RPT backfill triggered for company {req.company_id}", "entities": ents}
        else:
            raise HTTPException(status_code=400, detail="module must be master, trx, or rpt")
    finally:
        cur.close()
        conn.close()

@app.get("/api/v1/companies")
async def list_companies():
    """List all company configurations including ESB credentials."""
    from app.core.db import get_db_connection
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT id, esb_company_code, company_name, esb_username, esb_password,
                   is_active, created_at, updated_at
            FROM company_configs
            ORDER BY id
        """)
        companies = []
        for r in cur.fetchall():
            row = dict(r)
            # Mask password for display
            if row.get('esb_password'):
                row['esb_password_masked'] = row['esb_password'][:8] + '***'
            companies.append(row)
        return {"companies": companies}
    finally:
        cur.close()
        conn.close()

@app.put("/api/v1/companies/{company_id}")
async def update_company(company_id: int, company: dict):
    """Update company configuration including ESB credentials."""
    from app.core.db import get_db_connection
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Build update query dynamically based on provided fields
        updates = []
        values = []

        if company.get('esb_username') is not None:
            updates.append("esb_username = %s")
            values.append(company['esb_username'])
        if company.get('esb_password') is not None:
            updates.append("esb_password = %s")
            values.append(company['esb_password'])
        if company.get('company_name') is not None:
            updates.append("company_name = %s")
            values.append(company['company_name'])
        if company.get('is_active') is not None:
            updates.append("is_active = %s")
            values.append(company['is_active'])

        if not updates:
            return {"error": "No fields to update"}

        updates.append("updated_at = NOW()")
        values.append(company_id)

        query = f"""
            UPDATE company_configs
            SET {', '.join(updates)}
            WHERE id = %s
            RETURNING id, esb_company_code, company_name, esb_username, is_active, updated_at
        """
        cur.execute(query, values)
        result = cur.fetchone()
        conn.commit()

        if not result:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Company not found")

        return {"status": "success", "company": dict(result)}
    finally:
        cur.close()
        conn.close()

@app.get("/api/v1/settings/engine")
async def get_engine_settings():
    from app.core.db import get_db_connection
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT sync_batch_size, work_hours_interval_minutes, morning_window_interval_minutes FROM engine_settings WHERE id = 1")
        row: Any = cur.fetchone()
        if row:
            return dict(row)
        return {"error": "Settings not found"}
    finally:
        cur.close()
        conn.close()

@app.put("/api/v1/settings/engine")
async def update_engine_settings(settings: dict):
    from app.core.db import get_db_connection
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            UPDATE engine_settings
            SET sync_batch_size = %s,
                work_hours_interval_minutes = %s,
                morning_window_interval_minutes = %s,
                updated_at = NOW()
            WHERE id = 1
        """, (settings.get('sync_batch_size', 1000),
              settings.get('work_hours_interval_minutes', 30),
              settings.get('morning_window_interval_minutes', 30)))
        conn.commit()
        return {"status": "success", "message": "Engine settings updated"}
    finally:
        cur.close()
        conn.close()


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# PARALLEL FETCHING ENDPOINTS (Optimized for All Companies queries)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# These endpoints replace sequential per-company API calls with parallel
# concurrent execution, reducing latency from 8x to ~1x for All Companies views.

@app.get("/api/v1/parallel/master/summary")
async def parallel_master_summary(force_refresh: bool = False):
    """Fetch master data summary for ALL active companies in a SINGLE call.

    This is an optimized replacement for iterating through each company
    with /api/v1/master/summary. Uses parallel database queries and caching.

    Args:
        force_refresh: Bypass cache if True

    Returns:
        {
            "companies": [{company_id, company_code, company_name, entities: {...}}],
            "totals": {entity: total_count},
            "total_companies": 8,
            "total_records": 123456,
            "from_cache": false
        }
    """
    from app.services.aggregation import fetch_all_companies_master_summary
    return fetch_all_companies_master_summary(use_cache=not force_refresh)


@app.get("/api/v1/parallel/trx/summary")
async def parallel_trx_summary(force_refresh: bool = False):
    """Fetch TRX staging summary for ALL active companies in a SINGLE call.

    Returns per-company and aggregated TRX entity counts with latest sync times.

    Returns:
        {
            "companies": [{company_id, company_code, company_name, entities: {...}}],
            "totals": {entity: {count, companies_with_data}},
            "total_companies": 8
        }
    """
    from app.services.aggregation import fetch_all_companies_trx_summary
    return fetch_all_companies_trx_summary(use_cache=not force_refresh)


@app.get("/api/v1/parallel/reports/{slug}")
async def parallel_report(slug: str, date_from: str, date_to: str,
                         limit: int = 200, use_cache: bool = False):
    """Fetch report data for ALL active companies in a SINGLE call.

    This is the KEY optimization: instead of 8 separate /api/v1/reports/{slug}
    calls (one per company), this returns all companies in ONE parallel query.

    Args:
        slug: Report slug (e.g., "stock-opname-report")
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        limit: Max rows per company (default 200)
        use_cache: Enable caching for this query (default False)

    Returns:
        {
            "slug": "stock-opname-report",
            "companies": [{
                "company_id": 1,
                "company_code": "CALF",
                "company_name": "PT Yuda Prawira...",
                "rows": [...],
                "count": 150
            }],
            "total_count": 1200,
            "limit_per_company": 200
        }
    """
    from datetime import date
    from app.services.aggregation import fetch_all_companies_report
    from app.services.reports import REPORTS

    if slug not in REPORTS:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Report not found: {slug}")

    spec = REPORTS[slug]

    # Table-backed reports (esb_data.report_* tables) are queried directly per
    # active company and assembled into the same response shape as the
    # parallel staging aggregator, so the FE viewer needs no special casing.
    if spec.get("source") == "table":
        from app.services.reports import run_report
        from app.core.db import get_db_connection as _conn
        from psycopg2.extras import RealDictCursor
        conn = _conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("SELECT id, esb_company_code, company_name FROM esb_data.company_configs WHERE is_active = true ORDER BY id")
            cos = [dict(r) for r in cur.fetchall()]
        finally:
            cur.close()
            conn.close()
        companies = []
        total = 0
        for co in cos:
            try:
                out = run_report(slug, co["id"], None,
                                 date.fromisoformat(date_from),
                                 date.fromisoformat(date_to),
                                 min(limit, 1000), 0)
                rows, count = out["rows"], out["total"]
            except Exception:
                rows, count = [], 0
            total += count
            companies.append({
                "company_id": co["id"],
                "company_code": co["esb_company_code"],
                "company_name": co["company_name"],
                "rows": [{"payload": r} for r in rows],
                "count": count,
            })
        return {
            "slug": slug,
            "companies": companies,
            "total_count": total,
            "limit_per_company": min(limit, 1000),
        }

    return fetch_all_companies_report(
        slug=slug,
        entity_type=spec["entity"],
        date_from=date.fromisoformat(date_from),
        date_to=date.fromisoformat(date_to),
        limit=min(limit, 1000),
        use_cache=use_cache
    )


@app.get("/api/v1/parallel/direct-reports/{report_type}")
async def parallel_direct_report(report_type: str, date_from: str, date_to: str,
                                use_cache: bool = False):
    """Fetch direct report (T2) for ALL active companies in a SINGLE call.

    Args:
        report_type: Report type (e.g., "RPT_STOCK_MOVEMENT")
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        use_cache: Enable caching (default False)

    Returns:
        {
            "report_type": "RPT_STOCK_MOVEMENT",
            "companies": [...],
            "total_count": 5000
        }
    """
    from datetime import date
    from app.services.aggregation import fetch_all_companies_direct_report

    return fetch_all_companies_direct_report(
        report_type=report_type,
        date_from=date.fromisoformat(date_from),
        date_to=date.fromisoformat(date_to),
        use_cache=use_cache
    )


@app.get("/api/v1/parallel/integration-hub")
async def parallel_integration_hub(force_refresh: bool = False):
    """Get complete Integration Hub dashboard data in a SINGLE optimized call.

    This endpoint aggregates ALL the key metrics needed for the dashboard:
    - Master data totals across all companies
    - TRX staging totals
    - Direct reports totals
    - Per-company summary
    - Recent sync status

    This replaces multiple separate API calls with one efficient query.

    Returns:
        {
            "active_companies": 8,
            "master_data": {entity: count},
            "master_data_total": 123456,
            "trx_staging": {entity: {count, earliest, latest, companies}},
            "trx_total_records": 50000,
            "direct_reports": {type: {lines, companies, ...}},
            "direct_reports_total": 10000,
            "sync_status_24h": {...},
            "companies": [{id, code, name, branches, products, trx_records, report_lines}],
            "from_cache": false
        }
    """
    from app.services.aggregation import get_integration_hub_summary
    return get_integration_hub_summary()


@app.post("/api/v1/parallel/cache/invalidate")
async def invalidate_parallel_cache():
    """Invalidate all parallel fetching cache entries.

    Call this after triggering manual syncs to ensure fresh data.
    """
    from app.services.aggregation import invalidate_all_parallel_cache
    invalidate_all_parallel_cache()
    return {"status": "success", "message": "Cache invalidated"}


@app.get("/api/v1/parallel/companies")
async def parallel_companies():
    """Get all active companies' metadata for parallel data fetching.

    Returns:
        {
            "companies": [{id, esb_company_code, company_name, esb_username}]
        }
    """
    from app.core.db import get_db_connection
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT id, esb_company_code, company_name
            FROM company_configs
            WHERE is_active = true AND esb_company_code IS NOT NULL
            ORDER BY id
        """)
        return {
            "companies": [dict(r) for r in cur.fetchall()],
            "count": cur.rowcount
        }
    finally:
        cur.close()
        conn.close()


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# DYNAMIC CONFIGURATION API ENDPOINTS (New ESB Data Schema)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

@app.get("/api/v1/endpoint-registry")
async def get_endpoint_registry(only_documented: bool = False, category: str = None):
    """Get all endpoints from the dynamic registry.
    
    Args:
        only_documented: Only return endpoints documented in ESB API
        category: Filter by category ('master' or 'report')
    
    Returns:
        List of endpoint configurations
    """
    from app.core.db import get_db_connection
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        base = "SELECT * FROM esb_data.endpoint_registry WHERE is_active = true"
        params = []
        
        if only_documented:
            base += " AND is_documented = true"
        if category:
            base += " AND category = %s"
            params.append(category)
            
        base += " ORDER BY category, entity"
        cur.execute(base, params)
        endpoints = [dict(row) for row in cur.fetchall()]
        return {"endpoints": endpoints, "count": len(endpoints)}
    finally:
        cur.close()
        conn.close()


@app.post("/api/v1/endpoint-registry")
async def create_endpoint(endpoint: dict):
    """Create a new endpoint in the registry.
    
    Args:
        endpoint: {entity, path, id_field, response_shape, is_active, is_documented, category, module, description}
    
    Returns:
        Created endpoint record
    """
    from app.core.db import get_db_connection
    from fastapi import HTTPException
    
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            INSERT INTO esb_data.endpoint_registry 
            (entity, path, id_field, response_shape, is_active, is_documented, category, module, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            endpoint.get("entity"), endpoint.get("path"), endpoint.get("id_field"),
            endpoint.get("response_shape"), endpoint.get("is_active", True),
            endpoint.get("is_documented", False), endpoint.get("category"),
            endpoint.get("module"), endpoint.get("description")
        ))
        result = cur.fetchone()
        conn.commit()
        return dict(result)
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create endpoint: {str(e)}")
    finally:
        cur.close()
        conn.close()


@app.put("/api/v1/endpoint-registry/{entity}")
async def update_endpoint(entity: str, endpoint: dict):
    """Update an existing endpoint in the registry.
    
    Args:
        entity: The entity identifier (e.g., 'BRANCH', 'PRODUCT')
        endpoint: Fields to update
    
    Returns:
        Updated endpoint record
    """
    from app.core.db import get_db_connection
    from fastapi import HTTPException
    
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        updates = []
        values = []
        
        for field in ["path", "id_field", "response_shape", "is_active", "is_documented", "category", "module", "description"]:
            if field in endpoint:
                updates.append(f"{field} = %s")
                values.append(endpoint[field])
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        values.append(entity)
        query = f"""
            UPDATE esb_data.endpoint_registry
            SET {', '.join(updates)}, updated_at = NOW()
            WHERE entity = %s
            RETURNING *
        """
        cur.execute(query, values)
        result = cur.fetchone()
        conn.commit()
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Endpoint not found: {entity}")
            
        return dict(result)
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to update endpoint: {str(e)}")
    finally:
        cur.close()
        conn.close()


@app.delete("/api/v1/endpoint-registry/{entity}")
async def delete_endpoint(entity: str):
    """Delete (deactivate) an endpoint from the registry.
    
    Args:
        entity: The entity identifier to delete
    
    Returns:
        Success message
    """
    from app.core.db import get_db_connection
    from fastapi import HTTPException
    
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            UPDATE esb_data.endpoint_registry
            SET is_active = false, updated_at = NOW()
            WHERE entity = %s
            RETURNING entity
        """, (entity,))
        result = cur.fetchone()
        conn.commit()
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Endpoint not found: {entity}")
            
        return {"status": "success", "message": f"Endpoint {entity} deactivated"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to delete endpoint: {str(e)}")
    finally:
        cur.close()
        conn.close()


@app.get("/api/v1/sync-schedules")
async def get_sync_schedules(company_id: int = None, module: str = None, enabled_only: bool = True):
    """Get sync schedules from the dynamic scheduling system.
    
    Args:
        company_id: Filter by company_id
        module: Filter by module ('master' or 'report')
        enabled_only: Only return enabled schedules
    
    Returns:
        List of sync schedules with joined endpoint and company info
    """
    from app.services.tasks import _get_sync_schedules
    
    schedules = _get_sync_schedules(company_id=company_id, module=module, enabled_only=enabled_only)
    return {"schedules": schedules, "count": len(schedules)}


@app.post("/api/v1/sync-schedules")
async def create_sync_schedule(schedule: dict):
    """Create a new sync schedule.
    
    Args:
        schedule: {company_id, endpoint_id, module, cron_expr, enabled, date_from, date_to, custom_params}
    
    Returns:
        Created schedule record
    """
    from app.core.db import get_db_connection
    from fastapi import HTTPException
    import json
    
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            INSERT INTO esb_data.sync_schedules 
            (company_id, endpoint_id, module, cron_expr, enabled, date_from, date_to, custom_params)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            schedule.get("company_id"), schedule.get("endpoint_id"), schedule.get("module"),
            schedule.get("cron_expr"), schedule.get("enabled", True),
            schedule.get("date_from"), schedule.get("date_to"),
            json.dumps(schedule.get("custom_params", {}))
        ))
        result = cur.fetchone()
        conn.commit()
        return dict(result)
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create schedule: {str(e)}")
    finally:
        cur.close()
        conn.close()


@app.put("/api/v1/sync-schedules/{schedule_id}")
async def update_sync_schedule(schedule_id: int, schedule: dict):
    """Update an existing sync schedule.
    
    Args:
        schedule_id: The schedule ID to update
        schedule: Fields to update
    
    Returns:
        Updated schedule record
    """
    from app.core.db import get_db_connection
    from fastapi import HTTPException
    import json
    
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        updates = []
        values = []
        
        for field in ["company_id", "endpoint_id", "module", "cron_expr", "enabled", "date_from", "date_to"]:
            if field in schedule:
                updates.append(f"{field} = %s")
                values.append(schedule[field])
        
        if "custom_params" in schedule:
            updates.append("custom_params = %s")
            values.append(json.dumps(schedule["custom_params"]))
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        values.append(schedule_id)
        query = f"""
            UPDATE esb_data.sync_schedules
            SET {', '.join(updates)}, updated_at = NOW()
            WHERE id = %s
            RETURNING *
        """
        cur.execute(query, values)
        result = cur.fetchone()
        conn.commit()
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Schedule not found: {schedule_id}")
            
        return dict(result)
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to update schedule: {str(e)}")
    finally:
        cur.close()
        conn.close()


@app.delete("/api/v1/sync-schedules/{schedule_id}")
async def delete_sync_schedule(schedule_id: int):
    """Delete a sync schedule.
    
    Args:
        schedule_id: The schedule ID to delete
    
    Returns:
        Success message
    """
    from app.core.db import get_db_connection
    from fastapi import HTTPException
    
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("DELETE FROM esb_data.sync_schedules WHERE id = %s RETURNING id", (schedule_id,))
        result = cur.fetchone()
        conn.commit()
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Schedule not found: {schedule_id}")
            
        return {"status": "success", "message": f"Schedule {schedule_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to delete schedule: {str(e)}")
    finally:
        cur.close()
        conn.close()


@app.get("/api/v1/master-normalization")
async def get_master_normalization(entity_type: str = None, company_id: int = None):
    """Get master data normalization rules.
    
    Args:
        entity_type: Filter by entity type ('COMPANY', 'BRANCH', 'PRODUCT')
        company_id: Filter by company_id
    
    Returns:
        List of normalization rules
    """
    from app.core.db import get_db_connection
    
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        base = "SELECT * FROM esb_data.master_normalization WHERE is_active = true"
        params = []
        
        if entity_type:
            base += " AND entity_type = %s"
            params.append(entity_type)
        if company_id:
            base += " AND company_id = %s"
            params.append(company_id)
            
        base += " ORDER BY entity_type, company_id"
        cur.execute(base, params)
        rules = [dict(row) for row in cur.fetchall()]
        return {"normalization_rules": rules, "count": len(rules)}
    finally:
        cur.close()
        conn.close()


@app.put("/api/v1/master-normalization/{rule_id}")
async def update_master_normalization(rule_id: int, rule: dict):
    """Update a master data normalization rule.
    
    Args:
        rule_id: The rule ID to update
        rule: Fields to update (normalized_name, is_active, etc.)
    
    Returns:
        Updated normalization rule
    """
    from app.core.db import get_db_connection
    from fastapi import HTTPException
    
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        updates = []
        values = []
        
        for field in ["normalized_name", "original_name", "is_active"]:
            if field in rule:
                updates.append(f"{field} = %s")
                values.append(rule[field])
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        values.append(rule_id)
        query = f"""
            UPDATE esb_data.master_normalization
            SET {', '.join(updates)}, updated_at = NOW()
            WHERE id = %s
            RETURNING *
        """
        cur.execute(query, values)
        result = cur.fetchone()
        conn.commit()
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Normalization rule not found: {rule_id}")
            
        return dict(result)
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to update normalization rule: {str(e)}")
    finally:
        cur.close()
        conn.close()


@app.post("/api/v1/master-normalization")
async def create_master_normalization(rule: dict):
    """Create a new master data normalization rule.
    
    Args:
        rule: {entity_type, esb_id, company_id, normalized_name, original_name, is_active}
    
    Returns:
        Created normalization rule
    """
    from app.core.db import get_db_connection
    from fastapi import HTTPException
    
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            INSERT INTO esb_data.master_normalization 
            (entity_type, esb_id, company_id, normalized_name, original_name, is_active)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            rule.get("entity_type"), rule.get("esb_id"), rule.get("company_id"),
            rule.get("normalized_name"), rule.get("original_name"),
            rule.get("is_active", True)
        ))
        result = cur.fetchone()
        conn.commit()
        return dict(result)
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create normalization rule: {str(e)}")
    finally:
        cur.close()
        conn.close()


@app.get("/api/v1/data-inventory")
async def get_data_inventory():
    """One-shot inventory of everything the engine has consumed: row counts for
    every esb_data master/report table, staging totals, active schedules with
    next dispatch, and recent sync activity. Powers the Configuration overview."""
    from app.core.db import get_db_connection
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema='esb_data' ORDER BY table_name
        """)
        tables = [r["table_name"] for r in cur.fetchall()]

        master, reports = {}, {}
        for t in tables:
            if t.startswith(("master_", "report_")):
                try:
                    cur.execute(f"SELECT COUNT(*) AS n FROM esb_data.{t}")
                    n = cur.fetchone()["n"]
                except Exception:
                    conn.rollback()
                    n = 0
                (master if t.startswith("master_") else reports)[t] = n

        # staging totals
        staging = {}
        for label, sql in [
            ("trx_raw_staging", "SELECT COUNT(*) AS n FROM public.trx_raw_staging"),
            ("report_raw_staging", "SELECT COUNT(*) AS n FROM public.report_raw_staging"),
            ("esb_raw_staging", "SELECT COUNT(*) AS n FROM public.esb_raw_staging"),
            ("sync_history", "SELECT COUNT(*) AS n FROM public.sync_history"),
        ]:
            try:
                cur.execute(sql)
                staging[label] = cur.fetchone()["n"]
            except Exception:
                conn.rollback()
                staging[label] = 0

        # date ranges for the big report tables
        ranges = {}
        for t, col in [("report_pos_sales", "sales_date"),
                       ("report_pos_sales_head", "sales_date"),
                       ("report_goods_receipt_recapitulation", "report_date")]:
            try:
                cur.execute(f"SELECT MIN({col}::date)::text AS mn, MAX({col}::date)::text AS mx, COUNT(DISTINCT {col}::date) AS days FROM esb_data.{t}")
                r0 = cur.fetchone()
                ranges[t] = {"from": r0["mn"], "to": r0["mx"], "days": r0["days"]}
            except Exception:
                conn.rollback()
                ranges[t] = None

        # engine state
        cur.execute("SELECT sync_enabled AS e FROM public.engine_settings WHERE id=1")
        row = cur.fetchone()
        engine_enabled = bool(row["e"]) if row else False

        cur.execute("""
            SELECT ss.id, er.entity, ss.module, ss.cron_expr, ss.enabled,
                   ss.last_run, ss.next_run, cc.esb_company_code
            FROM esb_data.sync_schedules ss
            JOIN esb_data.endpoint_registry er ON er.id = ss.endpoint_id
            JOIN esb_data.company_configs cc ON cc.id = ss.company_id
            WHERE ss.enabled = true
            ORDER BY ss.next_run ASC NULLS FIRST
        """)
        schedules = [dict(zip(["id", "entity", "module", "cron_expr", "enabled",
                               "last_run", "next_run", "company"], tuple(r.values())))
                     for r in cur.fetchall()]

        cur.execute("""
            SELECT entity_type, status, records_processed, error_message, started_at, completed_at
            FROM public.sync_history ORDER BY id DESC LIMIT 15
        """)
        recent = [dict(zip(["entity_type", "status", "records_processed", "error_message",
                            "started_at", "completed_at"], tuple(r.values())))
                  for r in cur.fetchall()]

        cur.execute("""
            SELECT entity_type, status, COUNT(*) AS n
            FROM public.sync_history
            WHERE completed_at > NOW() - INTERVAL '24 hours'
            GROUP BY 1, 2
        """)
        day_stats = [dict(zip(["entity_type", "status", "n"], tuple(r.values()))) for r in cur.fetchall()]

        return {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "engine_enabled": engine_enabled,
            "master_tables": master,
            "master_total": sum(master.values()),
            "report_tables": reports,
            "report_total": sum(reports.values()),
            "report_ranges": ranges,
            "staging": staging,
            "active_schedules": schedules,
            "recent_activity": recent,
            "last_24h": day_stats,
        }
    finally:
        cur.close()
        conn.close()


@app.get("/api/v1/master/{entity}/rows")
async def master_entity_rows(entity: str, company_id: int = 1, limit: int = 100,
                             offset: int = 0, search: str = None):
    """Paginated rows from an esb_data.master_* table (entity = table suffix,
    e.g. 'product' or 'PRODUCT'). Columns are introspected so any new master
    table works without code changes."""
    from app.core.db import get_db_connection
    from fastapi import HTTPException
    table_suffix = "".join(ch for ch in entity.lower() if ch.isalnum() or ch == "_")
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='esb_data' AND table_name = %s",
            (f"master_{table_suffix}",))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail=f"Unknown master entity: {entity}")

        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='esb_data' AND table_name=%s ORDER BY ordinal_position",
            (f"master_{table_suffix}",))
        columns = [r["column_name"] for r in cur.fetchall()]

        # pick a deterministic order column
        order_col = next((c for c in ["esb_id", "id", "code", "name"] if c in columns), columns[0])

        where = ""
        params: list = []
        text_cols = [c for c in columns if c in ("name", "code", "esb_id", "description", "original_name")]
        if search and text_cols:
            like = " OR ".join(f"{c}::text ILIKE %s" for c in text_cols)
            where = f" WHERE ({like})"
            params = [f"%{search}%"] * len(text_cols)

        cur.execute(f"SELECT COUNT(*) AS n FROM esb_data.master_{table_suffix}{where}", params)
        total = cur.fetchone()["n"]

        cols_sql = ", ".join(f'"{c}"' for c in columns if c != "raw_data")
        cur.execute(
            f"SELECT {cols_sql} FROM esb_data.master_{table_suffix}{where} "
            f'ORDER BY "{order_col}" LIMIT %s OFFSET %s',
            params + [min(limit, 500), offset])
        rows = [dict(r) for r in cur.fetchall()]
        return {"entity": entity.upper(), "table": f"esb_data.master_{table_suffix}",
                "columns": [c for c in columns if c != "raw_data"],
                "rows": rows, "total": total}
    finally:
        cur.close()
        conn.close()


@app.post("/api/v1/reports/{report_type}/sync")
async def trigger_report_sync(report_type: str, body: dict):
    """Manually trigger a report sync, overriding the schedule.
    
    Args:
        report_type: The report type (e.g., 'RPT_GOODS_RECEIPT_RECAPITULATION')
        body: {company_id, date_from, date_to, branch_esb_id}
    
    Returns:
        Status of the triggered sync
    """
    from app.core.db import get_db_connection
    from app.core.worker import celery_app
    from fastapi import HTTPException
    
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Validate that the report type exists in endpoint registry
        cur.execute("""
            SELECT er.*, cc.esb_company_code, cc.esb_username, cc.esb_password
            FROM esb_data.endpoint_registry er
            JOIN esb_data.sync_schedules ss ON er.id = ss.endpoint_id
            JOIN esb_data.company_configs cc ON ss.company_id = cc.id
            WHERE er.entity = %s AND er.category = 'report' AND ss.enabled = true
        """, (report_type,))
        schedule_info = cur.fetchone()
        
        if not schedule_info:
            raise HTTPException(status_code=404, detail=f"Report type not found or not enabled: {report_type}")
        
        # For now, we'll just trigger a placeholder task
        # In the future, this will dispatch to the actual report sync implementation
        celery_app.send_task("app.services.reports.sync_report", kwargs={
            "report_type": report_type,
            "company_id": body.get("company_id", schedule_info["company_id"]),
            "date_from": body.get("date_from"),
            "date_to": body.get("date_to"),
            "branch_esb_id": body.get("branch_esb_id")
        })
        
        return {
            "status": "triggered",
            "report_type": report_type,
            "company_id": body.get("company_id", schedule_info["company_id"]),
            "message": f"Manual sync triggered for {report_type}"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger report sync: {str(e)}")
    finally:
        cur.close()
        conn.close()


@app.get("/api/v1/master/summary")
async def master_summary_new():
    """Master data summary from esb_data.master_* tables (dynamic — any new
    master table created by the engine is picked up automatically)."""
    from app.core.db import get_db_connection
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'esb_data' AND table_name LIKE 'master_%'
            ORDER BY table_name
        """)
        tables = [r["table_name"] for r in cur.fetchall()]

        row_counts: dict[str, int] = {}
        per_company: dict[str, dict] = {}
        for t in tables:
            entity = t[len("master_"):].upper()
            try:
                cur.execute(f"SELECT COUNT(*) AS n FROM esb_data.{t}")
                row_counts[entity] = cur.fetchone()["n"]
            except Exception:
                conn.rollback()
                row_counts[entity] = 0
            try:
                cur.execute(
                    f"SELECT cc.esb_company_code AS code, COUNT(*) AS n "
                    f"FROM esb_data.{t} m JOIN esb_data.company_configs cc ON cc.id = m.company_id "
                    f"GROUP BY 1")
                per_company[entity] = {r["code"]: r["n"] for r in cur.fetchall()}
            except Exception:
                conn.rollback()
                per_company[entity] = {}

        # Get sync status from the cron schedule system
        cur.execute("""
            SELECT er.entity, MAX(ss.last_run) as last_sync,
                   CASE WHEN COUNT(CASE WHEN ss.last_run IS NOT NULL THEN 1 END) > 0 THEN 'SUCCESS' ELSE 'PENDING' END as status,
                   BOOL_OR(ss.enabled) as enabled
            FROM esb_data.sync_schedules ss
            JOIN esb_data.endpoint_registry er ON ss.endpoint_id = er.id
            WHERE er.category = 'master'
            GROUP BY er.entity
        """)
        info = {d["entity"]: d for d in (dict(row) for row in cur.fetchall())}

        entities = []
        for entity in row_counts:
            i = info.get(entity, {})
            entities.append({
                "entity": entity,
                "table": f"esb_data.master_{entity.lower()}",
                "row_count": row_counts[entity],
                "per_company": per_company.get(entity, {}),
                "last_sync": i.get("last_sync"),
                "last_status": i.get("status"),
                "schedule_enabled": bool(i.get("enabled", False)),
            })
        entities.sort(key=lambda e: -e["row_count"])
        return {"entities": entities}
    finally:
        cur.close()
        conn.close()


# COGS RATIO ANALYSIS ENDPOINTS
# ==============================

@app.get("/api/v1/cogs-ratio")
async def get_cogs_ratio(
    period: str,
    branch_type: str = None
):
    """
    Get COGS ratio analysis for all branches for a given period.

    Parameters:
    - period: Period in YYYY-MM format (required)
    - branch_type: Filter by branch type: OUTLET, HUB WH, HUB CK (optional)

    Returns branch-level metrics including:
    - Revenue and COGS per branch
    - COGS ratio vs target (default 65%)
    - Usage ratio (actual vs theoretical)
    - Flagging for branches needing investigation
    """
    from app.core.db import get_db_connection
    from app.utils.cogs_calculator import calculate_cogs_metrics

    try:
        conn = get_db_connection()
        metrics = calculate_cogs_metrics(conn, period, branch_type)
        conn.close()

        # Calculate summary KPIs
        if metrics:
            total_branches = len(metrics)
            flagged_branches = sum(1 for m in metrics if m['flagged'])
            avg_cogs = sum(m['cogsRatio'] for m in metrics) / total_branches
            avg_usage = sum(m['usageRatio'] for m in metrics) / total_branches
            total_revenue = sum(m['revenue'] for m in metrics)
            total_cogs = sum(m['cogs'] for m in metrics)

            summary = {
                'totalBranches': total_branches,
                'flaggedBranches': flagged_branches,
                'avgCogsRatio': round(avg_cogs, 1),
                'avgUsageRatio': round(avg_usage, 1),
                'totalRevenue': total_revenue,
                'totalCogs': total_cogs
            }
        else:
            summary = {
                'totalBranches': 0,
                'flaggedBranches': 0,
                'avgCogsRatio': 0,
                'avgUsageRatio': 0,
                'totalRevenue': 0,
                'totalCogs': 0
            }

        return {
            'summary': summary,
            'data': metrics
        }

    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Failed to calculate COGS ratio: {str(e)}")


@app.get("/api/v1/cogs-ratio/periods")
async def get_cogs_ratio_periods():
    """
    Get available periods that have COGS data in report_pos_sales_head.

    Returns periods in YYYY-MM format, newest first, up to 12 months back.
    Falls back to generating months from current date if no data exists.
    """
    from app.core.db import get_db_connection
    from datetime import date, timedelta
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT DISTINCT TO_CHAR(sales_date, 'YYYY-MM') AS period
            FROM esb_data.report_pos_sales_head
            ORDER BY period DESC
            LIMIT 12
        """)
        rows = cur.fetchall()
        periods = [r["period"] for r in rows]

        if not periods:
            today = date.today()
            for i in range(12):
                d = date(today.year, today.month, 1)
                d = d.replace(month=((d.month - 1 - i - 1) % 12) + 1)
                year_offset = (today.month - 1 - i - 1) // 12
                d = d.replace(year=d.year + year_offset)
                if i == 0:
                    d = date(today.year, today.month, 1)
                periods.append(d.strftime("%Y-%m"))

        import calendar
        result = []
        for p in periods:
            year, month = int(p[:4]), int(p[5:7])
            label = f"{calendar.month_name[month]} {year}"
            result.append({"value": p, "label": label})

        return result
    finally:
        conn.rollback()
        cur.close()
        conn.close()


@app.get("/api/v1/cogs-ratio/trend")
async def get_cogs_ratio_trend(
    branch_id: int = None,
    periods: str = None,
):
    """
    Get COGS ratio trend across multiple periods.

    Parameters:
    - branch_id: Optional branch ID filter
    - periods: Optional comma-separated list of YYYY-MM periods (defaults to last 6 months)

    Returns per-period aggregates for trend visualization.
    """
    from app.core.db import get_db_connection
    from datetime import date
    import calendar
    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        period_list = []
        if periods:
            period_list = [p.strip() for p in periods.split(",") if p.strip()]
        else:
            today = date.today()
            for i in range(6):
                m = today.month - i
                y = today.year
                while m <= 0:
                    m += 12
                    y -= 1
                period_list.append(f"{y}-{m:02d}")
            period_list.reverse()

        if not period_list:
            return []

        cur.execute("""
            SELECT period_label,
                   AVG(cogs_ratio) AS avg_cogs_ratio,
                   AVG(usage_ratio) AS avg_usage_ratio,
                   SUM(revenue) AS total_revenue,
                   SUM(cogs) AS total_cogs,
                   COUNT(*) AS branch_count,
                   COALESCE(SUM(CASE WHEN flagged THEN 1 ELSE 0 END), 0) AS flagged_branches
            FROM esb_data.analysis_cogs_snapshot
            WHERE period_label = ANY(%s)
              AND (%s::int IS NULL OR branch_id = %s::int)
            GROUP BY period_label
            ORDER BY period_label
        """, (period_list, branch_id, branch_id))
        snapshot_rows = cur.fetchall()

        if snapshot_rows:
            result = []
            for r in snapshot_rows:
                p = r["period_label"]
                year, month = int(p[:4]), int(p[5:7])
                result.append({
                    "period": p,
                    "period_label": f"{calendar.month_name[month]} {year}",
                    "avgCogsRatio": round(float(r["avg_cogs_ratio"]), 1),
                    "avgUsageRatio": round(float(r["avg_usage_ratio"]), 1),
                    "totalRevenue": float(r["total_revenue"]) if r["total_revenue"] else 0.0,
                    "totalCogs": float(r["total_cogs"]) if r["total_cogs"] else 0.0,
                    "branchCount": r["branch_count"],
                    "flaggedBranches": int(r["flagged_branches"]),
                })
            return result

        cur.execute("""
            SELECT TO_CHAR(sh.sales_date, 'YYYY-MM') AS period,
                   AVG(65.0) AS avg_cogs_ratio,
                   AVG(100.0) AS avg_usage_ratio,
                   SUM(sh.grand_total) AS total_revenue,
                   SUM(sh.grand_total) * 0.65 AS total_cogs,
                   COUNT(DISTINCT mb.id) AS branch_count,
                   0 AS flagged_branches
            FROM esb_data.report_pos_sales_head sh
            JOIN esb_data.master_branch mb ON mb.branch_code = sh.branch_code
            WHERE TO_CHAR(sh.sales_date, 'YYYY-MM') = ANY(%s)
              AND (%s::int IS NULL OR mb.id = %s::int)
            GROUP BY period
            ORDER BY period
        """, (period_list, branch_id, branch_id))
        raw_rows = cur.fetchall()

        result = []
        for r in raw_rows:
            p = r["period"]
            year, month = int(p[:4]), int(p[5:7])
            result.append({
                "period": p,
                "period_label": f"{calendar.month_name[month]} {year}",
                "avgCogsRatio": round(float(r["avg_cogs_ratio"]), 1),
                "avgUsageRatio": round(float(r["avg_usage_ratio"]), 1),
                "totalRevenue": float(r["total_revenue"]) if r["total_revenue"] else 0.0,
                "totalCogs": float(r["total_cogs"]) if r["total_cogs"] else 0.0,
                "branchCount": r["branch_count"],
                "flaggedBranches": int(r["flagged_branches"]),
            })
        return result
    finally:
        conn.rollback()
        cur.close()
        conn.close()


@app.get("/api/v1/cogs-ratio/{branch_id}")
async def get_cogs_ratio_by_branch(
    branch_id: int,
    period: str
):
    """
    Get detailed COGS ratio analysis for a specific branch.

    Parameters:
    - branch_id: Branch ID (required)
    - period: Period in YYYY-MM format (required)
    """
    from app.core.db import get_db_connection
    from psycopg2.extras import RealDictCursor

    try:
        conn = get_db_connection()
        query = """
        SELECT
            mb.id as branch_id,
            mb.branch_code,
            mb.name as branch_name,
            mb.raw_data->>'branchType' as branch_type,
            %s as period,

            COALESCE(SUM(sh.grand_total), 0) as revenue,
            COALESCE(SUM(sh.grand_total), 0) * 0.65 as cogs,
            65.0 as target_cogs_ratio,
            MAX(sh.synced_at) as last_updated
        FROM esb_data.master_branch mb
        LEFT JOIN esb_data.report_pos_sales_head sh ON mb.branch_code = sh.branch_code
            AND TO_CHAR(sh.sales_date, 'YYYY-MM') = %s
        WHERE mb.id = %s
        GROUP BY mb.id, mb.branch_code, mb.name, mb.raw_data->>'branchType'
        """

        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query, (period, period, branch_id))
        result = cur.fetchone()

        if not result:
            conn.close()
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Branch not found")

        revenue = float(result['revenue']) if result['revenue'] else 0
        cogs = float(result['cogs']) if result['cogs'] else 0
        target_cogs = float(result['target_cogs_ratio']) if result['target_cogs_ratio'] else 65.0
        last_updated = result['last_updated']

        cogs_ratio = (cogs / revenue * 100) if revenue > 0 else 0
        gap = cogs_ratio - target_cogs

        # Normalize branch type
        branch_type = result['branch_type']
        normalized_branch_type = 'OUTLET'
        if branch_type:
            if 'HUB' in branch_type and 'WH' in branch_type:
                normalized_branch_type = 'HUB WH'
            elif 'HUB' in branch_type and 'CK' in branch_type:
                normalized_branch_type = 'HUB CK'

        conn.close()

        return {
            'branchId': result['branch_id'],
            'branchCode': result['branch_code'],
            'branchName': result['branch_name'],
            'branchType': normalized_branch_type,
            'period': period,
            'revenue': revenue,
            'cogs': cogs,
            'cogsRatio': round(cogs_ratio, 1),
            'targetCogsRatio': target_cogs,
            'gap': round(gap, 1),
            'lastUpdated': str(last_updated)[:10] if last_updated else None
        }

    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Failed to get COGS ratio for branch: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────
# Phase 5: Analysis Snapshot API (pre-computed from analysis tables)
# ─────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/analysis/cogs-snapshot")
async def get_cogs_snapshot(
    period: str,
    company_id: int = 1,
    branch_type: typing.Optional[str] = None,
    flagged_only: bool = False,
):
    """Pre-computed COGS ratio snapshot from esb_data.analysis_cogs_snapshot.

    Falls back to computing from raw tables if snapshot is empty.
    Query params: period=YYYY-MM, company_id, branch_type, flagged_only.
    """
    from app.services.aggregation import refresh_cogs_snapshot
    from datetime import datetime

    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        where = "WHERE s.company_id = %s AND s.period_label = %s"
        params = [company_id, period]
        if branch_type:
            where += " AND s.branch_type = %s"
            params.append(branch_type)
        if flagged_only:
            where += " AND s.flagged = TRUE"

        cur.execute(f"""
            SELECT s.branch_id, s.branch_esb_id, s.branch_code, s.branch_name,
                   s.branch_type, s.period_label,
                   s.revenue, s.cogs, s.cogs_ratio, s.target_cogs_ratio,
                   s.gap, s.teoretis_usage, s.actual_usage, s.usage_ratio,
                   s.flagged, s.trend,
                   s.last_updated::text, s.refreshed_at::text
            FROM esb_data.analysis_cogs_snapshot s
            {where}
            ORDER BY s.branch_type, s.branch_name
        """, params)
        rows = cur.fetchall()

        if rows:
            total = len(rows)
            flagged = sum(1 for r in rows if r[14])
            avg_cogs = sum(float(r[8]) for r in rows) / total
            avg_usage = sum(float(r[13]) for r in rows) / total
            total_rev = sum(float(r[6]) for r in rows)
            total_cogs = sum(float(r[7]) for r in rows)
        else:
            # No snapshot — compute on-the-fly
            conn.close()
            period_date = datetime.strptime(period, "%Y-%m").date().replace(day=1)
            result = refresh_cogs_snapshot(company_id, period_date)
            if result["written"] > 0:
                return await get_cogs_snapshot(period, company_id, branch_type, flagged_only)
            total = flagged = 0
            avg_cogs = avg_usage = total_rev = total_cogs = 0.0
            rows = []

        return {
            "period": period,
            "company_id": company_id,
            "summary": {
                "total_branches": total,
                "flagged_branches": flagged,
                "avg_cogs_ratio": round(avg_cogs, 1),
                "avg_usage_ratio": round(avg_usage, 1),
                "total_revenue": total_rev,
                "total_cogs": total_cogs,
            },
            "data": [
                {
                    "branch_id": r[0], "branch_esb_id": r[1], "branch_code": r[2],
                    "branch_name": r[3], "branch_type": r[4], "period_label": r[5],
                    "revenue": float(r[6]), "cogs": float(r[7]),
                    "cogs_ratio": float(r[8]), "target_cogs_ratio": float(r[9]),
                    "gap": float(r[10]), "teoretis_usage": float(r[11]),
                    "actual_usage": float(r[12]), "usage_ratio": float(r[13]),
                    "flagged": r[14], "trend": r[15],
                    "last_updated": r[16], "refreshed_at": r[17],
                }
                for r in rows
            ],
        }
    finally:
        cur.close()
        conn.close()


@app.get("/api/v1/analysis/usage-ratio")
async def get_usage_ratio(
    period: str,
    company_id: int = 1,
    branch_id: typing.Optional[int] = None,
    flagged_only: bool = False,
    limit: int = 200,
):
    """Pre-computed usage ratio from esb_data.analysis_usage_ratio.

    Shows per-product actual vs theoretical material consumption.
    """
    from app.services.aggregation import refresh_usage_ratio
    from datetime import datetime

    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        where = "WHERE u.company_id = %s AND u.period_label = %s"
        params = [company_id, period]
        if branch_id:
            where += " AND u.branch_id = %s"
            params.append(branch_id)
        if flagged_only:
            where += " AND u.flagged = TRUE"

        cur.execute(f"""
            SELECT u.branch_id, u.branch_code, u.branch_name,
                   u.period_label, u.product_code, u.product_name,
                   u.category_name, u.teoretis_qty, u.actual_qty,
                   u.usage_ratio, u.efficiency_pct, u.flagged
            FROM esb_data.analysis_usage_ratio u
            {where}
            ORDER BY u.branch_name, u.product_name
            LIMIT %s
        """, params + [min(limit, 1000)])
        rows = cur.fetchall()

        if rows:
            total = len(rows)
            flagged = sum(1 for r in rows if r[11])
            avg_ratio = sum(float(r[9]) for r in rows) / total
        else:
            conn.close()
            period_date = datetime.strptime(period, "%Y-%m").date().replace(day=1)
            result = refresh_usage_ratio(company_id, period_date)
            if result["written"] > 0:
                return await get_usage_ratio(period, company_id, branch_id, flagged_only, limit)
            total = flagged = 0
            avg_ratio = 0.0
            rows = []

        return {
            "period": period,
            "company_id": company_id,
            "branch_id": branch_id,
            "summary": {
                "total_products": total,
                "flagged_products": flagged,
                "avg_usage_ratio": round(avg_ratio, 1),
            },
            "data": [
                {
                    "branch_id": r[0], "branch_code": r[1], "branch_name": r[2],
                    "period_label": r[3], "product_code": r[4],
                    "product_name": r[5], "category_name": r[6],
                    "teoretis_qty": float(r[7]), "actual_qty": float(r[8]),
                    "usage_ratio": float(r[9]), "efficiency_pct": float(r[10]),
                    "flagged": r[11],
                }
                for r in rows
            ],
        }
    finally:
        cur.close()
        conn.close()


@app.get("/api/v1/dashboard/summary")
async def get_dashboard_summary(period: str):
    """
    Dashboard summary KPIs for a given period.

    Returns aggregated COGS, usage, revenue, and operational metrics
    to power the main dashboard page.
    """
    from app.core.db import get_db_connection

    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Prevent runaway queries
        cur.execute("SET LOCAL statement_timeout = '15000'")

        # COGS from analysis snapshot
        cur.execute("""
            SELECT
                COUNT(*) AS total_branches,
                COALESCE(AVG(cogs_ratio), 0) AS avg_cogs_ratio,
                COALESCE(AVG(usage_ratio), 0) AS avg_usage_ratio,
                COALESCE(SUM(revenue), 0) AS total_revenue,
                COALESCE(SUM(cogs), 0) AS total_cogs,
                COALESCE(SUM(CASE WHEN flagged THEN 1 ELSE 0 END), 0) AS flagged_branches
            FROM esb_data.analysis_cogs_snapshot
            WHERE period_label = %s
        """, (period,))
        cogs_row = cur.fetchone()

        # Stock opname pending approvals (graceful if table doesn't exist)
        try:
            cur.execute("""
                SELECT COUNT(*) AS pending
                FROM esb_data.stock_opname_header
                WHERE status IN ('draft', 'submitted')
            """)
            pending_so = dict(cur.fetchone())["pending"]
        except Exception:
            conn.rollback()
            pending_so = 0

        # Waste pending approvals (graceful if table doesn't exist)
        try:
            cur.execute("""
                SELECT COUNT(*) AS pending
                FROM esb_data.waste_header
                WHERE status IN ('draft', 'submitted')
            """)
            pending_waste = dict(cur.fetchone())["pending"]
        except Exception:
            conn.rollback()
            pending_waste = 0

        # Critical stock items (graceful if table doesn't exist)
        try:
            cur.execute("""
                SELECT COUNT(*) AS critical
                FROM esb_data.stock_opname_detail sod
                JOIN esb_data.stock_opname_header soh ON soh.id = sod.header_id
                WHERE sod.variance_qty < 0
                  AND soh.status = 'approved'
                  AND DATE(soh.created_at) >= CURRENT_DATE - INTERVAL '7 days'
            """)
            critical_stock = dict(cur.fetchone())["critical"]
        except Exception:
            conn.rollback()
            critical_stock = 0

        # Recent waste value MTD (graceful if table doesn't exist)
        try:
            cur.execute("""
                SELECT COALESCE(SUM(total_value), 0) AS waste_mtd
                FROM esb_data.waste_header
                WHERE TO_CHAR(waste_date, 'YYYY-MM') = %s
                  AND status = 'approved'
            """, (period,))
            waste_mtd_val = dict(cur.fetchone())["waste_mtd"]
        except Exception:
            conn.rollback()
            waste_mtd_val = 0

        cogs = dict(cogs_row)

        # Estimate data completeness from snapshot coverage
        cur.execute("""
            SELECT COUNT(DISTINCT branch_id) AS covered_branches
            FROM esb_data.analysis_cogs_snapshot
            WHERE period_label = %s
        """, (period,))
        covered = dict(cur.fetchone())["covered_branches"]

        cur.execute("SELECT COUNT(*) AS total_branches FROM esb_data.master_branch WHERE is_active = true")
        total_branches = dict(cur.fetchone())["total_branches"]
        data_completeness = round((covered / total_branches * 100) if total_branches > 0 else 0, 0)

        return {
            "period": period,
            "avgCogsRatio": round(float(cogs["avg_cogs_ratio"]), 1),
            "avgUsageRatio": round(float(cogs["avg_usage_ratio"]), 1),
            "totalRevenue": float(cogs["total_revenue"]),
            "totalCogs": float(cogs["total_cogs"]),
            "flaggedOutlets": int(cogs["flagged_branches"]),
            "pendingApprovals": int(pending_so) + int(pending_waste),
            "criticalStockItems": int(critical_stock),
            "wasteValueMTD": float(waste_mtd_val),
            "dataCompleteness": data_completeness,
            "hasStockOpnameData": False,
            "hasWasteData": False,
        }
    finally:
        conn.rollback()
        cur.close()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────
# SALES REPORTING ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/sales/recap-detail")
async def get_sales_recap_detail(
    period: str,
    branch_code: str = None,
    limit: int = 500,
    offset: int = 0,
):
    """
    Sales line-item detail from esb_data.report_pos_sales.

    Parameters:
    - period: YYYY-MM format
    - branch_code: optional filter
    - limit: max rows (default 500)
    - offset: pagination offset
    """
    from app.core.db import get_db_connection

    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        where = "WHERE l.company_id = 1 AND TO_CHAR(l.sales_date, 'YYYY-MM') = %s"
        params: list = [period]

        if branch_code:
            where += " AND h.branch_code = %s"
            params.append(branch_code)

        cur.execute(f"""
            SELECT
                l.id,
                l.sales_num,
                TO_CHAR(l.sales_date, 'YYYY-MM-DD') AS sales_date,
                COALESCE(h.branch_code, '') AS branch_code,
                COALESCE(l.menu_code, '') AS menu_code,
                COALESCE(l.menu_name, '') AS menu_name,
                COALESCE(l.menu_category_name, '') AS category_name,
                l.qty,
                COALESCE(l.price, 0) AS price,
                COALESCE(l.discount, 0) AS discount,
                l.total,
                COALESCE(l.cost, 0) AS cost,
                COALESCE(l.cost * l.qty, 0) AS cogs,
                COALESCE(l.synced_at::text, '') AS synced_at
            FROM esb_data.report_pos_sales l
            JOIN esb_data.report_pos_sales_head h
              ON h.company_id = l.company_id AND h.sales_num = l.sales_num
            {where}
            ORDER BY l.sales_date DESC, l.sales_num
            LIMIT %s OFFSET %s
        """, params + [min(limit, 2000), offset])
        rows = [dict(r) for r in cur.fetchall()]

        cur.execute(f"""
            SELECT COUNT(*) AS total
            FROM esb_data.report_pos_sales l
            JOIN esb_data.report_pos_sales_head h
              ON h.company_id = l.company_id AND h.sales_num = l.sales_num
            {where}
        """, params)
        total = cur.fetchone()["total"]

        return rows
    finally:
        conn.rollback()
        cur.close()
        conn.close()


@app.get("/api/v1/sales/recap-head")
async def get_sales_recap_head(
    period: str,
    branch_code: str = None,
    limit: int = 500,
    offset: int = 0,
):
    """
    Sales transaction header (receipt-level) from esb_data.report_pos_sales_head.

    Parameters:
    - period: YYYY-MM format
    - branch_code: optional filter
    - limit: max rows (default 500)
    - offset: pagination offset
    """
    from app.core.db import get_db_connection

    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        where = "WHERE company_id = 1 AND TO_CHAR(sales_date, 'YYYY-MM') = %s"
        params: list = [period]

        if branch_code:
            where += " AND branch_code = %s"
            params.append(branch_code)

        cur.execute(f"""
            SELECT
                sales_num,
                TO_CHAR(sales_date, 'YYYY-MM-DD') AS sales_date,
                branch_code,
                grand_total,
                (SELECT COUNT(*) FROM esb_data.report_pos_sales d
                 WHERE d.company_id = report_pos_sales_head.company_id
                   AND d.sales_num = report_pos_sales_head.sales_num) AS total_items,
                COALESCE(payment_method, 'cash') AS payment_method,
                synced_at::text AS synced_at
            FROM esb_data.report_pos_sales_head
            {where}
            ORDER BY sales_date DESC, sales_num
            LIMIT %s OFFSET %s
        """, params + [min(limit, 2000), offset])
        rows = [dict(r) for r in cur.fetchall()]

        cur.execute(f"""
            SELECT COUNT(*) AS total
            FROM esb_data.report_pos_sales_head
            {where}
        """, params)
        total = cur.fetchone()["total"]

        return rows
    finally:
        conn.rollback()
        cur.close()
        conn.close()


@app.get("/api/v1/sales/summary")
async def get_sales_summary(period: str):
    """
    Aggregated sales summary for a period.

    Returns total revenue, transactions, items, and average ticket size.
    """
    from app.core.db import get_db_connection

    from psycopg2.extras import RealDictCursor

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Use date range to allow index usage
        cur.execute("SET LOCAL statement_timeout = '90000'")

        # Use date range to allow index usage
        # Step 1: head-level stats (COUNT(*) per transaction, not DISTINCT)
        cur.execute(f"""
            SELECT
                COUNT(*) AS total_transactions,
                COALESCE(SUM(grand_total), 0) AS total_revenue
            FROM esb_data.report_pos_sales_head h
            WHERE h.company_id = 1
              AND h.sales_date >= %s
              AND h.sales_date < (%s::date + INTERVAL '1 month')
        """, (f"{period}-01", f"{period}-01"))
        head_row = dict(cur.fetchone())
        total_tx = int(head_row["total_transactions"] or 0)
        total_rev = float(head_row["total_revenue"] or 0)
        avg_ticket = total_rev / total_tx if total_tx > 0 else 0

        # Step 2: line-item level stats (direct query on report_pos_sales which has sales_date)
        cur.execute(f"""
            SELECT
                COUNT(*) AS total_items,
                COALESCE(SUM(qty), 0) AS total_qty
            FROM esb_data.report_pos_sales
            WHERE company_id = 1
              AND sales_date >= %s
              AND sales_date < (%s::date + INTERVAL '1 month')
        """, (f"{period}-01", f"{period}-01"))
        line_row = dict(cur.fetchone())
        total_items = int(line_row["total_items"] or 0)
        total_qty = float(line_row["total_qty"] or 0)

        # Per-branch breakdown
        cur.execute("""
            SELECT
                h.branch_code,
                h.branch_name,
                COUNT(*) AS transactions,
                COALESCE(SUM(h.grand_total), 0) AS revenue
            FROM esb_data.report_pos_sales_head h
            WHERE h.company_id = 1
              AND h.sales_date >= %s
              AND h.sales_date < (%s::date + INTERVAL '1 month')
            GROUP BY h.branch_code, h.branch_name
            ORDER BY revenue DESC
        """, (f"{period}-01", f"{period}-01"))
        branches = [dict(r) for r in cur.fetchall()]

        return {
            "totalRevenue": total_rev,
            "totalTransactions": total_tx,
            "totalItems": total_items,
            "totalQty": total_qty,
            "avgTicketSize": round(avg_ticket, 0),
            "branchBreakdown": [
                {
                    "branchCode": b["branch_code"],
                    "branchName": b["branch_name"],
                    "transactions": int(b["transactions"]),
                    "revenue": float(b["revenue"]),
                }
                for b in branches
            ],
        }
    finally:
        conn.rollback()
        cur.close()
        conn.close()
