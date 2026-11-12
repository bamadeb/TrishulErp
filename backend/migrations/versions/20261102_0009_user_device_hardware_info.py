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
    # Written out in full (no f-string): scripts/generate_models.py only reads literal DDL, and a
    # loop here made the generator drop these columns from the UserDevice model.
    op.execute("""
        IF COL_LENGTH(N'core.user_device', N'manufacturer') IS NULL
        BEGIN
            ALTER TABLE [core].[user_device] ADD [manufacturer] NVARCHAR(50) NULL;
            EXEC sys.sp_addextendedproperty N'MS_Description', N'Device manufacturer',
                N'SCHEMA', N'core', N'TABLE', N'user_device', N'COLUMN', N'manufacturer';
        END
    """)
    op.execute("""
        IF COL_LENGTH(N'core.user_device', N'model') IS NULL
        BEGIN
            ALTER TABLE [core].[user_device] ADD [model] NVARCHAR(100) NULL;
            EXEC sys.sp_addextendedproperty N'MS_Description', N'Device model',
                N'SCHEMA', N'core', N'TABLE', N'user_device', N'COLUMN', N'model';
        END
    """)
    op.execute("""
        IF COL_LENGTH(N'core.user_device', N'build_number') IS NULL
        BEGIN
            ALTER TABLE [core].[user_device] ADD [build_number] NVARCHAR(50) NULL;
            EXEC sys.sp_addextendedproperty N'MS_Description', N'Device build number',
                N'SCHEMA', N'core', N'TABLE', N'user_device', N'COLUMN', N'build_number';
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
