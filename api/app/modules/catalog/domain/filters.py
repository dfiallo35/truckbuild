"""What a caller may narrow a catalog read by.

The ``_eq`` / ``_in`` suffixes are the contract ``BaseRepositoryPostgres.filter`` and
``PlatformRepositoryPostgres.filter`` key off -- see ``app/core/domain/filters.py``. A field named
``slug`` rather than ``slug_eq`` would be silently ignored.
"""

from app.core.domain.filters import BaseFilter


class PlatformFilter(BaseFilter):
    """``order_by`` defaults to ``id`` rather than ``core``'s ``created_at``.

    ``GET /v1/catalog`` has always listed platforms in insertion order, and the seed loads all
    three inside one transaction -- so ordering on a timestamp would leave the order of the
    marketing site's platform list up to a tie-break nobody chose. The key is the order.
    """

    order_by: str | None = "id"

    slug_eq: str | None = None
    slug_in: list[str] | None = None
    purpose_eq: str | None = None
