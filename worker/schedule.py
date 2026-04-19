# worker/schedule.py
"""
Celery Beat scheduler configuration.

Usage:
    Start the scheduler in a SEPARATE terminal (alongside the worker):
    
    celery -A worker.schedule beat --loglevel=info

    This runs the periodic tasks defined below.
"""
from worker.tasks import celery_app

# Configure Celery Beat schedule
celery_app.conf.beat_schedule = {
    "scrape-tracked-products": {
        "task": "worker.tasks.run_scheduled_scrapes",
        "schedule": 3600.0,  # Run every 1 hour (checks which products are due)
    },
}

celery_app.conf.timezone = "UTC"
