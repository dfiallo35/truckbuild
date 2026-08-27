"""Loads seed/catalog.yaml into Postgres, upserting by slug so re-running is always safe.

Postgres remains the runtime source of truth; this file only keeps it in sync with the
version-controlled seed content. Run with ``python -m app.seed``.
"""

from pathlib import Path

import yaml
from sqlmodel import Session, select

from app.db import engine
from app.models import Asset, AssetKind, Option, OptionGroup, OptionRule, Platform

CATALOG_PATH = Path(__file__).resolve().parent.parent / "seed" / "catalog.yaml"


def _upsert_platform(session: Session, data: dict) -> Platform:
    platform = session.exec(select(Platform).where(Platform.slug == data["slug"])).first()
    if platform is None:
        platform = Platform(slug=data["slug"])

    platform.name = data["name"]
    platform.purpose = data["purpose"]
    platform.chassis_basis = data["chassis_basis"]
    platform.base_price_cents = data["base_price_cents"]
    platform.spec_highlights = data["spec_highlights"]
    platform.standard_equipment = data["standard_equipment"]
    session.add(platform)
    session.flush()
    return platform


def _upsert_platform_assets(session: Session, platform: Platform, data: dict) -> None:
    existing = session.exec(select(Asset).where(Asset.platform_id == platform.id)).all()
    by_key = {(asset.kind, asset.sort_order): asset for asset in existing}

    hero = data["hero_image"]
    asset = by_key.pop((AssetKind.hero, 0), None) or Asset(
        platform_id=platform.id, kind=AssetKind.hero, sort_order=0, url="", alt_text=""
    )
    asset.url = hero["url"]
    asset.alt_text = hero["alt_text"]
    session.add(asset)

    for i, image in enumerate(data.get("gallery", [])):
        asset = by_key.pop((AssetKind.gallery, i), None) or Asset(
            platform_id=platform.id, kind=AssetKind.gallery, sort_order=i, url="", alt_text=""
        )
        asset.url = image["url"]
        asset.alt_text = image["alt_text"]
        session.add(asset)

    # Layer 0 of the configurator viewer composite. Option layers carry the same kind but hang
    # off an option instead, at their own z-index.
    viewer_base = data.get("viewer_base")
    if viewer_base is not None:
        asset = by_key.pop((AssetKind.layer, 0), None) or Asset(
            platform_id=platform.id, kind=AssetKind.layer, sort_order=0, url="", alt_text=""
        )
        asset.url = viewer_base["url"]
        asset.alt_text = viewer_base["alt_text"]
        session.add(asset)

    for stale in by_key.values():
        session.delete(stale)


def _upsert_option_group(
    session: Session, platform: Platform, sort_order: int, data: dict
) -> OptionGroup:
    group = session.exec(
        select(OptionGroup).where(
            OptionGroup.platform_id == platform.id, OptionGroup.slug == data["slug"]
        )
    ).first()
    if group is None:
        group = OptionGroup(platform_id=platform.id, slug=data["slug"])

    group.name = data["name"]
    group.selection_mode = data["selection_mode"]
    group.required = data["required"]
    group.display_style = data["display_style"]
    group.sort_order = sort_order
    session.add(group)
    session.flush()
    return group


def _upsert_option(session: Session, group: OptionGroup, sort_order: int, data: dict) -> Option:
    option = session.exec(select(Option).where(Option.slug == data["slug"])).first()
    if option is None:
        option = Option(slug=data["slug"])

    option.group_id = group.id
    option.name = data["name"]
    option.price_delta_cents = data["price_delta_cents"]
    option.description = data.get("description", "")
    option.sort_order = sort_order
    session.add(option)
    session.flush()
    return option


def _upsert_option_assets(session: Session, option: Option, data: dict) -> None:
    """An option carries at most one ``layer`` (its contribution to the viewer composite, with
    ``sort_order`` holding the z-index) and one ``thumbnail`` (the chip a swatch group renders).
    Either may be absent -- an option without a layer simply contributes nothing to the viewer."""
    existing = session.exec(select(Asset).where(Asset.option_id == option.id)).all()
    by_kind = {asset.kind: asset for asset in existing}

    layer = data.get("layer")
    if layer is not None:
        asset = by_kind.pop(AssetKind.layer, None) or Asset(
            option_id=option.id, kind=AssetKind.layer, url="", alt_text=""
        )
        asset.url = layer["url"]
        asset.alt_text = layer["alt_text"]
        asset.sort_order = layer["z"]
        session.add(asset)

    swatch = data.get("swatch")
    if swatch is not None:
        asset = by_kind.pop(AssetKind.thumbnail, None) or Asset(
            option_id=option.id, kind=AssetKind.thumbnail, url="", alt_text=""
        )
        asset.url = swatch["url"]
        asset.alt_text = swatch["alt_text"]
        session.add(asset)

    for stale in by_kind.values():
        session.delete(stale)


def _sync_rules(session: Session, rules_data: list[dict]) -> None:
    slug_to_id = {option.slug: option.id for option in session.exec(select(Option)).all()}
    wanted = {
        (slug_to_id[rule["subject"]], rule["relation"], slug_to_id[rule["object"]])
        for rule in rules_data
    }

    existing = session.exec(select(OptionRule)).all()
    for rule in existing:
        key = (rule.subject_option_id, rule.relation, rule.object_option_id)
        if key not in wanted:
            session.delete(rule)
        else:
            wanted.discard(key)

    for subject_id, relation, object_id in wanted:
        session.add(
            OptionRule(subject_option_id=subject_id, relation=relation, object_option_id=object_id)
        )


def seed(session: Session, catalog: dict | None = None) -> None:
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


def main() -> None:
    with Session(engine) as session:
        seed(session)


if __name__ == "__main__":
    main()
