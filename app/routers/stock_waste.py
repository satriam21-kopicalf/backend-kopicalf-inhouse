"""
Stock Opname and Waste Management API
Supports outlet, hub-wh, and hub-ck branches for COGS calculation.
All queries use RealDictCursor and real esb_data schema columns:
- master_branch: branch_code (not code), branch type via raw_data->>'branchType'
- master_product: product_code (not code); no uom linkage (unit comes from movements/raw data)
"""
from fastapi import APIRouter, HTTPException, Query, Header
from pydantic import BaseModel
from psycopg2.extras import RealDictCursor
from typing import Optional, List, Dict, Any
from datetime import date, datetime
import json

router = APIRouter(prefix="/api/v1", tags=["stock-waste"])


def get_conn():
    from app.core.db import get_db_connection
    return get_db_connection()


# Product scope rules per stock opname period type.
#   daily_packaging -> PACKAGING only
#   weekly/monthly  -> raw materials (RAW MATERIAL*, Roasted Beans)
RAW_CATEGORY_SQL = "(upper(mp.category_name) LIKE 'RAW MATERIAL%' OR upper(mp.category_name) LIKE 'ROASTED%')"


def _validate_opname_scope(cur, period_type: str, resolved: list) -> None:
    """Reject details whose product category does not match the period scope."""
    if not resolved:
        return
    product_ids = [d["product_id"] for d in resolved]
    cur.execute("""
        SELECT id, product_code, category_name FROM esb_data.master_product
        WHERE id = ANY(%s)
    """, (product_ids,))
    cats = {r["id"]: (r["product_code"], r["category_name"] or "") for r in cur.fetchall()}
    offenders = []
    for d in resolved:
        code, cat = cats.get(d["product_id"], ("?", ""))
        upper = cat.upper()
        if period_type == "daily_packaging":
            ok = "PACKAG" in upper
        else:  # weekly / monthly
            ok = upper.startswith("RAW MATERIAL") or upper.startswith("ROASTED")
        if not ok:
            offenders.append(f"{code} ({cat or 'no category'})")
    if offenders:
        expected = "PACKAGING" if period_type == "daily_packaging" else "RAW MATERIAL / BAHAN BAKU"
        raise HTTPException(
            status_code=400,
            detail=f"Product scope violation for '{period_type}' opname (expected {expected}): "
                   + ", ".join(offenders[:10]),
        )


BRANCH_TYPE_CASE = """
    CASE COALESCE({col}, 'OUTLET')
        WHEN 'WAREHOUSE' THEN 'HUB WH'
        WHEN 'HUB_WAREHOUSE' THEN 'HUB WH'
        WHEN 'HUB WH' THEN 'HUB WH'
        WHEN 'CENTER_KITCHEN' THEN 'HUB CK'
        WHEN 'HUB_CK' THEN 'HUB CK'
        WHEN 'HUB CK' THEN 'HUB CK'
        ELSE 'OUTLET'
    END
"""

BRANCH_SELECT = f"""
    mb.id AS branch_id, mb.branch_code AS branch_code, mb.name AS branch_name,
    {BRANCH_TYPE_CASE.format(col="mb.raw_data->>'branchType'")} AS branch_type
"""


def _fetch_header(cur, table: str, date_col: str, row_id: int) -> Optional[Dict[str, Any]]:
    period_type_col = "h.period_type," if table == "stock_opname_header" else ""
    cur.execute(f"""
        SELECT h.id, h.branch_id, {BRANCH_SELECT},
               h.{date_col}, h.period_month, {period_type_col} h.status,
               {'h.total_variance_value' if table == 'stock_opname_header' else 'h.total_value'} AS total_value,
               h.item_count, h.approved_by, h.approved_at, h.notes,
               h.created_by, h.created_at, h.updated_at
        FROM esb_data.{table} h
        LEFT JOIN esb_data.master_branch mb ON mb.id = h.branch_id
        WHERE h.id = %s
    """, (row_id,))
    return cur.fetchone()


# ============== Pydantic Models ==============

class StockOpnameDetailCreate(BaseModel):
    product_id: Optional[int] = None
    product_code: Optional[str] = None
    system_qty: float = 0
    counted_qty: float = 0
    unit_cost: float = 0
    notes: Optional[str] = None
    movements: Optional[Dict[str, Any]] = None
    photos: Optional[List[str]] = None


