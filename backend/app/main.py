import time
from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.core.tracing import configure_langsmith
from app.db import SessionFactory

settings = get_settings()
configure_logging()
configure_langsmith(settings)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("application_started", environment=settings.app_env)
    yield
    logger.info("application_stopped")


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        logger.info(
            "request_completed",
            request_id=request_id,
            path=request.url.path,
            method=request.method,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {"code": exc.code, "message": exc.message, "details": exc.details},
            "request_id": request.state.request_id,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "请求参数无效",
                "details": {"errors": exc.errors()},
            },
            "request_id": request.state.request_id,
        },
    )


@app.get("/health", tags=["System"])
async def health() -> dict[str, object]:
    database = "unavailable"
    try:
        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        logger.warning("health_database_unavailable")
    return {
        "status": "ok",
        "service": settings.app_name,
        "database": database,
        "mock_mode": settings.ai_mock_mode,
    }


app.include_router(api_router)
