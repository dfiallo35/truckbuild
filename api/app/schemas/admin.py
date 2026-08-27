"""Response shapes for the staff-only endpoints.

The list is a summary rather than a page of full quotes: sales scans it for a name, a platform
and a total, and opens one. Sending every option line for every lead would make the common case
pay for the rare one.
"""

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import QuoteKind


class QuoteSummary(BaseModel):
    ref: str
    kind: QuoteKind
    created_at: datetime
    contact_name: str
    contact_email: str
    platform_slug: str | None
    platform_name: str | None
    total_cents: int | None
    line_count: int


class QuotePage(BaseModel):
    """``total`` counts the whole filtered set, not this page -- it is what tells the caller
    whether there is more to fetch."""

    items: list[QuoteSummary]
    total: int
    limit: int
    offset: int


class RevalidateIn(BaseModel):
    """An explicit set of tags, or ``None`` to mean "everything the catalog touches"."""

    tags: list[str] | None = None


class RevalidateOut(BaseModel):
    ok: bool
    tags: list[str]
    detail: str
