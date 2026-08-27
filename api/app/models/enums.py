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


class QuoteKind(StrEnum):
    """A lead is either a configured build or a general enquiry from /contact. Both land in the
    same table so sales reads one list and one series of reference numbers."""

    build = "build"
    enquiry = "enquiry"
