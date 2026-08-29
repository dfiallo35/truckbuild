"""add build model and option model effect tables

Revision ID: 789a1ecd05b7
Revises: 3c976a24e81e
Create Date: 2026-08-29 14:13:40.805752

Stage 14: two purely additive tables the 3D build view will read from in Stage 16. ``buildmodel``
carries one row per platform (``platform_id`` unique) and ``optionmodeleffect`` at most one row
per option (``option_id`` unique) -- both unique so a botched seed run cannot leave two rows for
the mapper to pick between arbitrarily.

``sa.DateTime(timezone=True)`` rather than the ``UTCDateTime`` the model declares, same as
``3c976a24e81e``: the two render identical DDL, and a migration is frozen SQL that must keep
applying after the application code it was generated from has moved.
"""

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "789a1ecd05b7"
down_revision: str | None = "3c976a24e81e"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "buildmodel",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("platform_id", sa.Integer(), nullable=False),
        sa.Column("url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("content_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("alt_text", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("camera_orbit_deg", sa.Float(), nullable=False),
        sa.Column("camera_distance_m", sa.Float(), nullable=False),
        sa.Column("camera_target_y_m", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["platform_id"], ["platform.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_buildmodel_platform_id"), "buildmodel", ["platform_id"], unique=True)
    op.create_table(
        "optionmodeleffect",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("option_id", sa.Integer(), nullable=False),
        sa.Column("nodes", sa.JSON(), nullable=True),
        sa.Column("material_target", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("base_color_hex", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("metalness", sa.Float(), nullable=True),
        sa.Column("roughness", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["option_id"], ["option.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_optionmodeleffect_option_id"), "optionmodeleffect", ["option_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_optionmodeleffect_option_id"), table_name="optionmodeleffect")
    op.drop_table("optionmodeleffect")
    op.drop_index(op.f("ix_buildmodel_platform_id"), table_name="buildmodel")
    op.drop_table("buildmodel")
