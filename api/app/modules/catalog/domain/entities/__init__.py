"""The catalog's SQLModel tables. Imported eagerly so relationship string references resolve
regardless of import order, and so Alembic's autogenerate sees every table.

Trimming this to what looks used produces a migration that silently drops tables;
``tests/test_entity_registry.py`` fails the moment a table here goes unregistered.
"""

from app.modules.catalog.domain.entities.asset import Asset
from app.modules.catalog.domain.entities.option import Option
from app.modules.catalog.domain.entities.option_group import OptionGroup
from app.modules.catalog.domain.entities.option_rule import OptionRule
from app.modules.catalog.domain.entities.platform import Platform

__all__ = ["Asset", "Option", "OptionGroup", "OptionRule", "Platform"]
