"""Service-call visibility by team, and permissions for managing teams (core.team, core.team_member).

The call register now shows each user only the calls their permission covers:

svc.call.view           every call in their branches (office roles, management)
svc.call.view.team      new: calls of the engineers in the teams they lead, plus unassigned calls (TEAM_LEAD)
svc.call.view.assigned  only the calls assigned to them (SERVICE_ENGINEER)

so svc.call.view is switched off for TEAM_LEAD and SERVICE_ENGINEER (the row is kept, inactive, as the
role screen does).

core.team.view    see teams and their members
core.team.manage  add and change teams, choose the lead and members, mark them active or inactive

Both: ADMIN only.

Revision ID: 0014_team_call_visibility
Revises: 0013_role_management
Created: 2026-11-02
"""

import sqlalchemy as sa
from alembic import op

revision = "0014_team_call_visibility"
down_revision = "0013_role_management"
branch_labels = None
depends_on = None


_GRANT = sa.text("""
    INSERT INTO [core].[role_permission] ([role_id], [permission_id])
    SELECT r.[id], p.[id]
    FROM [core].[role] r
    JOIN [core].[permission] p ON p.[code] = :permission
    WHERE r.[code] = :role
      AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                      WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
""")

_SET_ACTIVE = sa.text("""
    UPDATE rp SET rp.[is_active] = :active, rp.[updated_at] = SYSUTCDATETIME()
    FROM [core].[role_permission] rp
    JOIN [core].[role] r ON r.[id] = rp.[role_id]
    JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
    WHERE p.[code] = :permission AND r.[code] = :role;
""")


def _grant(permission: str, role: str) -> None:
    op.execute(_GRANT.bindparams(permission=permission, role=role))
    op.execute(_SET_ACTIVE.bindparams(permission=permission, role=role, active=True))


def _set_view_all(active: bool) -> None:
    for role in ("TEAM_LEAD", "SERVICE_ENGINEER"):
        op.execute(_SET_ACTIVE.bindparams(permission="svc.call.view", role=role, active=active))


def upgrade() -> None:
    op.execute("""
        INSERT INTO [core].[permission] ([code], [module], [description])
        SELECT v.[code], v.[module], v.[description]
        FROM (VALUES
            (N'svc.call.view.team', N'Service',
             N'View service calls of the engineers in teams one leads, and unassigned calls'),
            (N'core.team.view', N'Core', N'See teams and their members'),
            (N'core.team.manage', N'Core',
             N'Add and change teams, choose the lead and members, mark them active or inactive')
        ) v([code], [module], [description])
        WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] p WHERE p.[code] = v.[code]);

        UPDATE [core].[permission] SET [description] = N'View every service call in one''s branches'
        WHERE [code] = N'svc.call.view';
        UPDATE [core].[permission] SET [description] = N'View service calls assigned to oneself'
        WHERE [code] = N'svc.call.view.assigned';
    """)
    _grant("svc.call.view.team", "TEAM_LEAD")
    _grant("core.team.view", "ADMIN")
    _grant("core.team.manage", "ADMIN")
    _set_view_all(False)


def downgrade() -> None:
    _set_view_all(True)
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] IN (N'svc.call.view.team', N'core.team.view', N'core.team.manage');
        DELETE FROM [core].[permission] WHERE [code] IN (N'svc.call.view.team', N'core.team.view', N'core.team.manage');
        UPDATE [core].[permission] SET [description] = N'View service calls assigned to oneself (mobile)'
        WHERE [code] = N'svc.call.view.assigned';
    """)
