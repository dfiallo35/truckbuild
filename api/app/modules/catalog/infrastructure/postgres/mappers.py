"""Table -> domain translation: the seam between how the catalog is stored and what it means.

Assembly, not field copying. A domain ``Platform`` carries its groups, options, assets and rules
as *loaded values*, and the rows those come from arrive here already fetched by the repository --
so this module is handed everything it needs and never touches a session. That is what makes the
N+1 fix structural rather than a habit: a mapper with no session cannot lazy-load, whatever it is
asked for.

The rule mapping is the one translation with a decision in it. The table stores option ids because
that is what a foreign key can enforce; the entity carries slugs because that is what a customer
picks, what a shared build URL contains, and what ``web/src/lib/rules.ts`` mirrors.
"""

from dataclasses import dataclass, field

from app.core.infrastructure.postgres.mappers import BaseMapper
from app.modules.catalog.domain.enums import AssetKind
from app.modules.catalog.domain.models import Asset, Option, OptionGroup, OptionRule, Platform
from app.modules.catalog.infrastructure.postgres.tables import (
    AssetTable,
    OptionGroupTable,
    OptionRuleTable,
    OptionTable,
    PlatformTable,
)


@dataclass(frozen=True)
class CatalogRows:
    """Every row set the platforms of one read are assembled from, bucketed by owner.

    One of these is built per call to the repository, from a fixed number of queries however many
    platforms the read covers. Passing it is *required* rather than defaulted: a mapper called
    without it would hand back a ``Platform`` with no options and no rules, which serializes as a
    valid-looking but empty platform. A ``TypeError`` at the call site is the better failure.
    """

    groups_by_platform: dict[int, list[OptionGroupTable]] = field(default_factory=dict)
    options_by_group: dict[int, list[OptionTable]] = field(default_factory=dict)
    assets_by_platform: dict[int, list[AssetTable]] = field(default_factory=dict)
    assets_by_option: dict[int, list[AssetTable]] = field(default_factory=dict)
    rules_by_platform: dict[int, list[OptionRuleTable]] = field(default_factory=dict)
    slug_by_option_id: dict[int, str] = field(default_factory=dict)


def _asset(row: AssetTable | None) -> Asset | None:
    if row is None:
        return None
    return Asset(
        id=row.id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        kind=row.kind,
        url=row.url,
        alt_text=row.alt_text,
        sort_order=row.sort_order,
    )


class PlatformMapper(BaseMapper):
    def to_domain(self, table: PlatformTable, rows: CatalogRows) -> Platform:
        assets = rows.assets_by_platform.get(table.id, [])
        return Platform(
            id=table.id,
            created_at=table.created_at,
            updated_at=table.updated_at,
            slug=table.slug,
            name=table.name,
            purpose=table.purpose,
            chassis_basis=table.chassis_basis,
            base_price_cents=table.base_price_cents,
            spec_highlights=table.spec_highlights,
            standard_equipment=table.standard_equipment,
            hero_image=_asset(next((a for a in assets if a.kind == AssetKind.hero), None)),
            viewer_base=_asset(next((a for a in assets if a.kind == AssetKind.layer), None)),
            gallery=[_asset(a) for a in assets if a.kind == AssetKind.gallery],
            option_groups=[
                self._group(group, rows) for group in rows.groups_by_platform.get(table.id, [])
            ],
            rules=[
                OptionRule(
                    id=rule.id,
                    created_at=rule.created_at,
                    updated_at=rule.updated_at,
                    subject=rows.slug_by_option_id[rule.subject_option_id],
                    relation=rule.relation,
                    object=rows.slug_by_option_id[rule.object_option_id],
                )
                for rule in rows.rules_by_platform.get(table.id, [])
            ],
        )

    def _group(self, row: OptionGroupTable, rows: CatalogRows) -> OptionGroup:
        return OptionGroup(
            id=row.id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            slug=row.slug,
            name=row.name,
            selection_mode=row.selection_mode,
            required=row.required,
            display_style=row.display_style,
            sort_order=row.sort_order,
            options=[
                self._option(option, rows) for option in rows.options_by_group.get(row.id, [])
            ],
        )

    def _option(self, row: OptionTable, rows: CatalogRows) -> Option:
        assets = rows.assets_by_option.get(row.id, [])
        return Option(
            id=row.id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            slug=row.slug,
            name=row.name,
            price_delta_cents=row.price_delta_cents,
            description=row.description,
            sort_order=row.sort_order,
            layer=_asset(next((a for a in assets if a.kind == AssetKind.layer), None)),
            swatch=_asset(next((a for a in assets if a.kind == AssetKind.thumbnail), None)),
        )

    def to_table(self, entity: Platform) -> PlatformTable:  # pragma: no cover - read-only module
        """Not implemented, and deliberately not faked.

        The catalog is loaded from the versioned ``seed/catalog.yaml`` (see ``app/seed.py``) and
        is never written over HTTP, so nothing calls this. A shallow implementation that quietly
        dropped the option, asset and rule graph would be worse than its absence -- it would look
        like a working write path right up to the first caller that lost data through it.
        """
        raise NotImplementedError(
            "the catalog is seeded from seed/catalog.yaml, not written through the repository"
        )
