"""The query vocabulary every repository speaks.

A filter is a plain pydantic object rather than a pile of keyword arguments so that a use case
can build one, narrow it, and hand it on without any layer above the repository knowing what SQL
it becomes.

**The suffix convention is load-bearing.** ``_eq``, ``_in``, ``_ilike``, ``_gte`` and ``_lte``
name the comparison, and ``BaseRepositoryPostgres.filter`` -- along with every feature's override
of it -- keys off exactly these names. A field called ``created_after`` would be silently
ignored, so the suffix is the contract, not a style preference.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, field_validator


class BaseFilter(BaseModel):
    """Filters every table supports, because ``BaseTable`` gives every table these columns.

    ``limit``/``offset`` rather than the reference repository's ``page``/``size``:
    ``GET /v1/admin/quotes`` already takes ``limit`` and ``offset`` and the admin page already
    reads them, and the wire contract does not move for a naming preference.

    Every bound is optional. ``None`` means "no limit", which is what a catalog read wants --
    a page size belongs to the endpoint that has a page, and arrives via the presentation-layer
    filter that carries the bound.
    """

    limit: int | None = None
    offset: int | None = None
    order_by: str | None = "created_at"

    id_eq: int | None = None
    created_at_gte: datetime | None = None
    created_at_lte: datetime | None = None
    updated_at_gte: datetime | None = None
    updated_at_lte: datetime | None = None

    @field_validator("created_at_gte", "created_at_lte", "updated_at_gte", "updated_at_lte")
    @classmethod
    def assume_utc(cls, value: datetime | None) -> datetime | None:
        """A naive datetime is UTC, decided here rather than by the driver.

        A date-only query param (``?created_at_gte=2026-08-28``) parses to a naive datetime, and
        a driver binding that to a ``timestamptz`` column resolves it against the host machine's
        local timezone. That makes the boundary of a range query depend on where the process
        happens to be running, which is the kind of bug that only shows up after a deploy moves
        region.
        """
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
