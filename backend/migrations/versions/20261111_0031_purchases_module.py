"""Purchases: purchase orders with approval, GRN against PO, supplier invoices, payments, credit notes and
allocations. The tables exist since v3 (pur.*); this adds what the screens and rules need.

    pur.purchase_order       status 'Received' (fully received); other_charges, CGST/SGST/IGST split;
                             who submitted / approved / closed it and when; approval_note, close_reason
    pur.purchase_order_line  gst_pct
    pur.grn_line             qty_invoiced (a GRN line is invoiced once; the invoice never adds stock again)
    pur.supplier_invoice     other_charges, remarks, is_direct (no GRN behind it), posted_by_user_id
    pur.supplier_invoice_line gst_pct, discount_pct
    pur.supplier_payment     bank_name, cheque_date, remarks, posted_by_user_id
    pur.debit_note           (a supplier credit note) note_type, supplier's note no / date, branch, location
                             (purchase returns take stock out there), CGST/SGST/IGST, remarks, posted_by_user_id
    pur.debit_note_line      item optional (price differences), description, gst_pct, taxable_value,
                             the GRN batch and rack a returned item leaves from
    pur.supplier_allocation  allocated_by_user_id, reversed_at / reversed_by_user_id / reversal_reason
                             (a reversed allocation is kept, is_active = 0)
    core.supplier            contact_person, opening_balance (+ = we owe), opening_balance_date
    core.payment_terms       IMMEDIATE, NET15, NET30, NET45, NET60 when the table is empty

Number series per active branch: PURCHASE_ORDER <BRANCH>/PO/, SUPPLIER_INVOICE <BRANCH>/PI/,
SUPPLIER_PAYMENT <BRANCH>/PV/, SUPPLIER_CREDIT_NOTE <BRANCH>/SCN/.

Permissions (pur.po.approve already exists):
    pur.supplier.view / pur.supplier.manage   suppliers
    pur.po.view / pur.po.manage               purchase orders
    pur.po.close                              close or cancel an outstanding purchase order
    pur.grn.manage                            receive goods (moved from inv.grn.manage, which keeps opening stock)
    pur.account.view                          supplier invoices, payments, credit notes, statements, allocations
    pur.invoice.manage                        record supplier invoices against GRNs
    pur.invoice.direct                        invoices without a GRN (direct, or against a PO not yet received)
    pur.payment.manage                        payments to suppliers
    pur.credit_note.manage                    supplier credit notes and purchase returns
    pur.allocation.manage / pur.allocation.reverse

Idempotent: every statement checks first. All these tables are empty on RDS (2026-11-10).
The DDL is written out in full (no f-strings): scripts/generate_models.py reads op.execute literals.

Revision ID: 0031_purchases_module
Revises: 0030_inventory_module
Created: 2026-11-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0031_purchases_module"
down_revision = "0030_inventory_module"
branch_labels = None
depends_on = None

_PERMISSIONS = (
    ("pur.supplier.view", "See suppliers, their balances and transactions"),
    ("pur.supplier.manage", "Add and change suppliers"),
    ("pur.po.view", "See purchase orders and what is still to be received"),
    ("pur.po.manage", "Create and change purchase orders and send them for approval"),
    ("pur.po.close", "Close or cancel an outstanding purchase order"),
    ("pur.grn.manage", "Receive goods (GRN), against a purchase order or direct"),
    ("pur.account.view", "See supplier invoices, payments, credit notes, statements and allocations"),
    ("pur.invoice.manage", "Record supplier invoices against goods received"),
    ("pur.invoice.direct", "Record supplier invoices without a GRN"),
    ("pur.payment.manage", "Record payments to suppliers"),
    ("pur.credit_note.manage", "Record supplier credit notes and purchase returns"),
    ("pur.allocation.manage", "Allocate payments and credit notes to supplier invoices"),
    ("pur.allocation.reverse", "Reverse an allocation"),
)
_ALL = [code for code, _ in _PERMISSIONS] + ["pur.po.approve"]
_GRANTS = {
    "ADMIN": _ALL,
    "PURCHASE": [
        "pur.supplier.view", "pur.supplier.manage", "pur.po.view", "pur.po.manage", "pur.po.close",
        "pur.grn.manage", "pur.account.view", "pur.invoice.manage", "pur.credit_note.manage",
    ],
    "ACCOUNTS": [
        "pur.supplier.view", "pur.supplier.manage", "pur.po.view", "pur.account.view", "pur.invoice.manage",
        "pur.invoice.direct", "pur.payment.manage", "pur.credit_note.manage", "pur.allocation.manage",
        "pur.allocation.reverse",
    ],
    "INVENTORY": ["pur.supplier.view", "pur.po.view", "pur.grn.manage"],
    "WAREHOUSE": ["pur.supplier.view", "pur.po.view", "pur.grn.manage"],
    "MANAGEMENT": ["pur.supplier.view", "pur.po.view", "pur.account.view"],
}  # fmt: skip
_SERIES = (
    ("PURCHASE_ORDER", "/PO/"),
    ("SUPPLIER_INVOICE", "/PI/"),
    ("SUPPLIER_PAYMENT", "/PV/"),
    ("SUPPLIER_CREDIT_NOTE", "/SCN/"),
)
_TERMS = (
    ("IMMEDIATE", "Immediate", 0),
    ("NET15", "15 days", 15),
    ("NET30", "30 days", 30),
    ("NET45", "45 days", 45),
    ("NET60", "60 days", 60),
)

_GRANT = sa.text("""
    INSERT INTO [core].[role_permission] ([role_id], [permission_id])
    SELECT r.[id], p.[id]
    FROM [core].[role] r
    JOIN [core].[permission] p ON p.[code] = :permission
    WHERE r.[code] = :role
      AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp
                      WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);
