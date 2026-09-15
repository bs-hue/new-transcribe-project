"""HTTP middleware: correlation IDs and request logging.

Every request gets an ID. It is bound to the logging context, so every log line
produced while handling that request carries it automatically — including lines
from deep inside a use case that knows nothing about HTTP. It is also returned in
the response header, so a user reporting "it failed at 3pm" can hand us the exact
ID and we can find that one request in a log full of concurrent work (NFR-O1).
"""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

CORRELATION_HEADER = "X-Correlation-ID"

logger = get_logger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Assign a correlation ID to each request and log its completion."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Honour an incoming ID so a chain of calls shares one trace; otherwise
        # mint a fresh one.
        correlation_id = request.headers.get(CORRELATION_HEADER) or str(uuid.uuid4())

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        request.state.correlation_id = correlation_id

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # The error handlers turn this into a response; we only record that
            # the request died and how long it took before doing so.
            logger.exception(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            raise

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers[CORRELATION_HEADER] = correlation_id

        # Path only, never the query string: query strings can carry values we
        # have promised never to log (NFR-S6, API_SPECIFICATION §9).
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response
