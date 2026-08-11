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

