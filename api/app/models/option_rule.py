from sqlmodel import Field, SQLModel, UniqueConstraint

from app.models.enums import RuleRelation


class OptionRule(SQLModel, table=True):
    """A compatibility relation between two options: ``subject`` requires or excludes
    ``object``. See docs/domain-model.md for the rules the seed catalog must exercise."""

    __table_args__ = (
        UniqueConstraint(
            "subject_option_id", "relation", "object_option_id", name="uq_option_rule"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    subject_option_id: int = Field(foreign_key="option.id", index=True)
    relation: RuleRelation
    object_option_id: int = Field(foreign_key="option.id", index=True)
