"""Parts requests, next step: an alert when an engineer requests parts, and the office's review.

    core.alert_rule / core.alert   alert type 'SVC_PART_REQUEST' (an event on the call: raised when the request
                                   is saved, resolved once every requested part is quoted or rejected)
    core.alert_rule                rule PART_REQUEST, active, to the ADMIN and WAREHOUSE roles (the holders of
                                   svc.part_request.review)
    svc.service_part_request       review_note: why a part was rejected (or any note from the reviewer)

Revision ids 0033 / 0034 are taken by another developer's leave migrations already on RDS, hence 0035.
"""

from alembic import op

revision = "0035_part_request_alerts"
down_revision = "0032_sales_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF OBJECT_ID(N'[core].[CK_core_alert_rule_alert_type]', N'C') IS NOT NULL
            ALTER TABLE [core].[alert_rule] DROP CONSTRAINT [CK_core_alert_rule_alert_type];
    """)
    op.execute("""
        ALTER TABLE [core].[alert_rule] ADD CONSTRAINT [CK_core_alert_rule_alert_type] CHECK ([alert_type] IN (N'SVC_CALL_UNASSIGNED', N'SVC_SLA_DUE', N'SVC_STATUS_STALE', N'SVC_AWAITING_PARTS', N'SVC_CALL_REOPENED', N'MACHINE_COVERAGE_EXPIRY', N'SVC_PART_REQUEST'));
    """)
    op.execute("""
        IF OBJECT_ID(N'[core].[CK_core_alert_alert_type]', N'C') IS NOT NULL
            ALTER TABLE [core].[alert] DROP CONSTRAINT [CK_core_alert_alert_type];
    """)
    op.execute("""
        ALTER TABLE [core].[alert] ADD CONSTRAINT [CK_core_alert_alert_type] CHECK ([alert_type] IN (N'SVC_CALL_UNASSIGNED', N'SVC_SLA_DUE', N'SVC_STATUS_STALE', N'SVC_AWAITING_PARTS', N'SVC_CALL_REOPENED', N'MACHINE_COVERAGE_EXPIRY', N'SVC_PART_REQUEST'));
    """)
    op.execute("""
        IF COL_LENGTH(N'svc.service_part_request', N'review_note') IS NULL
            ALTER TABLE [svc].[service_part_request] ADD [review_note] NVARCHAR(300) NULL;
    """)
    op.execute("""
        INSERT INTO [core].[alert_rule]
            ([company_id], [code], [name], [description], [alert_type], [severity], [parameters], [reraise_policy],
             [is_active])
        SELECT c.[id], N'PART_REQUEST', N'Parts requested on a call',
               N'An engineer requested parts on a service call; quote or reject them.',
               N'SVC_PART_REQUEST', N'Warning', N'{}', N'Never', 1
        FROM [core].[company] c
        WHERE c.[id] = (SELECT MIN([id]) FROM [core].[company])
          AND NOT EXISTS (SELECT 1 FROM [core].[alert_rule] ar WHERE ar.[code] = N'PART_REQUEST');
    """)
    op.execute("""
        INSERT INTO [core].[alert_rule_recipient] ([alert_rule_id], [recipient_type], [role_id])
        SELECT ar.[id], N'Role', r.[id]
        FROM [core].[alert_rule] ar JOIN [core].[role] r ON r.[code] IN (N'ADMIN', N'WAREHOUSE')
        WHERE ar.[code] = N'PART_REQUEST'
          AND NOT EXISTS (SELECT 1 FROM [core].[alert_rule_recipient] x
                          WHERE x.[alert_rule_id] = ar.[id] AND x.[role_id] = r.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM [core].[alert_recipient] WHERE [alert_id] IN
            (SELECT [id] FROM [core].[alert] WHERE [alert_type] = N'SVC_PART_REQUEST');
        DELETE FROM [core].[alert] WHERE [alert_type] = N'SVC_PART_REQUEST';
        DELETE FROM [core].[alert_rule_recipient] WHERE [alert_rule_id] IN
            (SELECT [id] FROM [core].[alert_rule] WHERE [alert_type] = N'SVC_PART_REQUEST');
        DELETE FROM [core].[alert_rule] WHERE [alert_type] = N'SVC_PART_REQUEST';
    """)
    op.execute("ALTER TABLE [svc].[service_part_request] DROP COLUMN [review_note];")
    op.execute("ALTER TABLE [core].[alert_rule] DROP CONSTRAINT [CK_core_alert_rule_alert_type];")
    op.execute("""
        ALTER TABLE [core].[alert_rule] ADD CONSTRAINT [CK_core_alert_rule_alert_type] CHECK ([alert_type] IN (N'SVC_CALL_UNASSIGNED', N'SVC_SLA_DUE', N'SVC_STATUS_STALE', N'SVC_AWAITING_PARTS', N'SVC_CALL_REOPENED', N'MACHINE_COVERAGE_EXPIRY'));
    """)
    op.execute("ALTER TABLE [core].[alert] DROP CONSTRAINT [CK_core_alert_alert_type];")
    op.execute("""
        ALTER TABLE [core].[alert] ADD CONSTRAINT [CK_core_alert_alert_type] CHECK ([alert_type] IN (N'SVC_CALL_UNASSIGNED', N'SVC_SLA_DUE', N'SVC_STATUS_STALE', N'SVC_AWAITING_PARTS', N'SVC_CALL_REOPENED', N'MACHINE_COVERAGE_EXPIRY'));
    """)
