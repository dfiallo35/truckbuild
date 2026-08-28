"""The quotes module's router, as ``app/main.py`` mounts it.

Separate from ``quotes_api.py`` for the reasons ``catalog``'s ``routes.py`` gives: the prefix and
the tag are facts about where this module sits in one particular application rather than about
the endpoints themselves, and registering rather than decorating keeps the routed template a
request is logged under equal to the path a reader sees.

Route order is preserved because route order is what the OpenAPI document is generated from, and
a reordered document is a diff for every reader of it.
"""

from fastapi import APIRouter

from app.modules.quotes.presentation.quotes_api import create_enquiry, create_quote

router = APIRouter(prefix="/v1", tags=["quotes"])

router.add_api_route(
    "/quotes", create_quote, methods=["POST"], status_code=201, response_model=None
)
router.add_api_route(
    "/enquiries", create_enquiry, methods=["POST"], status_code=201, response_model=None
)
