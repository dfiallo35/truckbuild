"""The catalog's facade: what ``quotes``, ``admin`` and this module's own router are allowed to
see of it.

``BaseService`` builds the seven standard CRUD use cases; ``init_use_cases`` swaps in the two the
catalog actually answers with and adds the revalidation one. The create/update/delete shapes stay
registered and stay unreachable -- the catalog is loaded from the versioned
``seed/catalog.yaml``, not written over HTTP.
"""

from collections.abc import Iterable

from app.core.application.services import BaseService
from app.core.application.use_cases import BaseUseCase
from app.core.domain.enums import UseCaseEnum
from app.modules.catalog.application.dtos import CatalogOutput, PlatformOutput
from app.modules.catalog.application.mappers import PlatformMapper
from app.modules.catalog.application.use_cases import (
    GetCatalogUseCase,
    GetPlatformUseCase,
    RevalidateCatalogUseCase,
)
from app.modules.catalog.domain.enums import CatalogUseCaseEnum
from app.modules.catalog.domain.filters import PlatformFilter
from app.modules.catalog.domain.interfaces import ICacheInvalidator, RevalidateResult


class CatalogService(BaseService):
    mapper = PlatformMapper()
    filter_class = PlatformFilter

    def __init__(self, repository=None, invalidator: ICacheInvalidator | None = None) -> None:
        super().__init__(repository=repository, invalidator=invalidator)

    def init_use_cases(self, deps: dict) -> dict[UseCaseEnum | CatalogUseCaseEnum, BaseUseCase]:
        use_cases = super().init_use_cases(deps)
        use_cases[UseCaseEnum.list] = GetCatalogUseCase(**deps)
        use_cases[UseCaseEnum.get_by_id] = GetPlatformUseCase(**deps)
        use_cases[CatalogUseCaseEnum.revalidate] = RevalidateCatalogUseCase(**deps)
        return use_cases

    def get_catalog(self, filters: PlatformFilter | None = None) -> CatalogOutput:
        return self.list_entities(filters or self.filter_class())

    def get_platform(self, slug: str) -> PlatformOutput:
        return self.use_cases[UseCaseEnum.get_by_id].exec(slug)

    def revalidate(self, tags: Iterable[str] | None = None) -> RevalidateResult:
        return self.use_cases[CatalogUseCaseEnum.revalidate].exec(tags)
