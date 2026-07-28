import uuid

from fastapi import FastAPI, Request
from prometheus_fastapi_instrumentator import Instrumentator

from . import health
from .config import settings
from .errors import register_error_handlers
from .logging import correlation_id, setup_logging

CORRELATION_HEADER = "X-Correlation-Id"


def create_app(service_name: str, version: str = "1.0.0") -> FastAPI:
    settings.service_name = service_name
    setup_logging(service_name, settings.log_level)

    app = FastAPI(
        title=f"{service_name} service",
        version=version,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    @app.middleware("http")
    async def _correlation(request: Request, call_next):
        cid = request.headers.get(CORRELATION_HEADER) or str(uuid.uuid4())
        correlation_id.set(cid)
        response = await call_next(request)
        response.headers[CORRELATION_HEADER] = cid
        return response

    register_error_handlers(app)
    app.include_router(health.router)
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    return app