class StockOpnameDetailResponse(BaseModel):
    id: int
    product_id: int
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    uom_name: Optional[str] = None
    system_qty: float
    counted_qty: float
    variance_qty: float
    unit_cost: float
    variance_value: float
    notes: Optional[str] = None
    movements: Optional[Dict[str, Any]] = None
    photos: Optional[List[str]] = None


class StockOpnameCreate(BaseModel):
    branch_id: int
    opname_date: date
    period_month: str
    period_type: Optional[str] = None
    notes: Optional[str] = None
    details: List[StockOpnameDetailCreate]


class StockOpnameUpdate(BaseModel):
    opname_date: Optional[date] = None
    period_month: Optional[str] = None
    notes: Optional[str] = None
    details: Optional[List[StockOpnameDetailCreate]] = None


class StockOpnameHeaderResponse(BaseModel):
    id: int
    branch_id: int
    branch_code: Optional[str] = None
    branch_name: Optional[str] = None
    branch_type: Optional[str] = None
    opname_date: date
    period_month: str
    period_type: Optional[str] = None
    status: str
    total_value: float
    total_variance_value: Optional[float] = None
    item_count: int
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StockOpnameApprovalAction(BaseModel):
    action: str
    notes: Optional[str] = None


class WasteDetailCreate(BaseModel):
    product_id: Optional[int] = None
    product_code: Optional[str] = None
    qty: float
    unit_cost: float = 0
    reason: str = "other"
    notes: Optional[str] = None
    photos: Optional[List[str]] = None


class WasteDetailResponse(BaseModel):
    id: int
    product_id: int
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    uom_name: Optional[str] = None
    qty: float
    unit_cost: float
    total_value: float
    reason: str
    notes: Optional[str] = None
    photos: Optional[List[str]] = None


class WasteCreate(BaseModel):
    branch_id: int
    waste_date: date
    period_month: str
    notes: Optional[str] = None
    details: List[WasteDetailCreate]


class WasteUpdate(BaseModel):
    waste_date: Optional[date] = None
    period_month: Optional[str] = None
    notes: Optional[str] = None
    details: Optional[List[WasteDetailCreate]] = None


class WasteHeaderResponse(BaseModel):
    id: int
    branch_id: int
    branch_code: Optional[str] = None
    branch_name: Optional[str] = None
    branch_type: Optional[str] = None
    waste_date: date
    period_month: str
    status: str
    total_value: float
    item_count: int
    total_qty: Optional[float] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WasteApprovalAction(BaseModel):
    action: str
    notes: Optional[str] = None


class StockOpnameSummaryResponse(BaseModel):
    total: int
    draft: int
    submitted: int
    approved: int
    rejected: int
    total_variance_value: float
    pending_count: int


class WasteSummaryResponse(BaseModel):
    total: int
    draft: int
    submitted: int
    approved: int
    rejected: int
    total_value: float
    total_qty: float
    pending_count: int


# ============== Stock Opname Endpoints ==============

# NOTE: Route ordering matters in FastAPI. Specific routes (e.g. /pending-count,
# /summary) must be defined BEFORE parameterized routes (e.g. /{opname_id}).

@router.get("/stock-opname", response_model=List[StockOpnameHeaderResponse])
async def list_stock_opnames(
    branch_id: Optional[int] = Query(None),
    branch_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    period_month: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    limit: int = Query(200, le=500),
    offset: int = Query(0, ge=0),
):
    """List stock opname records with filtering."""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    query = f"""
        SELECT soh.id, soh.branch_id, {BRANCH_SELECT},
               soh.opname_date, soh.period_month, soh.period_type, soh.status,
               soh.total_variance_value AS total_value,
               soh.item_count, soh.approved_by,
               soh.approved_at, soh.notes, soh.created_by, soh.created_at, soh.updated_at
        FROM esb_data.stock_opname_header soh
        LEFT JOIN esb_data.master_branch mb ON mb.id = soh.branch_id
        WHERE 1=1
    """
    params: list = []
    if branch_id:
        query += " AND soh.branch_id = %s"
        params.append(branch_id)
    if branch_type:
        query += " AND COALESCE(mb.raw_data->>'branchType', 'OUTLET') = %s"
        params.append(branch_type)
    if status:
        query += " AND soh.status = %s"
        params.append(status)
    if period_month:
        query += " AND soh.period_month = %s"
        params.append(period_month)
    if date_from:
        query += " AND soh.opname_date >= %s"
        params.append(date_from)
    if date_to:
        query += " AND soh.opname_date <= %s"
        params.append(date_to)
    query += " ORDER BY soh.opname_date DESC, soh.id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    try:
        cur.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]
    except Exception:
        conn.rollback()
        rows = []
    finally:
        cur.close()
        conn.close()
    return rows


