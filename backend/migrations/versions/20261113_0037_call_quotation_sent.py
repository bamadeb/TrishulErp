"""Service call status 'Quotation sent': the office made a sales quotation from the call's parts request.

    svc.service_call.current_status   adds 'Quotation sent' (between 'Awaiting parts' and 'Parts ready')

Revision id 0036 is taken by another developer's holiday migration already on RDS, hence 0037.
"""

from alembic import op

revision = "0037_call_quotation_sent"
down_revision = "0035_part_request_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF OBJECT_ID(N'[svc].[CK_svc_service_call_current_status]', N'C') IS NOT NULL
            ALTER TABLE [svc].[service_call] DROP CONSTRAINT [CK_svc_service_call_current_status];
    """)
    op.execute("""
        ALTER TABLE [svc].[service_call] ADD CONSTRAINT [CK_svc_service_call_current_status] CHECK ([current_status] IN (N'Logged', N'Assigned', N'Call ID linked', N'Customer contacted', N'Trip started', N'Reached site', N'In progress', N'Report submitted', N'Awaiting parts', N'Quotation sent', N'Parts ready', N'Revisit scheduled', N'Closed', N'Pending OEM closure', N'Completed', N'Reopened', N'Cancelled'));
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE [svc].[service_call] SET [current_status] = N'Awaiting parts' WHERE [current_status] = N'Quotation sent';
    """)
    op.execute("ALTER TABLE [svc].[service_call] DROP CONSTRAINT [CK_svc_service_call_current_status];")
    op.execute("""
        ALTER TABLE [svc].[service_call] ADD CONSTRAINT [CK_svc_service_call_current_status] CHECK ([current_status] IN (N'Logged', N'Assigned', N'Call ID linked', N'Customer contacted', N'Trip started', N'Reached site', N'In progress', N'Report submitted', N'Awaiting parts', N'Parts ready', N'Revisit scheduled', N'Closed', N'Pending OEM closure', N'Completed', N'Reopened', N'Cancelled'));
    """)
