"""One admin operation, one class. ``admin`` owns no data of its own -- these are thin wrappers
over ports two other modules define, which is what keeps ``presentation/admin_api.py`` from
calling a repository directly.

Nothing here names a session, a query, ``HTTPException`` or a status code -- the same discipline
``catalog``'s and ``quotes``' use cases keep.
"""

from collections.abc import Iterable

from app.core.application.use_cases import BaseUseCase, GetByIdUseCase, PaginateUseCase
from app.modules.admin.application.dtos import QuoteDetailOutput, QuotePageOutput
from app.modules.catalog.application.services import CatalogService
from app.modules.catalog.domain.interfaces import RevalidateResult
from app.modules.quotes.domain.exceptions import QuoteNotFoundError
from app.modules.quotes.domain.filters import QuoteFilter
from app.modules.quotes.domain.models import Quote


class ListQuotesUseCase(PaginateUseCase):
    """Newest first, which is the only order a lead list is ever read in -- ``QuoteFilter``'s own
    default, unchanged by this stage.

    ``exec`` is overridden rather than only ``get_output``, for the reason ``QuotePageOutput``
    exists: the envelope is ``admin``'s own paginated shape, not core's generic one, and only
    ``exec`` decides which gets built.
    """

    def exec(self, filters: QuoteFilter) -> QuotePageOutput:
        filters = self.pre_run(filters=filters)
        self.validate(filters=filters)
        total, entities = self.run(filters=filters)
        entities = self.post_run(filters=filters, entities=entities)
        return QuotePageOutput(
            items=self.get_output(entities),
            total=total,
            limit=filters.limit,
            offset=filters.offset,
        )


class GetQuoteUseCase(GetByIdUseCase):
    """One lead by its public reference -- the number a customer quotes back over the phone.

    ``exec`` is overridden rather than a hook because the identifier really is different: refs are
    this module's public identifiers and the integer key is never in this port's vocabulary -- the
    same reason ``catalog``'s ``GetPlatformUseCase`` overrides its own ``exec`` for a slug. ``run``
    goes through ``by_ref``, the repository's own dedicated lookup, rather than a filter this use
    case would otherwise rebuild.
    """

    def get_output(self, entity: Quote) -> QuoteDetailOutput:
        return self.mapper.to_detail(entity)

    def run(self, filters: QuoteFilter) -> Quote:
        quote = self.repository.by_ref(filters.ref_eq)
        if quote is None:
            raise QuoteNotFoundError(filters.ref_eq)
        return quote

    def exec(self, ref: str) -> QuoteDetailOutput:
        filters = self.filter_class(ref_eq=ref)
        filters = self.pre_run(filters=filters)
        self.validate(filters=filters)
        quote = self.run(filters=filters)
        quote = self.post_run(filters=filters, entity=quote)
        return self.get_output(quote)


class RevalidateCatalogUseCase(BaseUseCase):
    """Bust the web app's catalog cache by hand, delegating to the ``RevalidateCatalogUseCase``
    ``catalog`` already owns (Stage 10) through its facade.

    ``admin`` triggers a revalidation on an operator's say-so; it does not own the decision about
    what "everything the catalog touches" means, which is why this holds a ``CatalogService``
    rather than a repository and an invalidator of its own.
    """

    def __init__(self, *args, catalog: CatalogService | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.catalog = catalog

    def pre_run(self, tags: Iterable[str] | None) -> Iterable[str] | None:
        return tags

    def validate(self, tags: Iterable[str] | None) -> None:
        pass

    def run(self, tags: Iterable[str] | None) -> RevalidateResult:
        return self.catalog.revalidate(tags)

    def post_run(self, tags: Iterable[str] | None, result: RevalidateResult) -> RevalidateResult:
        return result

    def exec(self, tags: Iterable[str] | None = None) -> RevalidateResult:
        tags = self.pre_run(tags)
        self.validate(tags)
        result = self.run(tags)
        return self.post_run(tags, result)
