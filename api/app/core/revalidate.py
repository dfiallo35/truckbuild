"""Cache revalidation: tells the web app to drop the cache tags a catalog change touched.

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
from dataclasses import dataclass

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

REVALIDATE_PATH = "/api/revalidate"
TIMEOUT_SECONDS = 10.0

CATALOG_TAG = "catalog"


def platform_tag(slug: str) -> str:
    return f"platform-{slug}"


def tags_for_platforms(slugs: Iterable[str]) -> list[str]:
    """Both tiers, because the two are not interchangeable.

    ``platform-<slug>`` covers that platform's detail page and configurator; ``catalog`` covers
    everything that lists or spans platforms -- home, /builds, the purpose pages, the sitemap. A
    repriced option changes both a detail page and the "from $X" on a listing, so a change to one
    platform still has to take ``catalog`` with it.
    """
    return [CATALOG_TAG, *sorted({platform_tag(slug) for slug in slugs})]


@dataclass(frozen=True)
class RevalidateResult:
    ok: bool
    tags: tuple[str, ...]
    detail: str


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
