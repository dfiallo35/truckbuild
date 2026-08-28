"""validate_selection is exercised against the shared fixtures/pricing-cases.json, and against
every requires/excludes rule in the seed catalog, both satisfied and violated. See
.claude/skills/pricing-mirror."""

from app.modules.catalog.domain.rules import (
    OptionRule,
    RuleablePlatform,
    RuleViolation,
    validate_selection,
)
from tests.conftest import rules_for_platform


def _rules_platform(catalog_yaml: dict, slug: str) -> RuleablePlatform:
    rules = [
        OptionRule(subject=rule["subject"], relation=rule["relation"], object=rule["object"])
        for rule in rules_for_platform(catalog_yaml, slug)
    ]
    return RuleablePlatform(slug=slug, rules=rules)


def _violation_matches(violation: RuleViolation, expected: dict) -> bool:
    if violation.kind != expected["kind"] or violation.option != expected["option"]:
        return False
    if expected["kind"] == "requires":
        return violation.needs == expected["needs"]
    return violation.conflicts_with == expected["conflicts_with"]


def test_rules_fixture_cases(catalog_yaml: dict, pricing_cases: list[dict]) -> None:
    for case in pricing_cases:
        platform = _rules_platform(catalog_yaml, case["platform"])
        violations = validate_selection(platform, case["selected"])
        assert len(violations) == len(case["expected_violations"]), case["name"]
        for violation, expected in zip(violations, case["expected_violations"], strict=True):
            assert _violation_matches(violation, expected), case["name"]


def test_winch_requires_heavy_bumper_violation() -> None:
    platform = RuleablePlatform(
        slug="p",
        rules=[OptionRule(subject="winch", relation="requires", object="bumper-heavy")],
    )
    violations = validate_selection(platform, ["winch"])
    assert violations == [RuleViolation(kind="requires", option="winch", needs="bumper-heavy")]


def test_winch_requires_heavy_bumper_satisfied() -> None:
    platform = RuleablePlatform(
        slug="p",
        rules=[OptionRule(subject="winch", relation="requires", object="bumper-heavy")],
    )
    assert validate_selection(platform, ["winch", "bumper-heavy"]) == []


def test_requires_rule_does_not_fire_when_subject_unselected() -> None:
    platform = RuleablePlatform(
        slug="p",
        rules=[OptionRule(subject="winch", relation="requires", object="bumper-heavy")],
    )
    assert validate_selection(platform, ["bumper-heavy"]) == []


def test_lithium_excludes_compact_galley_violation() -> None:
    platform = RuleablePlatform(
        slug="p",
        rules=[OptionRule(subject="lithium-600ah", relation="excludes", object="galley-compact")],
    )
    violations = validate_selection(platform, ["lithium-600ah", "galley-compact"])
    assert violations == [
        RuleViolation(kind="excludes", option="lithium-600ah", conflicts_with="galley-compact")
    ]


def test_lithium_excludes_compact_galley_satisfied() -> None:
    platform = RuleablePlatform(
        slug="p",
        rules=[OptionRule(subject="lithium-600ah", relation="excludes", object="galley-compact")],
    )
    assert validate_selection(platform, ["lithium-600ah", "galley-full"]) == []


def test_no_rules_no_violations() -> None:
    platform = RuleablePlatform(slug="p", rules=[])
    assert validate_selection(platform, ["anything"]) == []
