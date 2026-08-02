from typing import Any


class AppError(Exception):
    code = "APPLICATION_ERROR"
    status_code = 400

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    code = "RESOURCE_NOT_FOUND"
    status_code = 404


class PermissionDeniedError(AppError):
    code = "PERMISSION_DENIED"
    status_code = 403


class ValidationError(AppError):
    code = "VALIDATION_ERROR"
    status_code = 422


class ConflictError(AppError):
    code = "RESOURCE_CONFLICT"
    status_code = 409


class StorageError(AppError):
    code = "STORAGE_ERROR"
    status_code = 502


class ParserError(AppError):
    code = "PARSER_ERROR"


class EmbeddingError(AppError):
    code = "EMBEDDING_ERROR"
    status_code = 502


class VectorStoreError(AppError):
    code = "VECTOR_STORE_ERROR"
    status_code = 502


class TaskError(AppError):
    code = "TASK_ERROR"
