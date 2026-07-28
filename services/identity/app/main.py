import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.adapters.routes import router as identity_router
from app.infrastructure import models  # noqa: F401
from app.infrastructure.seed import seed_admin_from_env
from shared_kernel.app import create_app
from shared_kernel.db import Base, engine
from shared_kernel.outbox import OutboxMessage  # noqa: F401

log = logging.getLogger(__name__)

app = create_app("identity")
app.include_router(identity_router)

# Keep stub health under service prefix for gateway smoke
ops = APIRouter(prefix="/api/v1/identity", tags=["ops"])


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
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_pending_request
                ON role_requests(user_id, requested_role)
                WHERE status = 'PENDING'
                """
            )
        )
    try:
        seed_admin_from_env()
    except Exception:
        log.exception("admin seed failed; will retry on next start")
