"""What a catalog use case answers with: the bodies behind ``GET /v1/catalog`` and
``GET /v1/platforms/{slug}``.

In ``application`` rather than ``presentation`` because a use case builds one and a router only
serializes it -- and distinct from ``domain/models.py`` because an entity is a fact and a DTO is
a message. They look alike today and diverge the first time the wire needs a field the domain
does not have, or must stop sending one it does: ``Asset.sort_order`` is already such a field,
carried by the entity and spent by the mapper on ordering rather than sent.

Pure pydantic -- no ``fastapi``, no ``sqlmodel``. The field names, types and order are the wire
contract and are checked against ``tests/golden/`` on every stage of the migration.
"""

from app.core.application.dtos import BaseOutput
from app.modules.catalog.domain.enums import AssetKind, DisplayStyle, RuleRelation, SelectionMode


class AssetOutput(BaseOutput):
    kind: AssetKind
    url: str
    alt_text: str


class LayerOutput(BaseOutput):
    """One image in the configurator viewer composite. ``z_index`` is what stacks it; the
    platform's own base layer is always 0."""

    url: str
    alt_text: str
    z_index: int


class OptionOutput(BaseOutput):
    slug: str
    name: str
    price_delta_cents: int
    description: str
    layer: LayerOutput | None = None
    swatch: AssetOutput | None = None


class OptionGroupOutput(BaseOutput):
    slug: str
    name: str
    selection_mode: SelectionMode
    required: bool
    display_style: DisplayStyle
    options: list[OptionOutput]


class OptionRuleOutput(BaseOutput):
    subject: str
    relation: RuleRelation
    object: str


class PlatformOutput(BaseOutput):
    slug: str
    name: str
    purpose: str
    chassis_basis: str
    base_price_cents: int
    spec_highlights: list[str]
    standard_equipment: list[str]
    hero_image: AssetOutput | None
    viewer_base: LayerOutput | None
    gallery: list[AssetOutput]
    option_groups: list[OptionGroupOutput]
    rules: list[OptionRuleOutput]


class CatalogOutput(BaseOutput):
    platforms: list[PlatformOutput]
