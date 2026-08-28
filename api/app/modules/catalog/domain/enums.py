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
    layer = "layer"
