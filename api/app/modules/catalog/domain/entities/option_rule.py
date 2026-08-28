from sqlmodel import Field, UniqueConstraint

from app.core.infrastructure.postgres.tables import BaseTable
from app.modules.catalog.domain.enums import RuleRelation


class OptionRule(BaseTable, table=True):
    """A compatibility relation between two options: ``subject`` requires or excludes
    ``object``. See docs/domain-model.md for the rules the seed catalog must exercise."""

    __table_args__ = (
        UniqueConstraint(
            "subject_option_id", "relation", "object_option_id", name="uq_option_rule"
        ),
    )

    subject_option_id: int = Field(foreign_key="option.id", index=True)
    relation: RuleRelation
    object_option_id: int = Field(foreign_key="option.id", index=True)
