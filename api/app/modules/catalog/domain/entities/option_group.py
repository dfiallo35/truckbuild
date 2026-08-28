from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, UniqueConstraint

from app.core.infrastructure.postgres.tables import BaseTable
from app.modules.catalog.domain.entities.option import Option
from app.modules.catalog.domain.enums import DisplayStyle, SelectionMode

if TYPE_CHECKING:
    from app.modules.catalog.domain.entities.platform import Platform


class OptionGroup(BaseTable, table=True):
    """One step in the configurator (e.g. "Power System"). ``slug`` is unique per platform."""

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

    platform: "Platform" = Relationship(back_populates="option_groups")
    options: list[Option] = Relationship(
        back_populates="group",
        sa_relationship_kwargs={"order_by": "Option.sort_order"},
    )
