"""Query parameters for the lead list -- the presentation-layer half of
``quotes.domain.filters.QuoteFilter``.

The domain filter says what the repository can narrow a lead read by; this one says what a caller
may ask for. ``MAX_PAGE_SIZE`` lives here rather than on ``QuoteFilter``: a bound on a query
parameter is an HTTP concern and belongs where FastAPI can reject it with a 422 before anything
else runs -- the case ``core/presentation/filters.py`` was built for.

Field names stay ``kind``/``platform_slug``/``q``, the wire contract ``GET /v1/admin/quotes``
already answers to; ``to_domain`` is the one place that translates them to ``QuoteFilter``'s
``_eq``/``search`` vocabulary.
"""

from typing import Annotated

from fastapi import Query
from pydantic import BaseModel

from app.modules.quotes.domain.enums import QuoteKind
from app.modules.quotes.domain.filters import QuoteFilter

MAX_PAGE_SIZE = 100


class AdminQuoteFilter(BaseModel):
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 25
    offset: Annotated[int, Query(ge=0)] = 0
    kind: QuoteKind | None = None
    platform_slug: str | None = None
    q: Annotated[str | None, Query(max_length=200, description="ref, name, or email")] = None

    def to_domain(self) -> QuoteFilter:
        return QuoteFilter(
            limit=self.limit,
            offset=self.offset,
            kind_eq=self.kind,
            platform_slug_eq=self.platform_slug,
            search=self.q,
        )