@router.get("/stock-opname/summary", response_model=StockOpnameSummaryResponse)
async def get_stock_opname_summary(period_month: Optional[str] = Query(None)):
    """Aggregate counts for the stock opname KPI strip."""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    where = " WHERE period_month = %s" if period_month else ""
    args = (period_month,) if period_month else ()
    try:
        cur.execute(f"""
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE status = 'draft') AS draft,
                   COUNT(*) FILTER (WHERE status = 'submitted') AS submitted,
                   COUNT(*) FILTER (WHERE status = 'approved') AS approved,
                   COUNT(*) FILTER (WHERE status = 'rejected') AS rejected,
                   COALESCE(SUM(total_variance_value), 0) AS total_variance_value
            FROM esb_data.stock_opname_header{where}
        """, args)
        row = dict(cur.fetchone())
    except Exception:
        conn.rollback()
        row = {"total": 0, "draft": 0, "submitted": 0, "approved": 0,
               "rejected": 0, "total_variance_value": 0}
    finally:
        cur.close()
        conn.close()
    row["pending_count"] = row.get("draft", 0) + row.get("submitted", 0)
    return row


@router.get("/stock-opname/pending-count")
async def get_pending_stock_opname_count():
    """Count of pending (draft + submitted) stock opname records for dashboard badges."""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT COUNT(*) AS count FROM esb_data.stock_opname_header WHERE status IN ('draft', 'submitted')")
        row = dict(cur.fetchone())
    except Exception:
        conn.rollback()
        row = {"count": 0}
    finally:
        cur.close()
        conn.close()
    return {"count": row["count"]}


@router.get("/stock-opname/{opname_id}", response_model=StockOpnameHeaderResponse)
async def get_stock_opname(opname_id: int):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        row = _fetch_header(cur, "stock_opname_header", "opname_date", opname_id)
        conn.commit()
    finally:
        cur.close()
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Stock opname not found")
    out = dict(row)
    out["total_variance_value"] = out["total_value"]
    return out


