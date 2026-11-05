"""Public transport has no GPS trip: travel by it is entered by hand, like Bus, Train and Other.

Trips already recorded with this vehicle type keep their GPS data and stay visible; only new Start trip
requests with it are refused (the engineer records manual travel instead).

Idempotent: setting the flag twice changes nothing.

Revision ID: 0019_public_transport_manual
Revises: 0018_manual_travel
Created: 2026-11-05
"""

from alembic import op

revision = "0019_public_transport_manual"
down_revision = "0018_manual_travel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE trk.trip_vehicle_type SET is_gps_tracked = 0
        WHERE code = N'Public transport' AND is_gps_tracked = 1;
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE trk.trip_vehicle_type SET is_gps_tracked = 1 WHERE code = N'Public transport';
    """)
