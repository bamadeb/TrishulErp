"""merge status and trip distance

Revision ID: 1e85a20c9857
Revises: 0008, 0008_svc_status_update
Created: 2026-10-31 17:54:27.831479
"""

from alembic import op

revision = '1e85a20c9857'
down_revision = ('0008', '0008_svc_status_update')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Hand-written, idempotent SQL: check the catalog / existing rows before changing anything.
    op.execute("""
    """)


def downgrade() -> None:
    op.execute("""
    """)
