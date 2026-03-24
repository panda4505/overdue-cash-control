"""rename errors to skipped_rows on import_records

Revision ID: 8a7266974e1b
Revises: a1b2c3d4e5f6
Create Date: 2026-03-24 03:08:58.578812

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '8a7266974e1b'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("import_records", "errors", new_column_name="skipped_rows")


def downgrade() -> None:
    op.alter_column("import_records", "skipped_rows", new_column_name="errors")
