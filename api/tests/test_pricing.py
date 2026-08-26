"""price_build is exercised against the shared fixtures/pricing-cases.json so the Python and
future TypeScript mirrors cannot silently drift. See .claude/skills/pricing-mirror."""

import pytest

from app.services.pricing import PriceableOption, PriceablePlatform, price_build
from tests.conftest import platform_by_slug


def _pricing_platform(catalog_yaml: dict, slug: str) -> PriceablePlatform:
    platform = platform_by_slug(catalog_yaml, slug)
    options = [
        PriceableOption(slug=option["slug"], price_delta_cents=option["price_delta_cents"])
        for group in platform["option_groups"]
        for option in group["options"]
    ]
    return PriceablePlatform(
        slug=platform["slug"],
        base_price_cents=platform["base_price_cents"],
        options=options,
    )


def _priceable_cases(pricing_cases: list[dict]) -> list[dict]:
    return [case for case in pricing_cases if case["expected_total_cents"] is not None]


def test_pricing_fixture_cases(catalog_yaml: dict, pricing_cases: list[dict]) -> None:
    cases = _priceable_cases(pricing_cases)
    assert cases, "expected at least one priceable fixture case"
    for case in cases:
        platform = _pricing_platform(catalog_yaml, case["platform"])
        breakdown = price_build(platform, case["selected"])
        assert breakdown.total_cents == case["expected_total_cents"], case["name"]


def test_price_build_base_price_with_no_options() -> None:
    platform = PriceablePlatform(slug="p", base_price_cents=100_00, options=[])
    breakdown = price_build(platform, [])
    assert breakdown.total_cents == 100_00
    assert breakdown.option_deltas == {}


def test_price_build_sums_selected_option_deltas() -> None:
    platform = PriceablePlatform(
        slug="p",
        base_price_cents=100_00,
        options=[
            PriceableOption(slug="a", price_delta_cents=10_00),
            PriceableOption(slug="b", price_delta_cents=20_00),
        ],
    )
    breakdown = price_build(platform, ["a", "b"])
    assert breakdown.total_cents == 130_00
    assert breakdown.option_deltas == {"a": 10_00, "b": 20_00}


def test_price_build_ignores_unselected_options() -> None:
    platform = PriceablePlatform(
        slug="p",
        base_price_cents=100_00,
        options=[
            PriceableOption(slug="a", price_delta_cents=10_00),
            PriceableOption(slug="b", price_delta_cents=20_00),
        ],
    )
    breakdown = price_build(platform, ["a"])
    assert breakdown.total_cents == 110_00
    assert breakdown.option_deltas == {"a": 10_00}


def test_price_build_rejects_unknown_option_slug() -> None:
    platform = PriceablePlatform(slug="p", base_price_cents=100_00, options=[])
    with pytest.raises(ValueError, match="not-a-real-option"):
        price_build(platform, ["not-a-real-option"])
