"""How the catalog is stored. SQLModel tables, and nothing about what any of it means.

The other half of every one of these is a pure pydantic entity in ``domain/models.py``, with
``mappers.py`` as the seam between them.

**``__tablename__`` is pinned on every table.** SQLModel derives it from the class name, so
renaming ``Platform`` to ``PlatformTable`` would silently rename five tables -- which autogenerate
writes as ``drop_table`` + ``create_table``, taking the data with it. The names below are the ones
``alembic/versions/4f1ee330b15e_add_catalog_tables.py`` created, and the index names derived from
them (``ix_platform_slug`` and friends) go on matching for the same reason.

Imported eagerly by ``alembic/env.py`` so autogenerate sees every table;
``tests/test_entity_registry.py`` fails the moment one goes unregistered.
"""

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, UniqueConstraint

from app.core.infrastructure.postgres.tables import BaseTable
from app.modules.catalog.domain.enums import AssetKind, DisplayStyle, RuleRelation, SelectionMode


class AssetTable(BaseTable, table=True):
    """An image. ``platform_id`` is set for hero/gallery assets and for the platform's viewer
    base layer; ``option_id`` for an option's thumbnail/layer -- exactly one of the two is
    populated.

    For ``layer`` assets ``sort_order`` carries the z-index in the configurator viewer
    composite, and the platform's base layer is always 0.
    """

    __tablename__ = "asset"

    kind: AssetKind
    url: str
    alt_text: str
    sort_order: int = 0

    platform_id: int | None = Field(default=None, foreign_key="platform.id", index=True)
    option_id: int | None = Field(default=None, foreign_key="option.id", index=True)


class OptionTable(BaseTable, table=True):
    """A choice within an option group. ``slug`` is globally unique -- it is the public
    identifier used in shared build URLs (``?o=slug-a,slug-b``)."""

    __tablename__ = "option"

    group_id: int = Field(foreign_key="optiongroup.id", index=True)
    slug: str = Field(unique=True, index=True)
    name: str
    price_delta_cents: int = 0
    description: str = ""
    sort_order: int = 0

    group: "OptionGroupTable" = Relationship(back_populates="options")


class OptionGroupTable(BaseTable, table=True):
    """One step in the configurator (e.g. "Power System"). ``slug`` is unique per platform."""

    __tablename__ = "optiongroup"
    __table_args__ = (
        UniqueConstraint("platform_id", "slug", name="uq_option_group_platform_slug"),
    )

    platform_id: int = Field(foreign_key="platform.id", index=True)
    slug: str = Field(index=True)
    name: str
    selection_mode: SelectionMode
    required: bool = False
    display_style: DisplayStyle
    sort_order: int = 0

    platform: "PlatformTable" = Relationship(back_populates="option_groups")
    options: list[OptionTable] = Relationship(
        back_populates="group",
        sa_relationship_kwargs={"order_by": "OptionTable.sort_order"},
    )


class OptionRuleTable(BaseTable, table=True):
    """A compatibility relation between two options: ``subject`` requires or excludes
    ``object``. See docs/domain-model.md for the rules the seed catalog must exercise."""

    __tablename__ = "optionrule"
    __table_args__ = (
        UniqueConstraint(
            "subject_option_id", "relation", "object_option_id", name="uq_option_rule"
        ),
    )

    subject_option_id: int = Field(foreign_key="option.id", index=True)
    relation: RuleRelation
    object_option_id: int = Field(foreign_key="option.id", index=True)


class PlatformTable(BaseTable, table=True):
    """A configurable product line. ``slug`` is the public identifier -- it appears in URLs and
    shared builds, so renaming one is a breaking change."""

    __tablename__ = "platform"

    slug: str = Field(unique=True, index=True)
    name: str
    purpose: str
    chassis_basis: str
    base_price_cents: int
    spec_highlights: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    standard_equipment: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    option_groups: list[OptionGroupTable] = Relationship(
        back_populates="platform",
        sa_relationship_kwargs={"order_by": "OptionGroupTable.sort_order"},
    )
