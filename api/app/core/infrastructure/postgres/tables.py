"""The base table every stored row extends, and the timestamp type that keeps it honest.

SQLModel tables rather than the reference repository's plain SQLAlchemy ``DeclarativeBase``: a
SQLModel table class *is* a SQLAlchemy declarative model, ``SQLModel.metadata`` is what
``alembic/env.py`` and ``tests/test_entity_registry.py`` read, and swapping it would churn both
for no boundary gain -- the boundary comes from the entity being a separate pure-pydantic class,
not from which declarative base the table uses.
"""

from datetime import UTC, date, datetime, time

from sqlalchemy import DateTime, func
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, SQLModel


class UTCDateTime(TypeDecorator):
    """``DateTime(timezone=True)`` that treats naive input as UTC.

    A driver binding a naive datetime to a ``timestamptz`` column resolves it against the host
    machine's local timezone, which makes anything that writes a timestamp without one -- a
    migration backfill, a test factory, a script -- quietly depend on where it ran. Normalizing
    at the bind boundary removes that ambiguity for every table at once rather than asking every
    author to remember it.

    The rendered DDL type is unchanged (``TIMESTAMP WITH TIME ZONE``), so adopting this on a
    column that already exists is not a migration.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        if isinstance(value, date):
            return datetime.combine(value, time.min, tzinfo=UTC)
        return value


def utcnow() -> datetime:
    return datetime.now(UTC)


class BaseTable(SQLModel):
    """``id``, ``created_at``, ``updated_at`` -- on every table, without exception.

    Not a table itself: subclasses declare ``table=True`` and inherit these three columns.

    The timestamps carry a ``server_default`` of ``now()`` as well as a Python default so that a
    row inserted by something that is not this application -- a migration, a repair run in
    ``psql`` -- still gets them. ``updated_at`` additionally carries ``onupdate``, so it moves
    without anyone having to remember to move it.
    """

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        default_factory=utcnow,
        nullable=False,
        sa_type=UTCDateTime,
        sa_column_kwargs={"server_default": func.now()},
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        nullable=False,
        sa_type=UTCDateTime,
        sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()},
    )
