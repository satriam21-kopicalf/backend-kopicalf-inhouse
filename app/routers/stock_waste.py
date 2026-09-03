"""
Stock Opname and Waste Management API
Supports outlet, hub-wh, and hub-ck branches for COGS calculation
"""
from fastapi import APIRouter, HTTPException, Query, Header
from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime

router = APIRouter(prefix="/api/v1", tags=["stock-waste"])


def get_conn():
    from app.core.db import get_db_connection
    conn = get_db_connection()
    return conn

# ============== Pydantic Models ==============

class StockOpnameDetailCreate(BaseModel):
    product_id: int
    system_qty: float
    counted_qty: float
    unit_cost: float
    notes: Optional[str] = None


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


class StockOpnameCreate(BaseModel):
    branch_id: int
    opname_date: date
    period_month: str
    notes: Optional[str] = None
    details: List[StockOpnameDetailCreate]


class StockOpnameHeaderResponse(BaseModel):
    id: int
    branch_id: int
    branch_code: Optional[str] = None
    branch_name: Optional[str] = None
    branch_type: Optional[str] = None
    opname_date: date
    period_month: str
    status: str
    total_variance_value: float
    item_count: int
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: datetime


class StockOpnameApprovalAction(BaseModel):
    action: str
    notes: Optional[str] = None


class WasteDetailCreate(BaseModel):
    product_id: int
    qty: float
    unit_cost: float
    reason: str
    notes: Optional[str] = None


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


class WasteCreate(BaseModel):
    branch_id: int
    waste_date: date
    period_month: str
    notes: Optional[str] = None
    details: List[WasteDetailCreate]


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
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: datetime


class WasteApprovalAction(BaseModel):
    action: str
    notes: Optional[str] = None


# ============== Stock Opname Endpoints ==============

@router.get("/stock-opname", response_model=List[StockOpnameHeaderResponse])
async def list_stock_opnames(
    branch_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    period_month: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """List all stock opname records with filtering."""
    conn = get_conn()
    cur = conn.cursor()

    query = """
        SELECT soh.id, soh.branch_id, mb.code AS branch_code, mb.name AS branch_name,
               mb.branch_type, soh.opname_date, soh.period_month, soh.status,
               soh.total_variance_value, soh.item_count, soh.approved_by,
               soh.approved_at, soh.notes, soh.created_by, soh.created_at, soh.updated_at
        FROM esb_data.stock_opname_header soh
        LEFT JOIN esb_data.master_branch mb ON mb.id = soh.branch_id
        WHERE 1=1
    """
    params = []

    if branch_id:
        query += " AND soh.branch_id = %s"
        params.append(branch_id)
    if status:
        query += " AND soh.status = %s"
        params.append(status)
    if period_month:
        query += " AND soh.period_month = %s"
        params.append(period_month)

    query += " ORDER BY soh.created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    try:
        cur.execute(query, params)
        rows = cur.fetchall()
    except Exception:
        conn.rollback()
        rows = []
    finally:
        cur.close()
        conn.close()

    return [dict(row) for row in rows]


@router.get("/stock-opname/{opname_id}", response_model=StockOpnameHeaderResponse)
async def get_stock_opname(opname_id: int):
    """Get a single stock opname record."""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT soh.id, soh.branch_id, mb.code AS branch_code, mb.name AS branch_name,
               mb.branch_type, soh.opname_date, soh.period_month, soh.status,
               soh.total_variance_value, soh.item_count, soh.approved_by,
               soh.approved_at, soh.notes, soh.created_by, soh.created_at, soh.updated_at
        FROM esb_data.stock_opname_header soh
        LEFT JOIN esb_data.master_branch mb ON mb.id = soh.branch_id
        WHERE soh.id = %s
    """, (opname_id,))
    
    row = cur.fetchone()
    cur.close()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Stock opname not found")
    
    return dict(row)


@router.get("/stock-opname/{opname_id}/details", response_model=List[StockOpnameDetailResponse])
async def get_stock_opname_details(opname_id: int):
    """Get line items for a stock opname record."""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT sod.id, sod.product_id, mp.code AS product_code, mp.name AS product_name,
               mu.name AS uom_name, sod.system_qty, sod.counted_qty,
               (sod.counted_qty - sod.system_qty) AS variance_qty,
               sod.unit_cost,
               ((sod.counted_qty - sod.system_qty) * sod.unit_cost) AS variance_value,
               sod.notes
        FROM esb_data.stock_opname_detail sod
        LEFT JOIN esb_data.master_product mp ON mp.id = sod.product_id
        LEFT JOIN esb_data.master_uom mu ON mu.id = mp.uom_id
        WHERE sod.header_id = %s
        ORDER BY mp.name
    """, (opname_id,))
    
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(row) for row in rows]


