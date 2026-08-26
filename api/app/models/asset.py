from sqlmodel import Field, SQLModel

from app.models.enums import AssetKind


class Asset(SQLModel, table=True):
    """An image. ``platform_id`` is set for hero/gallery assets, ``option_id`` for
    thumbnail/layer assets -- exactly one of the two is populated, depending on ``kind``."""

    id: int | None = Field(default=None, primary_key=True)
    kind: AssetKind
    url: str
    alt_text: str
    sort_order: int = 0

    platform_id: int | None = Field(default=None, foreign_key="platform.id", index=True)
    option_id: int | None = Field(default=None, foreign_key="option.id", index=True)
