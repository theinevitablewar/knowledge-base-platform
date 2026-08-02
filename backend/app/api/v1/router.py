from fastapi import APIRouter

from . import agent, audit, auth, documents, knowledge, retrieval, tasks

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(knowledge.router)
api_router.include_router(documents.router)
api_router.include_router(retrieval.router)
api_router.include_router(tasks.router)
api_router.include_router(audit.router)
api_router.include_router(agent.router)
