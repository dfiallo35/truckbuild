"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers.catalog import router as catalog_router

settings = get_settings()

app = FastAPI(
    title="TruckBuild API",
    version="0.1.0",
    description="Catalog, configurator pricing, and quote submission for TruckBuild.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(catalog_router)


@app.get("/healthz", tags=["meta"])
async def healthz() -> dict[str, str]:
    """Liveness probe used by Docker Compose and the Fly.io health check."""
    return {"status": "ok", "environment": settings.environment}
