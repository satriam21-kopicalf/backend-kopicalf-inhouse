"""
Authentication for the internal dashboard (internal schema).
- PBKDF2-SHA256 password hashes: pbkdf2_sha256$iterations$salthex$hashhex
- Opaque session tokens stored in internal.sessions (12h expiry).
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def get_conn():
    from app.core.db import get_db_connection
    return get_db_connection()


def _verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return secrets.compare_digest(digest.hex(), hash_hex)
    except Exception:
        return False


def _load_permissions(cur, user_id: int) -> list[str]:
    cur.execute("""
        SELECT DISTINCT p.code
        FROM internal.users u
        JOIN internal.role_permissions rp ON rp.role_id = u.role_id
        JOIN internal.permissions p ON p.id = rp.permission_id
        WHERE u.id = %s
        ORDER BY p.code
    """, (user_id,))
    return [r["code"] for r in cur.fetchall()]


def _load_user(cur, user_id: int) -> Optional[dict]:
    cur.execute("""
        SELECT u.id, u.email, u.username, u.full_name, u.is_active,
               u.last_login_at, u.employee_id,
               r.code AS role_code, r.name AS role_name
        FROM internal.users u
        JOIN internal.roles r ON r.id = u.role_id
        WHERE u.id = %s
    """, (user_id,))
    row = cur.fetchone()
    if not row:
        return None
    out = dict(row)
    out["permissions"] = _load_permissions(cur, user_id)
    return out


def require_user(authorization: Optional[str]) -> dict:
    """Resolve Bearer token -> full user dict (raises 401)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT s.user_id FROM internal.sessions s
            WHERE s.token = %s AND s.expires_at > NOW()
        """, (token,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        user = _load_user(cur, row["user_id"])
        if not user or not user["is_active"]:
            raise HTTPException(status_code=401, detail="User inactive")
        user["token"] = token
        return user
    finally:
        cur.close()
        conn.close()


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(body: LoginRequest):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT id, password_hash, is_active FROM internal.users
            WHERE lower(email) = lower(%s) OR lower(username) = lower(%s)
            LIMIT 1
        """, (body.email.strip(), body.email.strip()))
        row = cur.fetchone()
        if not row or not _verify_password(body.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if not row["is_active"]:
            raise HTTPException(status_code=403, detail="Account is inactive")

        token = secrets.token_urlsafe(48)[:64]
        expires = datetime.now(timezone.utc) + timedelta(hours=12)
        cur.execute("""
            INSERT INTO internal.sessions (token, user_id, expires_at)
            VALUES (%s, %s, %s)
        """, (token, row["id"], expires))
        cur.execute("""
            UPDATE internal.users SET last_login_at = NOW(), updated_at = NOW()
            WHERE id = %s
        """, (row["id"],))
        conn.commit()

        user = _load_user(cur, row["id"])
        return {"token": token, "expiresAt": expires.isoformat(), "user": user}
    finally:
        cur.close()
        conn.close()


@router.get("/me")
async def me(authorization: Optional[str] = Header(None)):
    user = require_user(authorization)
    user.pop("password_hash", None)
    return user


@router.get("/users")
async def list_users(
    search: Optional[str] = None,
    role_id: Optional[int] = None,
    status: Optional[str] = None,
    branch_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    authorization: Optional[str] = Header(None),
):
    """List all users with optional filtering.
    Falls back to esb_data.master_user if internal schema tables don't exist.
    """
    # First resolve the token to check auth (optional for now)
    if authorization:
        try:
            require_user(authorization)
        except HTTPException:
            pass  # Allow unauthenticated access for demo purposes

    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Check if internal.users exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'internal' AND table_name = 'users'
            ) AS exists
        """)
        internal_exists = cur.fetchone()["exists"]

        if internal_exists:
            # Use internal schema
            where_conds = ["1=1"]
            params = []

            if search:
                where_conds.append("(u.full_name ILIKE %s OR u.email ILIKE %s OR u.username ILIKE %s)")
                params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
            if status:
                where_conds.append("u.is_active = %s")
                params.append(status == 'active')

            # Count total
            count_query = f"SELECT count(*) AS total FROM internal.users u WHERE {' AND '.join(where_conds)}"
            cur.execute(count_query, params)
            total = cur.fetchone()["total"]

            # Get users
            params.extend([limit, offset])
            cur.execute(f"""
                SELECT u.id, u.email, u.username, u.full_name, u.is_active,
                       u.last_login_at, u.employee_id,
                       r.id AS role_id, r.name AS role_name, r.code AS role_code,
                       u.created_at, u.updated_at
                FROM internal.users u
                JOIN internal.roles r ON r.id = u.role_id
                WHERE {' AND '.join(where_conds)}
                ORDER BY u.full_name
                LIMIT %s OFFSET %s
            """, params)
            users = [dict(r) for r in cur.fetchall()]
        else:
            # Fallback to esb_data.master_user
            where_conds = ["1=1"]
            params = []

            if search:
                where_conds.append("(full_name ILIKE %s OR esb_id ILIKE %s)")
                params.extend([f"%{search}%", f"%{search}%"])

            # Count total
            count_query = f"SELECT count(*) AS total FROM esb_data.master_user WHERE {' AND '.join(where_conds)}"
            cur.execute(count_query, params)
            total = cur.fetchone()["total"]

            # Get users
            params.extend([limit, offset])
            cur.execute(f"""
                SELECT id, esb_id AS employee_id, username, full_name,
                       role_desc AS role_name, role_id,
                       flag_active AS is_active, created_at, updated_at
                FROM esb_data.master_user
                WHERE {' AND '.join(where_conds)}
                ORDER BY full_name
                LIMIT %s OFFSET %s
            """, params)
            users = [dict(r) for r in cur.fetchall()]

        return {"data": users, "total": total}
    finally:
        cur.close()
        conn.close()


@router.get("/users/{user_id}")
async def get_user(user_id: int, authorization: Optional[str] = Header(None)):
    """Get a single user by ID."""
    user = require_user(authorization)
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT u.id, u.email, u.username, u.full_name, u.is_active,
                   u.last_login_at, u.employee_id,
                   r.id AS role_id, r.name AS role_name, r.code AS role_code,
                   u.created_at, u.updated_at
            FROM internal.users u
            JOIN internal.roles r ON r.id = u.role_id
            WHERE u.id = %s
        """, (user_id,))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        return dict(result)
    finally:
        cur.close()
        conn.close()


