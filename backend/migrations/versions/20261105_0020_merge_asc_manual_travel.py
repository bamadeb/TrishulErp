"""Join the ASC visit and manual travel migrations. No schema change.

0018_manual_travel continues from 0016_trk_gps_diagnostics, while 0017_asc_call_visits continues from
0010_organization, so the two lines need one head for `alembic upgrade head` to work.

Revision ID: 0020_merge_asc_manual_travel
Revises: 0017_asc_call_visits, 0019_public_transport_manual
Created: 2026-11-05
"""

revision = "0020_merge_asc_manual_travel"
down_revision = ("0017_asc_call_visits", "0019_public_transport_manual")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
