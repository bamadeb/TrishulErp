"""Alert module (phase 1: in-app alerts).

Adds:
  * core.alert_rule            Alert Master: one configured rule (type from the code catalogue + parameters,
                               brand/branch scope, severity, re-raise policy).
  * core.alert_rule_recipient  Who receives a rule's alerts: a role, a named user, or a person taken from the
                               record (the call's assigned engineer / the user who logged it). In-app only.
  * core.alert                 Every alert raised. A filtered unique index allows only one open (not
                               Resolved) alert per rule and business record (dedupe_key).
  * core.alert_recipient       Each recipient's inbox entry (read state).
  * core.app_user 'system'     Locked account the background job (TrishulJobs) works as; ADMIN role so
                               row-level security lets it see every branch and brand. It cannot sign in.
  * permissions                core.alert.view (own alerts: every role), core.alert.rule.view
                               (ADMIN, TEAM_LEAD, MANAGEMENT), core.alert.rule.manage (ADMIN).
  * six starter rules          one per alert type, seeded INACTIVE so nothing is raised until an
                               administrator reviews and activates them.

SLA due times are not configured here: they come from svc.sla_rule (see modules/service/sla.py).

Revision ID: 0010_alert_module
Revises: 0009_machine_management
Created: 2026-11-02
"""

from alembic import op