@router.get("/stock-opname/{opname_id}/details", response_model=List[StockOpnameDetailResponse])
async def get_stock_opname_details(opname_id: int):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT sod.id, sod.product_id, mp.product_code AS product_code,
                   mp.name AS product_name,
                   COALESCE(sod.movements->>'uomName', NULL) AS uom_name,
                   sod.system_qty, sod.counted_qty,
                   (sod.counted_qty - sod.system_qty) AS variance_qty,
                   sod.unit_cost,
                   ((sod.counted_qty - sod.system_qty) * sod.unit_cost) AS variance_value,
                   sod.notes, sod.movements, sod.photos
            FROM esb_data.stock_opname_detail sod
            LEFT JOIN esb_data.master_product mp ON mp.id = sod.product_id
            WHERE sod.header_id = %s
            ORDER BY mp.name NULLS LAST, sod.id
        """, (opname_id,))
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()
    return rows


def _resolve_products(cur, details) -> List[Dict[str, Any]]:
    """Resolve product_code -> product_id (and fetch unit_cost from BOM hpp when available).
    Works for both StockOpnameDetailCreate and WasteDetailCreate payloads."""
    resolved = []
    for d in details:
        pid = d.product_id
        hpp = None
        if d.product_code and not pid:
            cur.execute("""
                SELECT id FROM esb_data.master_product WHERE product_code = %s
                ORDER BY id LIMIT 1
            """, (d.product_code,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=400, detail=f"Unknown product_code: {d.product_code}")
            pid = row["id"]
        if not pid:
            raise HTTPException(status_code=400, detail="product_id or product_code is required")
        cur.execute("""
            SELECT COALESCE(SUM(bm.hpp * bm.qty) / NULLIF(SUM(bm.qty), 0), 0) AS unit_cost
            FROM esb_data.master_bom_material bm
            JOIN esb_data.master_product mp2 ON mp2.esb_id = bm.bom_esb_id
            WHERE mp2.id = %s
        """, (pid,))
        r = cur.fetchone()
        if r and r["unit_cost"]:
            hpp = float(r["unit_cost"])
        item = {
            "product_id": pid,
            "unit_cost": d.unit_cost if d.unit_cost else (hpp or 0),
            "notes": d.notes,
            "photos": d.photos,
        }
        if hasattr(d, "qty"):
            item["qty"] = d.qty
            item["reason"] = d.reason
        else:
            item["system_qty"] = d.system_qty
            item["counted_qty"] = d.counted_qty
            item["movements"] = d.movements
        resolved.append(item)
    return resolved


@router.post("/stock-opname", response_model=StockOpnameHeaderResponse)
async def create_stock_opname(data: StockOpnameCreate, x_user_id: str = Header("system")):
    """Create a stock opname record (draft status). unit_cost defaults to BOM-derived cost when omitted."""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        details = _resolve_products(cur, data.details)
        _validate_opname_scope(cur, data.period_type or 'monthly', details)
        total_variance = sum((d["counted_qty"] - d["system_qty"]) * d["unit_cost"] for d in details)
        cur.execute("""
            INSERT INTO esb_data.stock_opname_header
                (branch_id, opname_date, period_month, period_type, status, total_variance_value,
                 item_count, created_by, created_at, updated_at, notes)
            VALUES (%s, %s, %s, %s, 'draft', %s, %s, %s, NOW(), NOW(), %s)
            RETURNING id
        """, (
            data.branch_id, data.opname_date, data.period_month,
            data.period_type or 'monthly',
            total_variance, len(details), x_user_id, data.notes
        ))
        header_id = cur.fetchone()["id"]
        for d in details:
            variance_qty = d["counted_qty"] - d["system_qty"]
            cur.execute("""
                INSERT INTO esb_data.stock_opname_detail
                    (header_id, product_id, system_qty, counted_qty, unit_cost,
                     variance_qty, variance_value, notes, movements, photos)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                header_id, d["product_id"], d["system_qty"], d["counted_qty"],
                d["unit_cost"], variance_qty, variance_qty * d["unit_cost"],
                d["notes"],
                json.dumps(d["movements"]) if d["movements"] else None,
                json.dumps(d["photos"]) if d["photos"] else None,
            ))
        conn.commit()
        row = _fetch_header(cur, "stock_opname_header", "opname_date", header_id)
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()
    out = dict(row)
    out["total_variance_value"] = out["total_value"]
    return out


@router.put("/stock-opname/{opname_id}", response_model=StockOpnameHeaderResponse)
async def update_stock_opname(
    opname_id: int,
    data: StockOpnameUpdate,
    x_user_id: str = Header("system"),
):
    """Update a stock opname. Only draft or rejected records can be edited."""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT status FROM esb_data.stock_opname_header WHERE id = %s", (opname_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Stock opname not found")
        if row["status"] not in ("draft", "rejected"):
            raise HTTPException(status_code=400, detail=f"Cannot edit record in status '{row['status']}'")
        sets, params = ["updated_at = NOW()"], []
        if data.opname_date is not None:
            sets.append("opname_date = %s")
            params.append(data.opname_date)
        if data.period_month is not None:
            sets.append("period_month = %s")
            params.append(data.period_month)
        if data.notes is not None:
            sets.append("notes = %s")
            params.append(data.notes)
        if data.details is not None:
            details = _resolve_products(cur, data.details)
            cur.execute("SELECT COALESCE(period_type, 'monthly') AS pt FROM esb_data.stock_opname_header WHERE id = %s", (opname_id,))
            pt_row = cur.fetchone()
            _validate_opname_scope(cur, pt_row["pt"] if pt_row else 'monthly', details)
            total_variance = sum((d["counted_qty"] - d["system_qty"]) * d["unit_cost"] for d in details)
            sets += ["total_variance_value = %s", "item_count = %s"]
            params += [total_variance, len(details)]
            cur.execute("DELETE FROM esb_data.stock_opname_detail WHERE header_id = %s", (opname_id,))
            for d in details:
                variance_qty = d["counted_qty"] - d["system_qty"]
                cur.execute("""
                    INSERT INTO esb_data.stock_opname_detail
                        (header_id, product_id, system_qty, counted_qty, unit_cost,
                         variance_qty, variance_value, notes, movements, photos)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    opname_id, d["product_id"], d["system_qty"], d["counted_qty"],
                    d["unit_cost"], variance_qty, variance_qty * d["unit_cost"],
                    d["notes"],
                    json.dumps(d["movements"]) if d["movements"] else None,
                    json.dumps(d["photos"]) if d["photos"] else None,
                ))
        params.append(opname_id)
        cur.execute(f"""
            UPDATE esb_data.stock_opname_header SET {', '.join(sets)}
            WHERE id = %s
        """, params)
        conn.commit()
        out_row = _fetch_header(cur, "stock_opname_header", "opname_date", opname_id)
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()
    out = dict(out_row)
    out["total_variance_value"] = out["total_value"]
    return out


@router.delete("/stock-opname/{opname_id}")
async def delete_stock_opname(opname_id: int):
    """Delete a stock opname. Only draft or rejected records can be deleted."""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            DELETE FROM esb_data.stock_opname_header
            WHERE id = %s AND status IN ('draft', 'rejected')
            RETURNING id
        """, (opname_id,))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise HTTPException(status_code=400, detail="Not found or not deletable (only draft/rejected)")
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()
    return {"deleted": row["id"]}


