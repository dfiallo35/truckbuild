"""Staff-only endpoints: read submitted leads, and push a cache revalidation by hand.

**Auth is a single bearer token, deliberately.** ``ADMIN_TOKEN`` is shared by the two or three
people who read leads, which is honest for that number and no more. It is an accepted risk
recorded in docs/decisions.md, not an oversight, and the upgrade path is real user accounts --
sessions, per-person tokens, an audit trail of who read what -- the moment more than a couple of
people need access, or the moment anything here can *write*. Everything below is read-only apart
from the revalidation trigger, which busts a cache and nothing more.

The endpoints are unlisted rather than secret: the guard is on the router, so a route added here
is guarded by construction rather than by the author remembering to add a dependency.
"""

import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, or_
from sqlmodel import Session, col, select

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.revalidate import revalidate, tags_for_platforms
from app.modules.admin.presentation.schemas import (
    QuotePage,
    QuoteSummary,
    RevalidateIn,
    RevalidateOut,
)
from app.modules.catalog.domain.entities import Platform
from app.modules.quotes.domain.entities import Quote, QuoteLine
from app.modules.quotes.domain.enums import QuoteKind
from app.modules.quotes.presentation.schemas import QuoteDetail

logger = logging.getLogger(__name__)

# ``auto_error=False`` so a missing header lands in the check below and answers in this API's
# error shape, rather than in FastAPI's own.
_bearer = HTTPBearer(auto_error=False, description="ADMIN_TOKEN")

SessionDep = Annotated[Session, Depends(get_session)]
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


router = APIRouter(prefix="/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])

MAX_PAGE_SIZE = 100


def _escape_like(term: str) -> str:
    """``%`` and ``_`` are wildcards to ``ILIKE``; a search for ``100%`` should look for that."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/quotes", response_model=QuotePage)
def list_quotes(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    kind: QuoteKind | None = None,
    platform_slug: str | None = None,
    q: Annotated[str | None, Query(max_length=200, description="ref, name, or email")] = None,
) -> QuotePage:
    """Newest first, which is the only order a lead list is ever read in."""
    conditions = []
    if kind is not None:
        conditions.append(col(Quote.kind) == kind)
    if platform_slug:
        conditions.append(col(Quote.platform_slug) == platform_slug)
    if q:
        term = f"%{_escape_like(q.strip())}%"
        conditions.append(
            or_(
                col(Quote.ref).ilike(term, escape="\\"),
                col(Quote.contact_name).ilike(term, escape="\\"),
                col(Quote.contact_email).ilike(term, escape="\\"),
            )
        )

    total = session.exec(select(func.count()).select_from(Quote).where(*conditions)).one()

    # One count per page rather than per row: a lead list is read constantly and the line count
    # is the only thing on a summary that is not already on the quote row.
    line_counts = dict(
        session.exec(
            select(col(QuoteLine.quote_id), func.count())
            .group_by(col(QuoteLine.quote_id))
            .where(
                col(QuoteLine.quote_id).in_(
                    select(col(Quote.id))
                    .where(*conditions)
                    .order_by(col(Quote.created_at).desc(), col(Quote.id).desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
        ).all()
    )

    rows = session.exec(
        select(Quote)
        .where(*conditions)
        # ``id`` breaks the tie: two leads can share a created_at to the microsecond under a
        # test's clock, and a page boundary that wobbles drops or repeats a lead.
        .order_by(col(Quote.created_at).desc(), col(Quote.id).desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return QuotePage(
        items=[
            QuoteSummary(
                ref=row.ref,
                kind=row.kind,
                created_at=row.created_at,
                contact_name=row.contact_name,
                contact_email=row.contact_email,
                platform_slug=row.platform_slug,
                platform_name=row.platform_name,
                total_cents=row.total_cents,
                line_count=line_counts.get(row.id, 0),
            )
            for row in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/quotes/{ref}", response_model=QuoteDetail)
def get_quote(ref: str, session: SessionDep) -> QuoteDetail:
    """The whole lead by its public reference -- the number the customer quotes on the phone."""
    quote = session.exec(select(Quote).where(col(Quote.ref) == ref)).first()
    if quote is None:
        raise HTTPException(status_code=404, detail=f"no quote with reference {ref!r}")
    return QuoteDetail.from_row(quote)


@router.post("/revalidate", response_model=RevalidateOut)
def trigger_revalidate(
    payload: RevalidateIn, session: SessionDep, settings: SettingsDep
) -> RevalidateOut:
    """Bust the web app's catalog cache by hand.

    ``python -m app.seed`` does this on its own for a catalog it loaded. This exists for the
    edit it cannot see -- a price changed directly in Postgres, a row fixed during an incident --
    where the data is already right and only the cache disagrees. With no tags named it drops
    everything the catalog touches, which is the right default for "I changed something, I am not
    certain what it reaches".
    """
    tags = payload.tags
    if tags is None:
        slugs = session.exec(select(col(Platform.slug))).all()
        tags = tags_for_platforms(slugs)

    result = revalidate(tags, settings)
    if not result.ok:
        # Loudly, and to the operator's face. A revalidation that silently did not happen is a
        # wrong price on a public page that nothing downstream will notice.
        raise HTTPException(status_code=502, detail=f"revalidation failed: {result.detail}")
    return RevalidateOut(ok=True, tags=list(result.tags), detail=result.detail)
