from celery import Celery
from app.config import settings

# Redis URL from config (using REDIS_HOST/PORT)
# "redis://redis:6379/0"
redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"

celery_app = Celery("terracube", broker=redis_url, backend=redis_url, include=["app.services.ingest"])

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

# Auto-discover tasks in packages
celery_app.autodiscover_tasks(["app.services"]) 
