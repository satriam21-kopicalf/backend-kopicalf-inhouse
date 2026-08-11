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

celery_app.conf.beat_schedule = {
    'sync-master-data-work-hours': {
        'task': 'app.services.tasks.sync_master_data',
        'schedule': crontab(minute='*/15', hour='7-22'), # Every 15 minutes between 07:00 and 22:59
    },
    'sync-master-data-morning-window': {
        'task': 'app.services.tasks.sync_master_data',
        'schedule': crontab(minute='*/10', hour='2-6'), # Every 10 minutes between 02:00 and 06:59
    }
}
