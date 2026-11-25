"""Complaint management: employees raise complaints to a department; its leaders work them.

  * core.complaint_issue_type   issue types per department (Super Admin maintains them); 'Other' seeded for
                                every active department
  * core.complaint              one complaint: number, department, issue type, description, status, who raised it
  * core.complaint_history      append-only: raised, every status change and every note, with who and when
  * core.number_series          COMPLAINT series per branch: <branch code>/CMP/00001
  * Attachments                 core.attachment rows with entity_type 'core.complaint' (the shared document
                                service; nothing to create)
  * Alerts                      types CMP_COMPLAINT_RAISED (to the department's leaders) and CMP_COMPLAINT_UPDATED
                                (to the person who raised it); entity type 'core.complaint'; one active event rule
                                each
  * Permissions                 core.complaint.raise (every role), core.complaint.manage (complaints of one's own
                                department; assign via Role Management), core.complaint.manage_all (every
                                department and the issue types; ADMIN)

A department's leaders are its head (hr.department.head_employee_id) and every employee of the department whose
role has core.complaint.manage.

Revision ID: 0048_complaints
Revises: 0047_trk_gps_ms_precision
Created: 2026-11-25
"""

from alembic import op

revision = "0048_complaints"
down_revision = "0047_trk_gps_ms_precision"
branch_labels = None
depends_on = None

_STATUSES = "N'Open', N'In Progress', N'On Hold', N'Resolved', N'Closed'"

_STD = """
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_{t}_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_{t}_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL"""

_ALERT_TYPES_BEFORE = (
    "N'SVC_CALL_UNASSIGNED', N'SVC_SLA_DUE', N'SVC_STATUS_STALE', N'SVC_AWAITING_PARTS', N'SVC_CALL_REOPENED', "
    "N'MACHINE_COVERAGE_EXPIRY', N'SVC_PART_REQUEST'"
)
_ALERT_TYPES_AFTER = _ALERT_TYPES_BEFORE + ", N'CMP_COMPLAINT_RAISED', N'CMP_COMPLAINT_UPDATED'"
_ENTITY_TYPES_BEFORE = "N'svc.service_call', N'core.machine_unit', N'svc.service_contract'"
_ENTITY_TYPES_AFTER = _ENTITY_TYPES_BEFORE + ", N'core.complaint'"

_PERMISSIONS = (
    ("core.complaint.raise", "Raise a complaint to a department and see your own complaints"),
    ("core.complaint.manage", "View and update the complaints of your own department"),
    ("core.complaint.manage_all", "View and update complaints of every department; maintain issue types"),
)


def _std(table: str) -> str:
    return _STD.format(t=table)


