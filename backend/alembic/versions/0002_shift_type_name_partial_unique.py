from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("shift_types_name_key", "shift_types", type_="unique")
    op.create_index(
        "shift_types_name_active_unique",
        "shift_types",
        ["name"],
        unique=True,
        postgresql_where="deactivated_at IS NULL",
    )


def downgrade() -> None:
    op.drop_index("shift_types_name_active_unique", table_name="shift_types")
    op.create_unique_constraint("shift_types_name_key", "shift_types", ["name"])
