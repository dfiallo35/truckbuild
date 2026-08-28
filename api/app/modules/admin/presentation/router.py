"""Staff-only endpoints: read submitted leads, and push a cache revalidation by hand.

**Auth is a single bearer token, deliberately.** ``ADMIN_TOKEN`` is shared by the two or three
people who read leads, which is honest for that number and no more. It is an accepted risk
recorded in docs/decisions.md, not an oversight, and the upgrade path is real user accounts --
sessions, per-person tokens, an audit trail of who read what -- the moment more than a couple of
people need access, or the moment anything here can *write*. Everything below is read-only apart
from the revalidation trigger, which busts a cache and nothing more.

The endpoints are unlisted rather than secret: the guard is on the router, so a route added here
is guarded by construction rather than by the author remembering to add a dependency.

``admin`` owns no tables. It reads leads through ``quotes``' repository port and the catalog
through ``catalog``'s, both bound at the composition root -- it may name another module's
``domain`` and ``application`` and never its adapters (the facade rule, CLAUDE.md). Stage 12
gives it use cases and output DTOs of its own; what it has today is a router that composes no
query.
"""

import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.modules.admin.presentation.schemas import (
    QuotePage,
    QuoteSummary,
    RevalidateIn,
    RevalidateOut,
)
from app.modules.catalog.application.services import CatalogService
from app.modules.catalog.domain.interfaces import ICacheInvalidator, IPlatformRepository
from app.modules.quotes.application.dtos import QuoteDetailOutput
from app.modules.quotes.application.mappers import QuoteMapper
from app.modules.quotes.domain.enums import QuoteKind
from app.modules.quotes.domain.exceptions import QuoteNotFoundError
from app.modules.quotes.domain.filters import QuoteFilter
from app.modules.quotes.domain.interfaces import IQuoteRepository

logger = logging.getLogger(__name__)

# ``auto_error=False`` so a missing header lands in the check below and answers in this API's
# error shape, rather than in FastAPI's own.
_bearer = HTTPBearer(auto_error=False, description="ADMIN_TOKEN")

SettingsDep = Annotated[Settings, Depends(get_settings)]

# How a stored lead is read back out. ``quotes``' own mapper, until Stage 12 gives ``admin`` the
# shapes it actually wants: a staff-facing lead view and a customer-facing submission response
# are two audiences whose fields will diverge the first time either changes.
_quotes = QuoteMapper()


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


def get_catalog_service(
    repository: Annotated[IPlatformRepository, Depends(get_platform_repository)],
    invalidator: Annotated[ICacheInvalidator, Depends(get_cache_invalidator)],
) -> CatalogService:
    return CatalogService(repository=repository, invalidator=invalidator)


CatalogDep = Annotated[CatalogService, Depends(get_catalog_service)]
QuotesDep = Annotated[IQuoteRepository, Depends(get_quote_repository)]


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


router = APIRouter(prefix="/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])

# A bound on a query parameter is an HTTP concern and belongs where FastAPI can reject it with a
# 422 before anything else runs.
MAX_PAGE_SIZE = 100


@router.get("/quotes", response_model=QuotePage)
def list_quotes(
    quotes: QuotesDep,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    kind: QuoteKind | None = None,
    platform_slug: str | None = None,
    q: Annotated[str | None, Query(max_length=200, description="ref, name, or email")] = None,
) -> QuotePage:
    """Newest first, which is the only order a lead list is ever read in.

    ``total`` counts the whole filtered set rather than this page: it is what tells the caller
    whether there is more to fetch, so the window is deliberately dropped from the count.
    """
    filters = QuoteFilter(
        limit=limit,
        offset=offset,
        kind_eq=kind,
        platform_slug_eq=platform_slug,
        search=q,
    )
    total = quotes.count(filters)

    return QuotePage(
        items=[
            QuoteSummary(
                ref=quote.ref,
                kind=quote.kind,
                created_at=quote.created_at,
                contact_name=quote.contact_name,
                contact_email=quote.contact_email,
                platform_slug=quote.platform_slug,
                platform_name=quote.platform_name,
                total_cents=quote.total_cents,
                line_count=len(quote.lines),
            )
            for quote in quotes.list(filters)
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/quotes/{ref}", response_model=QuoteDetailOutput)
def get_quote(ref: str, quotes: QuotesDep) -> QuoteDetailOutput:
    """The whole lead by its public reference -- the number the customer quotes on the phone.

    A missing one raises ``QuoteNotFoundError``, which ``core/presentation/errors.py`` renders as
    a 404 in this API's one error body. No ``HTTPException``: the status and the code ride on the
    domain error.
    """
    quote = quotes.by_ref(ref)
    if quote is None:
        raise QuoteNotFoundError(ref)
    return _quotes.to_api(quote)


@router.post("/revalidate", response_model=RevalidateOut)
def trigger_revalidate(payload: RevalidateIn, catalog: CatalogDep) -> RevalidateOut:
    """Bust the web app's catalog cache by hand.

    ``python -m app.seed`` does this on its own for a catalog it loaded. This exists for the
    edit it cannot see -- a price changed directly in Postgres, a row fixed during an incident --
    where the data is already right and only the cache disagrees. With no tags named it drops
    everything the catalog touches, which is the right default for "I changed something, I am not
    certain what it reaches" -- and choosing that default is ``catalog``'s decision, made in
    ``RevalidateCatalogUseCase``, not one this router re-derives with a query of its own.
    """
    result = catalog.revalidate(payload.tags)
    if not result.ok:
        # Loudly, and to the operator's face. A revalidation that silently did not happen is a
        # wrong price on a public page that nothing downstream will notice.
        raise HTTPException(status_code=502, detail=f"revalidation failed: {result.detail}")
    return RevalidateOut(ok=True, tags=list(result.tags), detail=result.detail)
