"""M4-ST1: Account nullable company_name, EUR/Paris defaults.

Revision ID: a1b2c3d4e5f6
Revises: 7d3f8c2b1a90
Create Date: 2026-03-22
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "7d3f8c2b1a90"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "accounts",
        "company_name",
        existing_type=sa.String(255),
        nullable=True,
    )
    op.execute("UPDATE accounts SET currency = 'EUR' WHERE currency = 'CZK'")
    op.execute(
        "UPDATE accounts SET timezone = 'Europe/Paris' WHERE timezone = 'Europe/Prague'"
    )


def downgrade():
    op.execute("UPDATE accounts SET company_name = '' WHERE company_name IS NULL")
    op.alter_column(
        "accounts",
        "company_name",
        existing_type=sa.String(255),
        nullable=False,
    )
    op.execute("UPDATE accounts SET currency = 'CZK' WHERE currency = 'EUR'")
    op.execute(
        "UPDATE accounts SET timezone = 'Europe/Prague' WHERE timezone = 'Europe/Paris'"
    )
