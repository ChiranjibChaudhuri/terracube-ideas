"""
Global exception handlers and error responses for TerraCube IDEAS.

This module provides standardized error responses for all API endpoints.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, StarletteHTTPException
from pydantic import ValidationError as PydanticValidationError
import logging
import uuid
import traceback
from typing import Any, Dict, Union, Tuple

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for API errors."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Union[str, Dict[str, Any], None] = None,
        error_code: str = "INTERNAL_ERROR"
    ):
        self.message = message
        self.status_code = status_code
        self.details = details
        self.error_code = error_code

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "error": self.error_code,
            "message": self.message,
            "status_code": self.status_code
        }
        if self.details:
            result["details"] = self.details
        return result


class ValidationError(APIError):
    """400 Bad Request - Invalid input."""

    def __init__(self, message: str, details: Union[str, Dict[str, Any], None] = None):
        super().__init__(
            message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
            error_code="VALIDATION_ERROR"
        )


class NotFoundError(APIError):
    """404 Not Found - Resource not found."""

    def __init__(self, message: str, details: Union[str, Dict[str, Any], None] = None):
        super().__init__(
            message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
            error_code="NOT_FOUND"
        )


class ConflictError(APIError):
    """409 Conflict - Resource state conflict."""

    def __init__(self, message: str, details: Union[str, Dict[str, Any], None] = None):
        super().__init__(
            message,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
            error_code="CONFLICT"
        )


class UnauthorizedError(APIError):
    """401 Unauthorized - Authentication required."""

    def __init__(self, message: str, details: Union[str, Dict[str, Any], None] = None):
        super().__init__(
            message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
            error_code="UNAUTHORIZED"
        )


class ForbiddenError(APIError):
    """403 Forbidden - Insufficient permissions."""

    def __init__(self, message: str, details: Union[str, Dict[str, Any], None] = None):
        super().__init__(
            message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
            error_code="FORBIDDEN"
        )


class ServiceUnavailableError(APIError):
    """503 Service Unavailable - Feature temporarily disabled."""

    def __init__(self, message: str, details: Union[str, Dict[str, Any], None] = None):
        super().__init__(
            message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
            error_code="SERVICE_UNAVAILABLE"
        )


def setup_global_handlers(app: FastAPI) -> None:
    """
    Attach global exception handlers to the FastAPI app.
    Call this after all routes are registered.
    """

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError
    ) -> JSONResponse:
        """Handle Pydantic/FastAPI validation errors with standard format."""
        logger.warning(f"Validation error: {exc.errors}")

        errors = []
        if hasattr(exc, 'errors'):
            for pydantic_error in exc.errors():
                errors.append({
                    "loc": ".".join(str(loc) for loc in pydantic_error["loc"]),
                    "msg": pydantic_error["msg"],
                    "type": pydantic_error["type"]
                })

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": errors} if errors else None
            }
        )

    @app.exception_handler(ValidationError)
    async def custom_validation_error(
        request: Request,
        exc: ValidationError
    ) -> JSONResponse:
        """Handle custom ValidationError exceptions."""
        logger.warning(f"Custom validation error: {exc}")

        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict()
        )

    @app.exception_handler(APIError)
    async def api_error_handler(
        request: Request,
        exc: APIError
    ) -> JSONResponse:
        """Handle custom APIError exceptions with standard format."""
        logger.error(f"API error: {exc.message}", extra={"request_id": getattr(request.state, "request_id", None)})

        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict()
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException
    ) -> JSONResponse:
        """Handle Starlette HTTP exceptions with standard format."""
        logger.warning(f"HTTP exception: {exc.detail}", extra={"request_id": getattr(request.state, "request_id", None)})

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTP_ERROR",
                "message": exc.detail or "An HTTP error occurred",
                "status_code": exc.status_code
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request,
        exc: Exception
    ) -> JSONResponse:
        """Catch-all for unexpected errors."""
        request_id = getattr(request.state, "request_id", "unknown")

        # Log full traceback for unexpected errors
        logger.error(
            f"Unhandled exception: {type(exc).__name__}: {exc}",
            exc_info=True,
            extra={"request_id": request_id}
        )

        # Don't expose internal error details in production
        # Check settings stored in app.state during lifespan
        settings = getattr(request.app.state, "settings", None)
        is_prod = settings and settings.ENVIRONMENT == "production"

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_ERROR",
                "message": "An unexpected error occurred" if is_prod else str(exc),
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
            }
        )


async def validate_uuid(value: str, field_name: str = "ID") -> uuid.UUID:
    """Validate and parse a UUID string, raising ValidationError if invalid."""
    try:
        return uuid.UUID(value)
    except ValueError:
        raise ValidationError(
            message=f"Invalid {field_name} format",
            details={"field": field_name, "value": value}
        )


async def validate_dataset_exists(dataset_id: uuid.UUID, db) -> Any:
    """Validate a dataset exists, raising NotFoundError if not."""
    from sqlalchemy import select
    from app.models import Dataset

    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    row = result.scalars().first()
    if row is None:
        raise NotFoundError(
            message=f"Dataset not found",
            details={"dataset_id": str(dataset_id)}
        )
    return row


def sanitize_dggid(dggid: str) -> str:
    """
    Sanitize a DGGS ID to prevent injection.
    DGGS IDs should be alphanumeric strings.
    """
    # DGGS IDs are typically alphanumeric (e.g., "2240000000", "2240011012")
    # Remove any characters that aren't alphanumeric or hyphen/underscore
    sanitized = "".join(c for c in dggid if c.isalnum() or c in ('-', '_'))
    if len(sanitized) != len(dggid):
        logger.warning(f"DGGID sanitized: {dggid} -> {sanitized}")
    return sanitized[:256]  # Reasonable max length


class RequestIdMiddleware:
    """
    Middleware to add a unique request ID to each request for tracing.
    """

    def __init__(self, app: FastAPI):
        self.app = app

    async def __call__(self, request: Request, call_next):
        import uuid
        request.state.request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response
