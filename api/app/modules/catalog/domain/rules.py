"""Option compatibility rules. Pure: no ``fastapi``, ``sqlmodel`` or ``sqlalchemy`` imports.

This purity is what lets the function be tested without a database and mirrored in
``web/src/lib/rules.ts`` for instant client-side feedback.

Since Stage 10 it takes the catalog's own ``Platform`` and its own ``OptionRule`` rather than the
``RuleablePlatform`` shim and a second ``OptionRule`` declared here. Both existed only because
entities used to be ORM rows; ``Platform.rules`` now carries the real thing, keyed by slug on both
sides of the mirror.
"""

from dataclasses import dataclass

from app.modules.catalog.domain.enums import RuleRelation
from app.modules.catalog.domain.models import Platform


@dataclass(frozen=True)
class RuleViolation:
    kind: RuleRelation
    option: str
    needs: str | None = None
    conflicts_with: str | None = None


def validate_selection(platform: Platform, selected_option_slugs: list[str]) -> list[RuleViolation]:
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
        if rule.relation == RuleRelation.requires and rule.object not in selected:
            violations.append(
                RuleViolation(kind=RuleRelation.requires, option=rule.subject, needs=rule.object)
            )
        elif rule.relation == RuleRelation.excludes and rule.object in selected:
            violations.append(
                RuleViolation(
                    kind=RuleRelation.excludes,
                    option=rule.subject,
                    conflicts_with=rule.object,
                )
            )
    return violations
