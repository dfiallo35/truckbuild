"""Build pricing. Pure: no ``fastapi``, ``sqlmodel`` or ``sqlalchemy`` imports.

This purity is what lets the function be tested without a database and mirrored in
``web/src/lib/pricing.ts`` for instant client-side feedback. The server call (``POST /v1/quotes``)
is the only one that is authoritative -- see docs/decisions.md.

Since Stage 10 it takes the catalog's own ``Platform`` rather than a ``PriceablePlatform`` shim.
The shim existed because entities used to *be* ORM rows that this module was forbidden to import;
with ``domain/models.py`` pure there is nothing left for it to protect. ``Platform.options`` is
the flattened option list the TypeScript mirror reads under the same name, so the two halves
still line up field for field -- see .claude/skills/pricing-mirror.
"""

from dataclasses import dataclass

from app.modules.catalog.domain.models import Platform


@dataclass(frozen=True)
class PriceBreakdown:
    base_price_cents: int
    option_deltas: dict[str, int]
    total_cents: int


def price_build(platform: Platform, selected_option_slugs: list[str]) -> PriceBreakdown:
    """Sum the platform base price and the price delta of every selected option.

    Raises ``ValueError`` if a selected slug does not belong to the platform -- a build referencing
    an option that does not exist is malformed input, not a zero-cost no-op.
    """
    deltas_by_slug = {option.slug: option.price_delta_cents for option in platform.options}
    unknown = [slug for slug in selected_option_slugs if slug not in deltas_by_slug]
    if unknown:
        raise ValueError(
            f"platform {platform.slug!r} has no option(s): {', '.join(sorted(unknown))}"
        )

    option_deltas = {slug: deltas_by_slug[slug] for slug in selected_option_slugs}
    total_cents = platform.base_price_cents + sum(option_deltas.values())
    return PriceBreakdown(
        base_price_cents=platform.base_price_cents,
        option_deltas=option_deltas,
        total_cents=total_cents,
    )
