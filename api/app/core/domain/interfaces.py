"""The ports the domain depends on, and nothing about how they are filled.

ABCs rather than ``Protocol``s, matching the reference repository: ``BaseRepositoryPostgres``
*inherits* ``IBaseRepository`` rather than merely happening to satisfy it, so the ABC is carrying
its own weight -- it supplies the shared shape and fails at construction rather than at the
first missing call.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.domain.filters import BaseFilter
from app.core.domain.models import BaseEntity


class IBaseRepository(ABC):
    """Storage, in domain terms: entities in, entities out, filters to narrow.

    Nothing here returns a table row or a session. A use case written against this can be tested
    with a dictionary, which is the whole reason the port exists.
    """

    @abstractmethod
    def create(self, entity: BaseEntity) -> BaseEntity:
        pass  # pragma: no cover

    @abstractmethod
    def list(self, filters: BaseFilter) -> list[BaseEntity]:
        pass  # pragma: no cover

    @abstractmethod
    def count(self, filters: BaseFilter) -> int:
        pass  # pragma: no cover

    @abstractmethod
    def update(self, entity: BaseEntity) -> BaseEntity:
        pass  # pragma: no cover

    @abstractmethod
    def delete(self, entity: BaseEntity) -> None:
        pass  # pragma: no cover


@dataclass(frozen=True)
class RateLimitVerdict:
    """Whether a hit is allowed, and how long to wait if not.

    In ``domain`` rather than beside the limiter because it is what ``IRateLimiter`` returns, and
    a port whose return type lives in an adapter is not a port.
    """

    allowed: bool
    retry_after_seconds: int = 0


class IRateLimiter(ABC):
    """Abuse control, as something the domain can ask rather than something it must import.

    Today the only implementation counts in process memory (see
    ``app/core/infrastructure/ratelimit.py``); the upgrade path is a shared counter, at which
    point nothing above this line changes.
    """

    @abstractmethod
    def check(self, key: str) -> RateLimitVerdict:
        pass  # pragma: no cover


@dataclass(frozen=True)
class StoredBlob:
    """Where a ``put`` landed. ``path`` is the storage-relative key handed to ``put`` -- distinct
    from ``url`` because a caller that wants to ``delete`` or overwrite the same blob later needs
    the key, not whatever a CDN front-ends it with.
    """

    url: str
    path: str
    byte_size: int


class IBlobStore(ABC):
    """Large binaries the database should not hold, as bytes in and a URL out.

    Beside ``IRateLimiter`` rather than in ``catalog``: ``put``/``delete``/``exists`` name no
    module's vocabulary, which is CLAUDE.md's rule for what belongs in ``core``. Today's only
    caller is ``python -m app.assets sync`` (Stage 15 of the archived development plan, Notion),
    writing GLB truck models; a second caller reaches for the same port rather than inventing its
    own.
    """

    @abstractmethod
    def put(self, path: str, data: bytes, content_type: str) -> StoredBlob:
        pass  # pragma: no cover

    @abstractmethod
    def delete(self, path: str) -> None:
        pass  # pragma: no cover

    @abstractmethod
    def exists(self, path: str) -> bool:
        pass  # pragma: no cover
