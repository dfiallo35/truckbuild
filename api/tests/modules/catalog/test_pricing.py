"""price_build is exercised against the shared fixtures/pricing-cases.json so the Python and
TypeScript mirrors cannot silently drift. See .claude/skills/pricing-mirror.

Since Stage 10 it takes the catalog's own ``Platform`` -- built here straight from the seed YAML,
with no database anywhere near it, which is what "the domain imports no ORM" buys.
"""

import pytest

from app.modules.catalog.domain.models import Option, OptionGroup, Platform
from app.modules.catalog.domain.pricing import price_build
from tests.conftest import platform_by_slug


def _platform(catalog_yaml: dict, slug: str) -> Platform:
    platform = platform_by_slug(catalog_yaml, slug)
    return Platform(
        slug=platform["slug"],
        name=platform["name"],
        purpose=platform["purpose"],
        chassis_basis=platform["chassis_basis"],
        base_price_cents=platform["base_price_cents"],
        option_groups=[
            OptionGroup(
                slug=group["slug"],
                name=group["name"],
                selection_mode=group["selection_mode"],
                required=group["required"],
                display_style=group["display_style"],
                options=[
                    Option(
                        slug=option["slug"],
                        name=option["name"],
                        price_delta_cents=option["price_delta_cents"],
                    )
                    for option in group["options"]
                ],
            )
            for group in platform["option_groups"]
        ],
    )


def _priceable(slug: str, base_price_cents: int, options: list[Option]) -> Platform:
    """A one-group platform, for the cases that are about the arithmetic rather than the
    catalog."""
    return Platform(
        slug=slug,
        name=slug,
        purpose="test",
        chassis_basis="test",
        base_price_cents=base_price_cents,
        option_groups=[
            OptionGroup(
                slug="g",
                name="Group",
                selection_mode="multi",
                display_style="card",
                options=options,
            )
        ],
    )


def _priceable_cases(pricing_cases: list[dict]) -> list[dict]:
    return [case for case in pricing_cases if case["expected_total_cents"] is not None]


def test_pricing_fixture_cases(catalog_yaml: dict, pricing_cases: list[dict]) -> None:
    cases = _priceable_cases(pricing_cases)
    assert cases, "expected at least one priceable fixture case"
    for case in cases:
        platform = _platform(catalog_yaml, case["platform"])
        breakdown = price_build(platform, case["selected"])
        assert breakdown.total_cents == case["expected_total_cents"], case["name"]


def test_price_build_base_price_with_no_options() -> None:
    platform = _priceable("p", 100_00, [])
    breakdown = price_build(platform, [])
    assert breakdown.total_cents == 100_00
    assert breakdown.option_deltas == {}


def test_price_build_sums_selected_option_deltas() -> None:
    platform = _priceable(
        "p",
        100_00,
        [
            Option(slug="a", name="A", price_delta_cents=10_00),
            Option(slug="b", name="B", price_delta_cents=20_00),
        ],
    )
    breakdown = price_build(platform, ["a", "b"])
    assert breakdown.total_cents == 130_00
    assert breakdown.option_deltas == {"a": 10_00, "b": 20_00}


def test_price_build_ignores_unselected_options() -> None:
    platform = _priceable(
        "p",
        100_00,
        [
            Option(slug="a", name="A", price_delta_cents=10_00),
            Option(slug="b", name="B", price_delta_cents=20_00),
        ],
    )
    breakdown = price_build(platform, ["a"])
    assert breakdown.total_cents == 110_00
    assert breakdown.option_deltas == {"a": 10_00}


def test_price_build_rejects_unknown_option_slug() -> None:
    platform = _priceable("p", 100_00, [])
    with pytest.raises(ValueError, match="not-a-real-option"):
        price_build(platform, ["not-a-real-option"])
