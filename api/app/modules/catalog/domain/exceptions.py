"""Errors the catalog raises when it cannot answer.

Raised from ``application``, rendered by the handler ``core/presentation/errors.py`` installs.
Nothing in this module names ``HTTPException``: the status and the machine-readable code ride on
the exception, and the decision to express them over HTTP is made at the edge.
"""

from app.core.domain.exceptions import NotFoundError


class PlatformNotFoundError(NotFoundError):
    """No platform with that slug.

    ``unknown_platform`` rather than the inherited ``not_found`` so the web app can tell "this
    build URL names a platform that no longer exists" apart from "that route does not exist" --
    and so a 404 from ``GET /v1/platforms/{slug}`` carries the same code as the one
    ``POST /v1/quotes`` already answers with for the same cause.
    """

    code = "unknown_platform"

    def __init__(self, slug: str) -> None:
        super().__init__(f"no platform with slug {slug!r}")