@router.post("/stock-opname/{opname_id}/submit", response_model=StockOpnameHeaderResponse)
async def submit_stock_opname(opname_id: int, x_user_id: str = Header("system")):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            UPDATE esb_data.stock_opname_header
            SET status = 'submitted', updated_at = NOW()
            WHERE id = %s AND status = 'draft'
        """, (opname_id,))
        if cur.rowcount == 0:
            conn.rollback()
            raise HTTPException(status_code=400, detail="Not found or not in draft status")
        conn.commit()
        row = _fetch_header(cur, "stock_opname_header", "opname_date", opname_id)
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
    out = dict(row)
    out["total_variance_value"] = out["total_value"]
    return out


@router.post("/stock-opname/{opname_id}/approve", response_model=StockOpnameHeaderResponse)
async def approve_stock_opname(
    opname_id: int,
    action: StockOpnameApprovalAction,
    x_user_id: str = Header("system"),
):
    if action.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")
    new_status = "approved" if action.action == "approve" else "rejected"
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            UPDATE esb_data.stock_opname_header
            SET status = %s, approved_by = %s, approved_at = NOW(),
                notes = COALESCE(%s, notes), updated_at = NOW()
            WHERE id = %s AND status = 'submitted'
        """, (new_status, x_user_id, action.notes, opname_id))
        if cur.rowcount == 0:
            conn.rollback()
            raise HTTPException(status_code=400, detail="Not found or not submitted")
        conn.commit()
        row = _fetch_header(cur, "stock_opname_header", "opname_date", opname_id)
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
    out = dict(row)
    out["total_variance_value"] = out["total_value"]
    return out


# ============== Waste Endpoints ==============

@router.get("/waste", response_model=List[WasteHeaderResponse])
async def list_waste_records(
    branch_id: Optional[int] = Query(None),
    branch_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    period_month: Optional[str] = Query(None),
    reason: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    limit: int = Query(200, le=500),
    offset: int = Query(0, ge=0),
):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    query = f"""
        SELECT wh.id, wh.branch_id, {BRANCH_SELECT},
               wh.waste_date, wh.period_month, wh.status,
               wh.total_value, wh.item_count, wh.approved_by,
               wh.approved_at, wh.notes, wh.created_by, wh.created_at, wh.updated_at,
               COALESCE((SELECT SUM(wd.qty) FROM esb_data.waste_detail wd
                         WHERE wd.header_id = wh.id), 0) AS total_qty
        FROM esb_data.waste_header wh
        LEFT JOIN esb_data.master_branch mb ON mb.id = wh.branch_id
        WHERE 1=1
    """
    params: list = []
    if branch_id:
        query += " AND wh.branch_id = %s"
        params.append(branch_id)
    if branch_type:
        query += " AND COALESCE(mb.raw_data->>'branchType', 'OUTLET') = %s"
        params.append(branch_type)
    if status:
        query += " AND wh.status = %s"
        params.append(status)
    if period_month:
        query += " AND wh.period_month = %s"
        params.append(period_month)
    if date_from:
        query += " AND wh.waste_date >= %s"
        params.append(date_from)
    if date_to:
        query += " AND wh.waste_date <= %s"
        params.append(date_to)
    if reason:
        query += " AND EXISTS (SELECT 1 FROM esb_data.waste_detail wd WHERE wd.header_id = wh.id AND wd.reason = %s)"
        params.append(reason)
    query += " ORDER BY wh.waste_date DESC, wh.id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    try:
        cur.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]
    except Exception:
        conn.rollback()
        rows = []
    finally:
        cur.close()
        conn.close()
    return rows


