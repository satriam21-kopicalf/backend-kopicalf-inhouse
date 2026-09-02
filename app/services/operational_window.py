"""
Operational Window Validation
Validates that data pulling tasks only run during allowed hours (03:00-08:00 WIB)
to minimize system load and external API throttling issues.
"""

import logging
from datetime import datetime
from typing import Optional
import pytz

logger = logging.getLogger(__name__)

# Jakarta timezone
JAKARTA = pytz.timezone('Asia/Jakarta')

# Operational window settings (in Asia/Jakarta timezone)
OPERATIONAL_START_HOUR = 3   # 03:00 WIB
OPERATIONAL_END_HOUR = 8     # 08:00 WIB


def is_within_operational_window(current_time: Optional[datetime] = None) -> bool:
    """
    Check if current time is within the operational window (03:00-08:00 WIB).

    Args:
        current_time: datetime to check (defaults to current time)

    Returns:
        True if within operational window, False otherwise
    """
    if current_time is None:
        current_time = datetime.now(JAKARTA)

    hour = current_time.hour
    is_within = OPERATIONAL_START_HOUR <= hour < OPERATIONAL_END_HOUR

    if not is_within:
        logger.info(
            f"Outside operational window (03:00-08:00 WIB): "
            f"current hour={hour:02d}, task will be skipped"
        )

    return is_within


def get_operational_window_status() -> dict:
    """
    Get current operational window status.

    Returns:
        Dict with window information: current_time, is_within_window, start_hour, end_hour, etc.
    """
    current_time = datetime.now(JAKARTA)
    current_hour = current_time.hour
    is_within = OPERATIONAL_START_HOUR <= current_hour < OPERATIONAL_END_HOUR

    # Calculate time to window boundaries
    if is_within:
        minutes_until_end = (OPERATIONAL_END_HOUR - current_hour) * 60 - current_time.minute
        return {
            'current_time': current_time.strftime('%Y-%m-%d %H:%M:%S %Z'),
            'is_within_window': True,
            'start_hour': OPERATIONAL_START_HOUR,
            'end_hour': OPERATIONAL_END_HOUR,
            'minutes_until_end': max(0, minutes_until_end),
            'window_duration_minutes': (OPERATIONAL_END_HOUR - OPERATIONAL_START_HOUR) * 60
        }
    else:
        # Calculate minutes until window starts
        if current_hour < OPERATIONAL_START_HOUR:
            minutes_until_start = (OPERATIONAL_START_HOUR - current_hour) * 60 - current_time.minute
        else:
            minutes_until_start = (24 - current_hour + OPERATIONAL_START_HOUR) * 60 - current_time.minute

        return {
            'current_time': current_time.strftime('%Y-%m-%d %H:%M:%S %Z'),
            'is_within_window': False,
            'start_hour': OPERATIONAL_START_HOUR,
            'end_hour': OPERATIONAL_END_HOUR,
            'minutes_until_start': max(0, minutes_until_start),
            'window_duration_minutes': (OPERATIONAL_END_HOUR - OPERATIONAL_START_HOUR) * 60
        }


def require_operational_window(task_func):
    """
    Decorator to ensure tasks only run within operational window.

    Usage:
        @require_operational_window
        @celery_app.task
        def my_sync_task():
            # Task logic here
            pass
    """
    def wrapper(*args, **kwargs):
        if not is_within_operational_window():
            logger.warning(f"Task {task_func.__name__} skipped - outside operational window")
            return None
        return task_func(*args, **kwargs)
    return wrapper


def log_operational_window_status():
    """
    Log current operational window status for monitoring purposes.
    """
    status = get_operational_window_status()

    if status['is_within_window']:
        logger.info(
            f"✓ Within operational window: {status['current_time']} | "
            f"Window: {status['start_hour']}:00-{status['end_hour']}:00 WIB | "
            f"Minutes until window ends: {status['minutes_until_end']} min"
        )
    else:
        logger.info(
            f"✗ Outside operational window: {status['current_time']} | "
            f"Next window starts in: {status['minutes_until_start']} min"
        )
