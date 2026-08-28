"""Cache revalidation: tells the web app to drop the cache tags a catalog change touched.

The one adapter behind ``ICacheInvalidator``. It lives in ``catalog`` rather than in ``core``
because the tags it carries name platforms and the catalog, which is one module's vocabulary --
``core`` holds what more than one module needs or what names no module at all.

Marketing pages render from ``use cache`` entries tagged ``catalog`` and ``platform-<slug>``
rather than from a live call to this API -- that is what keeps them prerendered and keeps a slow
API off the critical path (see docs/decisions.md). Those entries outlive a catalog edit by hours
unless something busts them, so this module is the seam that turns a database write into a
changed public page.

Unlike mail, a failure here is not benign. A lead the mailer drops is still recoverable from its
row in Postgres; a revalidation that quietly did not happen leaves a wrong price on a public page
and nothing downstream ever notices. So this never raises, but every failure is logged at ERROR
with the URL it tried, and the result says plainly whether the tags were dropped.

Sync rather than async like the mailer, because the caller that matters is ``python -m app.seed``
-- a plain script with no event loop. FastAPI runs the admin trigger in a threadpool.
"""

import logging
from collections.abc import Iterable

import httpx

from app.core.config import Settings
from app.modules.catalog.domain.interfaces import ICacheInvalidator, RevalidateResult

logger = logging.getLogger(__name__)

REVALIDATE_PATH = "/api/revalidate"
TIMEOUT_SECONDS = 10.0


def revalidate(tags: Iterable[str], settings: Settings) -> RevalidateResult:
    """POST the tags to the web app's revalidation route. Never raises."""
    tags = tuple(dict.fromkeys(tags))
    if not tags:
        return RevalidateResult(ok=True, tags=(), detail="nothing to revalidate")

    url = f"{settings.web_base_url.rstrip('/')}{REVALIDATE_PATH}"
    try:
        response = httpx.post(
            url,
            json={"tags": list(tags)},
            headers={"Authorization": f"Bearer {settings.revalidate_secret}"},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # A 401 here means the two REVALIDATE_SECRET values have drifted apart. Say so, because
        # the symptom otherwise is only "the site shows the old price" days later.
        hint = (
            " (do the REVALIDATE_SECRET values match?)" if exc.response.status_code == 401 else ""
        )
        detail = f"{url} answered {exc.response.status_code}{hint}"
        logger.error("cache revalidation failed for %s: %s", ", ".join(tags), detail)
        return RevalidateResult(ok=False, tags=tags, detail=detail)
    except Exception as exc:
        detail = f"could not reach {url}: {exc!r}"
        logger.error("cache revalidation failed for %s: %s", ", ".join(tags), detail)
        return RevalidateResult(ok=False, tags=tags, detail=detail)

    logger.info("revalidated cache tags: %s", ", ".join(tags))
    return RevalidateResult(ok=True, tags=tags, detail=f"{url} accepted {len(tags)} tag(s)")


class WebhookCacheInvalidator(ICacheInvalidator):
    """``ICacheInvalidator`` over the function above.

    The port is what ``RevalidateCatalogUseCase`` and ``admin`` depend on; this is the one thing
    that knows the cache is a Next.js app reached over HTTP with a shared secret. Swapping it for
    a CDN purge is a new class here and nothing else.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def invalidate(self, tags: Iterable[str]) -> RevalidateResult:
        return revalidate(tags, self.settings)
