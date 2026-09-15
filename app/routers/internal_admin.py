"""
Internal admin API: employees, users, roles & permissions (internal schema).
All endpoints require an authenticated user with admin.* permission.
"""
from datetime import date
from hashlib import pbkdf2_hmac
import os
import secrets
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from app.routers.auth import require_user

router = APIRouter(prefix="/api/v1/internal", tags=["internal-admin"])


def get_conn():
    from app.core.db import get_db_connection
    return get_db_connection()


def _require_perm(user: dict, code: str):
    if code not in (user.get("permissions") or []):
        raise HTTPException(status_code=403, detail=f"Permission required: {code}")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return f"pbkdf2_sha256$100000${salt.hex()}${digest.hex()}"


# ============ Employees ============

class EmployeeCreate(BaseModel):
    employee_code: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    division: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    employee_type: str = "STAFF"
    rate_class: Optional[str] = None
    base_salary: float = 0
    salary_type: str = "MONTHLY"
    join_date: Optional[date] = None
    status: str = "ACTIVE"
    branch_id: Optional[int] = None


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    division: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    employee_type: Optional[str] = None
    rate_class: Optional[str] = None
    base_salary: Optional[float] = None
    salary_type: Optional[str] = None
    join_date: Optional[date] = None
    status: Optional[str] = None
    branch_id: Optional[int] = None


class ShiftCreate(BaseModel):
    shift_name: str
    start_time: str
    end_time: str
    work_days: str = "1,2,3,4,5"
    break_minutes: int = 60
    effective_from: Optional[date] = None


class DeductionCreate(BaseModel):
    deduction_type: str
    amount: float
    period_month: str
    note: Optional[str] = None


@router.get("/employees")
async def list_employees(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    employee_type: Optional[str] = Query(None),
    limit: int = Query(200, le=1000),
    offset: int = Query(0, ge=0),
    authorization: Optional[str] = Header(None),
):
    user = require_user(authorization)
    _require_perm(user, "admin.employees")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        where, params = ["1=1"], []
        if search:
            where.append("(e.full_name ILIKE %s OR e.employee_code ILIKE %s OR e.email ILIKE %s)")
            params += [f"%{search}%"] * 3
        if status:
            where.append("e.status = %s")
            params.append(status)
        if employee_type:
            where.append("e.employee_type = %s")
            params.append(employee_type)
        params.extend([limit, offset])
        cur.execute(f"""
            SELECT e.*, mb.name AS branch_name,
                   (SELECT u.id FROM internal.users u WHERE u.employee_id = e.id LIMIT 1) AS user_id
            FROM internal.employees e
            LEFT JOIN esb_data.master_branch mb ON mb.id = e.branch_id
            WHERE {' AND '.join(where)}
            ORDER BY e.full_name
            LIMIT %s OFFSET %s
        """, params)
        rows = [dict(r) for r in cur.fetchall()]
        cur.execute(f"SELECT count(*) AS n FROM internal.employees e WHERE {' AND '.join(where)}",
                    params[:-2])
        total = cur.fetchone()["n"]
        return {"total": total, "rows": rows}
    finally:
        cur.close()
        conn.close()


@router.get("/employees/{employee_id}")
async def get_employee(employee_id: int, authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "admin.employees")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT * FROM internal.employees WHERE id = %s", (employee_id,))
        emp = cur.fetchone()
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")
        out = dict(emp)
        cur.execute("""
            SELECT * FROM internal.employee_shifts
            WHERE employee_id = %s ORDER BY is_active DESC, effective_from DESC
        """, (employee_id,))
        out["shifts"] = [dict(r) for r in cur.fetchall()]
        cur.execute("""
            SELECT * FROM internal.employee_deductions
            WHERE employee_id = %s ORDER BY period_month DESC, id DESC
        """, (employee_id,))
        out["deductions"] = [dict(r) for r in cur.fetchall()]
        return out
    finally:
        cur.close()
        conn.close()


