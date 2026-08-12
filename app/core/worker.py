from celery import Celery
import os
from dotenv import load_dotenv
from celery.schedules import crontab

load_dotenv()

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

celery_app = Celery(
    "kopicalf_esb_worker",
    broker=redis_url,
    backend=redis_url,
    include=['app.services.tasks']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Jakarta',
    enable_utc=True,
)

# DYNAMIC CRON ROUTER
# Runs every 5 minutes. The logic inside 'sync_master_data_router' will determine 
# whether it should actually trigger 'sync_master_data' based on engine_settings.
celery_app.conf.beat_schedule = {
    'dynamic-sync-router': {
        'task': 'app.services.tasks.sync_master_data_router',
        'schedule': crontab(minute='*/5'),
    }
}
