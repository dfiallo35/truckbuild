from datetime import datetime

from sqlalchemy import func
from sqlmodel import Field, Relationship

from app.core.infrastructure.postgres.tables import BaseTable, UTCDateTime, utcnow
from app.modules.quotes.domain.enums import QuoteKind


class QuoteLine(BaseTable, table=True):
    """One selected option, as it was priced at submission time.

    The option's name and price delta are copied rather than read through ``option_id``: a quote
    is a record of what was offered on a date, and repricing the catalog next quarter must not
    silently rewrite it. ``option_id`` survives only as a convenience for joining back to the
    live catalog, and is nulled rather than blocking a delete.
    """

    quote_id: int = Field(foreign_key="quote.id", index=True)
    option_id: int | None = Field(default=None, foreign_key="option.id")

    group_name: str
    option_slug: str
    option_name: str
    price_delta_cents: int
    sort_order: int = 0

    quote: "Quote" = Relationship(back_populates="lines")


class Quote(BaseTable, table=True):
    """A submitted lead: a priced build, or a general enquiry with no build attached.

    ``ref`` is the public identifier -- it is what the customer is shown, what the confirmation
    email carries, and what sales quotes back over the phone. Prices are stored in the same
    snapshot spirit as ``QuoteLine``; ``total_cents`` is always the server's own computation,
    never a number the browser sent.
    """

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

    # Kept for abuse triage only. The API sits behind the web app, so this is the forwarded
    # visitor address rather than the socket peer -- see app/core/infrastructure/ratelimit.py.
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

    lines: list[QuoteLine] = Relationship(
        back_populates="quote",
        sa_relationship_kwargs={
            "order_by": "QuoteLine.sort_order",
            "cascade": "all, delete-orphan",
        },
    )
