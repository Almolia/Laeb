import logging

from fastapi import APIRouter

from app.adapters.routes import router as trading_router
from app.infrastructure import models  # noqa: F401
from shared_kernel.app import create_app
from shared_kernel.db import Base, engine
from shared_kernel.inbox import ProcessedEvent  # noqa: F401
from shared_kernel.outbox import OutboxMessage  # noqa: F401

log = logging.getLogger(__name__)

app = create_app("trading")
app.include_router(trading_router)

ops = APIRouter(prefix="/api/v1/trading", tags=["ops"])


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
    log.info("trading schema ready")