@router.post("/stock-opname", response_model=StockOpnameHeaderResponse)
async def create_stock_opname(data: StockOpnameCreate, x_user_id: str = Header("system")):
    """Create a new stock opname record (draft status)."""
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        total_variance = sum(
            (d.counted_qty - d.system_qty) * d.unit_cost
            for d in data.details
        )
        
        cur.execute("""
            INSERT INTO esb_data.stock_opname_header
                (branch_id, opname_date, period_month, status, total_variance_value,
                 item_count, created_by, created_at, updated_at, notes)
            VALUES (%s, %s, %s, 'draft', %s, %s, %s, NOW(), NOW(), %s)
            RETURNING id
        """, (
            data.branch_id, data.opname_date, data.period_month,
            total_variance, len(data.details), x_user_id, data.notes
        ))
        header_id = cur.fetchone()["id"]
        
        for detail in data.details:
            variance_qty = detail.counted_qty - detail.system_qty
            variance_value = variance_qty * detail.unit_cost
            cur.execute("""
                INSERT INTO esb_data.stock_opname_detail
                    (header_id, product_id, system_qty, counted_qty, unit_cost,
                     variance_qty, variance_value, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                header_id, detail.product_id, detail.system_qty, detail.counted_qty,
                detail.unit_cost, variance_qty, variance_value, detail.notes
            ))
        
        conn.commit()
        
        cur.execute("""
            SELECT soh.id, soh.branch_id, mb.code AS branch_code, mb.name AS branch_name,
                   mb.branch_type, soh.opname_date, soh.period_month, soh.status,
                   soh.total_variance_value, soh.item_count, soh.approved_by,
                   soh.approved_at, soh.notes, soh.created_by, soh.created_at, soh.updated_at
            FROM esb_data.stock_opname_header soh
            LEFT JOIN esb_data.master_branch mb ON mb.id = soh.branch_id
            WHERE soh.id = %s
        """, (header_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row)
        
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/stock-opname/{opname_id}/submit", response_model=StockOpnameHeaderResponse)
async def submit_stock_opname(opname_id: int, x_user_id: str = Header("system")):
    """Submit a stock opname for approval."""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE esb_data.stock_opname_header
        SET status = 'submitted', updated_at = NOW()
        WHERE id = %s AND status = 'draft'
        RETURNING id, branch_id, opname_date, period_month, status, total_variance_value,
                  item_count, approved_by, approved_at, notes, created_by, created_at, updated_at
    """, (opname_id,))
    
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Stock opname not found or not in draft status")
    
    conn.commit()
    cur.close()
    conn.close()
    return dict(row)


