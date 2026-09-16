#!/usr/bin/env python3
"""Verify migration data"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.core.db import get_db_connection, return_connection

def verify_data():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check divisions
        cur.execute("SELECT COUNT(*) FROM esb_data.master_division")
        div_count = cur.fetchone()[0]
        print(f"Divisions: {div_count}")

        cur.execute("SELECT code, name, manager_name FROM esb_data.master_division LIMIT 5")
        print("\nDivisions sample:")
        for row in cur.fetchall():
            print(f"  {row[0]} - {row[1]} (Manager: {row[2]})")

        # Check departments
        cur.execute("SELECT COUNT(*) FROM esb_data.master_department")
        dept_count = cur.fetchone()[0]
        print(f"\nDepartments: {dept_count}")

        cur.execute("SELECT code, name, division_name FROM esb_data.master_department LIMIT 5")
        print("\nDepartments sample:")
        for row in cur.fetchall():
            print(f"  {row[0]} - {row[1]} (Division: {row[2]})")

        # Check roles
        cur.execute("SELECT COUNT(*) FROM esb_data.master_role")
        role_count = cur.fetchone()[0]
        print(f"\nRoles: {role_count}")

        cur.execute("SELECT code, name FROM esb_data.master_role")
        print("\nRoles:")
        for row in cur.fetchall():
            print(f"  {row[0]} - {row[1]}")

        # Check permissions
        cur.execute("SELECT COUNT(*) FROM esb_data.master_permission")
        perm_count = cur.fetchone()[0]
        print(f"\nPermissions: {perm_count}")

        conn.commit()

    except Exception as e:
        print(f"Error: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            return_connection(conn)

if __name__ == '__main__':
    verify_data()
