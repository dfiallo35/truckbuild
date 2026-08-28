from sqlmodel import Field, SQLModel

from app.modules.catalog.domain.enums import AssetKind


class Asset(SQLModel, table=True):
    """An image. ``platform_id`` is set for hero/gallery assets and for the platform's viewer
    base layer; ``option_id`` for an option's thumbnail/layer -- exactly one of the two is
    populated.

    For ``layer`` assets ``sort_order`` carries the z-index in the configurator viewer
    composite, and the platform's base layer is always 0.
    """

    id: int | None = Field(default=None, primary_key=True)
    kind: AssetKind
    url: str
    alt_text: str
    sort_order: int = 0

    platform_id: int | None = Field(default=None, foreign_key="platform.id", index=True)
    option_id: int | None = Field(default=None, foreign_key="option.id", index=True)
