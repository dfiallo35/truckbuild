"""The base entity every module's domain models extend.

**Pure pydantic.** No ``sqlmodel``, no ``sqlalchemy``, no ``fastapi`` -- an entity is a fact
about the business, not a row and not a response body. That separation is what lets Stages 10-12
turn on a contract forbidding persistence imports from every ``domain/``; today most entities
still *are* SQLModel tables, and this is the class they migrate onto.
"""

from datetime import datetime

from pydantic import BaseModel


class EmptyEntity(BaseModel):
    """An entity with no identity of its own -- a value read from or written to somewhere else."""

    def to_dict(self, exclude_none: bool = False) -> dict:
        """JSON-mode dump, so a datetime or an enum comes out as something a mapper can hand
        straight to a driver or a serializer rather than as a Python object."""
        return self.model_dump(mode="json", exclude_none=exclude_none)


class BaseEntity(EmptyEntity):
    """A stored entity: an identity and the two timestamps ``BaseTable`` mandates.

    ``id`` is an integer, not the reference repository's UUID. This service's public identifiers
    are slugs (``bristlecone``) and quote refs (``TB-7Q4K2M``); the integer key is never
    serialized, never appears in a URL, and swapping it for a UUID would be a migration with no
    reader on the other side.

    All three are optional because an entity that has not been persisted yet has none of them --
    the database assigns the key and the ``now()`` server defaults assign the timestamps.
    """

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
