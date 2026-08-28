"""Read-only catalog endpoints. Three things happen here and nothing else: HTTP caching, the
call into the service, and turning a domain error into a status code.

Every query, every mapping and the 60-line serializer that used to live here left in Stage 10 --
see ``infrastructure/postgres/repositories.py`` and ``application/mappers.py``. What stayed is
what is genuinely about HTTP: the ETag, the ``Cache-Control`` window, and the conditional 304.

The handlers are plain functions; ``routes.py`` mounts them. That keeps the prefix out of this
file, and it keeps the routed template a request is logged under (``/v1/platforms/{slug}``, see
``core/presentation/telemetry.py``) equal to the path a reader sees, which a router nested inside
another router would not.

The catalog is small enough that one nested round trip per platform (or for the whole catalog)
costs less than splitting it across many endpoints.
"""

import hashlib
import json
from typing import Annotated

from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.modules.catalog.application.services import CatalogService


def get_catalog_service() -> CatalogService:  # pragma: no cover - bound in app/main.py
    """The service this module answers with, bound at the composition root.

    Declared here and filled in ``app/main.py`` from ``app/modules/catalog/dependencies.py``, the
    same way ``quotes`` and ``admin`` get their catalog ports. A router reaching for the
    repository and the invalidator itself would be ``presentation`` importing ``infrastructure``,
    and the two adapters are siblings that cannot see each other -- assembling them is somebody
    else's job, and this is how a module says which somebody.
    """
    raise NotImplementedError("get_catalog_service is bound at the composition root in app/main.py")


CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]

# Catalog content changes infrequently and is revalidated by the web app's cache tags (see
# docs/decisions.md), so a short browser/CDN cache window plus stale-while-revalidate is enough.
CACHE_CONTROL = "public, max-age=60, stale-while-revalidate=300"


def _etag_for(payload: BaseModel) -> str:
    digest = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
    return f'W/"{digest[:32]}"'


def _cached_response(request: Request, payload: BaseModel) -> Response:
    etag = _etag_for(payload)
    headers = {"ETag": etag, "Cache-Control": CACHE_CONTROL}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return JSONResponse(content=json.loads(payload.model_dump_json()), headers=headers)


def get_catalog(request: Request, service: CatalogServiceDep) -> Response:
    return _cached_response(request, service.get_catalog())


def get_platform(slug: str, request: Request, service: CatalogServiceDep) -> Response:
    """A missing platform raises ``PlatformNotFoundError`` from the use case, which
    ``core/presentation/errors.py`` renders as a 404 in this API's one error body. No
    ``HTTPException`` is raised here: the status and the machine-readable code ride on the domain
    error, and this layer only decides that they are expressed over HTTP."""
    return _cached_response(request, service.get_platform(slug))