""")
_PERMISSION = sa.text("""
    INSERT INTO [core].[permission] ([code], [module], [description])
    SELECT :code, N'Purchase', :description
    WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] WHERE [code] = :code);
""")
_BRANCH_SERIES = sa.text("""
    INSERT INTO [core].[number_series]
        ([company_id], [document_type], [branch_id], [principal_id], [fiscal_year_id],
         [prefix], [next_number], [padding], [suffix])
    SELECT b.[company_id], :document_type, b.[id], NULL, NULL, b.[code] + :infix, 1, 5, NULL
    FROM [core].[branch] b
    WHERE b.[is_active] = 1
      AND NOT EXISTS (SELECT 1 FROM [core].[number_series] ns
                      WHERE ns.[document_type] = :document_type AND ns.[branch_id] = b.[id]
                        AND ns.[principal_id] IS NULL AND ns.[fiscal_year_id] IS NULL);
""")
_TERM = sa.text("""
    INSERT INTO [core].[payment_terms] ([code], [description], [days_before_due])
    SELECT :code, :description, :days
    WHERE NOT EXISTS (SELECT 1 FROM [core].[payment_terms] WHERE [code] = :code);
""")
# Whoever may receive goods today (inv.grn.manage) keeps that right under the purchases permission.
_CARRY_GRN = sa.text("""
    INSERT INTO [core].[role_permission] ([role_id], [permission_id])
    SELECT rp.[role_id], np.[id]
    FROM [core].[role_permission] rp
    JOIN [core].[permission] op ON op.[id] = rp.[permission_id] AND op.[code] = N'inv.grn.manage'
    JOIN [core].[permission] np ON np.[code] = N'pur.grn.manage'
    WHERE NOT EXISTS (SELECT 1 FROM [core].[role_permission] x
                      WHERE x.[role_id] = rp.[role_id] AND x.[permission_id] = np.[id]);