@router.post("/employees")
async def create_employee(body: EmployeeCreate, authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "admin.employees")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            INSERT INTO internal.employees
                (employee_code, full_name, email, phone, division, department, position,
                 employee_type, rate_class, base_salary, salary_type, join_date, status, branch_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (body.employee_code, body.full_name, body.email, body.phone, body.division,
              body.department, body.position, body.employee_type, body.rate_class,
              body.base_salary, body.salary_type, body.join_date, body.status, body.branch_id))
        emp_id = cur.fetchone()["id"]
        conn.commit()
        cur.execute("SELECT * FROM internal.employees WHERE id = %s", (emp_id,))
        return dict(cur.fetchone())
    finally:
        cur.close()
        conn.close()


@router.put("/employees/{employee_id}")
async def update_employee(employee_id: int, body: EmployeeUpdate,
                          authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "admin.employees")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        sets, params = ["updated_at = NOW()"], []
        for field, value in body.model_dump(exclude_none=True).items():
            sets.append(f"{field} = %s")
            params.append(value)
        params.append(employee_id)
        cur.execute(f"""
            UPDATE internal.employees SET {', '.join(sets)} WHERE id = %s RETURNING id
        """, params)
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Employee not found")
        conn.commit()
        cur.execute("SELECT * FROM internal.employees WHERE id = %s", (employee_id,))
        return dict(cur.fetchone())
    finally:
        cur.close()
        conn.close()


@router.delete("/employees/{employee_id}")
async def delete_employee(employee_id: int, authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "admin.employees")
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT count(*) FROM internal.users WHERE employee_id = %s", (employee_id,))
        if cur.fetchone()[0]:
            raise HTTPException(status_code=400, detail="Employee has a linked user account")
        cur.execute("DELETE FROM internal.employees WHERE id = %s", (employee_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Employee not found")
        conn.commit()
        return {"status": "deleted"}
    finally:
        cur.close()
        conn.close()


@router.post("/employees/{employee_id}/shifts")
async def add_shift(employee_id: int, body: ShiftCreate,
                    authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "admin.employees")
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO internal.employee_shifts
                (employee_id, shift_name, start_time, end_time, work_days, break_minutes, effective_from)
            VALUES (%s,%s,%s,%s,%s,%s,COALESCE(%s, CURRENT_DATE))
        """, (employee_id, body.shift_name, body.start_time, body.end_time,
              body.work_days, body.break_minutes, body.effective_from))
        conn.commit()
        return {"status": "created"}
    finally:
        cur.close()
        conn.close()


@router.delete("/employees/{employee_id}/shifts/{shift_id}")
async def delete_shift(employee_id: int, shift_id: int, authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "admin.employees")
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM internal.employee_shifts WHERE id = %s AND employee_id = %s",
                    (shift_id, employee_id))
        conn.commit()
        return {"status": "deleted"}
    finally:
        cur.close()
        conn.close()


@router.post("/employees/{employee_id}/deductions")
async def add_deduction(employee_id: int, body: DeductionCreate,
                        authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "admin.employees")
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO internal.employee_deductions
                (employee_id, deduction_type, amount, period_month, note, created_by)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (employee_id, body.deduction_type, body.amount, body.period_month,
              body.note, user.get("email")))
        conn.commit()
        return {"status": "created"}
    finally:
        cur.close()
        conn.close()


@router.delete("/employees/{employee_id}/deductions/{deduction_id}")
async def delete_deduction(employee_id: int, deduction_id: int,
                           authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "admin.employees")
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM internal.employee_deductions WHERE id = %s AND employee_id = %s",
                    (deduction_id, employee_id))
        conn.commit()
        return {"status": "deleted"}
    finally:
        cur.close()
        conn.close()


# ============ Users ============

class UserCreate(BaseModel):
    email: str
    username: str
    password: str
    full_name: str
    role_id: int
    employee_id: Optional[int] = None
    is_active: bool = True


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role_id: Optional[int] = None
    employee_id: Optional[int] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


@router.get("/users")
async def list_users(authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "admin.users")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT u.id, u.email, u.username, u.full_name, u.is_active,
                   u.last_login_at, u.created_at,
                   u.role_id, r.code AS role_code, r.name AS role_name,
                   u.employee_id, e.employee_code, e.full_name AS employee_name
            FROM internal.users u
            JOIN internal.roles r ON r.id = u.role_id
            LEFT JOIN internal.employees e ON e.id = u.employee_id
            ORDER BY u.id
        """)
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


@router.post("/users")
async def create_user(body: UserCreate, authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "admin.users")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            INSERT INTO internal.users (email, username, password_hash, full_name, role_id, employee_id, is_active)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (body.email.lower(), body.username.lower(), hash_password(body.password),
              body.full_name, body.role_id, body.employee_id, body.is_active))
        new_id = cur.fetchone()["id"]
        conn.commit()
        return {"status": "created", "id": new_id}
    except Exception as e:
        conn.rollback()
        msg = str(e)
        if "users_email_key" in msg:
            raise HTTPException(status_code=400, detail="Email already exists")
        if "users_username_key" in msg:
            raise HTTPException(status_code=400, detail="Username already exists")
        raise HTTPException(status_code=400, detail=msg)
    finally:
        cur.close()
        conn.close()


