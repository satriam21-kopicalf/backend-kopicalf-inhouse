from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from app.services.tasks import sync_master_data

app = FastAPI(title="CALF Ecosystem Backend")

# Allow CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "calf-backend"}

@app.post("/sync/trigger")
async def trigger_sync():
    sync_master_data.delay()
    return {"status": "triggered", "message": "Manual synchronization triggered via Celery worker."}

@app.get("/api/v1/settings/engine")
async def get_engine_settings():
    from app.core.db import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT sync_batch_size, work_hours_interval_minutes, morning_window_interval_minutes FROM engine_settings WHERE id = 1")
        row = cur.fetchone()
        if row:
            return row
        return {"error": "Settings not found"}
    finally:
        cur.close()
        conn.close()

@app.put("/api/v1/settings/engine")
async def update_engine_settings(settings: dict):
    from app.core.db import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE engine_settings 
            SET sync_batch_size = %s, 
                work_hours_interval_minutes = %s, 
                morning_window_interval_minutes = %s,
                updated_at = NOW()
            WHERE id = 1
        """, (settings.get('sync_batch_size', 1000), 
              settings.get('work_hours_interval_minutes', 30), 
              settings.get('morning_window_interval_minutes', 30)))
        conn.commit()
        return {"status": "success", "message": "Engine settings updated"}
    finally:
        cur.close()
        conn.close()
