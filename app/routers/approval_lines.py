"""
Approval Lines API: approval configurations, workflows, and RBAC.
Manages multi-level approval chains based on department, division, and form type.
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Header, HTTPException, Query
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from app.routers.auth import require_user

router = APIRouter(prefix="/api/v1/approval-lines", tags=["approval-lines"])


def get_conn():
    from app.core.db import get_db_connection
    return get_db_connection()


def _require_perm(user: dict, code: str):
    if code not in (user.get("permissions") or []):
        raise HTTPException(status_code=403, detail=f"Permission required: {code}")


# ============ Pydantic Models ============

class ApprovalConfigCreate(BaseModel):
    name: str
    description: Optional[str] = None
    form_type: str  # e.g., 'FACILITY_REQUEST', 'TOOL_REQUEST', 'PURCHASE_REQUEST'
    department_id: Optional[int] = None
    division_id: Optional[int] = None
    branch_id: Optional[int] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    is_active: bool = True
    levels: list["ApprovalLevelCreate"] = []


class ApprovalConfigUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    form_type: Optional[str] = None
    department_id: Optional[int] = None
    division_id: Optional[int] = None
    branch_id: Optional[int] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    is_active: Optional[bool] = None


class ApprovalLevelCreate(BaseModel):
    level: int
    name: str
    approver_type: str  # 'USER', 'ROLE', 'DEPARTMENT_HEAD', 'DIVISION_HEAD'
    approver_id: Optional[int] = None  # user_id or role_id
    approver_ids: Optional[list[int]] = None  # multiple approvers
    is_auto_approve: bool = False
    timeout_hours: Optional[int] = None


class ApprovalLevelUpdate(BaseModel):
    name: Optional[str] = None
    approver_type: Optional[str] = None
    approver_id: Optional[int] = None
    approver_ids: Optional[list[int]] = None
    is_auto_approve: Optional[bool] = None
    timeout_hours: Optional[int] = None
    is_active: Optional[bool] = None


class ApprovalRequestCreate(BaseModel):
    config_id: int
    form_type: str
    reference_id: str  # ID of the form being approved
    requester_id: int
    department_id: Optional[int] = None
    division_id: Optional[int] = None
    amount: Optional[float] = None
    data_json: Optional[dict] = None


class ApprovalAction(BaseModel):
    action: str  # 'APPROVE', 'REJECT', 'REQUEST_INFO'
    note: Optional[str] = None


# ============ RBAC Models ============

class PermissionCreate(BaseModel):
    code: str  # e.g., 'approval.config.view', 'approval.request.approve'
    name: str
    module: str  # 'approval', 'approval.config', 'approval.request', 'approval.rbac'
    description: Optional[str] = None


class RolePermissionUpdate(BaseModel):
    permission_ids: list[int]
    page_access: dict[str, bool]  # { '/management/approval-lines': True, ... }
    crud_access: dict[str, str]  # { 'approval.config': 'CRUD', 'approval.request': 'RU' }


# ============ Approval Configurations ============

@router.get("/configurations")
async def list_configurations(
    search: Optional[str] = Query(None),
    form_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    authorization: Optional[str] = Header(None),
):
    """List approval configurations. Returns empty list if internal tables don't exist."""
    # Optional auth for now
    if authorization:
        try:
            user = require_user(authorization)
            _require_perm(user, "approval.config.view")
        except HTTPException:
            pass

    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Check if internal tables exist
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'internal' AND table_name = 'approval_configurations'
            ) AS exists
        """)
        if not cur.fetchone()["exists"]:
            return {"data": [], "total": 0}

        where, params = ["1=1"], []
        if search:
            where.append("(ac.name ILIKE %s OR ac.description ILIKE %s)")
            params += [f"%{search}%", f"%{search}%"]
        if form_type:
            where.append("ac.form_type = %s")
            params.append(form_type)
        if is_active is not None:
            where.append("ac.is_active = %s")
            params.append(is_active)
        params += [limit, offset]
        cur.execute(f"""
            SELECT ac.*,
                   (SELECT count(*) FROM internal.approval_levels al
                    WHERE al.config_id = ac.id AND al.is_active = true) AS level_count,
                   (SELECT json_agg(json_build_object(
                       'id', al.id, 'level', al.level, 'name', al.name,
                       'approver_type', al.approver_type
                   ) ORDER BY al.level)
                    FROM internal.approval_levels al
                    WHERE al.config_id = ac.id AND al.is_active = true) AS levels
            FROM internal.approval_configurations ac
            WHERE {' AND '.join(where)}
            ORDER BY ac.created_at DESC
            LIMIT %s OFFSET %s
        """, params)
        configs = [dict(r) for r in cur.fetchall()]
        cur.execute(f"""
            SELECT count(*) AS total FROM internal.approval_configurations ac
            WHERE {' AND '.join(where)}
        """, params[:-2])
        total = cur.fetchone()["total"]
        return {"data": configs, "total": total}
    finally:
        cur.close()
        conn.close()


@router.get("/configurations/{config_id}")
async def get_configuration(config_id: int, authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "approval.config.view")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT ac.*,
                   d.name AS department_name,
                   div.name AS division_name,
                   mb.name AS branch_name
            FROM internal.approval_configurations ac
            LEFT JOIN internal.departments d ON d.id = ac.department_id
            LEFT JOIN internal.divisions div ON div.id = ac.division_id
            LEFT JOIN esb_data.master_branch mb ON mb.id = ac.branch_id
            WHERE ac.id = %s
        """, (config_id,))
        config = cur.fetchone()
        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")
        config = dict(config)
        # Get levels with approvers
        cur.execute("""
            SELECT al.*,
                   json_agg(json_build_object(
                       'id', aa.id, 'approver_id', aa.approver_id,
                       'approver_name', COALESCE(u.full_name, r.name)
                   ) ORDER BY aa.id) FILTER (WHERE aa.id IS NOT NULL) AS approvers
            FROM internal.approval_levels al
            LEFT JOIN internal.approval_approvers aa ON aa.level_id = al.id
            LEFT JOIN internal.users u ON u.id = aa.approver_id AND aa.approver_type = 'USER'
            LEFT JOIN internal.roles r ON r.id = aa.approver_id AND aa.approver_type = 'ROLE'
            WHERE al.config_id = %s
            GROUP BY al.id
            ORDER BY al.level
        """, (config_id,))
        config["levels"] = [dict(r) for r in cur.fetchall()]
        return config
    finally:
        cur.close()
        conn.close()


