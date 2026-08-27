"""add quote tables

Revision ID: 479594251a94
Revises: 4f1ee330b15e
Create Date: 2026-08-27 13:17:51.372374

"""

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "479594251a94"
down_revision: str | None = "4f1ee330b15e"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "quote",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ref", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("kind", sa.Enum("build", "enquiry", name="quotekind"), nullable=False),
        # Null for a general enquiry, which has contact details but no configured build.
        sa.Column("platform_id", sa.Integer(), nullable=True),
        sa.Column("platform_slug", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("platform_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("base_price_cents", sa.Integer(), nullable=True),
        sa.Column("total_cents", sa.Integer(), nullable=True),
        sa.Column("contact_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("contact_email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("contact_phone", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("intended_use", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("timeline", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("source_ip", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["platform_id"], ["platform.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_quote_created_at"), "quote", ["created_at"], unique=False)
    op.create_index(op.f("ix_quote_platform_id"), "quote", ["platform_id"], unique=False)
    op.create_index(op.f("ix_quote_platform_slug"), "quote", ["platform_slug"], unique=False)
    # ``ref`` is the public identifier the customer is given; two leads sharing one is worse
    # than a failed insert, so uniqueness is enforced here rather than trusted to the generator.
    op.create_index(op.f("ix_quote_ref"), "quote", ["ref"], unique=True)

    op.create_table(
        "quoteline",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quote_id", sa.Integer(), nullable=False),
        sa.Column("option_id", sa.Integer(), nullable=True),
        sa.Column("group_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("option_slug", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("option_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("price_delta_cents", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["option_id"], ["option.id"]),
        sa.ForeignKeyConstraint(["quote_id"], ["quote.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_quoteline_quote_id"), "quoteline", ["quote_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_quoteline_quote_id"), table_name="quoteline")
    op.drop_table("quoteline")

    op.drop_index(op.f("ix_quote_ref"), table_name="quote")
    op.drop_index(op.f("ix_quote_platform_slug"), table_name="quote")
    op.drop_index(op.f("ix_quote_platform_id"), table_name="quote")
    op.drop_index(op.f("ix_quote_created_at"), table_name="quote")
    op.drop_table("quote")
    # ``drop_table`` leaves the enum type behind, and the next upgrade would then fail on a
    # type that already exists.
    sa.Enum(name="quotekind").drop(op.get_bind(), checkfirst=True)
