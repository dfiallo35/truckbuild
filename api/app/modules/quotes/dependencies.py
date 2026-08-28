"""How the quotes module's pieces are assembled for a request.

**The module's composition root, and deliberately outside its four layers** -- for the same
reason ``core/config.py`` is outside the kernel's, and ``catalog/dependencies.py`` outside its.
Every layer contract in ``pyproject.toml`` says adapters and inner layers may not see each other;
this file has to see both, because ``application`` names ``IQuoteRepository``, ``IMailer`` and
``IRateLimiter`` and something has to know which adapters fill them.

``app/main.py`` binds the ports declared in ``presentation/quotes_api.py`` and in
``admin/presentation/router.py`` to the providers below.
"""

from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.core.domain.interfaces import IRateLimiter
from app.core.infrastructure.postgres.database import get_session
from app.core.infrastructure.ratelimit import RateLimiter
from app.modules.catalog.domain.interfaces import IPlatformRepository
from app.modules.quotes.application.interfaces import IMailer
from app.modules.quotes.application.services import QuoteService
from app.modules.quotes.domain.interfaces import IQuoteRepository
from app.modules.quotes.infrastructure.mail import ResendMailer
from app.modules.quotes.infrastructure.postgres.repositories import QuoteRepositoryPostgres
from app.modules.quotes.presentation.quotes_api import get_platform_repository

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
PlatformRepositoryDep = Annotated[IPlatformRepository, Depends(get_platform_repository)]

# Process-global on purpose: a limiter that was rebuilt per request would count to one and never
# reach its limit. It is still injected rather than reached for, which is what makes it
# substitutable in a test and what makes moving to a shared counter a change to this file only.
#
# Being per-instance is the known liability docs/decisions.md records: on serverless each running
# copy keeps its own window. The fix is a shared store behind `IRateLimiter`, and that interface
# now exists.
_limiter = RateLimiter(
    limit=get_settings().quote_rate_limit,
    window_seconds=get_settings().quote_rate_limit_window_seconds,
)


def get_rate_limiter() -> IRateLimiter:
    return _limiter


def get_quote_repository(session: SessionDep) -> IQuoteRepository:
    return QuoteRepositoryPostgres(session)


def get_mailer(settings: SettingsDep) -> IMailer:
    return ResendMailer(settings)


QuoteRepositoryDep = Annotated[IQuoteRepository, Depends(get_quote_repository)]
RateLimiterDep = Annotated[IRateLimiter, Depends(get_rate_limiter)]


def get_quote_service(
    repository: QuoteRepositoryDep,
    platforms: PlatformRepositoryDep,
    limiter: RateLimiterDep,
    settings: SettingsDep,
) -> QuoteService:
    return QuoteService(
        repository=repository,
        platforms=platforms,
        limiter=limiter,
        min_submit_ms=settings.quote_min_submit_ms,
    )
