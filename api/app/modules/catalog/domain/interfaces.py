"""The ports the catalog depends on, and nothing about how they are filled.

``IPlatformRepository`` is owned here rather than in ``core`` because ``catalog`` owns the data:
a port belongs to the module whose vocabulary it speaks. ``quotes`` and ``admin`` consume it --
that is what ``admin -> quotes -> catalog`` means -- and neither may name the Postgres adapter
that implements it (the facade rule, CLAUDE.md); the binding is made at the composition root in
``app/main.py``.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass

from app.core.domain.interfaces import IBaseRepository
from app.modules.catalog.domain.filters import PlatformFilter
from app.modules.catalog.domain.models import Platform


class IPlatformRepository(IBaseRepository):
    """Reading the catalog, in domain terms.

    ``list(filters)`` is inherited and is the "every platform, fully loaded" case -- the two
    methods below are the lookups that have a caller outside this module and would otherwise be
    re-derived, slightly differently, in each of them.

    Every ``Platform`` that comes back has its groups, options, assets and rules already loaded.
    That is a promise of the port, not an accident of the adapter: a caller that could trigger a
    query by reading an attribute is a caller that can reintroduce the N+1 this stage removed.

    One trap worth naming, because it costs ten minutes every time: ``list`` is a method here, so
    it shadows the builtin inside the body of any class implementing this. An annotation like
    ``list[str]`` written *after* it raises ``TypeError: 'function' object is not subscriptable``
    at class-creation time. ``from __future__ import annotations`` at the top of the
    implementation is the fix that does not rename the port.
    """

    @abstractmethod
    def by_slug(self, slug: str) -> Platform | None:
        pass  # pragma: no cover

    @abstractmethod
    def slugs(self) -> list[str]:
        """Every platform slug, and nothing else -- what naming the cache tags needs, without
        paying for the whole graph."""
        pass  # pragma: no cover

    @abstractmethod
    def upsert_from_catalog(self, catalog: dict) -> list[str]:
        """Upsert every platform in ``catalog`` by slug, and return the slugs it covered.

        Bulk, and shaped like the YAML it reads -- not a single-entity write. ``create`` and
        ``update`` take one already-built ``Platform``, which has no room for "insert this
        option, delete that stale asset, sync these rules" across three nested levels. The seed
        is the one caller.
        """
        pass  # pragma: no cover

    @abstractmethod
    def list(self, filters: PlatformFilter) -> list[Platform]:
        pass  # pragma: no cover


@dataclass(frozen=True)
class RevalidateResult:
    """Whether the tags were dropped, and what to say if they were not.

    In ``domain`` because it is what ``ICacheInvalidator`` returns, and a port whose return type
    lives in an adapter is not a port.
    """

    ok: bool
    tags: tuple[str, ...]
    detail: str


class ICacheInvalidator(ABC):
    """Telling whoever caches the catalog that it has changed."""

    @abstractmethod
    def invalidate(self, tags: Iterable[str]) -> RevalidateResult:
        pass  # pragma: no cover
