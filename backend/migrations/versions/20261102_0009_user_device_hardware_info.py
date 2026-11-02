"""Record the phone's manufacturer, model and build number on core.user_device.

The Android app sends them with device registration so support can tell which handset a bug or a
missing push notification comes from. All three are nullable: older app builds do not send them.

Revision ID: 0009_user_device_hw
Revises: 0009_machine_management
Created: 2026-11-02
"""

from alembic import op

revision = "0009_user_device_hw"
down_revision = "0009_machine_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE [core].[user_device] ADD
            [manufacturer] NVARCHAR(50) NULL,
            [model] NVARCHAR(100) NULL,
            [build_number] NVARCHAR(50) NULL;
    """)
    for column, text in (
        ("manufacturer", "Device manufacturer"),
        ("model", "Device model"),
        ("build_number", "Device build number"),
    ):
        op.execute(f"""
            EXEC sys.sp_addextendedproperty N'MS_Description', N'{text}',
                N'SCHEMA', N'core', N'TABLE', N'user_device', N'COLUMN', N'{column}';
        """)


def downgrade() -> None:
    for column in ("manufacturer", "model", "build_number"):
        op.execute(f"""
            EXEC sys.sp_dropextendedproperty N'MS_Description',
                N'SCHEMA', N'core', N'TABLE', N'user_device', N'COLUMN', N'{column}';
        """)
    op.execute("""
        ALTER TABLE [core].[user_device] DROP COLUMN [manufacturer], [model], [build_number];
    """)
