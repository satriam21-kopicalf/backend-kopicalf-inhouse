#!/usr/bin/env python3
import psycopg2
import os

db_url = os.getenv("DB_POOLER_URL")
conn = psycopg2.connect(db_url)
cur = conn.cursor()

print("="*80)
print("RECENT POS SYNC HISTORY")
print("="*80)

cur.execute("""
    SELECT id, entity_type, status, records_processed, started_at, completed_at
    FROM public.sync_history
    WHERE entity_type LIKE '%POS%'
    ORDER BY id DESC
    LIMIT 10
""")

for r in cur.fetchall():
    print("\nID: " + str(r[0]))
    print("Type: " + str(r[1]))
    print("Status: " + str(r[2]))
    print("Records: " + str(r[3]))
    print("Started: " + str(r[4]))
    print("Completed: " + str(r[5]))

conn.close()
