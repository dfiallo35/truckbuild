from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

from app.models.enums import DisplayStyle, SelectionMode
from app.models.option import Option

if TYPE_CHECKING:
    from app.models.platform import Platform


class OptionGroup(SQLModel, table=True):
    """One step in the configurator (e.g. "Power System"). ``slug`` is unique per platform."""

    __table_args__ = (
        UniqueConstraint("platform_id", "slug", name="uq_option_group_platform_slug"),
    )

    id: int | None = Field(default=None, primary_key=True)
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
