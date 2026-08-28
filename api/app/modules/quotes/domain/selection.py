"""Everything that can be wrong with a submitted selection, as facts rather than as a response.

Two passes, and the order between them matters:

- **Structural.** Unknown slugs, duplicates, a single-select group given two choices, a required
  group given none. The configurator cannot produce any of these -- ``web/src/lib/build.ts``
  repairs the URL it reads -- but a hand-rolled POST can, and a build with two cabs and no
  habitat is not a build.
- **Compatibility rules.** ``catalog``'s own ``validate_selection`` over the rules the repository
  loaded onto the platform, with the slugs resolved to the names a person would recognise.

A ``SelectionViolation`` knows nothing about status codes, field names or HTTP. It carries the
machine-readable ``kind`` that reaches the wire and the nouns a sentence about it is built from;
``presentation/quotes_api.py`` writes the sentence. That split is the point: what is wrong with a
build is a fact about the catalog, and the wording a customer reads is not.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.modules.catalog.domain.models import Platform
from app.modules.catalog.domain.rules import validate_selection


class SelectionViolationKind(StrEnum):
    """The structural faults. Rule violations carry ``catalog``'s own ``RuleRelation`` values
    (``requires`` / ``excludes``) instead, which is what the wire has always said."""

    unknown_option = "unknown_option"
    duplicate_option = "duplicate_option"
    too_many_in_group = "too_many_in_group"
    missing_required_group = "missing_required_group"


@dataclass(frozen=True)
class SelectionViolation:
    """One thing wrong with a selection.

    ``subject`` is whatever the violation is *about* -- the platform, the group, or the option --
    and ``options`` the ones at fault. Both are already display names wherever a name exists; an
    unknown slug has none, so it stays a slug.
    """

    kind: str
    subject: str = ""
    options: tuple[str, ...] = ()


def structural_violations(platform: Platform, selected: list[str]) -> list[SelectionViolation]:
    """Everything wrong with a selection before compatibility rules are even consulted."""
    known = {option.slug for option in platform.options}
    violations: list[SelectionViolation] = []

    unknown = sorted({slug for slug in selected if slug not in known})
    if unknown:
        violations.append(
            SelectionViolation(
                kind=SelectionViolationKind.unknown_option,
                subject=platform.name,
                options=tuple(unknown),
            )
        )

    duplicates = sorted({slug for slug in selected if selected.count(slug) > 1})
    if duplicates:
        violations.append(
            SelectionViolation(
                kind=SelectionViolationKind.duplicate_option, options=tuple(duplicates)
            )
        )

    chosen = set(selected)
    for group in platform.option_groups:
        in_group = [option.slug for option in group.options if option.slug in chosen]
        if group.selection_mode == "single" and len(in_group) > 1:
            violations.append(
                SelectionViolation(
                    kind=SelectionViolationKind.too_many_in_group,
                    subject=group.name,
                    options=tuple(in_group),
                )
            )
        if group.required and not in_group:
            violations.append(
                SelectionViolation(
                    kind=SelectionViolationKind.missing_required_group, subject=group.name
                )
            )

    return violations


def rule_violations(platform: Platform, selected: list[str]) -> list[SelectionViolation]:
    """The catalog's compatibility rules, with every slug resolved to its option's name.

    The check itself is ``catalog``'s -- this module owns neither the rules nor the relation
    between two options. What it adds is the resolution from slug to name, because an option's
    name is a fact about the catalog and the router should not have to go looking for one.
    """
    name_of = {option.slug: option.name for option in platform.options}

    violations: list[SelectionViolation] = []
    for violation in validate_selection(platform, selected):
        other = violation.needs or violation.conflicts_with or ""
        violations.append(
            SelectionViolation(
                kind=violation.kind,
                subject=name_of.get(violation.option, violation.option),
                options=(name_of.get(other, other),),
            )
        )
    return violations
