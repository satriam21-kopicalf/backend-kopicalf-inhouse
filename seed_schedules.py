import os
import psycopg2
from app.services.tasks import MASTER_ENDPOINTS, OPTIONAL_ENDPOINTS
from dotenv import load_dotenv

load_dotenv()
DSN = os.getenv("DB_POOLER_URL")

conn = psycopg2.connect(DSN)
cur = conn.cursor()

endpoints = MASTER_ENDPOINTS + OPTIONAL_ENDPOINTS
for ep in endpoints:
    entity = ep["entity"]
    # default interval 1440 mins for master data, enabled=true
    cur.execute('''
        INSERT INTO md_sync_schedules (entity_type, interval_minutes, enabled, description)
        VALUES (%s, 1440, true, %s)
        ON CONFLICT (entity_type) DO NOTHING;
    ''', (entity, f"Master data sync for {entity}"))

conn.commit()
cur.close()
conn.close()
print("Seeded md_sync_schedules with master data endpoints.")
