"""Query parameters, as a model -- the presentation-layer half of the filter pair.

Two filter classes for one concept looks redundant right up to the first time a query parameter
needs something the domain has no opinion about: a bound (``le=MAX_PAGE_SIZE``), an alias for a
name the URL already uses, a default that belongs to one endpoint rather than to the table. The
domain filter says what a repository can narrow by; this one says what a caller may ask for.

``domain_filter_class`` is the seam between them, and ``to_domain()`` the only crossing.
"""

from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel

from app.core.domain.filters import BaseFilter as DomainBaseFilter


class BaseFilter(BaseModel):
    domain_filter_class: ClassVar[type[DomainBaseFilter]] = DomainBaseFilter

    limit: int | None = None
    offset: int | None = None
    order_by: str | None = "created_at"

    id_eq: int | None = None
    created_at_gte: datetime | None = None
    created_at_lte: datetime | None = None
    updated_at_gte: datetime | None = None
    updated_at_lte: datetime | None = None

    def to_domain(self) -> DomainBaseFilter:
        return self.domain_filter_class(**self.model_dump())