""")


def upgrade() -> None:
    op.execute("""
        IF OBJECT_ID(N'[pur].[CK_pur_purchase_order_status]', N'C') IS NOT NULL
            ALTER TABLE [pur].[purchase_order] DROP CONSTRAINT [CK_pur_purchase_order_status];
    """)
    op.execute("""
        ALTER TABLE [pur].[purchase_order] ADD CONSTRAINT [CK_pur_purchase_order_status] CHECK ([status] IN (N'Draft', N'Pending approval', N'Approved', N'Sent', N'Part received', N'Received', N'Closed', N'Cancelled'));
    """)
    op.execute("""
        IF COL_LENGTH(N'pur.purchase_order', N'other_charges') IS NULL
        BEGIN
            ALTER TABLE [pur].[purchase_order] ADD [other_charges] DECIMAL(18,2) NOT NULL
                CONSTRAINT [DF_pur_purchase_order_other_charges] DEFAULT (0);
            ALTER TABLE [pur].[purchase_order] ADD [cgst] DECIMAL(18,2) NOT NULL
                CONSTRAINT [DF_pur_purchase_order_cgst] DEFAULT (0);
            ALTER TABLE [pur].[purchase_order] ADD [sgst] DECIMAL(18,2) NOT NULL
                CONSTRAINT [DF_pur_purchase_order_sgst] DEFAULT (0);
            ALTER TABLE [pur].[purchase_order] ADD [igst] DECIMAL(18,2) NOT NULL
                CONSTRAINT [DF_pur_purchase_order_igst] DEFAULT (0);
            ALTER TABLE [pur].[purchase_order] ADD [submitted_at] DATETIME2(0) NULL;
            ALTER TABLE [pur].[purchase_order] ADD [submitted_by_user_id] BIGINT NULL;
            ALTER TABLE [pur].[purchase_order] ADD [approved_at] DATETIME2(0) NULL;
            ALTER TABLE [pur].[purchase_order] ADD [approved_by_user_id] BIGINT NULL;
            ALTER TABLE [pur].[purchase_order] ADD [approval_note] NVARCHAR(300) NULL;
            ALTER TABLE [pur].[purchase_order] ADD [closed_at] DATETIME2(0) NULL;
            ALTER TABLE [pur].[purchase_order] ADD [closed_by_user_id] BIGINT NULL;
            ALTER TABLE [pur].[purchase_order] ADD [close_reason] NVARCHAR(300) NULL;
            ALTER TABLE [pur].[purchase_order] ADD CONSTRAINT [FK_pur_purchase_order_submitted_by_user_id]
                FOREIGN KEY ([submitted_by_user_id]) REFERENCES [core].[app_user]([id]);
            ALTER TABLE [pur].[purchase_order] ADD CONSTRAINT [FK_pur_purchase_order_approved_by_user_id]
                FOREIGN KEY ([approved_by_user_id]) REFERENCES [core].[app_user]([id]);
            ALTER TABLE [pur].[purchase_order] ADD CONSTRAINT [FK_pur_purchase_order_closed_by_user_id]
                FOREIGN KEY ([closed_by_user_id]) REFERENCES [core].[app_user]([id]);
        END
    """)
    op.execute("""
        IF COL_LENGTH(N'pur.purchase_order_line', N'gst_pct') IS NULL
            ALTER TABLE [pur].[purchase_order_line] ADD [gst_pct] DECIMAL(5,2) NOT NULL
                CONSTRAINT [DF_pur_purchase_order_line_gst_pct] DEFAULT (0);
    """)
    op.execute("""
        IF COL_LENGTH(N'pur.grn_line', N'qty_invoiced') IS NULL
            ALTER TABLE [pur].[grn_line] ADD [qty_invoiced] DECIMAL(18,3) NOT NULL
                CONSTRAINT [DF_pur_grn_line_qty_invoiced] DEFAULT (0);
    """)
    op.execute("""
        IF COL_LENGTH(N'pur.supplier_invoice', N'other_charges') IS NULL
        BEGIN
            ALTER TABLE [pur].[supplier_invoice] ADD [other_charges] DECIMAL(18,2) NOT NULL
                CONSTRAINT [DF_pur_supplier_invoice_other_charges] DEFAULT (0);
            ALTER TABLE [pur].[supplier_invoice] ADD [is_direct] BIT NOT NULL
                CONSTRAINT [DF_pur_supplier_invoice_is_direct] DEFAULT (0);
            ALTER TABLE [pur].[supplier_invoice] ADD [remarks] NVARCHAR(300) NULL;
            ALTER TABLE [pur].[supplier_invoice] ADD [posted_by_user_id] BIGINT NULL;
            ALTER TABLE [pur].[supplier_invoice] ADD CONSTRAINT [FK_pur_supplier_invoice_posted_by_user_id]
                FOREIGN KEY ([posted_by_user_id]) REFERENCES [core].[app_user]([id]);
        END
    """)
    op.execute("""
        IF COL_LENGTH(N'pur.supplier_invoice_line', N'gst_pct') IS NULL
        BEGIN
            ALTER TABLE [pur].[supplier_invoice_line] ADD [gst_pct] DECIMAL(5,2) NOT NULL
                CONSTRAINT [DF_pur_supplier_invoice_line_gst_pct] DEFAULT (0);
            ALTER TABLE [pur].[supplier_invoice_line] ADD [discount_pct] DECIMAL(5,2) NOT NULL
                CONSTRAINT [DF_pur_supplier_invoice_line_discount_pct] DEFAULT (0);
        END
    """)
    op.execute("""
        IF COL_LENGTH(N'pur.supplier_payment', N'bank_name') IS NULL
        BEGIN
            ALTER TABLE [pur].[supplier_payment] ADD [bank_name] NVARCHAR(100) NULL;
            ALTER TABLE [pur].[supplier_payment] ADD [cheque_date] DATE NULL;
            ALTER TABLE [pur].[supplier_payment] ADD [remarks] NVARCHAR(300) NULL;
            ALTER TABLE [pur].[supplier_payment] ADD [posted_by_user_id] BIGINT NULL;
            ALTER TABLE [pur].[supplier_payment] ADD CONSTRAINT [FK_pur_supplier_payment_posted_by_user_id]
                FOREIGN KEY ([posted_by_user_id]) REFERENCES [core].[app_user]([id]);
        END
    """)
    op.execute("""
        IF COL_LENGTH(N'pur.debit_note', N'note_type') IS NULL
        BEGIN
            ALTER TABLE [pur].[debit_note] ADD [note_type] NVARCHAR(30) NOT NULL
                CONSTRAINT [DF_pur_debit_note_note_type] DEFAULT (N'Other');
            ALTER TABLE [pur].[debit_note] ADD CONSTRAINT [CK_pur_debit_note_note_type]
                CHECK ([note_type] IN (N'Purchase return', N'Damaged goods', N'Price difference', N'Other'));
            ALTER TABLE [pur].[debit_note] ADD [supplier_note_no] NVARCHAR(40) NULL;
            ALTER TABLE [pur].[debit_note] ADD [supplier_note_date] DATE NULL;
            ALTER TABLE [pur].[debit_note] ADD [branch_id] BIGINT NULL;
            ALTER TABLE [pur].[debit_note] ADD [location_id] BIGINT NULL;
            ALTER TABLE [pur].[debit_note] ADD [cgst] DECIMAL(18,2) NOT NULL
                CONSTRAINT [DF_pur_debit_note_cgst] DEFAULT (0);
            ALTER TABLE [pur].[debit_note] ADD [sgst] DECIMAL(18,2) NOT NULL
                CONSTRAINT [DF_pur_debit_note_sgst] DEFAULT (0);
            ALTER TABLE [pur].[debit_note] ADD [igst] DECIMAL(18,2) NOT NULL
                CONSTRAINT [DF_pur_debit_note_igst] DEFAULT (0);
            ALTER TABLE [pur].[debit_note] ADD [remarks] NVARCHAR(300) NULL;
            ALTER TABLE [pur].[debit_note] ADD [posted_by_user_id] BIGINT NULL;
            ALTER TABLE [pur].[debit_note] ADD CONSTRAINT [FK_pur_debit_note_branch_id]
                FOREIGN KEY ([branch_id]) REFERENCES [core].[branch]([id]);
            ALTER TABLE [pur].[debit_note] ADD CONSTRAINT [FK_pur_debit_note_location_id]
                FOREIGN KEY ([location_id]) REFERENCES [core].[location]([id]);
            ALTER TABLE [pur].[debit_note] ADD CONSTRAINT [FK_pur_debit_note_posted_by_user_id]
                FOREIGN KEY ([posted_by_user_id]) REFERENCES [core].[app_user]([id]);
        END
    """)
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE [name] = N'UX_pur_debit_note_supplier_note'
                       AND [object_id] = OBJECT_ID(N'[pur].[debit_note]'))
            CREATE UNIQUE NONCLUSTERED INDEX [UX_pur_debit_note_supplier_note]
                ON [pur].[debit_note] ([supplier_id], [supplier_note_no]) WHERE [supplier_note_no] IS NOT NULL;
    """)
    op.execute("""
        IF COL_LENGTH(N'pur.debit_note_line', N'gst_pct') IS NULL
        BEGIN
            ALTER TABLE [pur].[debit_note_line] ALTER COLUMN [item_id] BIGINT NULL;
            ALTER TABLE [pur].[debit_note_line] ADD [description] NVARCHAR(200) NULL;
            ALTER TABLE [pur].[debit_note_line] ADD [gst_pct] DECIMAL(5,2) NOT NULL
                CONSTRAINT [DF_pur_debit_note_line_gst_pct] DEFAULT (0);
            ALTER TABLE [pur].[debit_note_line] ADD [taxable_value] DECIMAL(18,2) NOT NULL
                CONSTRAINT [DF_pur_debit_note_line_taxable_value] DEFAULT (0);
            ALTER TABLE [pur].[debit_note_line] ADD [grn_line_id] BIGINT NULL;
            ALTER TABLE [pur].[debit_note_line] ADD [stock_lot_id] BIGINT NULL;
            ALTER TABLE [pur].[debit_note_line] ADD [bin_id] BIGINT NULL;
            ALTER TABLE [pur].[debit_note_line] ADD CONSTRAINT [FK_pur_debit_note_line_grn_line_id]
                FOREIGN KEY ([grn_line_id]) REFERENCES [pur].[grn_line]([id]);
            ALTER TABLE [pur].[debit_note_line] ADD CONSTRAINT [FK_pur_debit_note_line_stock_lot_id]
                FOREIGN KEY ([stock_lot_id]) REFERENCES [inv].[stock_lot]([id]);
            ALTER TABLE [pur].[debit_note_line] ADD CONSTRAINT [FK_pur_debit_note_line_bin_id]
                FOREIGN KEY ([bin_id]) REFERENCES [inv].[bin]([id]);
        END
    """)
    op.execute("""
        IF COL_LENGTH(N'pur.supplier_allocation', N'reversed_at') IS NULL
        BEGIN
            ALTER TABLE [pur].[supplier_allocation] ADD [allocated_by_user_id] BIGINT NULL;
            ALTER TABLE [pur].[supplier_allocation] ADD [reversed_at] DATETIME2(0) NULL;
            ALTER TABLE [pur].[supplier_allocation] ADD [reversed_by_user_id] BIGINT NULL;
            ALTER TABLE [pur].[supplier_allocation] ADD [reversal_reason] NVARCHAR(300) NULL;
            ALTER TABLE [pur].[supplier_allocation] ADD CONSTRAINT [FK_pur_supplier_allocation_allocated_by_user_id]
                FOREIGN KEY ([allocated_by_user_id]) REFERENCES [core].[app_user]([id]);
            ALTER TABLE [pur].[supplier_allocation] ADD CONSTRAINT [FK_pur_supplier_allocation_reversed_by_user_id]
                FOREIGN KEY ([reversed_by_user_id]) REFERENCES [core].[app_user]([id]);
        END
    """)
    op.execute("""
        IF COL_LENGTH(N'core.supplier', N'opening_balance') IS NULL
        BEGIN
            ALTER TABLE [core].[supplier] ADD [contact_person] NVARCHAR(100) NULL;
            ALTER TABLE [core].[supplier] ADD [opening_balance] DECIMAL(18,2) NOT NULL
                CONSTRAINT [DF_core_supplier_opening_balance] DEFAULT (0);
            ALTER TABLE [core].[supplier] ADD [opening_balance_date] DATE NULL;
        END
    """)

    bind = op.get_bind()
    for code, description, days in _TERMS:
        bind.execute(_TERM, {"code": code, "description": description, "days": days})
    for document_type, infix in _SERIES:
        bind.execute(_BRANCH_SERIES, {"document_type": document_type, "infix": infix})
    for code, description in _PERMISSIONS:
        bind.execute(_PERMISSION, {"code": code, "description": description})
    for role, permissions in _GRANTS.items():
        for permission in permissions:
            bind.execute(_GRANT, {"role": role, "permission": permission})
    bind.execute(_CARRY_GRN)


def downgrade() -> None:
    expanding: sa.BindParameter[list[str]] = sa.bindparam("codes", expanding=True)
    codes = {"codes": [code for code, _ in _PERMISSIONS]}
    bind = op.get_bind()
    bind.execute(
        sa.text("""
            DELETE rp FROM [core].[role_permission] rp
            JOIN [core].[permission] p ON p.[id] = rp.[permission_id]
            WHERE p.[code] IN :codes
        """).bindparams(expanding),
        codes,
    )
    bind.execute(sa.text("DELETE FROM [core].[permission] WHERE [code] IN :codes").bindparams(expanding), codes)
    op.execute("""
        DELETE FROM [core].[number_series]
        WHERE [document_type] IN (N'PURCHASE_ORDER', N'SUPPLIER_INVOICE', N'SUPPLIER_PAYMENT', N'SUPPLIER_CREDIT_NOTE')
          AND [next_number] = 1;
    """)
    # Columns added here are left in place on downgrade: the tables were empty and the columns are harmless.
