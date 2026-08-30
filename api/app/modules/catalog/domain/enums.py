from enum import StrEnum


class SelectionMode(StrEnum):
    single = "single"
    multi = "multi"


class DisplayStyle(StrEnum):
    card = "card"
    swatch = "swatch"
    toggle = "toggle"


class RuleRelation(StrEnum):
    requires = "requires"
    excludes = "excludes"


class AssetKind(StrEnum):
    hero = "hero"
    gallery = "gallery"
    thumbnail = "thumbnail"


class CatalogUseCaseEnum(StrEnum):
    """The catalog's own use case, beyond the CRUD set ``core``'s ``UseCaseEnum`` names.

    Keyed into the same ``BaseService.use_cases`` dictionary: ``StrEnum`` members hash as their
    value, so the two enums coexist there without colliding, and a service still keys off a name
    CI can see rather than off a bare string.
    """

    revalidate = "revalidate"
