"""FastAPI application entrypoint: the composition root, and nothing else.

Which modules exist and in what order they are mounted is the one thing about this app that is
not generic, so it is all that is left here. Everything else -- CORS, the exception handlers,
telemetry -- is stated once in ``app/core/presentation/app.py``.

``app.main:app`` is named by ``vercel.json``, the Dockerfile and ``docker compose``; the path
does not move.
"""

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.presentation.app import create_app
from app.modules.admin import router as admin_router
from app.modules.catalog import router as catalog_router
from app.modules.quotes import router as quotes_router

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
