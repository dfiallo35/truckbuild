"""How the catalog's pieces are assembled for a request: session -> repository -> service.

**The module's composition root, and deliberately outside its four layers** -- for the same
reason ``core/config.py`` is outside the kernel's. Every layer contract in ``pyproject.toml`` says
that adapters and inner layers may not see each other; this file has to see both, because
``application`` names ``IPlatformRepository`` and ``ICacheInvalidator`` and something has to know
which adapters fill them. A file that is the exception to a rule does not belong inside the thing
the rule is about.

``app/main.py`` binds the ports ``quotes`` and ``admin`` declare to the two providers below, which
is how another module consumes the catalog without naming its adapters (the facade rule,
CLAUDE.md).
"""

from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.core.infrastructure.postgres.database import get_session
from app.modules.catalog.application.services import CatalogService
from app.modules.catalog.domain.interfaces import ICacheInvalidator, IPlatformRepository
from app.modules.catalog.infrastructure.postgres.repositories import PlatformRepositoryPostgres
from app.modules.catalog.infrastructure.webhook.revalidate import WebhookCacheInvalidator

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_platform_repository(session: SessionDep) -> IPlatformRepository:
    return PlatformRepositoryPostgres(session)


def get_cache_invalidator(settings: SettingsDep) -> ICacheInvalidator:
    return WebhookCacheInvalidator(settings)


PlatformRepositoryDep = Annotated[IPlatformRepository, Depends(get_platform_repository)]
CacheInvalidatorDep = Annotated[ICacheInvalidator, Depends(get_cache_invalidator)]


def get_catalog_service(
    repository: PlatformRepositoryDep, invalidator: CacheInvalidatorDep
) -> CatalogService:
    return CatalogService(repository=repository, invalidator=invalidator)


CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]
