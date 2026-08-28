"""The admin module's router, as ``app/main.py`` mounts it.

Separate from ``admin_api.py`` for the reasons ``catalog``'s and ``quotes``' own ``routes.py``
give: the prefix, the tag and the ``require_admin`` guard are facts about where this module sits
in one particular application rather than about the endpoints themselves, and registering rather
than decorating keeps the routed template a request is logged under equal to the path a reader
sees.

Route order is preserved because route order is what the OpenAPI document is generated from, and
a reordered document is a diff for every reader of it.
"""

from fastapi import APIRouter, Depends

from app.modules.admin.presentation.admin_api import get_quote, list_quotes, trigger_revalidate
from app.modules.admin.presentation.dependencies import require_admin

router = APIRouter(prefix="/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])

router.add_api_route("/quotes", list_quotes, methods=["GET"], response_model=None)
router.add_api_route("/quotes/{ref}", get_quote, methods=["GET"], response_model=None)
router.add_api_route("/revalidate", trigger_revalidate, methods=["POST"], response_model=None)
