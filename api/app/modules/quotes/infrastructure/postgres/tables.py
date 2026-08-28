"""How a lead is stored. The entities these carry are in ``domain/models.py``.

**``__tablename__`` is pinned on both tables.** SQLModel derives it from the class name, so
renaming ``Quote`` to ``QuoteTable`` in Stage 11 would otherwise have renamed two tables --
which autogenerate writes as ``drop_table`` + ``create_table``, i.e. as deleting every stored
lead. ``tests/test_entity_registry.py`` holds both names still.

The relationship between them stays here rather than moving onto the entities: the cascade is how
one insert writes a quote and its lines together, which is a fact about the write, not about what
a quote means.
"""

from datetime import datetime

from sqlalchemy import func
from sqlmodel import Field, Relationship

from app.core.infrastructure.postgres.tables import BaseTable, UTCDateTime, utcnow
from app.modules.quotes.domain.enums import QuoteKind


class QuoteLineTable(BaseTable, table=True):
    __tablename__ = "quoteline"

    quote_id: int = Field(foreign_key="quote.id", index=True)
    # A cross-module foreign key, which is fine: the boundary this migration draws is in the
    # code, not in the schema -- one process, one database, one `SQLModel.metadata`.
    option_id: int | None = Field(default=None, foreign_key="option.id")

    group_name: str
    option_slug: str
    option_name: str
    price_delta_cents: int
    sort_order: int = 0

    quote: "QuoteTable" = Relationship(back_populates="lines")


class QuoteTable(BaseTable, table=True):
    __tablename__ = "quote"

    ref: str = Field(unique=True, index=True)
    kind: QuoteKind

    platform_id: int | None = Field(default=None, foreign_key="platform.id", index=True)
    platform_slug: str | None = Field(default=None, index=True)
    platform_name: str | None = None
    base_price_cents: int | None = None
    total_cents: int | None = None

    contact_name: str
    contact_email: str
    contact_phone: str = ""
    intended_use: str = ""
    timeline: str = ""
    notes: str = ""

    source_ip: str = ""

    # Redeclared rather than inherited from ``BaseTable`` only to keep the index: the admin lead
    # list orders on this column, and it is the one timestamp in the schema that predates the
    # base class. The type and the server default are the base's.
    created_at: datetime = Field(
        default_factory=utcnow,
        nullable=False,
        index=True,
        sa_type=UTCDateTime,
        sa_column_kwargs={"server_default": func.now()},
    )

    lines: list[QuoteLineTable] = Relationship(
        back_populates="quote",
        sa_relationship_kwargs={
            "order_by": "QuoteLineTable.sort_order",
            "cascade": "all, delete-orphan",
        },
    )
