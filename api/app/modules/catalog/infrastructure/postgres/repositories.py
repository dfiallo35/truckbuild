"""Every query the catalog module makes, and its one write, in one place.

Stage 13 moved the seed's bulk upsert here from ``app/seed.py``, onto
``IPlatformRepository.upsert_from_catalog`` -- a repository concern like everything else in this
class, not a script's inline table writes.

Before Stage 10 the queries were spread across two routers: three per platform inside
``_serialize_platform``, two lookups in the handlers, and three more in ``quotes`` -- plus one
lazy load per platform for its groups and one per group for its options, issued by attribute
access inside the request session. Reading the catalog therefore cost a number of round trips
proportional to how many platforms were seeded, which is the definition of an N+1.

**The fix is the shape of this class, not a tuning flag.** ``list`` issues a fixed seven
statements whatever it is asked for -- platforms, their groups, their options, every asset either
owns, the rules over them, every platform's build model, and every option's model effect --
buckets the rows by owner, and hands the mapper a complete ``CatalogRows``. Nothing above this
line holds a session, so nothing above this line can add an eighth.
``tests/modules/catalog/test_catalog_queries.py`` seeds a fourth platform and asserts the count
does not move.
"""

# `list` is a method on this class (it is the port's name for "read many"), which shadows the
# builtin inside the class body -- so `list[str]` in any annotation below it would resolve to the
# method. Deferring annotation evaluation is the fix that does not rename the port.
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import or_
from sqlalchemy.sql import Select
from sqlmodel import col, select

from app.core.infrastructure.postgres.repositories import BaseRepositoryPostgres
from app.modules.catalog.domain.enums import AssetKind
from app.modules.catalog.domain.exceptions import PlatformHasNoModelError, PlatformNotFoundError
from app.modules.catalog.domain.filters import PlatformFilter
from app.modules.catalog.domain.interfaces import IPlatformRepository
from app.modules.catalog.domain.models import Platform
from app.modules.catalog.infrastructure.postgres.mappers import CatalogRows, PlatformMapper
from app.modules.catalog.infrastructure.postgres.tables import (
    AssetTable,
    BuildModelTable,
    OptionGroupTable,
    OptionModelEffectTable,
    OptionRuleTable,
    OptionTable,
    PlatformTable,
)


