"""ASC master: contracts per machine, the plan price list, Excel import, and who may use them.

svc.service_contract / svc.contract_coverage / svc.contract_plan already exist (phase 1 + gap remediation);
this adds what the team's ASC register (Excel) records and the screens need:

  * svc.service_contract  branch, book no, OEM enrol / contract id, money receipt (MR) no, invoice ref,
                          new or renewal, and the service engineer (linked when the name matches an employee,
                          kept as text either way).
  * svc.contract_plan     machine_class (the offer letter's price rows) and gst_pct; price excludes GST.
  * 14 Tata Hitachi ASC plans from the offer letter of 14-05-2026: 6 months / 6 visits and
    12 months / 12 visits for each machine class. 5% parts discount, labour and travel covered.
  * number series SERVICE_CONTRACT per active branch: <BRANCH CODE>/ASC/00001.
  * permissions  svc.contract.view    see ASC contracts and plans (ADMIN, BACK_OFFICE, MANAGEMENT, TEAM_LEAD)
                 svc.contract.import  upload the ASC Excel register (ADMIN)
                 svc.contract.manage  already exists (create / renew contracts); now also maintains plans.

Revision ID: 0016_asc_master
Revises: 0015_byd_import_log
Created: 2026-11-03
"""

import sqlalchemy as sa
from alembic import op

revision = "0016_asc_master"
down_revision = "0015_byd_import_log"
branch_labels = None
depends_on = None

_GRANT = sa.text("""
    INSERT INTO [core].[role_permission] ([role_id], [permission_id])
    SELECT r.[id], p.[id]
    FROM [core].[role] r
    JOIN [core].[permission] p ON p.[code] = :permission
    WHERE r.[code] = :role
      AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                      WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
""")

_PLAN = sa.text("""
    INSERT INTO [svc].[contract_plan]
        ([code], [name], [principal_id], [contract_type], [duration_months], [visits_included],
         [visit_frequency_months], [price], [gst_pct], [machine_class], [covers_labour], [covers_parts],
         [covers_travel], [parts_discount_pct], [service_priority], [terms])
    SELECT :code, :name, p.[id], N'ASC', :months, :visits, 1, :price, 18, :machine_class, 1, 0, 1, 5, N'High',
           N'Periodical visits by our service engineers. First priority to ASC calls. '
           + N'5% discount on spare parts (except scheme items).'
    FROM [core].[principal] p
    WHERE p.[code] = N'TATA_HITACHI'
      AND NOT EXISTS (SELECT 1 FROM [svc].[contract_plan] cp WHERE cp.[code] = :code);
""")

# (code suffix, machine class, 12-month price, 6-month price) - amounts before GST, from the offer letter.
_PRICES = (
    ("7T", "Up to 7 Ton / BHL", 30000, 20000),
    ("10T", "10 Ton", 32000, 20000),
    ("10T-ZX", "10 Ton (ZX)", 32000, 20000),
    ("TWL", "TWL", 36000, 24000),
    ("20T", "20 Ton", 45000, 28000),
    ("20T-ZX", "20 Ton (ZX)", 45000, 28000),
    ("35T-ZX", "35 Ton (ZX)", 50000, 35000),
)

_PERMISSIONS = ("svc.contract.view", "svc.contract.import")