@router.get("/waste/summary", response_model=WasteSummaryResponse)
async def get_waste_summary(period_month: Optional[str] = Query(None)):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE wh.status = 'draft') AS draft,
                   COUNT(*) FILTER (WHERE wh.status = 'submitted') AS submitted,
                   COUNT(*) FILTER (WHERE wh.status = 'approved') AS approved,
                   COUNT(*) FILTER (WHERE wh.status = 'rejected') AS rejected,
                   COALESCE(SUM(wh.total_value), 0) AS total_value,
                   COALESCE((SELECT SUM(wd.qty) FROM esb_data.waste_detail wd
                             JOIN esb_data.waste_header wh2 ON wh2.id = wd.header_id
                             WHERE (%s IS NULL OR wh2.period_month = %s)), 0) AS total_qty
            FROM esb_data.waste_header wh
            WHERE (%s IS NULL OR wh.period_month = %s)
        """, (period_month, period_month, period_month, period_month))
        row = dict(cur.fetchone())
    except Exception:
        conn.rollback()
        row = {"total": 0, "draft": 0, "submitted": 0, "approved": 0,
               "rejected": 0, "total_value": 0, "total_qty": 0}
    finally:
        cur.close()
        conn.close()
    row["pending_count"] = row.get("draft", 0) + row.get("submitted", 0)
    return row


@router.get("/waste/pending-count")
async def get_pending_waste_count():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT COUNT(*) AS count FROM esb_data.waste_header WHERE status IN ('draft', 'submitted')")
        row = dict(cur.fetchone())
    except Exception:
        conn.rollback()
        row = {"count": 0}
    finally:
        cur.close()
        conn.close()
    return {"count": row["count"]}


@router.get("/waste/{waste_id}", response_model=WasteHeaderResponse)
async def get_waste_record(waste_id: int):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        row = _fetch_header(cur, "waste_header", "waste_date", waste_id)
        conn.commit()
    finally:
        cur.close()
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Waste record not found")
    return dict(row)


@router.get("/waste/{waste_id}/details", response_model=List[WasteDetailResponse])
async def get_waste_details(waste_id: int):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT wd.id, wd.product_id, mp.product_code AS product_code,
                   mp.name AS product_name,
                   COALESCE(mp.raw_data->>'uomName', NULL) AS uom_name,
                   wd.qty, wd.unit_cost,
                   (wd.qty * wd.unit_cost) AS total_value, wd.reason, wd.notes, wd.photos
            FROM esb_data.waste_detail wd
            LEFT JOIN esb_data.master_product mp ON mp.id = wd.product_id
            WHERE wd.header_id = %s
            ORDER BY mp.name NULLS LAST, wd.id
        """, (waste_id,))
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()
    return rows


@router.post("/waste", response_model=WasteHeaderResponse)
async def create_waste_record(data: WasteCreate, x_user_id: str = Header("system")):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        details = _resolve_products(cur, data.details)
        total_value = sum(d["qty"] * d["unit_cost"] for d in details)
        cur.execute("""
            INSERT INTO esb_data.waste_header
                (branch_id, waste_date, period_month, status, total_value, item_count,
                 created_by, created_at, updated_at, notes)
            VALUES (%s, %s, %s, 'draft', %s, %s, %s, NOW(), NOW(), %s)
            RETURNING id
        """, (
            data.branch_id, data.waste_date, data.period_month,
            total_value, len(details), x_user_id, data.notes
        ))
        header_id = cur.fetchone()["id"]
        for d in details:
            cur.execute("""
                INSERT INTO esb_data.waste_detail
                    (header_id, product_id, qty, unit_cost, total_value, reason, notes, photos)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                header_id, d["product_id"], d["qty"], d["unit_cost"],
                d["qty"] * d["unit_cost"], d["reason"], d["notes"],
                json.dumps(d["photos"]) if d["photos"] else None,
            ))
        conn.commit()
        row = _fetch_header(cur, "waste_header", "waste_date", header_id)
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()
    return dict(row)


@router.put("/waste/{waste_id}", response_model=WasteHeaderResponse)
async def update_waste_record(
    waste_id: int,
    data: WasteUpdate,
    x_user_id: str = Header("system"),
):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT status FROM esb_data.waste_header WHERE id = %s", (waste_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Waste record not found")
        if row["status"] not in ("draft", "rejected"):
            raise HTTPException(status_code=400, detail=f"Cannot edit record in status '{row['status']}'")
        sets, params = ["updated_at = NOW()"], []
        if data.waste_date is not None:
            sets.append("waste_date = %s")
            params.append(data.waste_date)
        if data.period_month is not None:
            sets.append("period_month = %s")
            params.append(data.period_month)
        if data.notes is not None:
            sets.append("notes = %s")
            params.append(data.notes)
        if data.details is not None:
            details = _resolve_products(cur, data.details)
            total_value = sum(d["qty"] * d["unit_cost"] for d in details)
            sets += ["total_value = %s", "item_count = %s"]
            params += [total_value, len(details)]
            cur.execute("DELETE FROM esb_data.waste_detail WHERE header_id = %s", (waste_id,))
            for d in details:
                cur.execute("""
                    INSERT INTO esb_data.waste_detail
                        (header_id, product_id, qty, unit_cost, total_value, reason, notes, photos)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    waste_id, d["product_id"], d["qty"], d["unit_cost"],
                    d["qty"] * d["unit_cost"], d["reason"], d["notes"],
                    json.dumps(d["photos"]) if d["photos"] else None,
                ))
        params.append(waste_id)
        cur.execute(f"UPDATE esb_data.waste_header SET {', '.join(sets)} WHERE id = %s", params)
        conn.commit()
        out_row = _fetch_header(cur, "waste_header", "waste_date", waste_id)
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()
    return dict(out_row)


