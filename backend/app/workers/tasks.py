import asyncio

import structlog

from .celery_app import celery_app
from .pipeline import cleanup_knowledge_base, delete_document_resources, ingest_document

logger = structlog.get_logger()


@celery_app.task(bind=True, max_retries=3, name="documents.ingest")
def ingest_task(self, task_id: str) -> None:
    logger.info("ingestion_started", task_id=task_id, retry_count=self.request.retries)
    try:
        asyncio.run(ingest_document(__import__("uuid").UUID(task_id)))
    except Exception as exc:
        logger.exception("ingestion_failed", task_id=task_id, retry_count=self.request.retries)
        raise self.retry(exc=exc, countdown=min(60, 2**self.request.retries)) from exc


@celery_app.task(name="documents.delete")
def delete_document_task(document_id: str) -> None:
    asyncio.run(delete_document_resources(__import__("uuid").UUID(document_id)))


@celery_app.task(name="knowledge_bases.cleanup")
def cleanup_knowledge_base_task(knowledge_base_id: str) -> None:
    asyncio.run(cleanup_knowledge_base(__import__("uuid").UUID(knowledge_base_id)))
