import time
import uuid

from fastapi import FastAPI, Request
from prometheus_client import Counter, Histogram

from .context import correlation_id

REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests handled",
    ("service", "method", "path", "status"),
)
LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ("service", "method", "path"),
)


def install_request_middleware(app: FastAPI, service_name: str) -> None:
    @app.middleware("http")
    async def request_context(request: Request, call_next):
        value = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
        token = correlation_id.set(value)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["X-Correlation-Id"] = value
            return response
        finally:
            elapsed = time.perf_counter() - started
            route = request.scope.get("route")
            path = getattr(route, "path", request.url.path)
            status = str(getattr(locals().get("response"), "status_code", 500))
            REQUESTS.labels(service_name, request.method, path, status).inc()
            LATENCY.labels(service_name, request.method, path).observe(elapsed)
            correlation_id.reset(token)
