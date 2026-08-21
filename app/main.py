from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from app.services.tasks import sync_master_data

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
async def trx_backfill_run(company_id: int = None, entity: str = None):
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

@app.get("/api/v1/master/summary")
async def master_summary():
    """Per-entity master-data stats: row counts, last sync, schedule interval.
    Optimized with batch queries for faster response."""
    from app.core.db import get_db_connection
    entity_tables = {
        "BRANCH": "md_outlets", "PRODUCT": "md_products", "CATEGORY": "md_categories",
        "PRODUCT_SUB_CATEGORY": "md_sub_categories", "PRODUCT_UNIT": "md_units",
        "PRICELIST": "md_pricelists", "SUPPLIER": "md_suppliers", "CUSTOMER": "md_customers",
        "BOM": "md_boms", "DOCUMENT_TEMPLATE": "md_document_templates",
        "ACC_PURPOSE": "md_purposes", "ACC_COST_CENTER": "md_cost_centers",
        "ACC_COA": "md_coas", "COMP_PROJECT": "md_projects", "COMP_USER": "md_users",
        "PARTNER_CUST_CAT": "md_customer_categories", "PARTNER_SUPP_CAT": "md_supplier_categories",
        "CUSTOMER_PRICELIST": "md_customer_pricelists", "PRODUCT_DETAIL": "md_product_details",
    }
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Batch query: get all row counts
        counts_sql = """
            SELECT 'BRANCH' as entity, (SELECT count(*) FROM md_outlets) as cnt
            UNION ALL SELECT 'PRODUCT', (SELECT count(*) FROM md_products)
            UNION ALL SELECT 'CATEGORY', (SELECT count(*) FROM md_categories)
            UNION ALL SELECT 'PRODUCT_SUB_CATEGORY', (SELECT count(*) FROM md_sub_categories)
            UNION ALL SELECT 'PRODUCT_UNIT', (SELECT count(*) FROM md_units)
            UNION ALL SELECT 'PRICELIST', (SELECT count(*) FROM md_pricelists)
            UNION ALL SELECT 'SUPPLIER', (SELECT count(*) FROM md_suppliers)
            UNION ALL SELECT 'CUSTOMER', (SELECT count(*) FROM md_customers)
            UNION ALL SELECT 'BOM', (SELECT count(*) FROM md_boms)
            UNION ALL SELECT 'DOCUMENT_TEMPLATE', (SELECT count(*) FROM md_document_templates)
            UNION ALL SELECT 'ACC_PURPOSE', (SELECT count(*) FROM md_purposes)
            UNION ALL SELECT 'ACC_COST_CENTER', (SELECT count(*) FROM md_cost_centers)
            UNION ALL SELECT 'ACC_COA', (SELECT count(*) FROM md_coas)
            UNION ALL SELECT 'COMP_PROJECT', (SELECT count(*) FROM md_projects)
            UNION ALL SELECT 'COMP_USER', (SELECT count(*) FROM md_users)
            UNION ALL SELECT 'PARTNER_CUST_CAT', (SELECT count(*) FROM md_customer_categories)
            UNION ALL SELECT 'PARTNER_SUPP_CAT', (SELECT count(*) FROM md_supplier_categories)
            UNION ALL SELECT 'CUSTOMER_PRICELIST', (SELECT count(*) FROM md_customer_pricelists)
            UNION ALL SELECT 'PRODUCT_DETAIL', (SELECT count(*) FROM md_product_details)
        """
        cur.execute(counts_sql)
        row_counts = {row["entity"]: row["cnt"] for row in cur.fetchall()}

        # Batch query: get sync history
        cur.execute("""
            SELECT DISTINCT ON (entity_type) entity_type, completed_at, status
            FROM sync_history WHERE completed_at IS NOT NULL
            ORDER BY entity_type, id DESC
        """)
        sync_status = {row["entity_type"]: {"last_sync": row["completed_at"], "status": row["status"]} for row in cur.fetchall()}

        # Batch query: get schedules
        cur.execute("SELECT entity_type, interval_minutes, enabled FROM md_sync_schedules")
        schedules = {row["entity_type"]: {"interval_minutes": row["interval_minutes"], "enabled": row["enabled"]} for row in cur.fetchall()}

        entities = []
        for entity, table in entity_tables.items():
            entities.append({
                "entity": entity, "table": table,
                "row_count": row_counts.get(entity, 0),
                "per_company": {},
                "last_sync": sync_status.get(entity, {}).get("last_sync"),
                "last_status": sync_status.get(entity, {}).get("status"),
                "interval_minutes": schedules.get(entity, {}).get("interval_minutes"),
                "schedule_enabled": schedules.get(entity, {}).get("enabled", False),
            })
        return {"entities": entities}
    finally:
        cur.close()
        conn.close()

@app.get("/api/v1/reports/summary")
async def reports_summary():
    """Per-report staging stats: row counts, period coverage, and last sync —
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
                r = cur.fetchone()
                row_count = r["lines"] or r["rows"] or 0
            else:
                cur.execute("""
                    SELECT count(*) AS rows, NULL::bigint AS lines,
                           min(doc_date) AS earliest, max(doc_date) AS latest,
                           max(synced_at) AS last_sync,
                           count(DISTINCT company_id) AS companies
                    FROM trx_raw_staging WHERE entity_type = %s
                """, (spec["entity"],))
                r = cur.fetchone()
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
                     branch_esb_id: str = None, limit: int = 200, offset: int = 0):
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
        result = {"status": row["status"]}
        if row["status"] == "ready" and row["file_path"]:
            from app.services.export_engine import make_signed_url
            result["download_url"] = make_signed_url(row["file_path"])
        if row["error_message"]:
            result["error"] = row["error_message"]
        return result
    finally:
        cur.close()
        conn.close()

from pydantic import BaseModel
import typing

class SyncTriggerRequest(BaseModel):
    company_id: int
    module: str
    entities: typing.Optional[typing.List[str]] = None
    date_from: typing.Optional[str] = None
    date_to: typing.Optional[str] = None

@app.post("/sync/trigger")
async def trigger_sync(req: typing.Optional[SyncTriggerRequest] = None):
    # Fallback to old behavior if no payload
    if not req:
        sync_master_data.delay()
        return {"status": "triggered", "message": "Manual global synchronization triggered via Celery worker."}
        
    from app.core.db import get_db_connection
    from app.services.tasks import sync_company_data, MASTER_ENTITIES
    from app.services.trx_engine import backfill_entity, rpt_backfill_entity
    from datetime import date
    from fastapi import HTTPException
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT esb_company_code, esb_username, esb_password FROM company_configs WHERE id = %s", (req.company_id,))
        co = cur.fetchone()
        if not co:
            raise HTTPException(status_code=404, detail="Company not found")
        
        if req.module == "master":
            ents = req.entities if req.entities else MASTER_ENTITIES
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
        row = cur.fetchone()
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


# ══════════════════════════════════════════════════════════════════════════════
# PARALLEL FETCHING ENDPOINTS (Optimized for All Companies queries)
# ══════════════════════════════════════════════════════════════════════════════
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