class PlatformRepositoryPostgres(BaseRepositoryPostgres, IPlatformRepository):
    mapper = PlatformMapper()
    table_class = PlatformTable

    def filter(self, filters: PlatformFilter, query: Select) -> Select:
        """The shared narrowing first, then the catalog's own -- the pattern every feature
        repository follows, so that ``id_eq``, the window and the ordering keep behaving
        identically wherever they are used."""
        query = super().filter(filters, query)

        if filters.slug_eq is not None:
            query = query.where(col(PlatformTable.slug) == filters.slug_eq)
        if filters.slug_in is not None:
            query = query.where(col(PlatformTable.slug).in_(filters.slug_in))
        if filters.purpose_eq is not None:
            query = query.where(col(PlatformTable.purpose) == filters.purpose_eq)

        return query

    def list(self, filters: PlatformFilter) -> list[Platform]:
        rows = self.session.exec(self.filter(filters, select(PlatformTable))).all()
        catalog_rows = self._rows_for(rows)
        return [self.mapper.to_domain(row, catalog_rows) for row in rows]

    def by_slug(self, slug: str) -> Platform | None:
        platforms = self.list(PlatformFilter(slug_eq=slug))
        return platforms[0] if platforms else None

    def slugs(self) -> list[str]:
        """One column, one statement -- naming the cache tags does not need the whole graph."""
        query = select(col(PlatformTable.slug)).order_by(col(PlatformTable.id))
        return list(self.session.exec(query).all())

    def write_model_reference(self, slug: str, url: str, content_hash: str, byte_size: int) -> None:
        """The one write ``python -m app.assets sync`` makes -- see the port's docstring for what
        it deliberately leaves alone. ``SyncModelsUseCase.validate`` has already confirmed both
        the platform and its ``BuildModelTable`` row exist before this is ever called; the checks
        here are what keeps that true rather than assumed."""
        platform = self.session.exec(
            select(PlatformTable).where(PlatformTable.slug == slug)
        ).first()
        if platform is None:
            raise PlatformNotFoundError(slug)

        model = self.session.exec(
            select(BuildModelTable).where(BuildModelTable.platform_id == platform.id)
        ).first()
        if model is None:
            raise PlatformHasNoModelError(slug)

        model.url = url
        model.content_hash = content_hash
        model.byte_size = byte_size
        self.session.add(model)
        self.session.commit()

    def _rows_for(self, platforms: list[PlatformTable]) -> CatalogRows:
        """Six statements, whatever the length of ``platforms``."""
        platform_ids = [platform.id for platform in platforms]

        groups = self.session.exec(
            select(OptionGroupTable)
            .where(col(OptionGroupTable.platform_id).in_(platform_ids))
            .order_by(col(OptionGroupTable.sort_order), col(OptionGroupTable.id))
        ).all()
        group_ids = [group.id for group in groups]

        options = self.session.exec(
            select(OptionTable)
            .where(col(OptionTable.group_id).in_(group_ids))
            .order_by(col(OptionTable.sort_order), col(OptionTable.id))
        ).all()
        option_ids = [option.id for option in options]

        # Both halves of the asset table in one pass: a platform's hero, gallery and viewer base
        # hang off `platform_id`, an option's layer and swatch off `option_id`.
        assets = self.session.exec(
            select(AssetTable)
            .where(
                or_(
                    col(AssetTable.platform_id).in_(platform_ids),
                    col(AssetTable.option_id).in_(option_ids),
                )
            )
            .order_by(col(AssetTable.sort_order), col(AssetTable.id))
        ).all()

        rules = self.session.exec(
            select(OptionRuleTable)
            .where(col(OptionRuleTable.subject_option_id).in_(option_ids))
            .order_by(col(OptionRuleTable.id))
        ).all()

        models = self.session.exec(
            select(BuildModelTable).where(col(BuildModelTable.platform_id).in_(platform_ids))
        ).all()

        effects = self.session.exec(
            select(OptionModelEffectTable).where(
                col(OptionModelEffectTable.option_id).in_(option_ids)
            )
        ).all()

        groups_by_platform: dict[int, list[OptionGroupTable]] = defaultdict(list)
        for group in groups:
            groups_by_platform[group.platform_id].append(group)

        options_by_group: dict[int, list[OptionTable]] = defaultdict(list)
        for option in options:
            options_by_group[option.group_id].append(option)

        assets_by_platform: dict[int, list[AssetTable]] = defaultdict(list)
        assets_by_option: dict[int, list[AssetTable]] = defaultdict(list)
        for asset in assets:
            if asset.platform_id is not None:
                assets_by_platform[asset.platform_id].append(asset)
            if asset.option_id is not None:
                assets_by_option[asset.option_id].append(asset)

        platform_by_group = {group.id: group.platform_id for group in groups}
        platform_by_option = {option.id: platform_by_group[option.group_id] for option in options}

        # A rule is the subject platform's, and only if both its ends are that platform's own
        # options. Nothing in seed/catalog.yaml pairs options across platforms, and a rule that
        # did would be a content mistake -- one dropped from a response is recoverable, one that
        # renders as a conflict with an option the customer cannot see is not.
        rules_by_platform: dict[int, list[OptionRuleTable]] = defaultdict(list)
        for rule in rules:
            platform_id = platform_by_option.get(rule.subject_option_id)
            if platform_id is None:
                continue
            if platform_by_option.get(rule.object_option_id) != platform_id:
                continue
            rules_by_platform[platform_id].append(rule)

        return CatalogRows(
            groups_by_platform=groups_by_platform,
            options_by_group=options_by_group,
            assets_by_platform=assets_by_platform,
            assets_by_option=assets_by_option,
            rules_by_platform=rules_by_platform,
            slug_by_option_id={option.id: option.slug for option in options},
            model_by_platform={model.platform_id: model for model in models},
            effect_by_option={effect.option_id: effect for effect in effects},
        )

    def upsert_from_catalog(self, catalog: dict) -> list[str]:
        """The bulk, idempotent write ``app/seed.py`` used to do inline against these tables
        directly. Stage 13 split the argparse shell (``app/seed.py``) from the YAML read
        (``catalog_file.py``) from this -- the actual storage write, which belongs here with
        every other catalog query.

        Commits before returning. Unlike ``create``/``update``, which only flush, this is the one
        write in the service that has to commit before it returns: ``SeedCatalogUseCase`` calls
        ``ICacheInvalidator.invalidate`` right after this, and revalidating a page cache before
        the row backing it is durable would tell the web app to refetch a value it can't yet see
        under read-committed isolation -- refreshing the cache to the *old* value. Same reasoning
        as ``QuoteRepositoryPostgres.create``'s early commit, for a different reason.

        ``catalog`` must be the *complete* catalog, not one platform's slice: ``_sync_rules``
        resyncs the whole ``optionrule`` table against ``catalog["rules"]``, deleting any rule
        not named there regardless of which platform it belongs to. That has always been true of
        the seed catalog this reads (``seed/catalog.yaml`` is one file naming every rule), so it
        was never reachable before -- a caller that upserts a subset of platforms with a partial
        rule list will silently drop every other platform's rules.
        """
        for platform_data in catalog["platforms"]:
            platform = self._upsert_platform(platform_data)
            self._upsert_platform_assets(platform, platform_data)
            self._upsert_platform_model(platform, platform_data)
            for group_order, group_data in enumerate(platform_data["option_groups"]):
                group = self._upsert_option_group(platform, group_order, group_data)
                for option_order, option_data in enumerate(group_data["options"]):
                    option = self._upsert_option(group, option_order, option_data)
                    self._upsert_option_assets(option, option_data)
                    self._upsert_option_model_effect(option, option_data)

        self.session.flush()
        self._sync_rules(catalog["rules"])
        self.session.commit()

        return [platform_data["slug"] for platform_data in catalog["platforms"]]

    def _upsert_platform(self, data: dict) -> PlatformTable:
        platform = self.session.exec(
            select(PlatformTable).where(PlatformTable.slug == data["slug"])
        ).first()
        if platform is None:
            platform = PlatformTable(slug=data["slug"])

        platform.name = data["name"]
        platform.purpose = data["purpose"]
        platform.chassis_basis = data["chassis_basis"]
        platform.base_price_cents = data["base_price_cents"]
        platform.spec_highlights = data["spec_highlights"]
        platform.standard_equipment = data["standard_equipment"]
        self.session.add(platform)
        self.session.flush()
        return platform

    def _upsert_platform_assets(self, platform: PlatformTable, data: dict) -> None:
        existing = self.session.exec(
            select(AssetTable).where(AssetTable.platform_id == platform.id)
        ).all()
        by_key = {(asset.kind, asset.sort_order): asset for asset in existing}

        hero = data["hero_image"]
        asset = by_key.pop((AssetKind.hero, 0), None) or AssetTable(
            platform_id=platform.id, kind=AssetKind.hero, sort_order=0, url="", alt_text=""
        )
        asset.url = hero["url"]
        asset.alt_text = hero["alt_text"]
        self.session.add(asset)

        for i, image in enumerate(data.get("gallery", [])):
            asset = by_key.pop((AssetKind.gallery, i), None) or AssetTable(
                platform_id=platform.id, kind=AssetKind.gallery, sort_order=i, url="", alt_text=""
            )
            asset.url = image["url"]
            asset.alt_text = image["alt_text"]
            self.session.add(asset)

        # Layer 0 of the configurator viewer composite. Option layers carry the same kind but
        # hang off an option instead, at their own z-index.
        viewer_base = data.get("viewer_base")
        if viewer_base is not None:
            asset = by_key.pop((AssetKind.layer, 0), None) or AssetTable(
                platform_id=platform.id, kind=AssetKind.layer, sort_order=0, url="", alt_text=""
            )
            asset.url = viewer_base["url"]
            asset.alt_text = viewer_base["alt_text"]
            self.session.add(asset)

        for stale in by_key.values():
            self.session.delete(stale)

    def _upsert_platform_model(self, platform: PlatformTable, data: dict) -> None:
        """The framing and description a platform's ``BuildModelTable`` row carries from
        ``seed/catalog.yaml``. ``url``, ``content_hash`` and ``byte_size`` are never touched here
        -- they are ``python -m app.assets sync``'s to write, and a re-seed that blanked them
        would silently un-publish every model."""
        model = data.get("model")
        existing = self.session.exec(
            select(BuildModelTable).where(BuildModelTable.platform_id == platform.id)
        ).first()

        if model is None:
            if existing is not None:
                self.session.delete(existing)
            return

        row = existing or BuildModelTable(platform_id=platform.id)
        row.alt_text = model["alt_text"]
        row.camera_orbit_deg = model["camera_orbit_deg"]
        row.camera_distance_m = model["camera_distance_m"]
        row.camera_target_y_m = model["camera_target_y_m"]
        self.session.add(row)

    def _upsert_option_group(
        self, platform: PlatformTable, sort_order: int, data: dict
    ) -> OptionGroupTable:
        group = self.session.exec(
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
        self.session.add(group)
        self.session.flush()
        return group

    def _upsert_option(self, group: OptionGroupTable, sort_order: int, data: dict) -> OptionTable:
        option = self.session.exec(
            select(OptionTable).where(OptionTable.slug == data["slug"])
        ).first()
        if option is None:
            option = OptionTable(slug=data["slug"])

        option.group_id = group.id
        option.name = data["name"]
        option.price_delta_cents = data["price_delta_cents"]
        option.description = data.get("description", "")
        option.sort_order = sort_order
        self.session.add(option)
        self.session.flush()
        return option

    def _upsert_option_assets(self, option: OptionTable, data: dict) -> None:
        """An option carries at most one ``layer`` (its contribution to the viewer composite,
        with ``sort_order`` holding the z-index) and one ``thumbnail`` (the chip a swatch group
        renders). Either may be absent -- an option without a layer simply contributes nothing to
        the viewer."""
        existing = self.session.exec(
            select(AssetTable).where(AssetTable.option_id == option.id)
        ).all()
        by_kind = {asset.kind: asset for asset in existing}

        layer = data.get("layer")
        if layer is not None:
            asset = by_kind.pop(AssetKind.layer, None) or AssetTable(
                option_id=option.id, kind=AssetKind.layer, url="", alt_text=""
            )
            asset.url = layer["url"]
            asset.alt_text = layer["alt_text"]
            asset.sort_order = layer["z"]
            self.session.add(asset)

        swatch = data.get("swatch")
        if swatch is not None:
            asset = by_kind.pop(AssetKind.thumbnail, None) or AssetTable(
                option_id=option.id, kind=AssetKind.thumbnail, url="", alt_text=""
            )
            asset.url = swatch["url"]
            asset.alt_text = swatch["alt_text"]
            self.session.add(asset)

        for stale in by_kind.values():
            self.session.delete(stale)

    def _upsert_option_model_effect(self, option: OptionTable, data: dict) -> None:
        """At most one ``OptionModelEffectTable`` row per option -- ``nodes`` for geometry,
        ``material_target`` plus a colour for a finish, either, both, or neither."""
        effect = data.get("model_effect")
        existing = self.session.exec(
            select(OptionModelEffectTable).where(OptionModelEffectTable.option_id == option.id)
        ).first()

        if effect is None:
            if existing is not None:
                self.session.delete(existing)
            return

        row = existing or OptionModelEffectTable(option_id=option.id)
        row.nodes = effect.get("nodes", [])
        row.material_target = effect.get("material_target")
        row.base_color_hex = effect.get("base_color_hex")
        row.metalness = effect.get("metalness")
        row.roughness = effect.get("roughness")
        self.session.add(row)

    def _sync_rules(self, rules_data: list[dict]) -> None:
        slug_to_id = {
            option.slug: option.id for option in self.session.exec(select(OptionTable)).all()
        }
        wanted = {
            (slug_to_id[rule["subject"]], rule["relation"], slug_to_id[rule["object"]])
            for rule in rules_data
        }

        existing = self.session.exec(select(OptionRuleTable)).all()
        for rule in existing:
            key = (rule.subject_option_id, rule.relation, rule.object_option_id)
            if key not in wanted:
                self.session.delete(rule)
            else:
                wanted.discard(key)

        for subject_id, relation, object_id in wanted:
            self.session.add(
                OptionRuleTable(
                    subject_option_id=subject_id, relation=relation, object_option_id=object_id
                )
            )
