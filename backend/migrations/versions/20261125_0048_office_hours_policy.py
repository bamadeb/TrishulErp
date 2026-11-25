"""Office hours policy: 9:30–5:30, 7.5 net hours, 3 grace days.

Updates the existing org rules row and inserts the General shift when hr.shift is empty.
No new tables.

Revision ID: 0048_office_hours_policy
Revises: 0047_trk_gps_ms_precision
Created: 2026-11-25
"""

import json
from datetime import datetime, time

from alembic import op
from sqlalchemy import text

revision = "0048_office_hours_policy"
down_revision = "0047_trk_gps_ms_precision"
branch_labels = None
depends_on = None

_POLICY = {
    "standardWorkHours": 7.5,
    "lateArrivalGraceMinutes": 15,
    "earlyExitGraceMinutes": 0,
    "graceDaysPerMonth": 3,
    "otAfterHours": 7.5,
    "weeklyOffDays": ["SUN"],
    "workingDaysPerWeek": 6,
}


def upgrade() -> None:
    connection = op.get_bind()
    row = connection.execute(
        text(
            """
            SELECT id, setting_value
            FROM core.system_setting
            WHERE setting_key = 'hr.attendance.rules' AND company_id IS NULL
            """
        )
    ).fetchone()
    if row is not None:
        payload = json.loads(row.setting_value or "{}")
        payload.update(_POLICY)
        connection.execute(
            text("UPDATE core.system_setting SET setting_value = :value WHERE id = :id"),
            {"value": json.dumps(payload), "id": row.id},
        )

    exists = connection.execute(text("SELECT TOP 1 id FROM hr.shift WHERE code = 'GEN'")).fetchone()
    if exists is None:
        connection.execute(
            text(
                """
                INSERT INTO hr.shift
                    (code, name, start_time, end_time, grace_minutes, half_day_hours, is_active, created_at)
                VALUES
                    ('GEN', 'General', :start_time, :end_time, 15, 3.75, 1, :created_at)
                """
            ),
            {
                "start_time": time(9, 30),
                "end_time": time(17, 30),
                "created_at": datetime.utcnow(),
            },
        )


def downgrade() -> None:
    connection = op.get_bind()
    row = connection.execute(
        text(
            """
            SELECT id, setting_value
            FROM core.system_setting
            WHERE setting_key = 'hr.attendance.rules' AND company_id IS NULL
            """
        )
    ).fetchone()
    if row is not None:
        payload = json.loads(row.setting_value or "{}")
        payload.update(
            {
                "standardWorkHours": 8.0,
                "lateArrivalGraceMinutes": 15,
                "earlyExitGraceMinutes": 15,
                "otAfterHours": 8.0,
            }
        )
        payload.pop("graceDaysPerMonth", None)
        connection.execute(
            text("UPDATE core.system_setting SET setting_value = :value WHERE id = :id"),
            {"value": json.dumps(payload), "id": row.id},
        )
