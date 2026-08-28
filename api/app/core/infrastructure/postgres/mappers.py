"""Table <-> domain translation.

The other half of the pair whose first half is ``core/application/mappers.py``. Same name, same
shape, different job: this one knows about columns and joins, that one knows about what a caller
is allowed to see. Keeping them apart is what lets a column be added without the wire moving,
and a response field be added without a migration.
"""

from abc import ABC, abstractmethod

from app.core.domain.models import BaseEntity
from app.core.infrastructure.postgres.tables import BaseTable


class BaseMapper(ABC):
    @abstractmethod
    def to_table(self, entity: BaseEntity) -> BaseTable:
        pass  # pragma: no cover

    @abstractmethod
    def to_domain(self, table: BaseTable) -> BaseEntity:
        pass  # pragma: no cover
