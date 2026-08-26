"""Option compatibility rules. Pure: no ``fastapi`` or ``sqlmodel`` imports.

This purity is what lets the function be tested without a database and mirrored in
``web/src/lib/rules.ts`` for instant client-side feedback.
"""

from dataclasses import dataclass, field
from typing import Literal

RuleRelation = Literal["requires", "excludes"]


@dataclass(frozen=True)
class OptionRule:
    subject: str
    relation: RuleRelation
    object: str


@dataclass(frozen=True)
class RuleablePlatform:
    slug: str
    rules: list[OptionRule] = field(default_factory=list)


@dataclass(frozen=True)
class RuleViolation:
    kind: RuleRelation
    option: str
    needs: str | None = None
    conflicts_with: str | None = None


def validate_selection(
    platform: RuleablePlatform, selected_option_slugs: list[str]
) -> list[RuleViolation]:
    """Return every rule violated by the selection.

    A ``requires`` rule fires when its subject is selected without its object. An ``excludes``
    rule fires when both its subject and object are selected -- which side is named "subject" in
    the data does not matter, since the check is symmetric on selection membership.
    """
    selected = set(selected_option_slugs)
    violations: list[RuleViolation] = []
    for rule in platform.rules:
        if rule.subject not in selected:
            continue
        if rule.relation == "requires" and rule.object not in selected:
            violations.append(
                RuleViolation(kind="requires", option=rule.subject, needs=rule.object)
            )
        elif rule.relation == "excludes" and rule.object in selected:
            violations.append(
                RuleViolation(kind="excludes", option=rule.subject, conflicts_with=rule.object)
            )
    return violations
