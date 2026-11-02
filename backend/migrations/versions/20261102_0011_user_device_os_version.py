"""Record the phone's OS version (e.g. "Android 13") on core.user_device.

Sent by the Android app with device registration. Nullable: older app builds do not send it.

Also merges the two heads that existed (0010_alert_module and 0009_user_device_hw).

Revision ID: 0011_user_device_os
Revises: 0010_alert_module, 0009_user_device_hw
Created: 2026-11-02
"""

from alembic import op

revision = "0011_user_device_os"
down_revision = ("0010_alert_module", "0009_user_device_hw")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF COL_LENGTH(N'core.user_device', N'os_version') IS NULL
        BEGIN
            ALTER TABLE [core].[user_device] ADD [os_version] NVARCHAR(30) NULL;
            EXEC sys.sp_addextendedproperty N'MS_Description', N'Device OS version',
                N'SCHEMA', N'core', N'TABLE', N'user_device', N'COLUMN', N'os_version';
        END
    """)


def downgrade() -> None:
    op.execute("""
        EXEC sys.sp_dropextendedproperty N'MS_Description',
            N'SCHEMA', N'core', N'TABLE', N'user_device', N'COLUMN', N'os_version';
        ALTER TABLE [core].[user_device] DROP COLUMN [os_version];
    """)
