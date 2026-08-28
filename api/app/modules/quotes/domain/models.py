"""A submitted lead and the option lines it was priced from.

**Pure pydantic.** No ``sqlmodel``, no ``fastapi`` -- the SQLModel tables these are stored as live
in ``infrastructure/postgres/tables.py`` and the mapper between them beside those. Until Stage 11
these two classes *were* the tables; splitting them is what lets ``price_build``, the selection
checks and ``SubmitQuoteUseCase`` be exercised without a database.

The snapshot rule is the one piece of behaviour carried in the shape rather than in a function,
so it is restated on both classes: a quote is a record of what was offered on a date.
"""

from app.core.domain.models import BaseEntity
from app.modules.quotes.domain.enums import QuoteKind


class QuoteLine(BaseEntity):
    """One selected option, as it was priced at submission time.

    The option's name and price delta are *copied* rather than read through ``option_id``:
    repricing the catalog next quarter must not silently rewrite a quote that was already sent.
    ``option_id`` survives only as a convenience for joining back to the live catalog, and is
    nulled rather than blocking a delete.
    """

    quote_id: int | None = None
    option_id: int | None = None

    group_name: str
    option_slug: str
    option_name: str
    price_delta_cents: int
    sort_order: int = 0


class Quote(BaseEntity):
    """A submitted lead: a priced build, or a general enquiry with no build attached.

    ``ref`` is the public identifier -- what the customer is shown, what the confirmation email
    carries, and what sales quotes back over the phone. It is empty on an entity that has not
    been stored yet: the unique index on ``quote.ref`` is what decides a ref is free, so
    allocating one is ``QuoteRepositoryPostgres.create``'s business rather than the caller's.

    Prices are stored in the same snapshot spirit as ``QuoteLine``; ``total_cents`` is always the
    server's own computation, never a number the browser sent.
    """

    ref: str = ""
    kind: QuoteKind

    platform_id: int | None = None
    platform_slug: str | None = None
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

    lines: list[QuoteLine] = []
