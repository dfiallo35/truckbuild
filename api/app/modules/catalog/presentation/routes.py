"""The catalog module's router, as ``app/main.py`` mounts it.

Separate from ``catalog_api.py`` so that the prefix and the tag -- facts about where this module
sits in one particular application rather than about the endpoints themselves -- are stated once,
in one place, and so the handlers stay plain functions.

Registered rather than decorated, and on *this* router rather than an inner one: FastAPI keeps an
included router nested, so ``request.scope["route"].path`` is the path of the router that owns the
route. A handler decorated on a prefix-less inner router would be logged as ``/platforms/{slug}``
while being served at ``/v1/platforms/{slug}``.

Route order is preserved because route order is what the OpenAPI document is generated from, and a
reordered document is a diff for every reader of it.
"""

from fastapi import APIRouter

from app.modules.catalog.presentation.catalog_api import get_catalog, get_platform

router = APIRouter(prefix="/v1", tags=["catalog"])

router.add_api_route("/catalog", get_catalog, methods=["GET"], response_model=None)
router.add_api_route("/platforms/{slug}", get_platform, methods=["GET"], response_model=None)
