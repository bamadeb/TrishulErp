"""Company name of a brand, and the permission to manage brands.

  * core.principal.company_id     the company (core.company) behind the brand; its name is shown beside
    the brand name in every brand dropdown.
  * core.brand.manage             open the Companies & brands screen: add and change brands, mark them
    active or inactive. ADMIN only.

Revision ID: 0043_brand_company_name
Revises: 0042_machine_engineer
Created: 2026-11-21
"""

from alembic import op

revision = "0043_brand_company_name"
down_revision = "0042_machine_engineer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        IF COL_LENGTH('core.principal', 'company_id') IS NULL
            ALTER TABLE [core].[principal] ADD [company_id] BIGINT NULL
                CONSTRAINT [FK_core_principal_company_id] FOREIGN KEY REFERENCES [core].[company] ([id]);
    """)
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.extended_properties WHERE name = N'MS_Description'
                       AND major_id = OBJECT_ID(N'core.principal')
                       AND minor_id = COLUMNPROPERTY(OBJECT_ID(N'core.principal'), N'company_id', 'ColumnId'))
            EXEC sys.sp_addextendedproperty N'MS_Description',
            N'Company behind the brand, shown beside the brand name',
            N'SCHEMA', N'core', N'TABLE', N'principal', N'COLUMN', N'company_id';
    """)
    op.execute("""
        INSERT INTO [core].[permission] ([code], [module], [description])
        SELECT N'core.brand.manage', N'Admin', N'Add and change companies and brands, mark them active or inactive'
        WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] WHERE [code] = N'core.brand.manage');
    """)
    op.execute("""
        INSERT INTO [core].[role_permission] ([role_id], [permission_id])
        SELECT r.[id], p.[id]
        FROM [core].[role] r
        JOIN [core].[permission] p ON p.[code] = N'core.brand.manage'
        WHERE r.[code] = N'ADMIN'
          AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                          WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
    """)


def downgrade() -> None:
    op.execute("""
        DELETE rp FROM [core].[role_permission] rp
        JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
        WHERE p.[code] = N'core.brand.manage';
        DELETE FROM [core].[permission] WHERE [code] = N'core.brand.manage';
    """)
    op.execute("""
        EXEC sys.sp_dropextendedproperty N'MS_Description',
            N'SCHEMA', N'core', N'TABLE', N'principal', N'COLUMN', N'company_id';
    """)
    op.execute("ALTER TABLE [core].[principal] DROP CONSTRAINT [FK_core_principal_company_id], COLUMN [company_id];")
