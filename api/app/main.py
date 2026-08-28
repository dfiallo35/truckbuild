"""FastAPI application entrypoint: the composition root, and nothing else.

Which modules exist and in what order they are mounted is the one thing about this app that is
not generic, so it is all that is left here. Everything else -- CORS, the exception handlers,
telemetry -- is stated once in ``app/core/presentation/app.py``.

It is also where **every port a module declares is bound to the adapter that fills it**. A router
may not name an adapter: within a module because ``presentation`` and ``infrastructure`` are
sibling layers that cannot see each other, and across modules because of the facade rule
(CLAUDE.md). So each ``presentation`` declares what it needs as a dependency that raises, each
module's ``dependencies.py`` builds the concrete thing, and the two are joined here.

Something has to know how the pieces are assembled; this file is the one thing that is allowed to,
and ``tests/test_composition_root.py`` fails if a declared port is left unbound.

``app.main:app`` is named by ``vercel.json``, the Dockerfile and ``docker compose``; the path
does not move.
"""

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.presentation.app import create_app
from app.modules.admin import router as admin_router
from app.modules.admin.presentation.router import (
    get_cache_invalidator as admin_cache_invalidator_port,
)
from app.modules.admin.presentation.router import (
    get_platform_repository as admin_platform_repository_port,
)
from app.modules.catalog import router as catalog_router
from app.modules.catalog.dependencies import (
    get_cache_invalidator,
    get_catalog_service,
    get_platform_repository,
)
from app.modules.catalog.presentation.catalog_api import (
    get_catalog_service as catalog_service_port,
)
from app.modules.quotes import router as quotes_router
from app.modules.quotes.presentation.router import (
    get_platform_repository as quotes_platform_repository_port,
)

settings = get_settings()

root_router = APIRouter()

root_router.include_router(catalog_router)
root_router.include_router(quotes_router)
root_router.include_router(admin_router)


# Registered after the modules, as it was when it hung off the app directly: route order is what
# OpenAPI is generated from, and a reordered document is a diff for every reader of it.
@root_router.get("/healthz", tags=["meta"])
async def healthz() -> dict[str, str]:
    """Liveness probe used by Docker Compose and the host's health check.

    Also the way to wake a sleeping free-tier instance before a deploy that needs it -- see
    docs/deploy.md."""
    return {"status": "ok", "environment": settings.environment}


app = create_app(
    title="TruckBuild API",
    version="0.1.0",
    description="Catalog, configurator pricing, and quote submission for TruckBuild.",
    router=root_router,
    settings=settings,
)

# The cross-module bindings. Left of the arrow is a port a consuming module declared and cannot
# fill; right of it is the catalog adapter that fills it. `tests/test_composition_root.py` fails
# if a declared port is left unbound, because the symptom otherwise is a 500 on one endpoint.
PORT_BINDINGS = {
    catalog_service_port: get_catalog_service,
    quotes_platform_repository_port: get_platform_repository,
    admin_platform_repository_port: get_platform_repository,
    admin_cache_invalidator_port: get_cache_invalidator,
}

app.dependency_overrides.update(PORT_BINDINGS)