def _check(table: str, name: str, column: str, values: str) -> None:
    op.execute(f"""
        IF OBJECT_ID(N'[core].[{name}]', N'C') IS NOT NULL
            ALTER TABLE [core].[{table}] DROP CONSTRAINT [{name}];
    """)
    op.execute(f"ALTER TABLE [core].[{table}] ADD CONSTRAINT [{name}] CHECK ([{column}] IN ({values}));")


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE [core].[complaint_issue_type] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_complaint_issue_type] PRIMARY KEY,
            [department_id] BIGINT NOT NULL,
            [name] NVARCHAR(80) NOT NULL,
            [description] NVARCHAR(300) NULL,
            [sort_order] INT NOT NULL CONSTRAINT [DF_core_complaint_issue_type_sort_order] DEFAULT (0),
            {_std("complaint_issue_type")},
            CONSTRAINT [FK_core_complaint_issue_type_department]
                FOREIGN KEY ([department_id]) REFERENCES [hr].[department] ([id])
        );
        CREATE UNIQUE INDEX [UX_core_complaint_issue_type_name] ON [core].[complaint_issue_type] ([department_id], [name])
            WHERE [is_active] = 1;
    """)
    op.execute(f"""
        CREATE TABLE [core].[complaint] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_complaint] PRIMARY KEY,
            [company_id] BIGINT NOT NULL,
            [complaint_no] NVARCHAR(30) NOT NULL,
            [department_id] BIGINT NOT NULL,
            [issue_type_id] BIGINT NOT NULL,
            [description] NVARCHAR(2000) NOT NULL,
            [status] NVARCHAR(20) NOT NULL CONSTRAINT [DF_core_complaint_status] DEFAULT (N'Open')
                CONSTRAINT [CK_core_complaint_status] CHECK ([status] IN ({_STATUSES})),
            [raised_by_user_id] BIGINT NOT NULL,
            [raised_by_employee_id] BIGINT NULL,
            [branch_id] BIGINT NULL,
            [raised_at] DATETIME2(0) NOT NULL,
            [raised_via] NVARCHAR(10) NULL
                CONSTRAINT [CK_core_complaint_raised_via] CHECK ([raised_via] IN (N'Web', N'Android', N'iOS', N'API')),
            [status_changed_at] DATETIME2(0) NULL,
            [resolved_at] DATETIME2(0) NULL,
            [closed_at] DATETIME2(0) NULL,
            {_std("complaint")},
            CONSTRAINT [UQ_core_complaint_no] UNIQUE ([company_id], [complaint_no]),
            CONSTRAINT [FK_core_complaint_company] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]),
            CONSTRAINT [FK_core_complaint_department] FOREIGN KEY ([department_id]) REFERENCES [hr].[department] ([id]),
            CONSTRAINT [FK_core_complaint_issue_type]
                FOREIGN KEY ([issue_type_id]) REFERENCES [core].[complaint_issue_type] ([id]),
            CONSTRAINT [FK_core_complaint_raised_by_user] FOREIGN KEY ([raised_by_user_id]) REFERENCES [core].[app_user] ([id]),
            CONSTRAINT [FK_core_complaint_raised_by_employee]
                FOREIGN KEY ([raised_by_employee_id]) REFERENCES [core].[employee] ([id]),
            CONSTRAINT [FK_core_complaint_branch] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id])
        );
        CREATE INDEX [IX_core_complaint_department_status] ON [core].[complaint] ([department_id], [status], [raised_at]);
        CREATE INDEX [IX_core_complaint_raised_by] ON [core].[complaint] ([raised_by_user_id], [raised_at]);
    """)
    op.execute(f"""
        CREATE TABLE [core].[complaint_history] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_complaint_history] PRIMARY KEY,
            [complaint_id] BIGINT NOT NULL,
            [action] NVARCHAR(20) NOT NULL
                CONSTRAINT [CK_core_complaint_history_action] CHECK ([action] IN (N'Raised', N'Status changed', N'Note')),
            [from_status] NVARCHAR(20) NULL,
            [to_status] NVARCHAR(20) NOT NULL CONSTRAINT [CK_core_complaint_history_to_status] CHECK ([to_status] IN ({_STATUSES})),
            [note] NVARCHAR(1000) NULL,
            [changed_by_user_id] BIGINT NOT NULL,
            [changed_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_complaint_history_changed_at] DEFAULT (SYSUTCDATETIME()),
            CONSTRAINT [FK_core_complaint_history_complaint] FOREIGN KEY ([complaint_id]) REFERENCES [core].[complaint] ([id]),
            CONSTRAINT [FK_core_complaint_history_user] FOREIGN KEY ([changed_by_user_id]) REFERENCES [core].[app_user] ([id])
        );
        CREATE INDEX [IX_core_complaint_history_complaint] ON [core].[complaint_history] ([complaint_id], [changed_at]);
    """)
    for table, description in [
        ("complaint_issue_type", "Issue types a complaint to a department can be about"),
        ("complaint", "A complaint raised by an employee to a department"),
        ("complaint_history", "Append-only history of a complaint: raised, status changes and notes"),
    ]:
        op.execute(
            f"EXEC sys.sp_addextendedproperty N'MS_Description', N'{description.replace(chr(39), chr(39) * 2)}', "
            f"N'SCHEMA', N'core', N'TABLE', N'{table}';"
        )

    # A starting issue type per department, so complaints can be raised before the Super Admin adds real ones.
    op.execute("""
        INSERT INTO [core].[complaint_issue_type] ([department_id], [name], [description], [sort_order])
        SELECT d.[id], N'Other', N'Anything not covered by the other issue types', 9999
        FROM [hr].[department] d
        WHERE d.[is_active] = 1
          AND NOT EXISTS (SELECT 1 FROM [core].[complaint_issue_type] t WHERE t.[department_id] = d.[id]);
    """)

    # Complaint numbers: one series per branch, like service calls (BHADRAK/CMP/00001). UX_core_number_series_k1
    # leaves the company out, so a company-wide (branch NULL) series could exist for one company only.
    op.execute("""
        INSERT INTO [core].[number_series] ([company_id], [branch_id], [document_type], [prefix], [next_number], [padding])
        SELECT b.[company_id], b.[id], N'COMPLAINT', b.[code] + N'/CMP/', 1, 5
        FROM [core].[branch] b
        WHERE NOT EXISTS (SELECT 1 FROM [core].[number_series] s
                          WHERE s.[branch_id] = b.[id] AND s.[document_type] = N'COMPLAINT');
    """)

    # Alerts.
    _check("alert_rule", "CK_core_alert_rule_alert_type", "alert_type", _ALERT_TYPES_AFTER)
    _check("alert", "CK_core_alert_alert_type", "alert_type", _ALERT_TYPES_AFTER)
    _check("alert", "CK_core_alert_entity_type", "entity_type", _ENTITY_TYPES_AFTER)
    op.execute("""
        INSERT INTO [core].[alert_rule]
            ([company_id], [code], [name], [description], [alert_type], [severity], [parameters], [reraise_policy],
             [is_active])
        SELECT c.[id], v.[code], v.[name], v.[description], v.[alert_type], v.[severity], N'{}', N'Never', 1
        FROM [core].[company] c
        CROSS JOIN (VALUES
            (N'COMPLAINT_RAISED', N'New complaint to a department',
             N'A complaint was raised to the department; its leaders are told.', N'CMP_COMPLAINT_RAISED', N'Warning'),
            (N'COMPLAINT_UPDATED', N'Complaint status changed',
             N'The department changed the status of a complaint or added a note; the person who raised it is told.',
             N'CMP_COMPLAINT_UPDATED', N'Info')
        ) v([code], [name], [description], [alert_type], [severity])
        WHERE c.[id] = (SELECT MIN([id]) FROM [core].[company])
          AND NOT EXISTS (SELECT 1 FROM [core].[alert_rule] ar WHERE ar.[code] = v.[code]);
    """)

    # Permissions.
    values = ", ".join(f"(N'{code}', N'{description}')" for code, description in _PERMISSIONS)
    op.execute(f"""
        INSERT INTO [core].[permission] ([code], [module], [description])
        SELECT v.[code], N'Core', v.[description]
        FROM (VALUES {values}) v([code], [description])
        WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] p WHERE p.[code] = v.[code]);
    """)  # noqa: S608 (constants above)
    # Every role raises complaints; the Administrator manages all of them.
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] = N'core.complaint.raise'
                                   OR (p.[code] = N'core.complaint.manage_all' AND r.[code] = N'ADMIN')
        WHERE NOT EXISTS (
            SELECT 1 FROM [core].[role_permission] rp WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]
        );
    """)


