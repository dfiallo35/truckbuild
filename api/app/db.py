"""Database engine and session management."""

from collections.abc import Generator

from sqlmodel import Session, create_engine

from app.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)


def get_session() -> Generator[Session]:
    """FastAPI dependency yielding a request-scoped session."""
    with Session(engine) as session:
        yield session
