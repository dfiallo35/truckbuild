"""Staff-only endpoints: read submitted leads, and push a cache revalidation by hand.

**Auth is a single bearer token, deliberately.** ``ADMIN_TOKEN`` is shared by the two or three
people who read leads, which is honest for that number and no more. It is an accepted risk
recorded in docs/decisions.md, not an oversight, and the upgrade path is real user accounts --
sessions, per-person tokens, an audit trail of who read what -- the moment more than a couple of
people need access, or the moment anything here can *write*. Everything below is read-only apart
from the revalidation trigger, which busts a cache and nothing more. ``require_admin`` guards the
whole router in ``presentation/routes.py``, so a route added here is guarded by construction
rather than by the author remembering to add a dependency.

Each handler does three things and nothing else: parse the query, call one use case, and render
what comes back. ``admin`` owns no repository of its own -- the query composition, the ordering
policy and the pagination live in ``quotes.infrastructure.postgres.repositories`` (Stage 11); what
this stage changes is what sits between the router and that repository: a use case, not a raw port.
"""

from typing import Annotated

from fastapi import HTTPException, Query

from app.modules.admin.application.dtos import (
    QuoteDetailOutput,
    QuotePageOutput,
    RevalidateOutput,
    RevalidateRequest,
)
from app.modules.admin.presentation.dependencies import (
    GetQuoteUseCaseDep,
    ListQuotesUseCaseDep,
    RevalidateUseCaseDep,
)
from app.modules.admin.presentation.filters import AdminQuoteFilter


def list_quotes(
    filters: Annotated[AdminQuoteFilter, Query()],
    use_case: ListQuotesUseCaseDep,
) -> QuotePageOutput:
    """Newest first, which is the only order a lead list is ever read in.

    ``total`` counts the whole filtered set rather than this page: it is what tells the caller
    whether there is more to fetch, so the window is deliberately dropped from the count.
    """
    return use_case.exec(filters.to_domain())


def get_quote(ref: str, use_case: GetQuoteUseCaseDep) -> QuoteDetailOutput:
    """The whole lead by its public reference -- the number the customer quotes on the phone.

    A missing one raises ``QuoteNotFoundError``, which ``core/presentation/errors.py`` renders as
    a 404 in this API's one error body. No ``HTTPException``: the status and the code ride on the
    domain error.
    """
    return use_case.exec(ref)


def trigger_revalidate(
    payload: RevalidateRequest, use_case: RevalidateUseCaseDep
) -> RevalidateOutput:
    """Bust the web app's catalog cache by hand.

    ``python -m app.seed`` does this on its own for a catalog it loaded. This exists for the
    edit it cannot see -- a price changed directly in Postgres, a row fixed during an incident --
    where the data is already right and only the cache disagrees. With no tags named it drops
    everything the catalog touches, which is the right default for "I changed something, I am not
    certain what it reaches" -- and choosing that default is ``catalog``'s decision, made in its
    own ``RevalidateCatalogUseCase``, not one this router re-derives with a query of its own.
    """
    result = use_case.exec(payload.tags)
    if not result.ok:
        # Loudly, and to the operator's face. A revalidation that silently did not happen is a
        # wrong price on a public page that nothing downstream will notice.
        raise HTTPException(status_code=502, detail=f"revalidation failed: {result.detail}")
    return RevalidateOutput(ok=True, tags=list(result.tags), detail=result.detail)