@router.post("/stock-opname/{opname_id}/approve", response_model=StockOpnameHeaderResponse)
async def approve_stock_opname(
    opname_id: int,
    action: StockOpnameApprovalAction,
    x_user_id: str = Header("system")
):
    """Approve or reject a stock opname."""
    if action.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")
    
    new_status = "approved" if action.action == "approve" else "rejected"
    
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE esb_data.stock_opname_header
        SET status = %s, approved_by = %s, approved_at = NOW(),
            notes = COALESCE(%s, notes), updated_at = NOW()
        WHERE id = %s AND status = 'submitted'
        RETURNING id, branch_id, opname_date, period_month, status, total_variance_value,
                  item_count, approved_by, approved_at, notes, created_by, created_at, updated_at
    """, (new_status, x_user_id, action.notes, opname_id))
    
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Stock opname not found or not submitted")
    
    conn.commit()
    cur.close()
    conn.close()
    return dict(row)


# ============== Waste Endpoints ==============

@router.get("/waste", response_model=List[WasteHeaderResponse])
async def list_waste_records(
    branch_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    period_month: Optional[str] = Query(None),
    reason: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    conn = get_conn()
    cur = conn.cursor()
    query = """SELECT wh.id, wh.branch_id, mb.code AS branch_code, mb.name AS branch_name,
               mb.branch_type, wh.waste_date, wh.period_month, wh.status,
               wh.total_value, wh.item_count, wh.approved_by,
               wh.approved_at, wh.notes, wh.created_by, wh.created_at, wh.updated_at
        FROM esb_data.waste_header wh
        LEFT JOIN esb_data.master_branch mb ON mb.id = wh.branch_id
        WHERE 1=1"""
    params = []
    if branch_id:
        query += " AND wh.branch_id = %s"
        params.append(branch_id)
    if status:
        query += " AND wh.status = %s"
        params.append(status)
    if period_month:
        query += " AND wh.period_month = %s"
        params.append(period_month)
    if reason:
        query += " AND EXISTS (SELECT 1 FROM esb_data.waste_detail wd WHERE wd.header_id = wh.id AND wd.reason = %s)"
        params.append(reason)
    query += " ORDER BY wh.created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    try:
        cur.execute(query, params)
        rows = cur.fetchall()
    except Exception:
        conn.rollback()
        rows = []
    finally:
        cur.close()
        conn.close()
    return [dict(row) for row in rows]


@router.get("/waste/{waste_id}", response_model=WasteHeaderResponse)
async def get_waste_record(waste_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT wh.id, wh.branch_id, mb.code AS branch_code, mb.name AS branch_name, mb.branch_type, wh.waste_date, wh.period_month, wh.status, wh.total_value, wh.item_count, wh.approved_by, wh.approved_at, wh.notes, wh.created_by, wh.created_at, wh.updated_at FROM esb_data.waste_header wh LEFT JOIN esb_data.master_branch mb ON mb.id = wh.branch_id WHERE wh.id = %s", (waste_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Waste record not found")
    return dict(row)


@router.get("/waste/{waste_id}/details", response_model=List[WasteDetailResponse])
async def get_waste_details(waste_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT wd.id, wd.product_id, mp.code AS product_code, mp.name AS product_name, mu.name AS uom_name, wd.qty, wd.unit_cost, (wd.qty * wd.unit_cost) AS total_value, wd.reason, wd.notes FROM esb_data.waste_detail wd LEFT JOIN esb_data.master_product mp ON mp.id = wd.product_id LEFT JOIN esb_data.master_uom mu ON mu.id = mp.uom_id WHERE wd.header_id = %s ORDER BY mp.name", (waste_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(row) for row in rows]


@router.post("/waste", response_model=WasteHeaderResponse)
async def create_waste_record(data: WasteCreate, x_user_id: str = Header("system")):
    conn = get_conn()
    cur = conn.cursor()
    try:
        total_value = sum(d.qty * d.unit_cost for d in data.details)
        cur.execute("INSERT INTO esb_data.waste_header (branch_id, waste_date, period_month, status, total_value, item_count, created_by, created_at, updated_at, notes) VALUES (%s, %s, %s, 'draft', %s, %s, %s, NOW(), NOW(), %s) RETURNING id", (data.branch_id, data.waste_date, data.period_month, total_value, len(data.details), x_user_id, data.notes))
        header_id = cur.fetchone()["id"]
        for detail in data.details:
            cur.execute("INSERT INTO esb_data.waste_detail (header_id, product_id, qty, unit_cost, total_value, reason, notes) VALUES (%s, %s, %s, %s, %s, %s, %s)", (header_id, detail.product_id, detail.qty, detail.unit_cost, detail.qty * detail.unit_cost, detail.reason, detail.notes))
        conn.commit()
        cur.execute("SELECT wh.id, wh.branch_id, mb.code AS branch_code, mb.name AS branch_name, mb.branch_type, wh.waste_date, wh.period_month, wh.status, wh.total_value, wh.item_count, wh.approved_by, wh.approved_at, wh.notes, wh.created_by, wh.created_at, wh.updated_at FROM esb_data.waste_header wh LEFT JOIN esb_data.master_branch mb ON mb.id = wh.branch_id WHERE wh.id = %s", (header_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row)
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/waste/{waste_id}/submit", response_model=WasteHeaderResponse)
async def submit_waste_record(waste_id: int, x_user_id: str = Header("system")):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE esb_data.waste_header SET status = 'submitted', updated_at = NOW() WHERE id = %s AND status = 'draft' RETURNING id, branch_id, waste_date, period_month, status, total_value, item_count, approved_by, approved_at, notes, created_by, created_at, updated_at", (waste_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Waste record not found or not in draft status")
    conn.commit()
    cur.close()
    conn.close()
    return dict(row)


@router.post("/waste/{waste_id}/approve", response_model=WasteHeaderResponse)
async def approve_waste_record(waste_id: int, action: WasteApprovalAction, x_user_id: str = Header("system")):
    if action.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")
    new_status = "approved" if action.action == "approve" else "rejected"
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE esb_data.waste_header SET status = %s, approved_by = %s, approved_at = NOW(), notes = COALESCE(%s, notes), updated_at = NOW() WHERE id = %s AND status = 'submitted' RETURNING id, branch_id, waste_date, period_month, status, total_value, item_count, approved_by, approved_at, notes, created_by, created_at, updated_at", (new_status, x_user_id, action.notes, waste_id))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Waste record not found or not submitted")
    conn.commit()
    cur.close()
    conn.close()
    return dict(row)


@router.get("/stock-opname/pending-count")
async def get_pending_stock_opname_count():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS count FROM esb_data.stock_opname_header WHERE status IN ('draft', 'submitted')")
    row = dict(cur.fetchone())
    cur.close()
    conn.close()
    return {"count": row["count"]}


@router.get("/waste/pending-count")
async def get_pending_waste_count():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS count FROM esb_data.waste_header WHERE status IN ('draft', 'submitted')")
    row = dict(cur.fetchone())
    cur.close()
    conn.close()
    return {"count": row["count"]}
