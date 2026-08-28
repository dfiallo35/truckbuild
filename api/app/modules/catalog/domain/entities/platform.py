from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel

from app.modules.catalog.domain.entities.option_group import OptionGroup


class Platform(SQLModel, table=True):
    """A configurable product line (the reference site's "model"). ``slug`` is the public
    identifier -- it appears in URLs and shared builds, so renaming one is a breaking change."""

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(unique=True, index=True)
    name: str
    purpose: str
    chassis_basis: str
    base_price_cents: int
    spec_highlights: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    standard_equipment: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    option_groups: list[OptionGroup] = Relationship(
        back_populates="platform",
        sa_relationship_kwargs={"order_by": "OptionGroup.sort_order"},
    )
