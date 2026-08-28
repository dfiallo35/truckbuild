"""Loads seed/catalog.yaml into Postgres, upserting by slug so re-running is always safe.

Postgres remains the runtime source of truth; this file only keeps it in sync with the
version-controlled seed content. Run with ``python -m app.seed``.

Writes through the catalog's SQLModel tables directly rather than through its repository: this
is a bulk upsert keyed on slugs, not a read model, and the repository deliberately has no write
path (see ``catalog/infrastructure/postgres/mappers.py``). Stage 13 revisits it. Being a script
rather than a module, it is allowed to name an adapter.

Loading the catalog is a catalog change, so the run finishes by busting the web app's cache tags
-- otherwise the rows are new and the public pages keep serving what they cached hours ago. Pass
``--no-revalidate`` where there is no web app to tell (CI, a database being prepared ahead of a
deploy); it is opt-out rather than opt-in because a stale public price is the costlier mistake.
"""

import argparse
import logging
from pathlib import Path

import yaml
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.infrastructure.postgres.database import engine
from app.modules.catalog.domain.cache_tags import tags_for_platforms
from app.modules.catalog.domain.enums import AssetKind
from app.modules.catalog.infrastructure.postgres.tables import (
    AssetTable,
    OptionGroupTable,
    OptionRuleTable,
    OptionTable,
    PlatformTable,
)
from app.modules.catalog.infrastructure.webhook.revalidate import revalidate

logger = logging.getLogger(__name__)

CATALOG_PATH = Path(__file__).resolve().parent.parent / "seed" / "catalog.yaml"


def _upsert_platform(session: Session, data: dict) -> PlatformTable:
    platform = session.exec(select(PlatformTable).where(PlatformTable.slug == data["slug"])).first()
    if platform is None:
        platform = PlatformTable(slug=data["slug"])

    platform.name = data["name"]
    platform.purpose = data["purpose"]
    platform.chassis_basis = data["chassis_basis"]
    platform.base_price_cents = data["base_price_cents"]
    platform.spec_highlights = data["spec_highlights"]
    platform.standard_equipment = data["standard_equipment"]
    session.add(platform)
    session.flush()
    return platform


def _upsert_platform_assets(session: Session, platform: PlatformTable, data: dict) -> None:
    existing = session.exec(select(AssetTable).where(AssetTable.platform_id == platform.id)).all()
    by_key = {(asset.kind, asset.sort_order): asset for asset in existing}

    hero = data["hero_image"]
    asset = by_key.pop((AssetKind.hero, 0), None) or AssetTable(
        platform_id=platform.id, kind=AssetKind.hero, sort_order=0, url="", alt_text=""
    )
    asset.url = hero["url"]
    asset.alt_text = hero["alt_text"]
    session.add(asset)

    for i, image in enumerate(data.get("gallery", [])):
        asset = by_key.pop((AssetKind.gallery, i), None) or AssetTable(
            platform_id=platform.id, kind=AssetKind.gallery, sort_order=i, url="", alt_text=""
        )
        asset.url = image["url"]
        asset.alt_text = image["alt_text"]
        session.add(asset)

    # Layer 0 of the configurator viewer composite. Option layers carry the same kind but hang
    # off an option instead, at their own z-index.
    viewer_base = data.get("viewer_base")
    if viewer_base is not None:
        asset = by_key.pop((AssetKind.layer, 0), None) or AssetTable(
            platform_id=platform.id, kind=AssetKind.layer, sort_order=0, url="", alt_text=""
        )
        asset.url = viewer_base["url"]
        asset.alt_text = viewer_base["alt_text"]
        session.add(asset)

    for stale in by_key.values():
        session.delete(stale)


def _upsert_option_group(
    session: Session, platform: PlatformTable, sort_order: int, data: dict
) -> OptionGroupTable:
    group = session.exec(
        select(OptionGroupTable).where(
            OptionGroupTable.platform_id == platform.id, OptionGroupTable.slug == data["slug"]
        )
    ).first()
    if group is None:
        group = OptionGroupTable(platform_id=platform.id, slug=data["slug"])

    group.name = data["name"]
    group.selection_mode = data["selection_mode"]
    group.required = data["required"]
    group.display_style = data["display_style"]
    group.sort_order = sort_order
    session.add(group)
    session.flush()
    return group


