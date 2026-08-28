"""What a caller may narrow a lead read by.

The ``_eq`` suffix is the contract ``BaseRepositoryPostgres.filter`` and
``QuoteRepositoryPostgres.filter`` key off -- see ``app/core/domain/filters.py``. A field named
``kind`` rather than ``kind_eq`` would be silently ignored.

``search`` is the deliberate exception, and is named for what it does rather than for a
comparison: it is one term matched case-insensitively across three columns at once (``ref``,
``contact_name``, ``contact_email``), which no single suffix describes. It is what the admin lead
list's search box sends.
"""

from app.core.domain.filters import BaseFilter
from app.modules.quotes.domain.enums import QuoteKind


class QuoteFilter(BaseFilter):
    """``order_by`` defaults to newest first, which is the only order a lead list is read in.

    The repository adds ``id`` as a tie-break in the same direction: two leads can share a
    ``created_at`` to the microsecond under a test's clock, and a page boundary that wobbles
    drops or repeats a lead.
    """

    order_by: str | None = "-created_at"

    ref_eq: str | None = None
    kind_eq: QuoteKind | None = None
    platform_slug_eq: str | None = None
    search: str | None = None