def upgrade() -> None:
    op.execute("""
        ALTER TABLE [svc].[service_contract] ADD
            [branch_id] BIGINT NULL,
            [book_no] NVARCHAR(20) NULL,
            [oem_contract_id] NVARCHAR(40) NULL,
            [receipt_no] NVARCHAR(60) NULL,
            [invoice_ref] NVARCHAR(60) NULL,
            [is_renewal] BIT NOT NULL CONSTRAINT [DF_svc_service_contract_is_renewal] DEFAULT (0),
            [engineer_employee_id] BIGINT NULL,
            [engineer_name] NVARCHAR(100) NULL;
    """)
    op.execute("""
        ALTER TABLE [svc].[service_contract] ADD
            CONSTRAINT [FK_svc_service_contract_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]),
            CONSTRAINT [FK_svc_service_contract_engineer_employee_id]
                FOREIGN KEY ([engineer_employee_id]) REFERENCES [core].[employee] ([id]);
        CREATE INDEX [IX_svc_service_contract_branch_id] ON [svc].[service_contract] ([branch_id]);
        CREATE INDEX [IX_svc_service_contract_engineer_employee_id] ON [svc].[service_contract] ([engineer_employee_id]);
        CREATE INDEX [IX_svc_service_contract_end_date] ON [svc].[service_contract] ([end_date]);
    """)
    op.execute("""
        ALTER TABLE [svc].[contract_plan] ADD
            [machine_class] NVARCHAR(40) NULL,
            [gst_pct] DECIMAL(5, 2) NULL;
    """)
    for suffix, machine_class, price_12, price_6 in _PRICES:
        for months, price in ((12, price_12), (6, price_6)):
            op.execute(
                _PLAN.bindparams(
                    code=f"ASC{months}-{suffix}",
                    name=f"ASC {months} months - {machine_class}",
                    months=months,
                    visits=months,
                    price=price,
                    machine_class=machine_class,
                )
            )
    op.execute("""
        INSERT INTO [core].[number_series]
            ([company_id], [document_type], [branch_id], [principal_id], [fiscal_year_id],
             [prefix], [next_number], [padding], [suffix])
        SELECT b.[company_id], N'SERVICE_CONTRACT', b.[id], NULL, NULL, b.[code] + N'/ASC/', 1, 5, NULL
        FROM [core].[branch] b
        WHERE b.[is_active] = 1
          AND NOT EXISTS (SELECT 1 FROM [core].[number_series] ns
                          WHERE ns.[document_type] = N'SERVICE_CONTRACT' AND ns.[branch_id] = b.[id]
                            AND ns.[principal_id] IS NULL AND ns.[fiscal_year_id] IS NULL);
    """)
    op.execute("""
        INSERT INTO [core].[permission] ([code], [module], [description])
        SELECT v.[code], v.[module], v.[description]
        FROM (VALUES
            (N'svc.contract.view', N'Service', N'See ASC contracts, plans and a machine''s ASC status'),
            (N'svc.contract.import', N'Service', N'Upload the ASC register (Excel)')
        ) v([code], [module], [description])
        WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] p WHERE p.[code] = v.[code]);

        UPDATE [core].[permission] SET [description] = N'Create, renew and cancel ASC contracts; maintain ASC plans'
        WHERE [code] = N'svc.contract.manage';
    """)
    for role in ("ADMIN", "BACK_OFFICE", "MANAGEMENT", "TEAM_LEAD"):
        op.execute(_GRANT.bindparams(permission="svc.contract.view", role=role))
    op.execute(_GRANT.bindparams(permission="svc.contract.import", role="ADMIN"))
    op.execute(_GRANT.bindparams(permission="svc.contract.manage", role="ADMIN"))


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] IN (N'svc.contract.view', N'svc.contract.import');
        DELETE FROM [core].[permission] WHERE [code] IN (N'svc.contract.view', N'svc.contract.import');
        UPDATE [core].[permission] SET [description] = N'Create / renew ASC and AMC contracts'
        WHERE [code] = N'svc.contract.manage';
    """)
    op.execute("""
        DELETE FROM [core].[number_series]
        WHERE [document_type] = N'SERVICE_CONTRACT' AND [next_number] = 1;
    """)
    op.execute("""
        DELETE FROM [svc].[contract_plan]
        WHERE [code] LIKE N'ASC%' AND [machine_class] IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM [svc].[service_contract] sc WHERE sc.[contract_plan_id] = [contract_plan].[id]);
    """)
    op.execute("""
        ALTER TABLE [svc].[contract_plan] DROP COLUMN [machine_class], [gst_pct];
    """)
    op.execute("""
        DROP INDEX [IX_svc_service_contract_end_date] ON [svc].[service_contract];
        DROP INDEX [IX_svc_service_contract_engineer_employee_id] ON [svc].[service_contract];
        DROP INDEX [IX_svc_service_contract_branch_id] ON [svc].[service_contract];
        ALTER TABLE [svc].[service_contract] DROP CONSTRAINT [FK_svc_service_contract_engineer_employee_id];
        ALTER TABLE [svc].[service_contract] DROP CONSTRAINT [FK_svc_service_contract_branch_id];
        ALTER TABLE [svc].[service_contract] DROP CONSTRAINT [DF_svc_service_contract_is_renewal];
        ALTER TABLE [svc].[service_contract] DROP COLUMN
            [branch_id], [book_no], [oem_contract_id], [receipt_no], [invoice_ref], [is_renewal],
            [engineer_employee_id], [engineer_name];
    """)
