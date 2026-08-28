"""The facade a module shows the rest of the application.

A service owns no logic of its own: it wires a mapper, a filter class and a repository into the
seven standard use cases, and hands out named methods over them. That is deliberate -- when a
feature needs the create path to also send mail, the change is a ``CreateUseCase`` subclass
swapped in by ``init_use_cases``, not a branch inside a growing service method.

Subclasses must set ``mapper`` and ``filter_class`` as class attributes; the constructor refuses
to build without them, because the alternative is an ``AttributeError`` raised inside whichever
use case happens to be called first.
"""

from app.core.application.dtos import (
    BaseBatchUpdateRequest,
    BaseCreateRequest,
    BaseOutput,
    BasePaginatedOutput,
    BaseUpdateRequest,
)
from app.core.application.mappers import BaseMapper
from app.core.application.use_cases import (
    BaseUseCase,
    BatchUpdateUseCase,
    CreateUseCase,
    DeleteUseCase,
    GetByIdUseCase,
    ListUseCase,
    PaginateUseCase,
    UpdateUseCase,
)
from app.core.domain.enums import UseCaseEnum
from app.core.domain.filters import BaseFilter
from app.core.domain.interfaces import IBaseRepository


class BaseService:
    mapper: BaseMapper
    filter_class: type[BaseFilter]

    def __init__(self, repository: IBaseRepository | None = None, **deps) -> None:
        if not hasattr(self, "mapper") or not hasattr(self, "filter_class"):
            raise ValueError(
                f"{type(self).__name__} must set `mapper` and `filter_class` as class attributes"
            )

        self.repository = repository
        self.use_cases = self.init_use_cases(
            dict(
                mapper=self.mapper,
                filter_class=self.filter_class,
                repository=repository,
                **deps,
            )
        )

    def init_use_cases(self, deps: dict) -> dict[UseCaseEnum, BaseUseCase]:
        """Override to swap a feature's own subclass in for one of these, keeping the rest."""
        return {
            UseCaseEnum.create: CreateUseCase(**deps),
            UseCaseEnum.list: ListUseCase(**deps),
            UseCaseEnum.paginate: PaginateUseCase(**deps),
            UseCaseEnum.get_by_id: GetByIdUseCase(**deps),
            UseCaseEnum.update: UpdateUseCase(**deps),
            UseCaseEnum.batch_update: BatchUpdateUseCase(**deps),
            UseCaseEnum.delete: DeleteUseCase(**deps),
        }

    def create(self, create_request: BaseCreateRequest) -> BaseOutput:
        return self.use_cases[UseCaseEnum.create].exec(create_request)

    def list_entities(self, filters: BaseFilter) -> list[BaseOutput]:
        return self.use_cases[UseCaseEnum.list].exec(filters)

    def paginate_entities(self, filters: BaseFilter) -> BasePaginatedOutput[BaseOutput]:
        return self.use_cases[UseCaseEnum.paginate].exec(filters)

    def get_by_id(self, id: int) -> BaseOutput:
        return self.use_cases[UseCaseEnum.get_by_id].exec(id)

    def update(self, id: int, update_request: BaseUpdateRequest) -> BaseOutput:
        return self.use_cases[UseCaseEnum.update].exec(id, update_request)

    def batch_update(self, batch_update_request: BaseBatchUpdateRequest) -> list[BaseOutput]:
        return self.use_cases[UseCaseEnum.batch_update].exec(batch_update_request)

    def delete(self, id: int) -> None:
        return self.use_cases[UseCaseEnum.delete].exec(id)
