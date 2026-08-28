"""Query parameters for the catalog reads, as a model.

Nothing narrows ``GET /v1/catalog`` today -- it answers with the whole catalog, which is small
enough that splitting it costs more round trips than it saves bytes. The class exists so that the
first parameter that *is* wanted (``?purpose=overland``, a slug list for a comparison page) is a
field here and a ``to_domain()`` away from the repository, rather than a new argument threaded
through the handler.

``domain_filter_class`` is the seam; ``to_domain()`` is the only crossing.
"""

from typing import ClassVar

from app.core.presentation.filters import BaseFilter
from app.modules.catalog.domain.filters import PlatformFilter as DomainPlatformFilter


class PlatformFilter(BaseFilter):
    domain_filter_class: ClassVar[type[DomainPlatformFilter]] = DomainPlatformFilter

    order_by: str | None = "id"

    slug_eq: str | None = None
    slug_in: list[str] | None = None
    purpose_eq: str | None = None
