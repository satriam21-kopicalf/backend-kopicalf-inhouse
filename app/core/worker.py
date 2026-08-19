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
    include=['app.services.tasks', 'app.services.trx_engine', 'app.services.export_engine']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Jakarta',
    enable_utc=True,
    # ── Broker/backend hygiene ───────────────────────────────────────────
    # visibility_timeout must exceed the longest possible task (night backfill
    # window up to 8h); 12h gives headroom and prevents in-flight re-delivery.
    broker_transport_options={'visibility_timeout': 43200},
    result_expires=86400,
    # One long task per worker process at a time; tasks are idempotent
    # (skip_if_synced + watermark + surrogate reconcile) so late ack is safe.
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

# ── Specialized worker topology ──────────────────────────────────────────────
# queue_master   : master-data sync lane (infrequent, configurable interval)
# queue_sync     : TRX delta lane + realtime + direct reports + completeness audit
# queue_backfill : Lane A historical backfill, TRX + RPT (24/7 every 25 min)
# queue_report   : on-demand report queries
# queue_export   : async XLSX/PDF exports
celery_app.conf.task_routes = {
    'app.services.tasks.sync_master_data_router': {'queue': 'queue_master'},
    'app.services.tasks.sync_master_data': {'queue': 'queue_master'},
    'app.services.tasks.sync_all_companies': {'queue': 'queue_master'},
    'app.services.tasks.sync_company_data': {'queue': 'queue_master'},
    'app.services.trx_engine.delta_sync_trx': {'queue': 'queue_sync'},
    'app.services.trx_engine.realtime_sync_trx': {'queue': 'queue_sync'},
    'app.services.trx_engine.completeness_audit': {'queue': 'queue_sync'},
    'app.services.trx_engine.sync_direct_reports': {'queue': 'queue_sync'},
    'app.services.trx_engine.sync_direct_reports_delta': {'queue': 'queue_sync'},
    'app.services.trx_engine.sync_direct_reports_company': {'queue': 'queue_sync'},
    'app.services.trx_engine.backfill_router': {'queue': 'queue_backfill'},
    'app.services.trx_engine.backfill_entity': {'queue': 'queue_backfill'},
    'app.services.trx_engine.rpt_backfill_entity': {'queue': 'queue_backfill'},
    'app.services.export_engine.generate_export': {'queue': 'queue_export'},
}

# Default queue for anything unrouted (delta/daily lane keeps old behavior safe)
celery_app.conf.task_default_queue = 'queue_sync'

# DYNAMIC CRON ROUTER
# Runs every 5 minutes. The logic inside 'sync_master_data_router' will determine
# whether it should actually trigger 'sync_master_data' based on engine_settings.
# It also dispatches the TRX delta lane when TRX_* entities are due.
celery_app.conf.beat_schedule = {
    'dynamic-sync-router': {
        'task': 'app.services.tasks.sync_master_data_router',
        'schedule': crontab(minute='*/5'),
    },
    # Lane C: Real-time sync (T-0 current day, every 5 minutes)
    'trx-realtime-sync': {
        'task': 'app.services.trx_engine.realtime_sync_trx',
        'schedule': crontab(minute='*/5'),
    },
    # Lane A: Historical backfill dispatch (every 25 minutes, 24/7)
    'trx-backfill-router': {
        'task': 'app.services.trx_engine.backfill_router',
        'schedule': crontab(minute='*/25'),
    },
    # Direct report LIVE delta: every 30 minutes, all companies in parallel
    # (window T-1..T; deep T-7 refresh stays on the 06:00 beat below)
    'trx-direct-reports-delta': {
        'task': 'app.services.trx_engine.sync_direct_reports_delta',
        'schedule': crontab(minute='*/30'),
    },
    # Direct period-based reports DEEP refresh (06:00 WIB, window T-7)
    'trx-direct-reports': {
        'task': 'app.services.trx_engine.sync_direct_reports',
        'schedule': crontab(hour=6, minute=0),
    },
    # Completeness audit + self-healing re-pull (07:15 WIB, after delta and
    # direct reports have fully settled)
    'trx-completeness-audit': {
        'task': 'app.services.trx_engine.completeness_audit',
        'schedule': crontab(hour=7, minute=15),
    },
}
