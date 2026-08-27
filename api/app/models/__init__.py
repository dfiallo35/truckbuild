"""SQLModel tables. Imported eagerly so relationship string references resolve regardless of
import order, and so Alembic's autogenerate sees every table."""

from app.models.asset import Asset
from app.models.enums import AssetKind, DisplayStyle, QuoteKind, RuleRelation, SelectionMode
from app.models.option import Option
from app.models.option_group import OptionGroup
from app.models.option_rule import OptionRule
from app.models.platform import Platform
from app.models.quote import Quote, QuoteLine

__all__ = [
    "Asset",
    "AssetKind",
    "DisplayStyle",
    "Option",
    "OptionGroup",
    "OptionRule",
    "Platform",
    "Quote",
    "QuoteKind",
    "QuoteLine",
    "RuleRelation",
    "SelectionMode",
]
