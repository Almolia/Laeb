from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from shared_kernel.config import get_settings
from app.api import router as wallet_router
from app.application.ledger import ensure_platform_account
from app.domain.model import DomainError
from shared_kernel.db import session_factory
from shared_kernel.errors import error_body
from shared_kernel.errors import install_error_handlers
from shared_kernel.logging import configure_logging
from shared_kernel.middleware import install_request_middleware

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(title="Wallet Service", version="1.0.0")
install_error_handlers(app)
install_request_middleware(app, settings.service_name)
app.include_router(wallet_router)


@app.on_event("startup")
def seed_platform_account() -> None:
    with session_factory()() as session:
        ensure_platform_account(session)
        session.commit()


@app.exception_handler(DomainError)
async def domain_error_handler(_request, exc: DomainError):
    return JSONResponse(status_code=exc.status, content=error_body(exc.code, exc.message))


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/ready", tags=["operations"])
def ready() -> dict[str, str]:
    with session_factory()() as session:
        session.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
