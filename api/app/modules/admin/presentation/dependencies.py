"""``admin``'s own composition: the guard every route sits behind, the ports this module consumes,
and the use cases built from them.

Three ports, bound to their owning modules' adapters at the composition root in ``app/main.py``:
``admin`` may name another module's ``domain`` and ``application`` and never its adapters (the
facade rule, CLAUDE.md), so it declares what it needs and lets the place that assembles the
application supply it.

Inside ``presentation/`` rather than beside the four layers, unlike ``catalog``'s and ``quotes``'
own module-root ``dependencies.py``: those exist to see an adapter and an inner layer of their
*own* module at once, and ``admin`` has no adapters of its own to see -- what it composes is
entirely ports two other modules already bind. ``admin`` builds no service facade either: three
thin use cases over two other modules' ports do not earn one.
"""

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.modules.admin.application.mappers import AdminQuoteMapper
from app.modules.admin.application.use_cases import (
    GetQuoteUseCase,
    ListQuotesUseCase,
    RevalidateCatalogUseCase,
)
from app.modules.catalog.application.services import CatalogService
from app.modules.catalog.domain.interfaces import ICacheInvalidator, IPlatformRepository
from app.modules.quotes.domain.filters import QuoteFilter
from app.modules.quotes.domain.interfaces import IQuoteRepository

# ``auto_error=False`` so a missing header lands in the check below and answers in this API's
# error shape, rather than in FastAPI's own.
_bearer = HTTPBearer(auto_error=False, description="ADMIN_TOKEN")

SettingsDep = Annotated[Settings, Depends(get_settings)]


def require_admin(
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> None:
    """Reject anything without the bearer token.

    ``compare_digest`` rather than ``==`` so a wrong token takes the same time to reject whatever
    prefix it shares with the real one; the token is long-lived and shared, which is exactly the
    kind that is worth guessing at.
    """
    presented = credentials.credentials if credentials else ""
    if not secrets.compare_digest(presented, settings.admin_token):
        raise HTTPException(
            status_code=401,
            detail="A valid admin bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# The three ports this module consumes, bound to their owning modules' adapters at the composition
# root in ``app/main.py``. ``admin`` may name another module's ``domain`` and ``application`` and
# never its adapters, so it declares what it needs and lets the place that assembles the
# application supply it.
def get_platform_repository() -> IPlatformRepository:  # pragma: no cover - bound in app/main.py
    raise NotImplementedError(
        "get_platform_repository is bound at the composition root in app/main.py"
    )


def get_cache_invalidator() -> ICacheInvalidator:  # pragma: no cover - bound in app/main.py
    raise NotImplementedError(
        "get_cache_invalidator is bound at the composition root in app/main.py"
    )


def get_quote_repository() -> IQuoteRepository:  # pragma: no cover - bound in app/main.py
    raise NotImplementedError(
        "get_quote_repository is bound at the composition root in app/main.py"
    )


QuoteRepositoryDep = Annotated[IQuoteRepository, Depends(get_quote_repository)]
PlatformRepositoryDep = Annotated[IPlatformRepository, Depends(get_platform_repository)]
CacheInvalidatorDep = Annotated[ICacheInvalidator, Depends(get_cache_invalidator)]

_mapper = AdminQuoteMapper()


def get_catalog_service(
    repository: PlatformRepositoryDep,
    invalidator: CacheInvalidatorDep,
) -> CatalogService:
    return CatalogService(repository=repository, invalidator=invalidator)


CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]


def get_list_quotes_use_case(quotes: QuoteRepositoryDep) -> ListQuotesUseCase:
    return ListQuotesUseCase(mapper=_mapper, filter_class=QuoteFilter, repository=quotes)


def get_get_quote_use_case(quotes: QuoteRepositoryDep) -> GetQuoteUseCase:
    return GetQuoteUseCase(mapper=_mapper, filter_class=QuoteFilter, repository=quotes)


def get_revalidate_use_case(catalog: CatalogServiceDep) -> RevalidateCatalogUseCase:
    return RevalidateCatalogUseCase(catalog=catalog)


ListQuotesUseCaseDep = Annotated[ListQuotesUseCase, Depends(get_list_quotes_use_case)]
GetQuoteUseCaseDep = Annotated[GetQuoteUseCase, Depends(get_get_quote_use_case)]
RevalidateUseCaseDep = Annotated[RevalidateCatalogUseCase, Depends(get_revalidate_use_case)]
