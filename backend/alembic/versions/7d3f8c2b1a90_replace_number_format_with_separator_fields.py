"""replace number_format with decimal_separator and thousands_separator

Revision ID: 7d3f8c2b1a90
Revises: 4a129036b96f
Create Date: 2026-03-21 14:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7d3f8c2b1a90"
down_revision: Union[str, None] = "4a129036b96f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("import_templates", "number_format")
    op.add_column("import_templates", sa.Column("decimal_separator", sa.String(length=5), nullable=True))
    op.add_column("import_templates", sa.Column("thousands_separator", sa.String(length=5), nullable=True))


def downgrade() -> None:
    op.drop_column("import_templates", "thousands_separator")
    op.drop_column("import_templates", "decimal_separator")
    op.add_column("import_templates", sa.Column("number_format", sa.String(length=20), nullable=True))
