from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def engine():
    global _engine
    if _engine is None:
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not set for this service")
        _engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    return _engine


def session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=engine(), expire_on_commit=False, future=True)
    return _SessionLocal


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    db = session_factory()()
    try:
        yield db
    finally:
        db.close()
