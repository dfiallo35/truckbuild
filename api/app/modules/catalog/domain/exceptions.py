"""Errors the catalog raises when it cannot answer.

Raised from ``application``, rendered by the handler ``core/presentation/errors.py`` installs.
Nothing in this module names ``HTTPException``: the status and the machine-readable code ride on
the exception, and the decision to express them over HTTP is made at the edge.
"""

from app.core.domain.exceptions import BaseError, NotFoundError


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


class PlatformHasNoModelError(NotFoundError):
    """A ``<slug>.glb`` file names a platform with no ``model:`` block in ``seed/catalog.yaml`` --
    there is no ``BuildModel`` row for ``python -m app.assets sync`` to write into. Raised before
    anything uploads, the same way a node or material mismatch is."""

    code = "platform_has_no_model"

    def __init__(self, slug: str) -> None:
        super().__init__(f"platform {slug!r} has no model framing in the catalog")


class InvalidModelFileError(BaseError):
    """A ``.glb`` that is not a valid glTF binary -- bad magic, an unsupported version, or a
    corrupt JSON chunk. Refused by ``catalog/infrastructure/glb.py`` before the sync it is part of
    reads anything else about it."""

    status_code = 422
    code = "invalid_model_file"

    def __init__(self, filename: str, reason: str) -> None:
        super().__init__(f"{filename}: {reason}")
        self.filename = filename


class ModelTooLargeError(BaseError):
    """A ``.glb`` over ``Settings.model_max_bytes`` -- refused before it is read, let alone
    uploaded. See Stage 15 of the archived development plan (Notion) for why there is a cap at
    all: a Vercel function caps a request body at 4.5 MB, which is why this is a CLI rather than
    an endpoint, but the sync still needs its own ceiling against a mistakenly huge export."""

    status_code = 422
    code = "model_too_large"

    def __init__(self, filename: str, byte_size: int, max_bytes: int) -> None:
        super().__init__(f"{filename} is {byte_size} bytes, over the {max_bytes} byte cap")
        self.filename = filename


class ModelContentMismatchError(BaseError):
    """An option's ``model_effect`` names a node or material its platform's GLB does not contain
    -- the validation Stage 15 exists for. Refuses the *whole* sync, not just this platform: a
    mismatch here means an option that still prices and still appears in the build sheet does
    nothing on screen, and nothing else would catch it. See
    Stage 15 of the archived development plan (Notion).
    """

    status_code = 422
    code = "model_content_mismatch"

    def __init__(
        self, platform_slug: str, option_slug: str, kind: str, name: str, filename: str
    ) -> None:
        super().__init__(
            f"platform {platform_slug!r}: option {option_slug!r} names {kind} {name!r}, "
            f"which {filename} does not contain"
        )
