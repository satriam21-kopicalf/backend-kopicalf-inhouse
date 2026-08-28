import typing
from typing import Any
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="CALF Ecosystem Backend")

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
    conn = get_db_connection()
    cur = conn.cursor()
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
    conn = get_db_connection()
    cur = conn.cursor()
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
    conn = get_db_connection()
    cur = conn.cursor()
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
    conn = get_db_connection()
    cur = conn.cursor()
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
    conn = get_db_connection()
    cur = conn.cursor()
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
    
    conn = get_db_connection()
    cur = conn.cursor()
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
    conn = get_db_connection()
    cur = conn.cursor()
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
    conn = get_db_connection()
    cur = conn.cursor()
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
    conn = get_db_connection()
    cur = conn.cursor()
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
    conn = get_db_connection()
    cur = conn.cursor()
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
        conn = _conn()
        cur = conn.cursor()
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
    conn = get_db_connection()
    cur = conn.cursor()
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
    conn = get_db_connection()
    cur = conn.cursor()
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
    
    conn = get_db_connection()
    cur = conn.cursor()
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
    
    conn = get_db_connection()
    cur = conn.cursor()
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
    
    conn = get_db_connection()
    cur = conn.cursor()
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
    
    conn = get_db_connection()
    cur = conn.cursor()
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
    
    conn = get_db_connection()
    cur = conn.cursor()
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
    
    conn = get_db_connection()
    cur = conn.cursor()
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
    
    conn = get_db_connection()
    cur = conn.cursor()
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
    
    conn = get_db_connection()
    cur = conn.cursor()
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
    
    conn = get_db_connection()
    cur = conn.cursor()
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
    conn = get_db_connection()
    cur = conn.cursor()
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
    conn = get_db_connection()
    cur = conn.cursor()
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
    
    conn = get_db_connection()
    cur = conn.cursor()
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
    conn = get_db_connection()
    cur = conn.cursor()
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
