"""Analysis snapshot API endpoints.

Provides pre-computed COGS ratio and usage ratio data from the
analysis tables. These replace the ad-hoc query approach in cogs_ratio.py
with faster, pre-materialized snapshots.

GET /api/v1/analysis/cogs-snapshot?period=YYYY-MM&company_id=1
GET /api/v1/analysis/usage-ratio?period=YYYY-MM&company_id=1&branch_id=...
"""
import typing
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.db import get_db_connection

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])


class COGSSnapshotRow(BaseModel):
    branch_id: int
    branch_esb_id: Optional[str]
    branch_code: str
    branch_name: str
    branch_type: Optional[str]
    period_label: str
    revenue: float
    cogs: float
    cogs_ratio: float
    target_cogs_ratio: float
    gap: float
    teoretis_usage: float
    actual_usage: float
    usage_ratio: float
    flagged: bool
    trend: str
    last_updated: Optional[str]
    refreshed_at: Optional[str]


class UsageRatioRow(BaseModel):
    branch_id: int
    branch_code: str
    branch_name: str
    period_label: str
    product_code: Optional[str]
    product_name: Optional[str]
    category_name: Optional[str]
    teoretis_qty: float
    actual_qty: float
    usage_ratio: float
    efficiency_pct: float
    flagged: bool


@router.get("/cogs-snapshot")
def get_cogs_snapshot(
    period: str = Query(..., description="Period in YYYY-MM format"),
    company_id: int = Query(1, description="Company ID"),
    branch_type: Optional[str] = Query(None, description="Filter by branch type"),
    flagged_only: bool = Query(False, description="Show only flagged branches"),
) -> dict:
    """Return pre-computed COGS snapshot for a period.

    Data comes from esb_data.analysis_cogs_snapshot (refreshed daily).
    Falls back to computing from raw tables if snapshot is empty.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        where = "WHERE s.company_id = %s AND s.period_label = %s"
        params: typing.List = [company_id, period]

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

        # Summary KPIs
        if rows:
            total = len(rows)
            flagged = sum(1 for r in rows if r[14])
            avg_cogs = sum(float(r[8]) for r in rows) / total
            avg_usage = sum(float(r[13]) for r in rows) / total
            total_rev = sum(float(r[6]) for r in rows)
            total_cogs = sum(float(r[7]) for r in rows)
        else:
            total = flagged = 0
            avg_cogs = avg_usage = total_rev = total_cogs = 0.0

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


@router.get("/usage-ratio")
def get_usage_ratio(
    period: str = Query(..., description="Period in YYYY-MM format"),
    company_id: int = Query(1, description="Company ID"),
    branch_id: Optional[int] = Query(None, description="Filter by branch"),
    flagged_only: bool = Query(False, description="Show only flagged products"),
    limit: int = Query(200, le=1000, description="Max rows returned"),
) -> dict:
    """Return pre-computed usage ratio data for a period.

    Data comes from esb_data.analysis_usage_ratio (refreshed daily).
    Shows per-product actual vs theoretical material consumption.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        where = "WHERE u.company_id = %s AND u.period_label = %s"
        params: typing.List = [company_id, period]

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
        """, params + [limit])
        rows = cur.fetchall()

        if rows:
            total = len(rows)
            flagged = sum(1 for r in rows if r[11])
            avg_ratio = sum(float(r[9]) for r in rows) / total
        else:
            total = flagged = 0
            avg_ratio = 0.0

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