@router.put("/users/{user_id}")
async def update_user(user_id: int, body: UserUpdate,
                      authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "admin.users")
    conn = get_conn()
    cur = conn.cursor()
    try:
        sets, params = ["updated_at = NOW()"], []
        for field in ("full_name", "role_id", "employee_id", "is_active"):
            value = getattr(body, field)
            if value is not None:
                sets.append(f"{field} = %s")
                params.append(value)
        if body.password:
            if len(body.password) < 8:
                raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
            sets.append("password_hash = %s")
            params.append(hash_password(body.password))
        params.append(user_id)
        cur.execute(f"UPDATE internal.users SET {', '.join(sets)} WHERE id = %s", params)
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
        conn.commit()
        return {"status": "updated"}
    finally:
        cur.close()
        conn.close()


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "admin.users")
    if user["id"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM internal.users WHERE id = %s", (user_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
        conn.commit()
        return {"status": "deleted"}
    finally:
        cur.close()
        conn.close()


# ============ Roles & permissions ============

@router.get("/roles")
async def list_roles(authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "admin.roles")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT r.*, count(u.id) AS user_count
            FROM internal.roles r
            LEFT JOIN internal.users u ON u.role_id = r.id
            GROUP BY r.id ORDER BY r.id
        """)
        roles = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT role_id, permission_id FROM internal.role_permissions")
        mapping: dict[int, list[int]] = {}
        for r in cur.fetchall():
            mapping.setdefault(r["role_id"], []).append(r["permission_id"])
        for r in roles:
            r["permission_ids"] = mapping.get(r["id"], [])
        return roles
    finally:
        cur.close()
        conn.close()


@router.get("/permissions")
async def list_permissions(authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "admin.roles")
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT * FROM internal.permissions ORDER BY module, code")
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


class RolePermissionsUpdate(BaseModel):
    permission_ids: list[int]


@router.put("/roles/{role_id}/permissions")
async def update_role_permissions(role_id: int, body: RolePermissionsUpdate,
                                  authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    _require_perm(user, "admin.roles")
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT is_system FROM internal.roles WHERE id = %s", (role_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Role not found")
        cur.execute("DELETE FROM internal.role_permissions WHERE role_id = %s", (role_id,))
        for pid in dict.fromkeys(body.permission_ids):
            cur.execute("""
                INSERT INTO internal.role_permissions (role_id, permission_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
            """, (role_id, pid))
        conn.commit()
        return {"status": "updated", "count": len(body.permission_ids)}
    finally:
        cur.close()
        conn.close()
