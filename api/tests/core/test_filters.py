"""The domain filter: the window it carries, and the timezone it refuses to leave undecided."""

from datetime import UTC, datetime, timedelta, timezone

from app.core.domain.filters import BaseFilter
from app.core.presentation.filters import BaseFilter as QueryFilter


def test_limit_and_offset_pass_through_untouched() -> None:
    """``limit``/``offset`` rather than ``page``/``size``: the numbers a caller sends are the
    numbers the repository gets, with no arithmetic in between to get wrong."""
    filters = BaseFilter(limit=25, offset=50)
    assert filters.limit == 25
    assert filters.offset == 50


def test_an_unwindowed_filter_bounds_nothing() -> None:
    """``None`` means "every row", which is what a catalog read wants. A default page size in
    core would silently truncate it."""
    filters = BaseFilter()
    assert filters.limit is None
    assert filters.offset is None


def test_a_naive_boundary_is_read_as_utc() -> None:
    """``?created_at_gte=2026-08-28`` parses to a naive datetime. Left naive, the driver resolves
    it against the host's local timezone and the boundary of the query moves with the deploy."""
    filters = BaseFilter(created_at_gte=datetime(2026, 8, 28))
    assert filters.created_at_gte == datetime(2026, 8, 28, tzinfo=UTC)


def test_an_aware_boundary_keeps_its_own_offset() -> None:
    """Only naive values are assumed; a caller that said which zone it meant is believed."""
    aware = datetime(2026, 8, 28, tzinfo=timezone(timedelta(hours=-5)))
    assert BaseFilter(created_at_lte=aware).created_at_lte == aware


def test_every_timestamp_boundary_is_normalized() -> None:
    """All four, not just the two that happened to have a test."""
    naive = datetime(2026, 8, 28, 9, 30)
    filters = BaseFilter(
        created_at_gte=naive,
        created_at_lte=naive,
        updated_at_gte=naive,
        updated_at_lte=naive,
    )
    assert all(
        value.tzinfo is UTC
        for value in (
            filters.created_at_gte,
            filters.created_at_lte,
            filters.updated_at_gte,
            filters.updated_at_lte,
        )
    )


def test_the_query_filter_builds_its_domain_counterpart() -> None:
    """``to_domain()`` is the only crossing between the two filter classes, and the domain side
    is where the UTC assumption is applied -- so a naive query param arrives normalized whichever
    door it came through."""
    domain = QueryFilter(limit=10, offset=0, created_at_gte=datetime(2026, 8, 28)).to_domain()

    assert isinstance(domain, BaseFilter)
    assert (domain.limit, domain.offset) == (10, 0)
    assert domain.created_at_gte == datetime(2026, 8, 28, tzinfo=UTC)


def test_a_subclass_declares_which_domain_filter_it_builds() -> None:
    """``domain_filter_class`` is a ClassVar, so a feature's query filter builds that feature's
    domain filter rather than the base one."""

    class PlatformFilter(BaseFilter):
        slug_eq: str | None = None

    class PlatformQueryFilter(QueryFilter):
        domain_filter_class = PlatformFilter
        slug_eq: str | None = None

    domain = PlatformQueryFilter(slug_eq="bristlecone").to_domain()
    assert isinstance(domain, PlatformFilter)
    assert domain.slug_eq == "bristlecone"
