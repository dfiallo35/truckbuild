"""``BaseRepositoryPostgres.filter`` against a throwaway table.

Declared here rather than borrowed from a module so the test says what it means: these are the
filters *every* table supports because ``BaseTable`` gives every table the columns. Borrowing
``platform`` would test the catalog's seed data as much as the filter.

Needs the local Postgres (the same one the API contract tests use); it creates its own table and
drops it again.
"""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlmodel import Session

from app.core.domain.exceptions import NotValidOrderByError
from app.core.domain.filters import BaseFilter
from app.core.domain.models import BaseEntity
from app.core.infrastructure.postgres.database import engine
from app.core.infrastructure.postgres.mappers import BaseMapper
from app.core.infrastructure.postgres.repositories import BaseRepositoryPostgres
from app.core.infrastructure.postgres.tables import BaseTable


class WidgetTable(BaseTable, table=True):
    __tablename__ = "test_widget"

    name: str


class Widget(BaseEntity):
    name: str


class WidgetMapper(BaseMapper):
    def to_table(self, entity: Widget) -> WidgetTable:
        return WidgetTable(**entity.model_dump())

    def to_domain(self, table: WidgetTable) -> Widget:
        return Widget(**table.model_dump())


class WidgetRepository(BaseRepositoryPostgres):
    mapper = WidgetMapper()
    table_class = WidgetTable


# Three rows a day apart, so a boundary can land between them rather than on top of one.
_DAYS = [datetime(2026, 8, day, 12, 0, tzinfo=UTC) for day in (26, 27, 28)]


@pytest.fixture
def repository() -> Iterator[WidgetRepository]:
    WidgetTable.__table__.create(engine, checkfirst=True)
    try:
        with Session(engine) as session:
            for name, moment in zip(("winch", "awning", "ladder"), _DAYS, strict=True):
                session.add(WidgetTable(name=name, created_at=moment, updated_at=moment))
            session.flush()
            yield WidgetRepository(session)
            # Rolled back rather than committed: the table is dropped either way, and nothing
            # this test writes should outlive it.
            session.rollback()
    finally:
        WidgetTable.__table__.drop(engine, checkfirst=True)


def _names(repository: WidgetRepository, filters: BaseFilter) -> list[str]:
    return [widget.name for widget in repository.list(filters)]


def test_an_unfiltered_list_returns_every_row(repository: WidgetRepository) -> None:
    assert sorted(_names(repository, BaseFilter())) == ["awning", "ladder", "winch"]


def test_id_eq_narrows_to_one_row(repository: WidgetRepository) -> None:
    winch = next(w for w in repository.list(BaseFilter()) if w.name == "winch")
    assert _names(repository, BaseFilter(id_eq=winch.id)) == ["winch"]


def test_created_at_gte_drops_everything_before_the_boundary(
    repository: WidgetRepository,
) -> None:
    assert _names(repository, BaseFilter(created_at_gte=_DAYS[1])) == ["awning", "ladder"]


def test_created_at_lte_drops_everything_after_it(repository: WidgetRepository) -> None:
    assert _names(repository, BaseFilter(created_at_lte=_DAYS[1])) == ["winch", "awning"]


def test_updated_at_bounds_narrow_the_same_way(repository: WidgetRepository) -> None:
    filters = BaseFilter(updated_at_gte=_DAYS[1], updated_at_lte=_DAYS[1])
    assert _names(repository, filters) == ["awning"]


def test_limit_and_offset_walk_the_ordering(repository: WidgetRepository) -> None:
    assert _names(repository, BaseFilter(limit=2)) == ["winch", "awning"]
    assert _names(repository, BaseFilter(limit=2, offset=2)) == ["ladder"]


def test_a_leading_minus_reverses_the_ordering(repository: WidgetRepository) -> None:
    assert _names(repository, BaseFilter(order_by="-created_at")) == [
        "ladder",
        "awning",
        "winch",
    ]


def test_an_unknown_order_by_is_rejected_rather_than_ignored(
    repository: WidgetRepository,
) -> None:
    """A dropped sort is a page that looks right, is in the wrong order, and gives nobody a
    reason to look."""
    with pytest.raises(NotValidOrderByError) as exc:
        repository.list(BaseFilter(order_by="nonexistent"))

    assert exc.value.status_code == 400
    assert "test_widget" in exc.value.message


def test_count_ignores_the_page_window(repository: WidgetRepository) -> None:
    """A count carrying the page's LIMIT answers "how many are on this page", which is the
    number the caller already has."""
    assert repository.count(BaseFilter(limit=1)) == 3
    assert repository.count(BaseFilter(created_at_gte=_DAYS[1])) == 2


def test_create_round_trips_through_the_mapper(repository: WidgetRepository) -> None:
    created = repository.create(Widget(name="tent"))

    assert created.id is not None
    # The server defaults land on the way back, so an entity that arrived without timestamps
    # leaves with them.
    assert created.created_at is not None
    assert created.updated_at is not None
    assert _names(repository, BaseFilter(id_eq=created.id)) == ["tent"]
