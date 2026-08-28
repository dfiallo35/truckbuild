from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship

from app.core.infrastructure.postgres.tables import BaseTable

if TYPE_CHECKING:
    from app.modules.catalog.domain.entities.option_group import OptionGroup


class Option(BaseTable, table=True):
    """A choice within an option group. ``slug`` is globally unique -- it is the public
    identifier used in shared build URLs (``?o=slug-a,slug-b``)."""

    group_id: int = Field(foreign_key="optiongroup.id", index=True)
    slug: str = Field(unique=True, index=True)
    name: str
    price_delta_cents: int = 0
    description: str = ""
    sort_order: int = 0

    group: "OptionGroup" = Relationship(back_populates="options")
