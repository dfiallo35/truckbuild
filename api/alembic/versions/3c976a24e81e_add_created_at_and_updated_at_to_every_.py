"""add created_at and updated_at to every table

Revision ID: 3c976a24e81e
Revises: 479594251a94
Create Date: 2026-08-28 14:35:31.867868

Stage 9 gives every table a ``BaseTable`` carrying ``id``, ``created_at`` and ``updated_at``.
Six tables gain both columns; ``quote`` already had an indexed ``created_at`` -- the column and
its index are left exactly as they are, because the admin lead list orders on that index and
dropping and recreating it buys nothing.

``sa.DateTime(timezone=True)`` rather than the ``UTCDateTime`` the model declares: the two render
identical DDL, and a migration is frozen SQL that must keep applying after the application code
it was generated from has moved. Autogenerate wrote the fully-qualified Python path here and did
not import it, which would have failed at ``alembic upgrade head``.

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3c976a24e81e"
down_revision: str | None = "479594251a94"
branch_labels: str | None = None
depends_on: str | None = None

# Both tiers of the seeded catalog plus the quote lines. Every one of these tables may already
# hold rows, so the columns land NOT NULL only because ``server_default`` fills the existing
# ones in the same statement.
_TABLES = ("asset", "option", "optiongroup", "optionrule", "platform", "quoteline")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )

    op.add_column(
        "quote",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Existing leads have never been updated, so the honest value is when they arrived -- not
    # the minute this migration happened to run. The other six tables have no earlier timestamp
    # to inherit, so ``now()`` is the only answer available there.
    op.execute("UPDATE quote SET updated_at = created_at")

    # ``quote.created_at`` predates BaseTable and has no server default, which the model now
    # says it has. SET DEFAULT alone: no rewrite, no drop, and ``ix_quote_created_at`` is not
    # touched.
    op.alter_column("quote", "created_at", server_default=sa.text("now()"))


def downgrade() -> None:
    op.alter_column("quote", "created_at", server_default=None)
    op.drop_column("quote", "updated_at")

    for table in reversed(_TABLES):
        op.drop_column(table, "updated_at")
        op.drop_column(table, "created_at")
