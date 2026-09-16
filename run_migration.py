#!/usr/bin/env python3
"""
Migration runner for esb_data schema
Usage: python run_migration.py
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.db import get_db_connection, return_connection

def run_migration():
    """Run the master tables migration."""

    migrations = [
        ('Master Tables', 'migrations/20260917000000_master_tables.sql'),
        ('Internal Auth Schema', 'migrations/20260917010000_internal_auth.sql'),
    ]

    conn = None
    try:
        print("[Migration] Connecting to database...")
        conn = get_db_connection()
        cur = conn.cursor()

        for name, filepath in migrations:
            print(f"\n[Migration] Running: {name}")
            print(f"[Migration] File: {filepath}")

            with open(filepath, 'r') as f:
                sql = f.read()

            try:
                cur.execute(sql)
                conn.commit()
                print(f"[Migration] SUCCESS: {name}")
            except Exception as e:
                conn.rollback()
                print(f"[Migration] ERROR in {name}: {e}")
                raise

        print("\n[Migration] All migrations completed successfully!")

    except Exception as e:
        print(f"\n[Migration] FAILED: {e}")
        sys.exit(1)
    finally:
        if conn:
            return_connection(conn)

if __name__ == '__main__':
    run_migration()