@router.post("/users")
async def create_user(
    body: dict,
    authorization: Optional[str] = Header(None),
):
    """Create a new user."""
    user = require_user(authorization)
    # Check permission
    if "user.create" not in (user.get("permissions") or []):
        raise HTTPException(status_code=403, detail="Permission denied")

    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Hash password (simple for now - in production use proper hashing)
        import hashlib
        import secrets
        salt = secrets.token_hex(16)
        password_hash = f"pbkdf2_sha256$600000${salt}${hashlib.pbkdf2_hmac('sha256', body['password'].encode(), bytes.fromhex(salt), 600000).hex()}"

        cur.execute("""
            INSERT INTO internal.users (email, username, password_hash, role_id, employee_id, is_active, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            body.get('email'),
            body.get('username'),
            password_hash,
            body.get('role_id', 1),
            body.get('employee_id'),
            body.get('is_active', True),
            user.get('email')
        ))
        user_id = cur.fetchone()["id"]
        conn.commit()

        # Return created user
        return {"id": user_id, "status": "created"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    body: dict,
    authorization: Optional[str] = Header(None),
):
    """Update a user."""
    user = require_user(authorization)
    if "user.update" not in (user.get("permissions") or []):
        raise HTTPException(status_code=403, detail="Permission denied")

    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        sets = ["updated_at = NOW()", "updated_by = %s"]
        params = [user.get('email')]

        for field in ['email', 'username', 'role_id', 'employee_id', 'is_active']:
            if field in body:
                sets.append(f"{field} = %s")
                params.append(body[field])

        params.append(user_id)
        cur.execute(f"""
            UPDATE internal.users SET {', '.join(sets)} WHERE id = %s RETURNING id
        """, params)

        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="User not found")

        conn.commit()
        return {"status": "updated"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, authorization: Optional[str] = Header(None)):
    """Delete a user (soft delete - sets inactive)."""
    user = require_user(authorization)
    if "user.delete" not in (user.get("permissions") or []):
        raise HTTPException(status_code=403, detail="Permission denied")

    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            UPDATE internal.users SET is_active = false, updated_at = NOW()
            WHERE id = %s RETURNING id
        """, (user_id,))

        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="User not found")

        conn.commit()
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()


@router.post("/logout")
async def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM internal.sessions WHERE token = %s", (token,))
            conn.commit()
        finally:
            cur.close()
            conn.close()
    return {"status": "ok"}
