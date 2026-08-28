"""The cache tags a catalog change invalidates.

Vocabulary, not transport: ``catalog`` and ``platform-<slug>`` are names the web app's
``use cache`` entries are tagged with (see docs/decisions.md), and deciding which of them a change
touches is a catalog decision. The HTTP call that carries them lives in
``infrastructure/webhook/revalidate.py``, and the use case that chooses them can reach this
without reaching an adapter.
"""

from collections.abc import Iterable

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
