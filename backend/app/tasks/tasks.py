from __future__ import annotations

from app.tasks.celery_app import celery_app


@celery_app.task(name="tasks.health_ping")
def health_ping() -> dict:
    return {"status": "ok", "component": "celery"}

