"""
Prometheus middleware — records HTTP request count and latency for every
request that passes through the FastAPI app.
"""
from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from engine.api.metrics import HTTP_REQUEST_DURATION, HTTP_REQUESTS_TOTAL


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        path = request.url.path
        method = request.method
        start = time.perf_counter()

        response = await call_next(request)

        duration = time.perf_counter() - start
        status_code = str(response.status_code)

        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status_code=status_code).inc()
        HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(duration)

        return response
