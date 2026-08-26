"""Response shapes for GET /v1/catalog and GET /v1/platforms/{slug}.

Plain Pydantic models rather than the SQLModel table classes, so the wire shape is decoupled
from storage and every field returned is deliberate.
"""

from pydantic import BaseModel

from app.models.enums import AssetKind, DisplayStyle, RuleRelation, SelectionMode


class AssetOut(BaseModel):
    kind: AssetKind
    url: str
    alt_text: str


class OptionOut(BaseModel):
    slug: str
    name: str
    price_delta_cents: int
    description: str


class OptionGroupOut(BaseModel):
    slug: str
    name: str
    selection_mode: SelectionMode
    required: bool
    display_style: DisplayStyle
    options: list[OptionOut]


class OptionRuleOut(BaseModel):
    subject: str
    relation: RuleRelation
    object: str


class PlatformOut(BaseModel):
    slug: str
    name: str
    purpose: str
    chassis_basis: str
    base_price_cents: int
    spec_highlights: list[str]
    standard_equipment: list[str]
    hero_image: AssetOut | None
    gallery: list[AssetOut]
    option_groups: list[OptionGroupOut]
    rules: list[OptionRuleOut]


class CatalogOut(BaseModel):
    platforms: list[PlatformOut]
