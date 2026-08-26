"""add catalog tables

Revision ID: 4f1ee330b15e
Revises:
Create Date: 2026-08-26 21:43:10.314568

"""

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4f1ee330b15e"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "platform",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("purpose", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("chassis_basis", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("base_price_cents", sa.Integer(), nullable=False),
        sa.Column("spec_highlights", sa.JSON(), nullable=True),
        sa.Column("standard_equipment", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_platform_slug"), "platform", ["slug"], unique=True)
    op.create_table(
        "optiongroup",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("platform_id", sa.Integer(), nullable=False),
        sa.Column("slug", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "selection_mode", sa.Enum("single", "multi", name="selectionmode"), nullable=False
        ),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column(
            "display_style",
            sa.Enum("card", "swatch", "toggle", name="displaystyle"),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["platform_id"], ["platform.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform_id", "slug", name="uq_option_group_platform_slug"),
    )
    op.create_index(
        op.f("ix_optiongroup_platform_id"), "optiongroup", ["platform_id"], unique=False
    )
    op.create_index(op.f("ix_optiongroup_slug"), "optiongroup", ["slug"], unique=False)
    op.create_table(
        "option",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("slug", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("price_delta_cents", sa.Integer(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["optiongroup.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_option_group_id"), "option", ["group_id"], unique=False)
    op.create_index(op.f("ix_option_slug"), "option", ["slug"], unique=True)
    op.create_table(
        "asset",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("hero", "gallery", "thumbnail", "layer", name="assetkind"),
            nullable=False,
        ),
        sa.Column("url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("alt_text", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("platform_id", sa.Integer(), nullable=True),
        sa.Column("option_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["option_id"], ["option.id"]),
        sa.ForeignKeyConstraint(["platform_id"], ["platform.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_asset_option_id"), "asset", ["option_id"], unique=False)
    op.create_index(op.f("ix_asset_platform_id"), "asset", ["platform_id"], unique=False)
    op.create_table(
        "optionrule",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subject_option_id", sa.Integer(), nullable=False),
        sa.Column("relation", sa.Enum("requires", "excludes", name="rulerelation"), nullable=False),
        sa.Column("object_option_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["object_option_id"], ["option.id"]),
        sa.ForeignKeyConstraint(["subject_option_id"], ["option.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subject_option_id", "relation", "object_option_id", name="uq_option_rule"
        ),
    )
    op.create_index(
        op.f("ix_optionrule_object_option_id"), "optionrule", ["object_option_id"], unique=False
    )
    op.create_index(
        op.f("ix_optionrule_subject_option_id"), "optionrule", ["subject_option_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_optionrule_subject_option_id"), table_name="optionrule")
    op.drop_index(op.f("ix_optionrule_object_option_id"), table_name="optionrule")
    op.drop_table("optionrule")
    sa.Enum(name="rulerelation").drop(op.get_bind(), checkfirst=True)

    op.drop_index(op.f("ix_asset_platform_id"), table_name="asset")
    op.drop_index(op.f("ix_asset_option_id"), table_name="asset")
    op.drop_table("asset")
    sa.Enum(name="assetkind").drop(op.get_bind(), checkfirst=True)

    op.drop_index(op.f("ix_option_slug"), table_name="option")
    op.drop_index(op.f("ix_option_group_id"), table_name="option")
    op.drop_table("option")

    op.drop_index(op.f("ix_optiongroup_slug"), table_name="optiongroup")
    op.drop_index(op.f("ix_optiongroup_platform_id"), table_name="optiongroup")
    op.drop_table("optiongroup")
    sa.Enum(name="displaystyle").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="selectionmode").drop(op.get_bind(), checkfirst=True)

    op.drop_index(op.f("ix_platform_slug"), table_name="platform")
    op.drop_table("platform")
