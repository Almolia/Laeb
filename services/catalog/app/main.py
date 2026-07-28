import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.adapters.routes import router as catalog_router
from app.infrastructure import models  # noqa: F401
from shared_kernel.app import create_app
from shared_kernel.db import Base, engine
from shared_kernel.inbox import ProcessedEvent  # noqa: F401
from shared_kernel.outbox import OutboxMessage  # noqa: F401

log = logging.getLogger(__name__)

app = create_app("catalog")
app.include_router(catalog_router)

ops = APIRouter(prefix="/api/v1/catalog", tags=["ops"])


@ops.get("/health")
def api_health():
    return {"status": "ok"}


@ops.get("/ping")
def ping():
    return {"pong": True}


app.include_router(ops)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine())
    with engine().begin() as conn:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_games_search ON games USING GIN(search_vector)"
            )
        )
    log.info("catalog schema ready")