@router.delete("/waste/{waste_id}")
async def delete_waste_record(waste_id: int):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            DELETE FROM esb_data.waste_header
            WHERE id = %s AND status IN ('draft', 'rejected')
            RETURNING id
        """, (waste_id,))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise HTTPException(status_code=400, detail="Not found or not deletable (only draft/rejected)")
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()
    return {"deleted": row["id"]}


@router.post("/waste/{waste_id}/submit", response_model=WasteHeaderResponse)
async def submit_waste_record(waste_id: int, x_user_id: str = Header("system")):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            UPDATE esb_data.waste_header
            SET status = 'submitted', updated_at = NOW()
            WHERE id = %s AND status = 'draft'
        """, (waste_id,))
        if cur.rowcount == 0:
            conn.rollback()
            raise HTTPException(status_code=400, detail="Not found or not in draft status")
        conn.commit()
        row = _fetch_header(cur, "waste_header", "waste_date", waste_id)
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
    return dict(row)


@router.post("/waste/{waste_id}/approve", response_model=WasteHeaderResponse)
async def approve_waste_record(
    waste_id: int,
    action: WasteApprovalAction,
    x_user_id: str = Header("system"),
):
    if action.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")
    new_status = "approved" if action.action == "approve" else "rejected"
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            UPDATE esb_data.waste_header
            SET status = %s, approved_by = %s, approved_at = NOW(),
                notes = COALESCE(%s, notes), updated_at = NOW()
            WHERE id = %s AND status = 'submitted'
        """, (new_status, x_user_id, action.notes, waste_id))
        if cur.rowcount == 0:
            conn.rollback()
            raise HTTPException(status_code=400, detail="Not found or not submitted")
        conn.commit()
        row = _fetch_header(cur, "waste_header", "waste_date", waste_id)
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
    return dict(row)


# ============== Stock System Endpoints ==============

@router.get("/stock/system")
async def get_stock_system(
    report_date: Optional[date] = Query(None, description="Balance date; default = latest available"),
    company_id: int = Query(1),
    scope: str = Query("all", description="all | packaging | raw"),
):
    """Product x branch stock matrix from report_stock_movement ending balances,
    overlaid with manual stock_system_adjustment overrides.
    scope filters product categories: packaging -> PACKAGING, raw -> RAW MATERIAL*/Roasted."""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if report_date is None:
            cur.execute("SELECT MAX(report_date) AS d FROM esb_data.report_stock_movement WHERE company_id = %s", (company_id,))
            r = cur.fetchone()
            report_date = r["d"] if r and r["d"] else None

        scope_sql = "TRUE"
        if scope == "packaging":
            scope_sql = "upper(category_name) LIKE '%%PACKAG%%'"
        elif scope == "raw":
            scope_sql = "upper(category_name) LIKE 'RAW MATERIAL%%' OR upper(category_name) LIKE 'ROASTED%%'"
        cur.execute(f"""
            SELECT id, product_code, name, category_name, sub_category_name, category_type_name
            FROM esb_data.master_product
            WHERE company_id = %s AND flag_active = true AND ({scope_sql})
            ORDER BY name
        """, (company_id,))
        products = cur.fetchall()

        balances: Dict[str, Dict[str, Any]] = {}
        uom_by_code: Dict[str, str] = {}
        if report_date is not None:
            cur.execute("""
                SELECT DISTINCT ON (sm.product_code, sm.branch_esb_id)
                       sm.product_code, sm.product_name, sm.branch_esb_id,
                       sm.qty_balance, sm.uom_name
                FROM esb_data.report_stock_movement sm
                WHERE sm.company_id = %s AND sm.report_date = %s
                ORDER BY sm.product_code, sm.branch_esb_id, sm.report_date DESC, sm.id DESC
            """, (company_id, report_date))
            for r in cur.fetchall():
                balances[(r["product_code"], r["branch_esb_id"])] = r
                if r.get("uom_name") and r["product_code"] not in uom_by_code:
                    uom_by_code[r["product_code"]] = r["uom_name"]

        cur.execute(f"""
            SELECT id, esb_id, branch_code, name,
                   {BRANCH_TYPE_CASE.format(col="raw_data->>'branchType'")} AS branch_type
            FROM esb_data.master_branch WHERE company_id = %s ORDER BY id
        """, (company_id,))
        branches = {b["esb_id"]: b for b in cur.fetchall() if b["esb_id"]}

        cur.execute("""
            SELECT branch_id, product_id, qty FROM esb_data.stock_system_adjustment
            WHERE company_id = %s AND adjust_date = COALESCE(%s, CURRENT_DATE)
        """, (company_id, report_date))
        adjustments = {(a["product_id"], a["branch_id"]): a["qty"] for a in cur.fetchall()}

        items = []
        for p in products:
            outlet: Dict[str, float] = {}
            hub_wh: Dict[str, float] = {}
            hub_ck: Dict[str, float] = {}
            for (pc, beid), bal in balances.items():
                if pc != p["product_code"] or beid not in branches:
                    continue
                b = branches[beid]
                qty = float(bal["qty_balance"] or 0)
                adj = adjustments.get((p["id"], b["id"]))
                if adj is not None:
                    qty = float(adj)
                bucket = {"OUTLET": outlet, "HUB WH": hub_wh}.get(b["branch_type"])
                if bucket is None and b["branch_type"] == "HUB CK":
                    bucket = hub_ck
                if bucket is not None:
                    bucket[str(b["id"])] = qty
            if not (outlet or hub_wh or hub_ck):
                continue
            items.append({
                "productId": p["id"],
                "productCode": p["product_code"],
                "productName": p["name"],
                "categoryName": p["category_name"],
                "categoryTypeName": p["category_type_name"],
                "unit": uom_by_code.get(p["product_code"]),
                "outletStock": outlet,
                "hubWhStock": hub_wh,
                "hubCkStock": hub_ck,
            })
        meta = {
            "report_date": str(report_date) if report_date else None,
            "branches": [
                {"id": b["id"], "branchCode": b["branch_code"], "branchName": b["name"], "branchType": b["branch_type"]}
                for b in branches.values()
            ],
        }
    finally:
        cur.close()
        conn.close()
    return {"meta": meta, "items": items}


class StockSystemAdjustment(BaseModel):
    productId: int
    branchId: int
    qty: float
    note: Optional[str] = None


class StockSystemUpdateRequest(BaseModel):
    stocks: List[StockSystemAdjustment]
    adjust_date: Optional[date] = None


@router.put("/stock/system")
async def update_stock_system(data: StockSystemUpdateRequest, x_user_id: str = Header("system")):
    """Persist manual stock adjustments (one row per product x branch)."""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        adjust_date = data.adjust_date or date.today()
        for s in data.stocks:
            cur.execute("""
                INSERT INTO esb_data.stock_system_adjustment
                    (company_id, branch_id, product_id, adjust_date, qty, note, created_by)
                VALUES (1, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (company_id, branch_id, product_id, adjust_date)
                DO UPDATE SET qty = EXCLUDED.qty, note = EXCLUDED.note,
                              created_by = EXCLUDED.created_by, updated_at = NOW()
            """, (s.branchId, s.productId, adjust_date, s.qty, s.note, x_user_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()
    return {"updated": len(data.stocks)}
