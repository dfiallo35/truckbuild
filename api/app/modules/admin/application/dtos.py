"""Staff-facing shapes for reading leads, and the manual cache-revalidation trigger.

Until this stage the router rendered leads through ``quotes``' own ``QuoteMapper`` and
``QuoteDetailOutput`` -- legal, since both are ``application``, but still borrowed: a staff-facing
lead view and a customer-facing submission response are two audiences whose fields will diverge
the first time either changes. These are ``admin``'s own, built from ``quotes.domain.Quote`` by
``application/mappers.py``.

The wire bodies are unchanged from what the borrowed shapes rendered: only where they live moved.
"""

from datetime import datetime

from pydantic import BaseModel

from app.core.application.dtos import BaseOutput, BasePaginatedOutput
from app.modules.quotes.domain.enums import QuoteKind


class QuoteSummaryOutput(BaseOutput):
    """One row of the lead list. A summary rather than the whole lead: sales scans it for a name,
    a platform and a total, and opens one. Sending every option line for every lead would make
    the common case pay for the rare one."""

    ref: str
    kind: QuoteKind
    created_at: datetime
    contact_name: str
    contact_email: str
    platform_slug: str | None
    platform_name: str | None
    total_cents: int | None
    line_count: int


class QuotePageOutput(BasePaginatedOutput[QuoteSummaryOutput]):
    """``total`` counts the whole filtered set, not this page -- it is what tells the caller
    whether there is more to fetch. ``GET /v1/admin/quotes`` always has a window, so ``limit`` and
    ``offset`` are narrowed from core's optional bounds to a stricter schema over an identical
    body -- the case ``core/application/dtos.py`` anticipates for ``BasePaginatedOutput``."""

    limit: int
    offset: int


class ContactOutput(BaseOutput):
    name: str
    email: str
    phone: str


class QuoteLineDetailOutput(BaseOutput):
    group_name: str
    option_slug: str
    option_name: str
    price_delta_cents: int


class QuoteDetailOutput(BaseOutput):
    """The whole lead, including the details only staff should see. What the admin detail
    endpoint answers with -- never returned to the browser that submitted it."""

    ref: str
    kind: QuoteKind
    platform_slug: str | None
    platform_name: str | None
    base_price_cents: int | None
    total_cents: int | None
    lines: list[QuoteLineDetailOutput]
    created_at: datetime
    contact: ContactOutput
    intended_use: str
    timeline: str
    notes: str


class RevalidateRequest(BaseModel):
    """An explicit set of tags, or ``None`` to mean "everything the catalog touches"."""

    tags: list[str] | None = None


class RevalidateOutput(BaseModel):
    ok: bool
    tags: list[str]
    detail: str
