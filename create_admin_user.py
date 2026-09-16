#!/usr/bin/env python3
"""
Create admin and demo users with proper password hashing
"""
import os
import sys
import hashlib
import secrets
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.core.db import get_db_connection, return_connection

def generate_password_hash(password: str) -> str:
    """Generate PBKDF2-SHA256 password hash matching the auth router format."""
    salt_hex = secrets.token_hex(32)
    iterations = 600000
    digest = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode(),
        bytes.fromhex(salt_hex),
        iterations
    )
    return f"pbkdf2_sha256${iterations}${salt_hex}${digest.hex()}"

def create_users():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get admin role id
        cur.execute("SELECT id FROM internal.roles WHERE code = 'ADMIN'")
        result = cur.fetchone()
        if not result:
            print("ERROR: ADMIN role not found. Run internal_auth migration first.")
            return
        admin_role_id = result[0]

        # Get manager role id
        cur.execute("SELECT id FROM internal.roles WHERE code = 'MANAGER'")
        result = cur.fetchone()
        manager_role_id = result[0] if result else None

        # Get staff role id
        cur.execute("SELECT id FROM internal.roles WHERE code = 'STAFF'")
        result = cur.fetchone()
        staff_role_id = result[0] if result else None

        # Create admin user with password "Admin@123"
        admin_password = "Admin@123"
        admin_hash = generate_password_hash(admin_password)
        cur.execute("""
            INSERT INTO internal.users (username, email, password_hash, full_name, role_id, is_active)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (username) DO UPDATE
            SET password_hash = EXCLUDED.password_hash,
                updated_at = NOW()
            RETURNING id, username, email
        """, ('admin', 'admin@kopicalf.com', admin_hash, 'System Administrator', admin_role_id, True))
        result = cur.fetchone()
        print(f"Admin user: {result[1]} ({result[2]}) - Password: {admin_password}")

        # Create demo manager user with password "Manager@123"
        if manager_role_id:
            manager_password = "Manager@123"
            manager_hash = generate_password_hash(manager_password)
            cur.execute("""
                INSERT INTO internal.users (username, email, password_hash, full_name, role_id, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (username) DO UPDATE
                SET password_hash = EXCLUDED.password_hash,
                    updated_at = NOW()
                RETURNING id, username, email
            """, ('manager', 'manager@kopicalf.com', manager_hash, 'Demo Manager', manager_role_id, True))
            result = cur.fetchone()
            print(f"Manager user: {result[1]} ({result[2]}) - Password: {manager_password}")

        # Create demo staff user with password "Staff@123"
        if staff_role_id:
            staff_password = "Staff@123"
            staff_hash = generate_password_hash(staff_password)
            cur.execute("""
                INSERT INTO internal.users (username, email, password_hash, full_name, role_id, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (username) DO UPDATE
                SET password_hash = EXCLUDED.password_hash,
                    updated_at = NOW()
                RETURNING id, username, email
            """, ('staff', 'staff@kopicalf.com', staff_hash, 'Demo Staff', staff_role_id, True))
            result = cur.fetchone()
            print(f"Staff user: {result[1]} ({result[2]}) - Password: {staff_password}")

        conn.commit()
        print("\nAll users created successfully!")

    except Exception as e:
        print(f"Error: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            return_connection(conn)

if __name__ == '__main__':
    create_users()
