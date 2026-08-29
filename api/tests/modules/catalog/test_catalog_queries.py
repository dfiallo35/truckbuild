"""The N+1 is gone, and stays gone.

Before Stage 10, reading the catalog cost a number of round trips proportional to how many
platforms were seeded: three explicit queries per platform inside ``_serialize_platform``, plus a
lazy load for each platform's groups and each group's options, issued by attribute access on ORM
objects inside the request session.

That is the kind of regression that reappears the moment someone adds a field and reaches for a
relationship, and it never shows up in a response body -- so it is asserted here rather than
eyeballed in a log. A fourth platform is inserted inside the test's own transaction and rolled
back, and the statement count must not move.
"""

from contextlib import contextmanager

from sqlalchemy import event
from sqlmodel import Session

from app.core.infrastructure.postgres.database import engine
from app.modules.catalog.domain.enums import AssetKind, DisplayStyle, RuleRelation, SelectionMode
from app.modules.catalog.domain.filters import PlatformFilter
from app.modules.catalog.infrastructure.postgres.repositories import PlatformRepositoryPostgres
from app.modules.catalog.infrastructure.postgres.tables import (
    AssetTable,
    OptionGroupTable,
    OptionRuleTable,
    OptionTable,
    PlatformTable,
)


@contextmanager
def counting_statements():
    """Count every statement the engine sends while the block runs."""
    counted = []

    def _count(*_args, **_kwargs) -> None:
        counted.append(1)

    event.listen(engine, "before_cursor_execute", _count)
    try:
        yield counted
    finally:
        event.remove(engine, "before_cursor_execute", _count)


def _read(session: Session) -> list:
    return PlatformRepositoryPostgres(session).list(PlatformFilter())


def _add_a_fourth_platform(session: Session) -> None:
    """A whole platform, not an empty one: a group, two options, an asset on each end, and a rule
    between them. An extra platform with nothing hanging off it would not exercise the queries
    that used to be per-platform."""
    platform = PlatformTable(
        slug="test-fourth-platform",
        name="Fourth",
        purpose="test",
        chassis_basis="test",
        base_price_cents=1_000_00,
        spec_highlights=["a"],
        standard_equipment=["b"],
    )
    session.add(platform)
    session.flush()

    session.add(
        AssetTable(
            platform_id=platform.id, kind=AssetKind.hero, url="/x.jpg", alt_text="x", sort_order=0
        )
    )

    group = OptionGroupTable(
        platform_id=platform.id,
        slug="test-fourth-group",
        name="Group",
        selection_mode=SelectionMode.multi,
        required=False,
        display_style=DisplayStyle.card,
        sort_order=0,
    )
    session.add(group)
    session.flush()

    first = OptionTable(group_id=group.id, slug="test-fourth-a", name="A", sort_order=0)
    second = OptionTable(group_id=group.id, slug="test-fourth-b", name="B", sort_order=1)
    session.add(first)
    session.add(second)
    session.flush()

    session.add(
        AssetTable(
            option_id=first.id, kind=AssetKind.layer, url="/y.png", alt_text="y", sort_order=10
        )
    )
    session.add(
        OptionRuleTable(
            subject_option_id=first.id,
            relation=RuleRelation.requires,
            object_option_id=second.id,
        )
    )
    session.flush()


def test_reading_the_catalog_costs_the_same_however_many_platforms_there_are() -> None:
    with Session(engine) as session:
        try:
            with counting_statements() as before:
                three = _read(session)

            _add_a_fourth_platform(session)

            with counting_statements() as after:
                four = _read(session)
        finally:
            # Nothing was committed; the fourth platform never existed outside this transaction.
            session.rollback()

    # Guard on the guard: if the insert had not landed, the counts would match vacuously.
    assert len(four) == len(three) + 1
    assert len(before) == len(after), (
        f"reading {len(three)} platforms took {len(before)} statements and reading {len(four)} "
        f"took {len(after)} -- the catalog read is N+1 again"
    )


def test_reading_the_catalog_is_seven_statements() -> None:
    """Named so the number is reviewable: platforms, their groups, their options, every asset
    either owns, the rules over them, every platform's build model, and every option's model
    effect. An eighth is not automatically wrong -- but it is a decision someone should have to
    make on purpose."""
    with Session(engine) as session, counting_statements() as counted:
        _read(session)

    assert len(counted) == 7


def test_a_platform_read_by_slug_costs_the_same_as_the_whole_catalog() -> None:
    """``by_slug`` is the path ``quotes`` prices a submission through, so it is the one that runs
    on every lead rather than once per cached page."""
    with Session(engine) as session, counting_statements() as counted:
        platform = PlatformRepositoryPostgres(session).by_slug("bristlecone")

    assert platform is not None
    assert platform.options and platform.rules
    assert len(counted) == 7
