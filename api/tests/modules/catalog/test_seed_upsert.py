"""``PlatformRepositoryPostgres.upsert_from_catalog`` is the real upsert app/seed.py used to do
inline -- run it twice, row counts must not move. ``test_seed_assets.py`` and the stage checkpoint
prove the same guarantee end to end against the real seed catalog; this proves it against a
minimal one that's cheap to mutate between assertions.
"""

from sqlmodel import Session, col, select

from app.core.infrastructure.postgres.database import engine
from app.modules.catalog.infrastructure.postgres.repositories import PlatformRepositoryPostgres
from app.modules.catalog.infrastructure.postgres.tables import (
    AssetTable,
    OptionGroupTable,
    OptionRuleTable,
    OptionTable,
    PlatformTable,
)

SLUG = "test-seed-upsert-platform"


def _existing_rules(session: Session) -> list[dict]:
    """``_sync_rules`` (inside ``upsert_from_catalog``) resyncs the *whole* ``optionrule`` table
    against whatever ``catalog["rules"]`` says, not just the platform(s) being upserted -- exactly
    what the original ``app/seed.py`` did, since its one real caller always passed the complete
    seed catalog. A test catalog has to carry the real rules back through unchanged, or it wipes
    every other platform's rules out from under the rest of this test session.
    """
    slug_by_id = {option.id: option.slug for option in session.exec(select(OptionTable)).all()}
    return [
        {
            "subject": slug_by_id[rule.subject_option_id],
            "relation": rule.relation,
            "object": slug_by_id[rule.object_option_id],
        }
        for rule in session.exec(select(OptionRuleTable)).all()
    ]


def _catalog(session: Session, *, price_delta: int = 500_00) -> dict:
    return {
        "platforms": [
            {
                "slug": SLUG,
                "name": "Test Upsert Platform",
                "purpose": "test",
                "chassis_basis": "test",
                "base_price_cents": 10_000_00,
                "spec_highlights": [],
                "standard_equipment": [],
                "hero_image": {"url": "/images/test-hero.jpg", "alt_text": "hero"},
                "viewer_base": {"url": "/images/test-base.png", "alt_text": "base"},
                "gallery": [],
                "option_groups": [
                    {
                        "slug": "trim",
                        "name": "Trim",
                        "selection_mode": "single",
                        "required": True,
                        "display_style": "card",
                        "options": [
                            {"slug": "trim-standard", "name": "Standard", "price_delta_cents": 0},
                            {
                                "slug": "trim-heavy",
                                "name": "Heavy",
                                "price_delta_cents": price_delta,
                            },
                        ],
                    }
                ],
            }
        ],
        "rules": _existing_rules(session),
    }


def _row_counts(session: Session) -> tuple[int, int, int]:
    platform = session.exec(select(PlatformTable).where(PlatformTable.slug == SLUG)).one()
    groups = session.exec(
        select(OptionGroupTable).where(OptionGroupTable.platform_id == platform.id)
    ).all()
    options = session.exec(
        select(OptionTable).where(col(OptionTable.group_id).in_([g.id for g in groups]))
    ).all()
    assets = session.exec(
        select(AssetTable).where(col(AssetTable.platform_id) == platform.id)
    ).all()
    return len(groups), len(options), len(assets)


def _cleanup(session: Session) -> None:
    """``upsert_from_catalog`` commits for real (see its docstring), so unlike the read-only
    tests in ``test_catalog_queries.py`` this can't rely on a rollback -- the test platform has
    to be torn down explicitly, in FK order, or it permanently inflates the platform count every
    other catalog test in this session asserts against.
    """
    platform = session.exec(select(PlatformTable).where(PlatformTable.slug == SLUG)).first()
    if platform is None:
        return

    groups = session.exec(
        select(OptionGroupTable).where(OptionGroupTable.platform_id == platform.id)
    ).all()
    option_ids = [
        option.id
        for group in groups
        for option in session.exec(
            select(OptionTable).where(OptionTable.group_id == group.id)
        ).all()
    ]

    for rule in session.exec(
        select(OptionRuleTable).where(col(OptionRuleTable.subject_option_id).in_(option_ids))
    ).all():
        session.delete(rule)
    for asset in session.exec(
        select(AssetTable).where(
            (col(AssetTable.platform_id) == platform.id)
            | (col(AssetTable.option_id).in_(option_ids))
        )
    ).all():
        session.delete(asset)
    for option_id in option_ids:
        session.delete(session.get(OptionTable, option_id))
    for group in groups:
        session.delete(group)
    session.delete(platform)
    session.commit()


def test_seeding_twice_does_not_duplicate_rows() -> None:
    with Session(engine) as session:
        repo = PlatformRepositoryPostgres(session)
        try:
            slugs = repo.upsert_from_catalog(_catalog(session))
            first = _row_counts(session)

            repo.upsert_from_catalog(_catalog(session))
            second = _row_counts(session)

            assert slugs == [SLUG]
            assert first == second == (1, 2, 2)
        finally:
            _cleanup(session)


def test_reseeding_updates_a_changed_field_in_place() -> None:
    with Session(engine) as session:
        repo = PlatformRepositoryPostgres(session)
        try:
            repo.upsert_from_catalog(_catalog(session, price_delta=500_00))
            repo.upsert_from_catalog(_catalog(session, price_delta=750_00))

            option = session.exec(select(OptionTable).where(OptionTable.slug == "trim-heavy")).one()
            assert option.price_delta_cents == 750_00
        finally:
            _cleanup(session)


def test_seeding_does_not_disturb_other_platforms_rules() -> None:
    with Session(engine) as session:
        repo = PlatformRepositoryPostgres(session)
        before = _existing_rules(session)
        assert before, "expected the real seed catalog to carry at least one rule"

        try:
            repo.upsert_from_catalog(_catalog(session))
            after = _existing_rules(session)
            assert {tuple(r.values()) for r in after} == {tuple(r.values()) for r in before}
        finally:
            _cleanup(session)
