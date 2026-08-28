"""Domain <-> DTO translation.

Deliberately a *different* mapper from the one in ``core/infrastructure/postgres/mappers.py``.
Domain-to-DTO and domain-to-table are different jobs: one answers "what may this caller see",
the other "how is this stored". They look like the same function on day one and drift apart the
first time a column is added that the wire must not carry, or a response field is computed from
two rows.
"""

from abc import ABC, abstractmethod

from app.core.application.dtos import BaseCreateRequest, BaseOutput, BaseUpdateRequest
from app.core.domain.models import BaseEntity


class BaseMapper(ABC):
    @abstractmethod
    def to_api(self, entity: BaseEntity) -> BaseOutput:
        pass  # pragma: no cover

    @abstractmethod
    def to_domain(self, create_request: BaseCreateRequest) -> BaseEntity:
        pass  # pragma: no cover

    @abstractmethod
    def to_update(self, entity: BaseEntity, update_request: BaseUpdateRequest) -> BaseEntity:
        pass  # pragma: no cover