def _upsert_option(
    session: Session, group: OptionGroupTable, sort_order: int, data: dict
) -> OptionTable:
    option = session.exec(select(OptionTable).where(OptionTable.slug == data["slug"])).first()
    if option is None:
        option = OptionTable(slug=data["slug"])

    option.group_id = group.id
    option.name = data["name"]
    option.price_delta_cents = data["price_delta_cents"]
    option.description = data.get("description", "")
    option.sort_order = sort_order
    session.add(option)
    session.flush()
    return option


def _upsert_option_assets(session: Session, option: OptionTable, data: dict) -> None:
    """An option carries at most one ``layer`` (its contribution to the viewer composite, with
    ``sort_order`` holding the z-index) and one ``thumbnail`` (the chip a swatch group renders).
    Either may be absent -- an option without a layer simply contributes nothing to the viewer."""
    existing = session.exec(select(AssetTable).where(AssetTable.option_id == option.id)).all()
    by_kind = {asset.kind: asset for asset in existing}

    layer = data.get("layer")
    if layer is not None:
        asset = by_kind.pop(AssetKind.layer, None) or AssetTable(
            option_id=option.id, kind=AssetKind.layer, url="", alt_text=""
        )
        asset.url = layer["url"]
        asset.alt_text = layer["alt_text"]
        asset.sort_order = layer["z"]
        session.add(asset)

    swatch = data.get("swatch")
    if swatch is not None:
        asset = by_kind.pop(AssetKind.thumbnail, None) or AssetTable(
            option_id=option.id, kind=AssetKind.thumbnail, url="", alt_text=""
        )
        asset.url = swatch["url"]
        asset.alt_text = swatch["alt_text"]
        session.add(asset)

    for stale in by_kind.values():
        session.delete(stale)


def _sync_rules(session: Session, rules_data: list[dict]) -> None:
    slug_to_id = {option.slug: option.id for option in session.exec(select(OptionTable)).all()}
    wanted = {
        (slug_to_id[rule["subject"]], rule["relation"], slug_to_id[rule["object"]])
        for rule in rules_data
    }

    existing = session.exec(select(OptionRuleTable)).all()
    for rule in existing:
        key = (rule.subject_option_id, rule.relation, rule.object_option_id)
        if key not in wanted:
            session.delete(rule)
        else:
            wanted.discard(key)

    for subject_id, relation, object_id in wanted:
        session.add(
            OptionRuleTable(
                subject_option_id=subject_id, relation=relation, object_option_id=object_id
            )
        )


def seed(session: Session, catalog: dict | None = None) -> list[str]:
    """Load the catalog and return the slugs of the platforms it covers, which is what the
    caller needs to name the cache tags the load affected."""
    if catalog is None:
        with CATALOG_PATH.open() as f:
            catalog = yaml.safe_load(f)

    for platform_data in catalog["platforms"]:
        platform = _upsert_platform(session, platform_data)
        _upsert_platform_assets(session, platform, platform_data)
        for group_order, group_data in enumerate(platform_data["option_groups"]):
            group = _upsert_option_group(session, platform, group_order, group_data)
            for option_order, option_data in enumerate(group_data["options"]):
                option = _upsert_option(session, group, option_order, option_data)
                _upsert_option_assets(session, option, option_data)

    session.flush()
    _sync_rules(session, catalog["rules"])
    session.commit()

    return [platform_data["slug"] for platform_data in catalog["platforms"]]


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-revalidate",
        action="store_true",
        help="skip the web app cache revalidation (no web app to tell, e.g. in CI)",
    )
    args = parser.parse_args(argv)

    with Session(engine) as session:
        slugs = seed(session)
    logger.info("seeded %d platform(s): %s", len(slugs), ", ".join(slugs))

    if args.no_revalidate:
        logger.info("skipping cache revalidation (--no-revalidate)")
        return

    # Failures are logged by the service and deliberately do not fail the seed: the catalog is
    # already loaded, and exiting non-zero here would fail a deploy over a cache that can be
    # dropped by hand with POST /v1/admin/revalidate.
    revalidate(tags_for_platforms(slugs), get_settings())


if __name__ == "__main__":
    main()
