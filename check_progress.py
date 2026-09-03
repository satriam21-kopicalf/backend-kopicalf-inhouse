#!/usr/bin/env python3
import psycopg2
import os

db_url = os.getenv("DB_POOLER_URL")
conn = psycopg2.connect(db_url)
cur = conn.cursor()

print("="*80)
print("CHECKING SYNC PROGRESS")
print("="*80)

# Check running sync
cur.execute("""
    SELECT id, entity_type, status, started_at, records_processed
    FROM public.sync_history
    WHERE status = 'STARTED'
    AND entity_type LIKE '%POS%'
    ORDER BY id DESC
    LIMIT 1
""")
running = cur.fetchone()

if running:
    print("\nRunning sync found:")
    print("  ID: " + str(running[0]))
    print("  Type: " + str(running[1]))
    print("  Status: " + str(running[2]))
    print("  Started: " + str(running[3]))
    print("  Records so far: " + str(running[4]))
else:
    print("\nNo running sync found")

# Check latest sync history
print("\n" + "="*80)
print("LATEST SYNC HISTORY")
print("="*80)
cur.execute("""
    SELECT id, entity_type, status, records_processed, started_at, completed_at
    FROM public.sync_history
    WHERE entity_type LIKE '%POS%'
    ORDER BY id DESC
    LIMIT 5
""")
for r in cur.fetchall():
    print("\nID: " + str(r[0]))
    print("Type: " + str(r[1]))
    print("Status: " + str(r[2]))
    print("Records: " + str(r[3]))
    print("Started: " + str(r[4]))
    print("Completed: " + str(r[5]))

conn.close()
