from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import router as wallet_router
from app.application.ledger import ensure_platform_account
from app.domain.model import DomainError
from shared_kernel.app import create_app
from shared_kernel.config import settings
from shared_kernel.db import session_factory
from shared_kernel.errors import AppError
from shared_kernel.health import register_readiness_check
from shared_kernel.logging import correlation_id

app = create_app("wallet")
app.include_router(wallet_router)


@app.on_event("startup")
def seed_platform_account() -> None:
    with session_factory()() as session:
        ensure_platform_account(session)
        session.commit()


def error_response(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "correlationId": correlation_id.get(),
            }
        },
    )


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError):
    # A1's published helper passes JSONResponse positional arguments in the
    # wrong order.  Keep the compatibility fix scoped to Wallet ownership.
    return error_response(exc.code, exc.message, exc.status_code)


@app.exception_handler(DomainError)
async def domain_error_handler(_request: Request, exc: DomainError):
    return error_response(exc.code, exc.message, exc.status)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    return error_response("VALIDATION_ERROR", str(exc.errors()), 422)


def database_ready() -> None:
    with session_factory()() as session:
        session.execute(text("SELECT 1"))


register_readiness_check(database_ready)
