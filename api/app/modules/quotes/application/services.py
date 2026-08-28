"""The quotes module's facade: what its own router and ``admin`` are allowed to see of it.

``BaseService`` builds the seven standard CRUD use cases; ``init_use_cases`` swaps the create
shape for ``SubmitQuoteUseCase`` and adds the enquiry, which the standard set has no name for.
The update, batch-update and delete shapes stay registered and stay unreachable -- a submitted
lead is a record of what was offered on a date, never edited.
"""

from app.core.application.services import BaseService
from app.core.application.use_cases import BaseUseCase
from app.core.domain.enums import UseCaseEnum
from app.core.domain.interfaces import IRateLimiter
from app.modules.catalog.domain.interfaces import IPlatformRepository
from app.modules.quotes.application.dtos import (
    EnquiryCreateRequest,
    QuoteCreateRequest,
    QuoteDetailOutput,
)
from app.modules.quotes.application.mappers import QuoteMapper
from app.modules.quotes.application.use_cases import (
    SubmitEnquiryUseCase,
    SubmitQuoteUseCase,
)
from app.modules.quotes.domain.enums import QuoteUseCaseEnum
from app.modules.quotes.domain.exceptions import QuoteNotFoundError
from app.modules.quotes.domain.filters import QuoteFilter
from app.modules.quotes.domain.interfaces import IQuoteRepository
from app.modules.quotes.domain.spam import DEFAULT_MIN_ELAPSED_MS


class QuoteService(BaseService):
    mapper = QuoteMapper()
    filter_class = QuoteFilter

    def __init__(
        self,
        repository: IQuoteRepository | None = None,
        platforms: IPlatformRepository | None = None,
        limiter: IRateLimiter | None = None,
        min_submit_ms: int = DEFAULT_MIN_ELAPSED_MS,
    ) -> None:
        super().__init__(
            repository=repository,
            platforms=platforms,
            limiter=limiter,
            min_submit_ms=min_submit_ms,
        )

    def init_use_cases(self, deps: dict) -> dict[UseCaseEnum | QuoteUseCaseEnum, BaseUseCase]:
        use_cases = super().init_use_cases(deps)
        use_cases[UseCaseEnum.create] = SubmitQuoteUseCase(**deps)
        use_cases[QuoteUseCaseEnum.submit_enquiry] = SubmitEnquiryUseCase(**deps)
        return use_cases

    def submit_quote(
        self, create_request: QuoteCreateRequest, source_ip: str = ""
    ) -> QuoteDetailOutput:
        return self.use_cases[UseCaseEnum.create].exec(create_request, source_ip)

    def submit_enquiry(
        self, create_request: EnquiryCreateRequest, source_ip: str = ""
    ) -> QuoteDetailOutput:
        return self.use_cases[QuoteUseCaseEnum.submit_enquiry].exec(create_request, source_ip)

    def get_by_ref(self, ref: str) -> QuoteDetailOutput:
        """One lead by its public reference, or a 404 -- never ``None``.

        Returning ``None`` for "not found" pushes the decision to every caller, and one of them
        eventually forgets and serializes it as ``null`` with a 200.
        """
        quote = self.repository.by_ref(ref)
        if quote is None:
            raise QuoteNotFoundError(ref)
        return self.mapper.to_api(quote)
