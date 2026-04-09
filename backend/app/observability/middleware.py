"""HTTP request logging middleware.

Records request/response information including:
- Request ID
- Method, path, query params
- Status code, response time
- User ID (if authenticated)
- Error details on exception
"""

import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.api.client_ip import extract_client_ip
from app.config.settings import get_settings


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log HTTP requests and responses."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        # Cache trusted proxies at initialization for performance
        self._trusted_proxies = get_settings().get_trusted_proxies()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Start timer
        start_time = time.perf_counter()

        # Log request
        request_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query": str(request.query_params),
            "client_ip": extract_client_ip(request, self._trusted_proxies),
            "user_agent": request.headers.get("User-Agent", ""),
        }

        logger.bind(request_id=request_id).info(
            f"Request started: {request.method} {request.url.path}",
            extra={"event": "request_started", **request_data},
        )

        # Process request
        try:
            response = await call_next(request)

            # Calculate response time
            response_time_ms = (time.perf_counter() - start_time) * 1000

            # Log response
            response_data = {
                **request_data,
                "status_code": response.status_code,
                "response_time_ms": round(response_time_ms, 2),
            }

            log_level = "INFO" if response.status_code < 400 else "WARNING"
            logger.bind(request_id=request_id).log(
                log_level,
                (f"Request completed: {request.method} {request.url.path} "
                 f"- {response.status_code} ({response_time_ms:.2f}ms)"),
                extra={"event": "request_completed", **response_data},
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            # Add security headers
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

            settings = get_settings()
            if settings.APP_ENV == "production":
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

            return response

        except Exception as exc:
            # Calculate response time for failed request
            response_time_ms = (time.perf_counter() - start_time) * 1000

            # Log error
            error_data = {
                **request_data,
                "response_time_ms": round(response_time_ms, 2),
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }

            logger.bind(request_id=request_id).exception(
                f"Request failed: {request.method} {request.url.path}",
                extra={"event": "request_failed", **error_data},
            )
            raise
