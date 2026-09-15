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
               r.code AS role_code, r.name AS role_name,
               e.employee_code, e.position, e.division, e.department, e.rate_class,
               e.branch_id AS branch_id, mb.name AS branch_name
        FROM internal.users u
        JOIN internal.roles r ON r.id = u.role_id
        LEFT JOIN internal.employees e ON e.id = u.employee_id
        LEFT JOIN esb_data.master_branch mb ON mb.id = e.branch_id
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
