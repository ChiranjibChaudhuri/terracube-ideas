"""
Structured logging configuration for TerraCube IDEAS.

Provides JSON-formatted logs with request tracing and performance metrics.
"""
import logging
import sys
from datetime import datetime
from typing import Any, Dict
from pythonjsonlogger import pythonjsonlogger
from app.config import settings

# Log format
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Structured JSON formatter
class StructuredFormatter(logging.Formatter):
    """Format log records as JSON with context."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Create base log dict
        log_dict = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_dict["exception"] = {
                "type": type(record.exc_info[0]).__name__,
                "message": str(record.exc_info[0]),
                "traceback": self.formatException(record.exc_info)
            }

        # Add extra context from record
        if hasattr(record, "context"):
            log_dict.update(record.context)

        # Add request_id if available (set by RequestIdMiddleware)
        request_id = getattr(record, "request_id", None)
        if request_id:
            log_dict["request_id"] = request_id

        # Add user_id if available (set by auth)
        user_id = getattr(record, "user_id", None)
        if user_id:
            log_dict["user_id"] = user_id

        # Add duration if available (for performance logging)
        duration_ms = getattr(record, "duration_ms", None)
        if duration_ms:
            log_dict["duration_ms"] = duration_ms

        return pythonjsonlogger.dumps(log_dict)


# Request logging middleware
class RequestLoggingMiddleware:
    """
    Middleware to log requests with timing information.

    Adds request_id to state and logs request duration.
    """

    def __init__(self, app, enabled: bool = True):
        self.app = app
        self.enabled = enabled
        self.logger = logging.getLogger("app.middleware.request_logging")

    async def __call__(self, request, call_next):
        import time
        import uuid

        # Skip if disabled
        if not self.enabled:
            return await call_next(request)

        # Generate request ID and add to state
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Start timer
        start_time = time.perf_counter()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log request (only for errors and slow requests in production)
        level = logging.INFO
        if response.status_code >= 500:
            level = logging.ERROR
        elif duration_ms > 1000:  # Slow request (>1s)
            level = logging.WARNING
        elif settings.ENVIRONMENT == "development":
            level = logging.INFO

        self.logger.log(
            level,
            "%s %s %s",
            request.method,
            str(request.url.path),
            response.status_code,
            f"{duration_ms:.0f}ms"
        )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        # Add duration to response headers in development
        if settings.ENVIRONMENT == "development":
            response.headers["X-Process-Time"] = f"{duration_ms:.0f}ms"

        return response


# Performance logging decorator
def log_performance(func):
    """
    Decorator to log function execution time.

    Usage:
        @log_performance
        async def my_function(arg1, arg2):
            ...
    """
    import functools
    import time

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)

        start_time = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log slow operations (>1s)
            if duration_ms > 1000:
                logger.warning(
                    "Slow operation: %s took %.0fms",
                    func.__name__,
                    duration_ms
                )

            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "Operation failed: %s (%.0fms): %s",
                func.__name__,
                duration_ms,
                str(e)
            )
            raise

    return wrapper


# Slow query logging
class SlowQueryLogger:
    """
    Context manager to log slow database queries.

    Usage:
        async with SlowQueryLogger("my_operation", threshold_ms=5000):
            # ... database operations
    """

    def __init__(self, operation_name: str, threshold_ms: int = 1000):
        self.operation_name = operation_name
        self.threshold_ms = threshold_ms
        self.logger = logging.getLogger("app.db.queries")

    async def __aenter__(self):
        import time
        self.start_time = time.perf_counter()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        import time

        duration_ms = (time.perf_counter() - self.start_time) * 1000

        if duration_ms > self.threshold_ms:
            self.logger.warning(
                "Slow query detected: %s took %.0fms (threshold: %.0fms)",
                self.operation_name,
                duration_ms,
                self.threshold_ms
            )

        return False


def setup_logging() -> None:
    """
    Configure structured logging for the application.

    Call this in app initialization or use logging.config.fileConfig.
    """
    # Configure root logger
    root_logger = logging.getLogger()

    # Set log level based on environment
    if settings.ENVIRONMENT == "production":
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG

    root_logger.setLevel(log_level)

    # Clear existing handlers
    root_logger.handlers = []

    # Console handler with JSON formatting in production
    import logging.handlers

    if settings.ENVIRONMENT == "production":
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(console_handler)
    else:
        # Development: pretty print with colors
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
            datefmt=LOG_DATE_FORMAT
        ))
        root_logger.addHandler(console_handler)

    # Set levels for specific loggers
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
