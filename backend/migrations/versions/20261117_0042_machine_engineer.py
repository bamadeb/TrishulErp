"""Service engineer attached to a machine: new service calls on it are assigned to them.

  * svc.machine_engineer   one row per machine with an engineer attached (UNIQUE machine_unit_id).
  * Pre-filled from the ASC register: a machine gets the engineer ("SE") of its latest ASC that names
    an active employee. Machines without one stay empty until set on the machine screen.

Revision ID: 0042_machine_engineer
Revises: 0041_asc_one_visit_per_day
Created: 2026-11-17
"""

from alembic import op

revision = "0042_machine_engineer"
down_revision = "0041_asc_one_visit_per_day"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE [svc].[machine_engineer] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_machine_engineer] PRIMARY KEY,
            [machine_unit_id] BIGINT NOT NULL,
            [engineer_employee_id] BIGINT NOT NULL,
            [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_machine_engineer_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [updated_at] DATETIME2(0) NULL,
            [updated_by_user_id] BIGINT NULL,
            CONSTRAINT [UQ_svc_machine_engineer_machine_unit_id] UNIQUE ([machine_unit_id]),
            CONSTRAINT [FK_svc_machine_engineer_machine_unit_id]
                FOREIGN KEY ([machine_unit_id]) REFERENCES [core].[machine_unit] ([id]),
            CONSTRAINT [FK_svc_machine_engineer_engineer_employee_id]
                FOREIGN KEY ([engineer_employee_id]) REFERENCES [core].[employee] ([id])
        );
    """)
    op.execute("""
        CREATE INDEX [IX_svc_machine_engineer_engineer_employee_id]
            ON [svc].[machine_engineer] ([engineer_employee_id]);
    """)
    op.execute("""
        EXEC sys.sp_addextendedproperty N'MS_Description',
            N'Service engineer attached to a machine: new service calls on it are assigned to them',
            N'SCHEMA', N'svc', N'TABLE', N'machine_engineer';
    """)
    op.execute("""
        INSERT INTO [svc].[machine_engineer] ([machine_unit_id], [engineer_employee_id])
        SELECT x.[machine_unit_id], x.[engineer_employee_id]
        FROM (
            SELECT cc.[machine_unit_id], sc.[engineer_employee_id],
                   ROW_NUMBER() OVER (PARTITION BY cc.[machine_unit_id] ORDER BY sc.[end_date] DESC, sc.[id] DESC) AS [n]
            FROM [svc].[service_contract] sc
            JOIN [svc].[contract_coverage] cc ON cc.[service_contract_id] = sc.[id] AND cc.[is_active] = 1
            JOIN [core].[employee] e ON e.[id] = sc.[engineer_employee_id] AND e.[is_active] = 1
            WHERE sc.[contract_type] = N'ASC' AND sc.[is_active] = 1 AND sc.[status] <> N'Cancelled'
        ) x
        WHERE x.[n] = 1;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE [svc].[machine_engineer];")
