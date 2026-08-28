"""Every query the catalog module makes, in one place.

Before Stage 10 these were spread across two routers: three per platform inside
``_serialize_platform``, two lookups in the handlers, and three more in ``quotes`` -- plus one
lazy load per platform for its groups and one per group for its options, issued by attribute
access inside the request session. Reading the catalog therefore cost a number of round trips
proportional to how many platforms were seeded, which is the definition of an N+1.

**The fix is the shape of this class, not a tuning flag.** ``list`` issues a fixed five statements
whatever it is asked for -- platforms, their groups, their options, every asset either owns, and
the rules over them -- buckets the rows by owner, and hands the mapper a complete
``CatalogRows``. Nothing above this line holds a session, so nothing above this line can add a
sixth. ``tests/modules/catalog/test_catalog_queries.py`` seeds a fourth platform and asserts the
count does not move.
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
from app.modules.catalog.domain.filters import PlatformFilter
from app.modules.catalog.domain.interfaces import IPlatformRepository
from app.modules.catalog.domain.models import Platform
from app.modules.catalog.infrastructure.postgres.mappers import CatalogRows, PlatformMapper
from app.modules.catalog.infrastructure.postgres.tables import (
    AssetTable,
    OptionGroupTable,
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

    def _rows_for(self, platforms: list[PlatformTable]) -> CatalogRows:
        """Four statements, whatever the length of ``platforms``."""
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
        )