def downgrade() -> None:
    codes = ", ".join(f"N'{code}'" for code, _ in _PERMISSIONS)
    op.execute(f"""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] IN ({codes});
        DELETE FROM [core].[permission] WHERE [code] IN ({codes});
    """)  # noqa: S608 (constants above)
    op.execute("""
        DELETE FROM [core].[alert_recipient] WHERE [alert_id] IN
            (SELECT [id] FROM [core].[alert] WHERE [alert_type] IN (N'CMP_COMPLAINT_RAISED', N'CMP_COMPLAINT_UPDATED'));
        DELETE FROM [core].[alert] WHERE [alert_type] IN (N'CMP_COMPLAINT_RAISED', N'CMP_COMPLAINT_UPDATED');
        DELETE FROM [core].[alert_rule_recipient] WHERE [alert_rule_id] IN
            (SELECT [id] FROM [core].[alert_rule] WHERE [alert_type] IN (N'CMP_COMPLAINT_RAISED', N'CMP_COMPLAINT_UPDATED'));
        DELETE FROM [core].[alert_rule] WHERE [alert_type] IN (N'CMP_COMPLAINT_RAISED', N'CMP_COMPLAINT_UPDATED');
    """)
    _check("alert", "CK_core_alert_entity_type", "entity_type", _ENTITY_TYPES_BEFORE)
    _check("alert", "CK_core_alert_alert_type", "alert_type", _ALERT_TYPES_BEFORE)
    _check("alert_rule", "CK_core_alert_rule_alert_type", "alert_type", _ALERT_TYPES_BEFORE)
    op.execute("""
        DELETE FROM [core].[attachment] WHERE [entity_type] = N'core.complaint';
        DELETE FROM [core].[number_series] WHERE [document_type] = N'COMPLAINT';
        DROP TABLE [core].[complaint_history];
        DROP TABLE [core].[complaint];
        DROP TABLE [core].[complaint_issue_type];
    """)
