# src/celery_app.py

from celery import Celery

# Use a relative import
from .config import app_config

celery_app = Celery(
    'comfy_tasks',
    broker=app_config.CELERY_BROKER_URL,
    backend=app_config.CELERY_BACKEND_URL,
    include=['src.worker']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)