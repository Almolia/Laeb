from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.orm import Session

from shared_kernel.config import get_settings
from shared_kernel.db import get_session
from shared_kernel.errors import install_error_handlers
from shared_kernel.logging import configure_logging
from shared_kernel.middleware import install_request_middleware

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(title="Wallet Service", version="1.0.0")
install_error_handlers(app)
install_request_middleware(app, settings.service_name)


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/ready", tags=["operations"])
def ready() -> dict[str, str]:
    session = next(get_session())
    try:
        session.execute(text("SELECT 1"))
    finally:
        session.close()
    return {"status": "ready"}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
