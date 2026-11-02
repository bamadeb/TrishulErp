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
    # Guarded: the columns may already exist (this was applied to the shared database before the
    # alert-module migration was chained in), so a re-run must be a no-op.
    for column, length, text in (
        ("manufacturer", 50, "Device manufacturer"),
        ("model", 100, "Device model"),
        ("build_number", 50, "Device build number"),
    ):
        op.execute(f"""
            IF COL_LENGTH(N'core.user_device', N'{column}') IS NULL
            BEGIN
                ALTER TABLE [core].[user_device] ADD [{column}] NVARCHAR({length}) NULL;
                EXEC sys.sp_addextendedproperty N'MS_Description', N'{text}',
                    N'SCHEMA', N'core', N'TABLE', N'user_device', N'COLUMN', N'{column}';
            END
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
