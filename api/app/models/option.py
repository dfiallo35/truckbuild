from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.option_group import OptionGroup


class Option(SQLModel, table=True):
    """A choice within an option group. ``slug`` is globally unique -- it is the public
    identifier used in shared build URLs (``?o=slug-a,slug-b``)."""

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="optiongroup.id", index=True)
    slug: str = Field(unique=True, index=True)
    name: str
    price_delta_cents: int = 0
    description: str = ""
    sort_order: int = 0

    group: "OptionGroup" = Relationship(back_populates="options")