@router.post("/configurations")
async def create_configuration(
    body: ApprovalConfigCreate,
    authorization: Optional[str] = Header(None),
):
    user = require_user(authorization)
    _require_perm(user, "approval.config.create")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Create config
        cur.execute("""
            INSERT INTO internal.approval_configurations
                (name, description, form_type, department_id, division_id, branch_id,
                 min_amount, max_amount, is_active, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (body.name, body.description, body.form_type, body.department_id,
              body.division_id, body.branch_id, body.min_amount, body.max_amount,
              body.is_active, user.get("email")))
        config_id = cur.fetchone()["id"]
        # Create levels
        for level_data in body.levels:
            cur.execute("""
                INSERT INTO internal.approval_levels
                    (config_id, level, name, approver_type, approver_id,
                     is_auto_approve, timeout_hours, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (config_id, level_data.level, level_data.name, level_data.approver_type,
                  level_data.approver_id, level_data.is_auto_approve, level_data.timeout_hours,
                  user.get("email")))
            level_id = cur.fetchone()["id"]
            # Add approvers
            if level_data.approver_ids:
                for approver_id in level_data.approver_ids:
                    cur.execute("""
                        INSERT INTO internal.approval_approvers
                            (level_id, approver_type, approver_id, created_by)
                        VALUES (%s, %s, %s, %s)
                    """, (level_id, level_data.approver_type, approver_id, user.get("email")))
        conn.commit()
        return {"status": "created", "id": config_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()


@router.put("/configurations/{config_id}")
async def update_configuration(
    config_id: int,
    body: ApprovalConfigUpdate,
    authorization: Optional[str] = Header(None),
):
    user = require_user(authorization)
    _require_perm(user, "approval.config.update")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        sets, params = ["updated_at = NOW()", "updated_by = %s"], [user.get("email")]
        for field, value in body.model_dump(exclude_none=True).items():
            sets.append(f"{field} = %s")
            params.append(value)
        params.append(config_id)
        cur.execute(f"""
            UPDATE internal.approval_configurations
            SET {', '.join(sets)} WHERE id = %s RETURNING id
        """, params)
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Configuration not found")
        conn.commit()
        return {"status": "updated"}
    finally:
        cur.close()
        conn.close()


@router.delete("/configurations/{config_id}")
async def delete_configuration(config_id: int, authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "approval.config.delete")
    conn = get_conn()
    cur = conn.cursor()
    try:
        # Check if there are pending requests
        cur.execute("""
            SELECT count(*) FROM internal.approval_requests
            WHERE config_id = %s AND status = 'PENDING'
        """, (config_id,))
        if cur.fetchone()[0] > 0:
            raise HTTPException(status_code=400,
                detail="Cannot delete: there are pending approval requests")
        cur.execute("DELETE FROM internal.approval_approvers WHERE level_id IN "
                    "(SELECT id FROM internal.approval_levels WHERE config_id = %s)", (config_id,))
        cur.execute("DELETE FROM internal.approval_levels WHERE config_id = %s", (config_id,))
        cur.execute("DELETE FROM internal.approval_configurations WHERE id = %s", (config_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Configuration not found")
        conn.commit()
        return {"status": "deleted"}
    finally:
        cur.close()
        conn.close()


# ============ Approval Levels ============

@router.post("/configurations/{config_id}/levels")
async def add_level(
    config_id: int,
    body: ApprovalLevelCreate,
    authorization: Optional[str] = Header(None),
):
    user = require_user(authorization)
    _require_perm(user, "approval.config.update")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT id FROM internal.approval_configurations WHERE id = %s", (config_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Configuration not found")
        cur.execute("""
            INSERT INTO internal.approval_levels
                (config_id, level, name, approver_type, approver_id,
                 is_auto_approve, timeout_hours, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (config_id, body.level, body.name, body.approver_type,
              body.approver_id, body.is_auto_approve, body.timeout_hours,
              user.get("email")))
        level_id = cur.fetchone()["id"]
        if body.approver_ids:
            for approver_id in body.approver_ids:
                cur.execute("""
                    INSERT INTO internal.approval_approvers
                        (level_id, approver_type, approver_id, created_by)
                    VALUES (%s, %s, %s, %s)
                """, (level_id, body.approver_type, approver_id, user.get("email")))
        conn.commit()
        return {"status": "created", "id": level_id}
    finally:
        cur.close()
        conn.close()


@router.put("/levels/{level_id}")
async def update_level(
    level_id: int,
    body: ApprovalLevelUpdate,
    authorization: Optional[str] = Header(None),
):
    user = require_user(authorization)
    _require_perm(user, "approval.config.update")
    conn = get_conn()
    cur = conn.cursor()
    try:
        sets, params = ["updated_at = NOW()"], []
        for field, value in body.model_dump(exclude_none=True).items():
            sets.append(f"{field} = %s")
            params.append(value)
        params.append(level_id)
        cur.execute(f"""
            UPDATE internal.approval_levels SET {', '.join(sets)} WHERE id = %s RETURNING id
        """, params)
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Level not found")
        conn.commit()
        return {"status": "updated"}
    finally:
        cur.close()
        conn.close()


@router.delete("/levels/{level_id}")
async def delete_level(level_id: int, authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "approval.config.delete")
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM internal.approval_approvers WHERE level_id = %s", (level_id,))
        cur.execute("DELETE FROM internal.approval_levels WHERE id = %s", (level_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Level not found")
        conn.commit()
        return {"status": "deleted"}
    finally:
        cur.close()
        conn.close()


# ============ Approval Requests ============

@router.get("/requests")
async def list_requests(
    status: Optional[str] = Query(None),  # PENDING, APPROVED, REJECTED, CANCELLED
    form_type: Optional[str] = Query(None),
    requester_id: Optional[int] = Query(None),
    is_approver: bool = Query(False),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    authorization: Optional[str] = Header(None),
):
    """List approval requests. Returns empty list if internal tables don't exist."""
    # Optional auth for now
    if authorization:
        try:
            user = require_user(authorization)
            _require_perm(user, "approval.request.view")
        except HTTPException:
            pass

    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Check if internal tables exist
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'internal' AND table_name = 'approval_requests'
            ) AS exists
        """)
        if not cur.fetchone()["exists"]:
            return {"data": [], "total": 0}

        # Build where clause
        where_conds = ["1=1"]
        params = []
        if status:
            where_conds.append("ar.status = %s")
            params.append(status)
        if form_type:
            where_conds.append("ar.form_type = %s")
            params.append(form_type)
        if requester_id:
            where_conds.append("ar.requester_id = %s")
            params.append(requester_id)
        where_clause = " AND ".join(where_conds)
        params += [limit, offset]
        cur.execute(f"""
            SELECT ar.*,
                   ac.name AS config_name,
                   u.full_name AS requester_name,
                   d.name AS department_name,
                   div.name AS division_name
            FROM internal.approval_requests ar
            JOIN internal.approval_configurations ac ON ac.id = ar.config_id
            JOIN internal.users u ON u.id = ar.requester_id
            LEFT JOIN internal.departments d ON d.id = ar.department_id
            LEFT JOIN internal.divisions div ON div.id = ar.division_id
            WHERE {where_clause}
            ORDER BY ar.created_at DESC
            LIMIT %s OFFSET %s
        """, params)
        requests = [dict(r) for r in cur.fetchall()]
        cur.execute(f"""
            SELECT count(*) AS total FROM internal.approval_requests ar
            WHERE {where_clause}
        """, params[:-2])
        total = cur.fetchone()["total"]
        return {"data": requests, "total": total}
    finally:
        cur.close()
        conn.close()


@router.get("/requests/{request_id}")
async def get_request(request_id: int, authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "approval.request.view")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT ar.*,
                   ac.name AS config_name,
                   u.full_name AS requester_name,
                   u.email AS requester_email
            FROM internal.approval_requests ar
            JOIN internal.approval_configurations ac ON ac.id = ar.config_id
            JOIN internal.users u ON u.id = ar.requester_id
            WHERE ar.id = %s
        """, (request_id,))
        request = cur.fetchone()
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        request = dict(request)
        # Get history
        cur.execute("""
            SELECT ah.*,
                   u.full_name AS actor_name,
                   al.name AS level_name
            FROM internal.approval_history ah
            JOIN internal.users u ON u.id = ah.actor_id
            LEFT JOIN internal.approval_levels al ON al.id = ah.level_id
            WHERE ah.request_id = %s
            ORDER BY ah.created_at ASC
        """, (request_id,))
        request["history"] = [dict(r) for r in cur.fetchall()]
        # Get current pending level
        cur.execute("""
            SELECT al.*, aa.approver_id, aa.approver_type
            FROM internal.approval_levels al
            LEFT JOIN internal.approval_approvers aa ON aa.level_id = al.id
            WHERE al.config_id = %s AND al.is_active = true
            AND al.level = (
                SELECT COALESCE(MAX(alh.level), 0)
                FROM internal.approval_history ah2
                JOIN internal.approval_levels alh ON alh.id = ah2.level_id
                WHERE ah2.request_id = %s AND ah2.action = 'APPROVE'
            ) + 1
            ORDER BY al.level
        """, (request["config_id"], request_id))
        request["current_pending_level"] = [dict(r) for r in cur.fetchall()]
        return request
    finally:
        cur.close()
        conn.close()


@router.post("/requests")
async def create_request(
    body: ApprovalRequestCreate,
    authorization: Optional[str] = Header(None),
):
    user = require_user(authorization)
    _require_perm(user, "approval.request.create")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Find matching config
        cur.execute("""
            SELECT ac.id, ac.name,
                   (SELECT al.id FROM internal.approval_levels al
                    WHERE al.config_id = ac.id AND al.level = 1 AND al.is_active = true
                    LIMIT 1) AS first_level_id
            FROM internal.approval_configurations ac
            WHERE ac.is_active = true
              AND ac.form_type = %s
              AND (ac.department_id IS NULL OR ac.department_id = %s)
              AND (ac.division_id IS NULL OR ac.division_id = %s)
              AND (ac.branch_id IS NULL OR ac.branch_id = %s)
              AND (ac.min_amount IS NULL OR ac.min_amount <= %s)
              AND (ac.max_amount IS NULL OR ac.max_amount >= %s)
            LIMIT 1
        """, (body.form_type, body.department_id, body.division_id,
              body.branch_id, body.amount or 0, body.amount or 999999999))
        config = cur.fetchone()
        if not config:
            # No approval needed - auto-approve
            return {"status": "no_approval_needed", "config_id": None}
        config_id = config["id"]
        # Create request
        cur.execute("""
            INSERT INTO internal.approval_requests
                (config_id, form_type, reference_id, requester_id, department_id,
                 division_id, amount, data_json, current_level, status, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, 'PENDING', %s)
            RETURNING id
        """, (config_id, body.form_type, body.reference_id, body.requester_id,
              body.department_id, body.division_id, body.amount,
              body.data_json, user.get("email")))
        request_id = cur.fetchone()["id"]
        # Log creation
        cur.execute("""
            INSERT INTO internal.approval_history
                (request_id, level_id, actor_id, action, note, created_by)
            VALUES (%s, %s, %s, 'SUBMIT', 'Request submitted', %s)
        """, (request_id, config["first_level_id"], user.get("id"), user.get("email")))
        conn.commit()
        return {"status": "created", "id": request_id, "config_id": config_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()


@router.post("/requests/{request_id}/approve")
async def approve_request(
    request_id: int,
    body: ApprovalAction,
    authorization: Optional[str] = Header(None),
):
    user = require_user(authorization)
    _require_perm(user, "approval.request.approve")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT * FROM internal.approval_requests WHERE id = %s", (request_id,))
        request = cur.fetchone()
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        if request["status"] != "PENDING":
            raise HTTPException(status_code=400, detail="Request is not pending")
        # Check if user is an approver for current level
        cur.execute("""
            SELECT aa.id FROM internal.approval_approvers aa
            JOIN internal.approval_levels al ON al.id = aa.level_id
            WHERE al.config_id = %s AND al.level = %s
              AND (aa.approver_id = %s OR aa.approver_type IN ('ROLE', 'DEPARTMENT_HEAD', 'DIVISION_HEAD'))
        """, (request["config_id"], request["current_level"], user.get("id")))
        if not cur.fetchone() and user.get("id") != request["requester_id"]:
            raise HTTPException(status_code=403, detail="You are not authorized to approve this request")
        # Get next level
        cur.execute("""
            SELECT id FROM internal.approval_levels
            WHERE config_id = %s AND level = %s + 1 AND is_active = true
            LIMIT 1
        """, (request["config_id"], request["current_level"]))
        next_level = cur.fetchone()
        if next_level:
            # Move to next level
            cur.execute("""
                UPDATE internal.approval_requests
                SET current_level = current_level + 1, updated_at = NOW()
                WHERE id = %s
            """, (request_id,))
            new_status = "PENDING"
        else:
            # Final approval
            new_status = "APPROVED"
        # Log action
        cur.execute("""
            INSERT INTO internal.approval_history
                (request_id, level_id, actor_id, action, note, created_by)
            VALUES (%s, (
                SELECT id FROM internal.approval_levels
                WHERE config_id = %s AND level = %s LIMIT 1
            ), %s, 'APPROVE', %s, %s)
        """, (request_id, request["config_id"], request["current_level"],
              user.get("id"), body.note, user.get("email")))
        # Update status
        cur.execute("""
            UPDATE internal.approval_requests
            SET status = %s, updated_at = NOW()
            WHERE id = %s
        """, (new_status, request_id))
        conn.commit()
        return {"status": new_status.lower()}
    finally:
        cur.close()
        conn.close()


@router.post("/requests/{request_id}/reject")
async def reject_request(
    request_id: int,
    body: ApprovalAction,
    authorization: Optional[str] = Header(None),
):
    user = require_user(authorization)
    _require_perm(user, "approval.request.reject")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT * FROM internal.approval_requests WHERE id = %s", (request_id,))
        request = cur.fetchone()
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        if request["status"] != "PENDING":
            raise HTTPException(status_code=400, detail="Request is not pending")
        cur.execute("""
            UPDATE internal.approval_requests
            SET status = 'REJECTED', updated_at = NOW()
            WHERE id = %s
        """, (request_id,))
        cur.execute("""
            INSERT INTO internal.approval_history
                (request_id, level_id, actor_id, action, note, created_by)
            VALUES (%s, (
                SELECT id FROM internal.approval_levels
                WHERE config_id = %s AND level = %s LIMIT 1
            ), %s, 'REJECT', %s, %s)
        """, (request_id, request["config_id"], request["current_level"],
              user.get("id"), body.note, user.get("email")))
        conn.commit()
        return {"status": "rejected"}
    finally:
        cur.close()
        conn.close()


# ============ RBAC - Permissions ============

@router.get("/permissions")
async def list_approval_permissions(authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "approval.rbac.view")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT * FROM internal.approval_permissions
            WHERE module LIKE 'approval%'
            ORDER BY module, code
        """)
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


@router.get("/form-types")
async def list_form_types(authorization: Optional[str] = Header(None)):
    """Get list of form types that can be configured for approval."""
    return [
        {"code": "FACILITY_REQUEST", "name": "Facility Request"},
        {"code": "TOOL_REQUEST", "name": "Tool & Heavy Tools Request"},
        {"code": "PURCHASE_REQUEST", "name": "Purchase Request"},
        {"code": "LEAVE_REQUEST", "name": "Leave Request"},
        {"code": "OVERTIME_REQUEST", "name": "Overtime Request"},
        {"code": "EXPENSE_REQUEST", "name": "Expense Request"},
    ]


# ============ Helper Endpoints ============

@router.get("/departments")
async def list_departments(authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "approval.config.view")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT id, name, code FROM internal.departments ORDER BY name")
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


@router.get("/divisions")
async def list_divisions(authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "approval.config.view")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT id, name, code FROM internal.divisions ORDER BY name")
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


@router.get("/users")
async def list_approval_users(
    search: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    user = require_user(authorization)
    _require_perm(user, "approval.config.view")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        where = "1=1"
        params = []
        if search:
            where += " AND (u.full_name ILIKE %s OR u.email ILIKE %s)"
            params = [f"%{search}%", f"%{search}%"]
        cur.execute(f"""
            SELECT u.id, u.full_name, u.email, r.name AS role_name
            FROM internal.users u
            JOIN internal.roles r ON r.id = u.role_id
            WHERE {where}
            ORDER BY u.full_name
            LIMIT 50
        """, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()