revision = "0010_alert_module"
down_revision = "0009_machine_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE [core].[alert_rule] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_alert_rule] PRIMARY KEY,
            [company_id] BIGINT NOT NULL,
            [code] NVARCHAR(40) NOT NULL,
            [name] NVARCHAR(150) NOT NULL,
            [description] NVARCHAR(500) NULL,
            [alert_type] NVARCHAR(40) NOT NULL,
            [principal_id] BIGINT NULL,
            [branch_id] BIGINT NULL,
            [severity] NVARCHAR(20) NOT NULL CONSTRAINT [DF_core_alert_rule_severity] DEFAULT (N'Warning'),
            [parameters] NVARCHAR(2000) NOT NULL CONSTRAINT [DF_core_alert_rule_parameters] DEFAULT (N'{}'),
            [reraise_policy] NVARCHAR(30) NOT NULL
                CONSTRAINT [DF_core_alert_rule_reraise_policy] DEFAULT (N'After resolution'),
            [cooldown_minutes] INT NOT NULL CONSTRAINT [DF_core_alert_rule_cooldown_minutes] DEFAULT (0),
            [last_run_at] DATETIME2(0) NULL,
            [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_alert_rule_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [updated_at] DATETIME2(0) NULL,
            [updated_by_user_id] BIGINT NULL,
            [is_active] BIT NOT NULL CONSTRAINT [DF_core_alert_rule_is_active] DEFAULT (1),
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [UX_core_alert_rule_code] UNIQUE ([code]),
            CONSTRAINT [CK_core_alert_rule_alert_type] CHECK ([alert_type] IN (
                N'SVC_CALL_UNASSIGNED', N'SVC_SLA_DUE', N'SVC_STATUS_STALE', N'SVC_AWAITING_PARTS',
                N'SVC_CALL_REOPENED', N'MACHINE_COVERAGE_EXPIRY')),
            CONSTRAINT [CK_core_alert_rule_severity] CHECK ([severity] IN (N'Info', N'Warning', N'Critical')),
            CONSTRAINT [CK_core_alert_rule_reraise_policy]
                CHECK ([reraise_policy] IN (N'Never', N'After resolution')),
            CONSTRAINT [CK_core_alert_rule_parameters_json] CHECK (ISJSON([parameters]) = 1),
            CONSTRAINT [CK_core_alert_rule_cooldown_minutes] CHECK ([cooldown_minutes] >= 0),
            CONSTRAINT [FK_core_alert_rule_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]),
            CONSTRAINT [FK_core_alert_rule_principal_id]
                FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]),
            CONSTRAINT [FK_core_alert_rule_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id])
        );
    """)
    op.execute("""
        CREATE TABLE [core].[alert_rule_recipient] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_alert_rule_recipient] PRIMARY KEY,
            [alert_rule_id] BIGINT NOT NULL,
            [recipient_type] NVARCHAR(30) NOT NULL,
            [role_id] BIGINT NULL,
            [app_user_id] BIGINT NULL,
            [channel] NVARCHAR(20) NOT NULL CONSTRAINT [DF_core_alert_rule_recipient_channel] DEFAULT (N'In-app'),
            [created_at] DATETIME2(0) NOT NULL
                CONSTRAINT [DF_core_alert_rule_recipient_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            CONSTRAINT [CK_core_alert_rule_recipient_recipient_type]
                CHECK ([recipient_type] IN (N'Role', N'User', N'Assigned engineer', N'Call logged by')),
            CONSTRAINT [CK_core_alert_rule_recipient_channel] CHECK ([channel] IN (N'In-app')),
            CONSTRAINT [CK_core_alert_rule_recipient_target] CHECK (
                ([recipient_type] = N'Role' AND [role_id] IS NOT NULL AND [app_user_id] IS NULL)
                OR ([recipient_type] = N'User' AND [app_user_id] IS NOT NULL AND [role_id] IS NULL)
                OR ([recipient_type] IN (N'Assigned engineer', N'Call logged by')
                    AND [role_id] IS NULL AND [app_user_id] IS NULL)),
            CONSTRAINT [FK_core_alert_rule_recipient_alert_rule_id]
                FOREIGN KEY ([alert_rule_id]) REFERENCES [core].[alert_rule] ([id]),
            CONSTRAINT [FK_core_alert_rule_recipient_role_id] FOREIGN KEY ([role_id]) REFERENCES [core].[role] ([id]),
            CONSTRAINT [FK_core_alert_rule_recipient_app_user_id]
                FOREIGN KEY ([app_user_id]) REFERENCES [core].[app_user] ([id])
        );
        CREATE INDEX [IX_core_alert_rule_recipient_alert_rule_id] ON [core].[alert_rule_recipient] ([alert_rule_id]);
    """)
    op.execute("""
        CREATE TABLE [core].[alert] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_alert] PRIMARY KEY,
            [alert_rule_id] BIGINT NOT NULL,
            [alert_type] NVARCHAR(40) NOT NULL,
            [company_id] BIGINT NOT NULL,
            [principal_id] BIGINT NULL,
            [branch_id] BIGINT NULL,
            [entity_type] NVARCHAR(40) NOT NULL,
            [entity_id] BIGINT NOT NULL,
            [dedupe_key] NVARCHAR(150) NOT NULL,
            [severity] NVARCHAR(20) NOT NULL,
            [title] NVARCHAR(200) NOT NULL,
            [message] NVARCHAR(1000) NOT NULL,
            [status] NVARCHAR(20) NOT NULL CONSTRAINT [DF_core_alert_status] DEFAULT (N'Open'),
            [raised_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_alert_raised_at] DEFAULT (SYSUTCDATETIME()),
            [acknowledged_at] DATETIME2(0) NULL,
            [acknowledged_by_user_id] BIGINT NULL,
            [resolved_at] DATETIME2(0) NULL,
            [resolved_by_user_id] BIGINT NULL,
            [resolution_note] NVARCHAR(200) NULL,
            [row_version] ROWVERSION NOT NULL,
            CONSTRAINT [CK_core_alert_alert_type] CHECK ([alert_type] IN (
                N'SVC_CALL_UNASSIGNED', N'SVC_SLA_DUE', N'SVC_STATUS_STALE', N'SVC_AWAITING_PARTS',
                N'SVC_CALL_REOPENED', N'MACHINE_COVERAGE_EXPIRY')),
            CONSTRAINT [CK_core_alert_entity_type]
                CHECK ([entity_type] IN (N'svc.service_call', N'core.machine_unit', N'svc.service_contract')),
            CONSTRAINT [CK_core_alert_severity] CHECK ([severity] IN (N'Info', N'Warning', N'Critical')),
            CONSTRAINT [CK_core_alert_status] CHECK ([status] IN (N'Open', N'Acknowledged', N'Resolved')),
            CONSTRAINT [FK_core_alert_alert_rule_id] FOREIGN KEY ([alert_rule_id]) REFERENCES [core].[alert_rule] ([id]),
            CONSTRAINT [FK_core_alert_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]),
            CONSTRAINT [FK_core_alert_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]),
            CONSTRAINT [FK_core_alert_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]),
            CONSTRAINT [FK_core_alert_acknowledged_by_user_id]
                FOREIGN KEY ([acknowledged_by_user_id]) REFERENCES [core].[app_user] ([id]),
            CONSTRAINT [FK_core_alert_resolved_by_user_id]
                FOREIGN KEY ([resolved_by_user_id]) REFERENCES [core].[app_user] ([id])
        );
        -- Duplicate prevention: at most one open (Open / Acknowledged) alert per rule and business record.
        CREATE UNIQUE INDEX [UX_core_alert_rule_open_key] ON [core].[alert] ([alert_rule_id], [dedupe_key])
            WHERE [status] <> N'Resolved';
        CREATE INDEX [IX_core_alert_rule_key] ON [core].[alert] ([alert_rule_id], [dedupe_key], [resolved_at]);
        CREATE INDEX [IX_core_alert_entity] ON [core].[alert] ([entity_type], [entity_id]);
    """)
    op.execute("""
        CREATE TABLE [core].[alert_recipient] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_alert_recipient] PRIMARY KEY,
            [alert_id] BIGINT NOT NULL,
            [app_user_id] BIGINT NOT NULL,
            [read_at] DATETIME2(0) NULL,
            [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_alert_recipient_created_at] DEFAULT (SYSUTCDATETIME()),
            CONSTRAINT [UX_core_alert_recipient] UNIQUE ([alert_id], [app_user_id]),
            CONSTRAINT [FK_core_alert_recipient_alert_id] FOREIGN KEY ([alert_id]) REFERENCES [core].[alert] ([id]),
            CONSTRAINT [FK_core_alert_recipient_app_user_id]
                FOREIGN KEY ([app_user_id]) REFERENCES [core].[app_user] ([id])
        );
        CREATE INDEX [IX_core_alert_recipient_user] ON [core].[alert_recipient] ([app_user_id], [read_at]);
    """)
    # The background job's account: locked (cannot sign in), ADMIN so row-level security shows it every row.
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM [core].[app_user] WHERE [username] = N'system')
            INSERT INTO [core].[app_user] ([cognito_sub], [username], [is_locked], [is_active])
            VALUES (N'system:trishul-jobs', N'system', 1, 1);
        INSERT INTO [core].[user_role] ([app_user_id], [role_id], [branch_id])
        SELECT u.[id], r.[id], NULL
        FROM [core].[app_user] u JOIN [core].[role] r ON r.[code] = N'ADMIN'
        WHERE u.[username] = N'system'
          AND NOT EXISTS (SELECT 1 FROM [core].[user_role] ur WHERE ur.[app_user_id] = u.[id] AND ur.[role_id] = r.[id]);
    """)
    op.execute("""
        INSERT INTO [core].[permission] ([code], [module], [description])
        SELECT v.[code], N'Core', v.[description]
        FROM (VALUES
            (N'core.alert.view', N'See and acknowledge my alerts'),
            (N'core.alert.rule.view', N'See alert rules (Alert Master)'),
            (N'core.alert.rule.manage', N'Add and change alert rules, activate or deactivate them')
        ) v([code], [description])
        WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] p WHERE p.[code] = v.[code]);
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] = N'core.alert.view'
           OR (p.[code] = N'core.alert.rule.view' AND r.[code] IN (N'ADMIN', N'TEAM_LEAD', N'MANAGEMENT'))
           OR (p.[code] = N'core.alert.rule.manage' AND r.[code] = N'ADMIN')
        WHERE NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)
    # Six starter rules, inactive. Team leads are told; engineers also hear about their own stuck calls.
    op.execute("""
        INSERT INTO [core].[alert_rule] ([company_id], [code], [name], [description], [alert_type], [severity],
                                         [parameters], [reraise_policy], [cooldown_minutes], [is_active])
        SELECT c.[id], v.[code], v.[name], v.[description], v.[alert_type], v.[severity], v.[parameters],
               v.[reraise_policy], 0, 0
        FROM (SELECT TOP 1 [id] FROM [core].[company] ORDER BY [id]) c
        CROSS JOIN (VALUES
            (N'CALL_UNASSIGNED', N'Service call not assigned', N'A call is still not assigned to an engineer.',
             N'SVC_CALL_UNASSIGNED', N'Warning', N'{"afterMinutes":30}', N'After resolution'),
            (N'SLA_DUE', N'SLA due soon or breached', N'Uses the SLA due time from the SLA rules (svc.sla_rule).',
             N'SVC_SLA_DUE', N'Critical', N'{"stages":["Due soon","Breached"]}', N'Never'),
            (N'STATUS_STALE', N'Call status unchanged', N'A call has stayed in the same status too long.',
             N'SVC_STATUS_STALE', N'Warning', N'{"afterHours":24}', N'After resolution'),
            (N'AWAITING_PARTS', N'Call waiting for parts', N'A call has been waiting for parts too long.',
             N'SVC_AWAITING_PARTS', N'Warning', N'{"afterDays":3}', N'After resolution'),
            (N'CALL_REOPENED', N'Service call reopened', N'Raised every time a call is reopened.',
             N'SVC_CALL_REOPENED', N'Critical', N'{}', N'Never'),
            (N'COVERAGE_EXPIRY', N'Warranty or AMC ending', N'A machine''s warranty or AMC ends soon.',
             N'MACHINE_COVERAGE_EXPIRY', N'Info', N'{"daysBefore":30,"coverage":["Warranty","AMC"]}', N'Never')
        ) v([code], [name], [description], [alert_type], [severity], [parameters], [reraise_policy])
        WHERE NOT EXISTS (SELECT 1 FROM [core].[alert_rule] ar WHERE ar.[code] = v.[code]);
        INSERT INTO [core].[alert_rule_recipient] ([alert_rule_id], [recipient_type], [role_id])
        SELECT ar.[id], N'Role', r.[id]
        FROM [core].[alert_rule] ar JOIN [core].[role] r ON r.[code] = N'TEAM_LEAD'
        WHERE ar.[code] IN (N'CALL_UNASSIGNED', N'SLA_DUE', N'STATUS_STALE', N'AWAITING_PARTS',
                            N'CALL_REOPENED', N'COVERAGE_EXPIRY')
          AND NOT EXISTS (SELECT 1 FROM [core].[alert_rule_recipient] x WHERE x.[alert_rule_id] = ar.[id]);
        INSERT INTO [core].[alert_rule_recipient] ([alert_rule_id], [recipient_type])
        SELECT ar.[id], N'Assigned engineer'
        FROM [core].[alert_rule] ar
        WHERE ar.[code] IN (N'SLA_DUE', N'STATUS_STALE', N'AWAITING_PARTS')
          AND NOT EXISTS (SELECT 1 FROM [core].[alert_rule_recipient] x
                          WHERE x.[alert_rule_id] = ar.[id] AND x.[recipient_type] = N'Assigned engineer');
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] IN (N'core.alert.view', N'core.alert.rule.view', N'core.alert.rule.manage');
        DELETE FROM [core].[permission]
        WHERE [code] IN (N'core.alert.view', N'core.alert.rule.view', N'core.alert.rule.manage');
        DELETE ur FROM [core].[user_role] ur JOIN [core].[app_user] u ON u.[id] = ur.[app_user_id]
        WHERE u.[username] = N'system';
        DELETE FROM [core].[app_user] WHERE [username] = N'system';
    """)
    op.execute("DROP TABLE [core].[alert_recipient];")
    op.execute("DROP TABLE [core].[alert];")
    op.execute("DROP TABLE [core].[alert_rule_recipient];")
    op.execute("DROP TABLE [core].[alert_rule];")
