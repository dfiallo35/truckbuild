"""What the catalog *means*, as pure pydantic. No ``sqlmodel``, no ``sqlalchemy``, no ``fastapi``.

The other half of every one of these lives in ``infrastructure/postgres/tables.py`` as a SQLModel
table, with ``infrastructure/postgres/mappers.py`` as the seam. That split is the point of the
stage: an entity is a fact about the business, a table is how it is stored, and the two stop being
the same class so that neither drags the other around.

**Everything nested here is a loaded value, not a lazy relationship.** ``Platform.option_groups``,
``Platform.rules`` and the assets hanging off each are ordinary lists that the repository filled
before it handed the entity over. That is the N+1 fix stated as a type: reading an attribute
cannot issue a query, because there is no session on the other side of it to issue one -- so the
repository, and only the repository, decides what a ``Platform`` costs to produce.
"""

from app.core.domain.models import BaseEntity
from app.modules.catalog.domain.enums import AssetKind, DisplayStyle, RuleRelation, SelectionMode


class Asset(BaseEntity):
    """An image. ``sort_order`` carries the gallery position for ``gallery`` assets and the
    z-index in the configurator viewer composite for ``layer`` ones; the platform's own base
    layer is always 0.

    ``platform_id`` / ``option_id`` -- which of the two owns the row -- are storage wiring and
    stay on the table. Here an asset is reached through the thing it belongs to.
    """

    kind: AssetKind
    url: str
    alt_text: str
    sort_order: int = 0


class Option(BaseEntity):
    """A choice within an option group. ``slug`` is globally unique -- it is the public
    identifier used in shared build URLs (``?o=slug-a,slug-b``), so renaming one is a breaking
    change."""

    slug: str
    name: str
    price_delta_cents: int = 0
    description: str = ""
    sort_order: int = 0

    layer: Asset | None = None
    swatch: Asset | None = None


class OptionGroup(BaseEntity):
    """One step in the configurator (e.g. "Power System"). ``slug`` is unique per platform."""

    slug: str
    name: str
    selection_mode: SelectionMode
    required: bool = False
    display_style: DisplayStyle
    sort_order: int = 0

    options: list[Option] = []


class OptionRule(BaseEntity):
    """A compatibility relation between two options: ``subject`` requires or excludes ``object``.

    Slugs, not ids. The table stores ``subject_option_id`` / ``object_option_id`` because that is
    what a foreign key can enforce; the *rule* is about the two options a customer picks, which
    they know by slug. The mapper resolves one into the other, and that resolution is the reason
    ``validate_selection`` can be mirrored in the browser at all.
    """

    subject: str
    relation: RuleRelation
    object: str


class Platform(BaseEntity):
    """A configurable product line (the reference site's "model"), with everything the
    configurator and the marketing pages need already loaded.

    ``slug`` is the public identifier -- it appears in URLs and shared builds, so renaming one is
    a breaking change.
    """

    slug: str
    name: str
    purpose: str
    chassis_basis: str
    base_price_cents: int
    spec_highlights: list[str] = []
    standard_equipment: list[str] = []

    hero_image: Asset | None = None
    viewer_base: Asset | None = None
    gallery: list[Asset] = []

    option_groups: list[OptionGroup] = []
    rules: list[OptionRule] = []

    @property
    def options(self) -> list[Option]:
        """Every option on the platform, flattened, in group then option order.

        Named ``options`` deliberately: it is the field ``web/src/lib/pricing.ts`` reads on its
        own ``PriceablePlatform``, so ``price_build`` looks the same on both sides of the mirror
        (see .claude/skills/pricing-mirror).
        """
        return [option for group in self.option_groups for option in group.options]
