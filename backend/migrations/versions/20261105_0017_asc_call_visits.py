"""ASC visits counted from completed service calls, and the ASC Manager who counts them.

  * svc.contract_visit    how many ASC visits one service call used, on which contract. One row per call;
                          svc.service_contract.visits_used stays the contract's total (it also holds the
                          visits the Excel register brought in) and moves with these rows.
  * permission svc.contract.visit   record the visits of a completed service call against its ASC.
  * role ASC_MANAGER      svc.contract.visit, svc.contract.view and svc.call.view (to open the call being
                          counted). ADMIN also gets svc.contract.visit.

Revision ID: 0017_asc_call_visits
Revises: 0010_organization
Created: 2026-11-05
"""

from alembic import op

revision = "0017_asc_call_visits"
down_revision = "0010_organization"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE [svc].[contract_visit] (
            [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_contract_visit] PRIMARY KEY,
            [service_contract_id] BIGINT NOT NULL,
            [service_call_id] BIGINT NOT NULL,
            [visits] SMALLINT NOT NULL,
            [remarks] NVARCHAR(300) NULL,
            [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_contract_visit_created_at] DEFAULT (SYSUTCDATETIME()),
            [created_by_user_id] BIGINT NULL,
            [updated_at] DATETIME2(0) NULL,
            [updated_by_user_id] BIGINT NULL,
            CONSTRAINT [UQ_svc_contract_visit_service_call_id] UNIQUE ([service_call_id]),
            CONSTRAINT [CK_svc_contract_visit_visits] CHECK ([visits] >= 1),
            CONSTRAINT [FK_svc_contract_visit_service_contract_id]
                FOREIGN KEY ([service_contract_id]) REFERENCES [svc].[service_contract] ([id]),
            CONSTRAINT [FK_svc_contract_visit_service_call_id]
                FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id])
        );
    """)
    op.execute("""
        CREATE INDEX [IX_svc_contract_visit_service_contract_id]
            ON [svc].[contract_visit] ([service_contract_id]);
    """)
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM [core].[permission] WHERE [code] = N'svc.contract.visit')
            INSERT INTO [core].[permission] ([code], [module], [description])
            VALUES (N'svc.contract.visit', N'Service', N'Record the visits of a completed service call against its ASC');
    """)
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM [core].[role] WHERE [code] = N'ASC_MANAGER')
            INSERT INTO [core].[role] ([code], [name], [description], [is_system])
            VALUES (N'ASC_MANAGER', N'ASC Manager', N'Counts ASC visits from completed service calls', 1);
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM (VALUES
            (N'ASC_MANAGER', N'svc.contract.visit'),
            (N'ASC_MANAGER', N'svc.contract.view'),
            (N'ASC_MANAGER', N'svc.call.view'),
            (N'ADMIN', N'svc.contract.visit')
        ) v([role_code], [permission_code])
        JOIN [core].[role] r ON r.[code] = v.[role_code]
        JOIN [core].[permission] p ON p.[code] = v.[permission_code]
        WHERE NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    """Visits already added to svc.service_contract.visits_used stay in that total."""
    op.execute("""
        DELETE ur FROM [core].[user_role] ur
        JOIN [core].[role] r ON r.[id] = ur.[role_id]
        WHERE r.[code] = N'ASC_MANAGER';
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[role] r ON r.[id] = rp.[role_id]
        WHERE r.[code] = N'ASC_MANAGER';
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] = N'svc.contract.visit';
        DELETE FROM [core].[role] WHERE [code] = N'ASC_MANAGER';
        DELETE FROM [core].[permission] WHERE [code] = N'svc.contract.visit';
    """)
    op.execute("DROP TABLE [svc].[contract_visit];")
