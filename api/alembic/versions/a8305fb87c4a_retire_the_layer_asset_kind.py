"""retire the layer asset kind

Revision ID: a8305fb87c4a
Revises: 789a1ecd05b7
Create Date: 2026-08-30 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8305fb87c4a"
down_revision: str | None = "789a1ecd05b7"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Postgres cannot drop a value from an enum type, so ``asset.kind`` has to move to a freshly
    created type that never had ``layer`` in it. The rows are deleted first: Stage 17 retires the
    2D viewer composite those rows served, so there is nothing left for them to mean once the
    ``layer`` kind is gone.
    """
    op.execute("DELETE FROM asset WHERE kind = 'layer'")

    op.execute("CREATE TYPE assetkind_new AS ENUM ('hero', 'gallery', 'thumbnail')")
    op.execute(
        "ALTER TABLE asset ALTER COLUMN kind TYPE assetkind_new USING kind::text::assetkind_new"
    )
    op.execute("DROP TYPE assetkind")
    op.execute("ALTER TYPE assetkind_new RENAME TO assetkind")


def downgrade() -> None:
    """Recreates the ``layer`` enum value so the column shape matches the pre-Stage-17 code again.
    It cannot recreate the rows ``upgrade()`` deleted -- those are gone for good, same as any
    other ``DELETE`` a migration in this set runs on deploy.
    """
    op.execute("CREATE TYPE assetkind_old AS ENUM ('hero', 'gallery', 'thumbnail', 'layer')")
    op.execute(
        "ALTER TABLE asset ALTER COLUMN kind TYPE assetkind_old USING kind::text::assetkind_old"
    )
    op.execute("DROP TYPE assetkind")
    op.execute("ALTER TYPE assetkind_old RENAME TO assetkind")
