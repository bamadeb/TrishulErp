"""Sales: customer branches, quotations with revisions, sales orders with approval and credit check,
deliveries (against an order or direct), invoices (against deliveries or direct), customer receipts
(order advances, on-account, against invoices) and allocations. The tables exist since v3 (sal.*);
this adds what the screens and rules need.

    core.customer_site       becomes the customer branch: site_code, gstin, billing_address,
                             billing_state_id, email (address = the delivery address)
    core.customer            opening_balance (+ = the customer owes us), opening_balance_date
    sal.quotation            status 'Submitted' / 'Converted'; customer branch, CGST/SGST/IGST,
                             other_charges, remarks, who submitted / approved (discounts) / recorded
                             the customer's answer and when
    sal.quotation_line       gst_pct
    sal.sales_order          status 'Pending approval' / 'Approved' / 'Part invoiced' / 'Closed';
                             customer branch, billing and delivery address, place of supply, is_prepaid,
                             CGST/SGST/IGST, other_charges, remarks, submitted / approved / closed by and when
    sal.sales_order_line     discount_pct, gst_pct, uom_id
    sal.delivery_note        customer branch, delivery address, reference, recipient phone, remarks,
                             posted_by, cancelled by / when / why (stock goes back to its batches)
    sal.delivery_note_line   qty_invoiced, price / discount / GST to invoice at, description, unit,
                             rack, unit_cost of the batches taken
    sal.sales_invoice        our GSTIN registration optional (none set up yet); source 'Delivery' /
                             'Direct'; customer branch, delivery address, other_charges, remarks,
                             is_direct, the location a direct invoice takes stock from, posted_by,
                             credit override by / when, cancelled by / when / why
    sal.sales_invoice_line   HSN and GST-rate master optional (empty masters); gst_pct, discount_pct,
                             the delivery line billed, the rack a direct line takes stock from
    sal.receipt              the sales order an advance is for, bank_name, cheque_date, remarks, posted_by
    sal.customer_allocation  allocated_by_user_id, reversed_at / reversed_by_user_id / reversal_reason

Number series per active branch: QUOTATION <BRANCH>/QT/, SALES_ORDER <BRANCH>/SO/,
DELIVERY_NOTE <BRANCH>/DN/, CUSTOMER_RECEIPT <BRANCH>/RV/ and SALES_INVOICE <first 6 of BRANCH>/SI/
(a GST invoice number is at most 16 characters).

Permissions (sal.quotation.approve and sal.credit.override already exist):
    sal.customer.view / sal.customer.manage     customer accounts, branches, credit terms
    sal.quotation.view / sal.quotation.manage   quotations
    sal.order.view / sal.order.manage / sal.order.approve / sal.order.close
    sal.delivery.manage                         deliver goods (stock goes out)
    sal.delivery.over_order                     deliver more than is outstanding on the order
    sal.account.view                            invoices, receipts, statements, allocations
    sal.invoice.manage                          invoice deliveries
    sal.invoice.direct                          invoices without a delivery
    sal.invoice.cancel                          cancel an invoice (reversal, nothing is deleted)
    sal.receipt.manage                          customer receipts and order advances
    sal.allocation.manage / sal.allocation.reverse

Idempotent: every statement checks first. All the sal tables are empty on RDS (2026-11-11).
The DDL is written out in full (no f-strings): scripts/generate_models.py reads op.execute literals.

Revision ID: 0032_sales_module
Revises: 0031_purchases_module
Created: 2026-11-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0032_sales_module"
down_revision = "0031_purchases_module"
branch_labels = None
depends_on = None

_PERMISSIONS = (
    ("sal.customer.view", "See customer accounts, balances, branches and statements"),
    ("sal.customer.manage", "Add and change customer branches, credit limits and payment terms"),
    ("sal.quotation.view", "See sales quotations"),
    ("sal.quotation.manage", "Create, revise and submit sales quotations and record the customer's answer"),
    ("sal.order.view", "See sales orders and what is still to be delivered"),
    ("sal.order.manage", "Create and change sales orders and send them for approval"),
    ("sal.order.approve", "Approve sales orders"),
    ("sal.order.close", "Close or cancel an outstanding sales order"),
    ("sal.delivery.manage", "Deliver goods to customers (stock goes out)"),
    ("sal.delivery.over_order", "Deliver more than is outstanding on a sales order"),
    ("sal.account.view", "See sales invoices, receipts, customer statements and allocations"),
    ("sal.invoice.manage", "Invoice goods delivered"),
    ("sal.invoice.direct", "Create invoices without a delivery note"),
    ("sal.invoice.cancel", "Cancel a sales invoice"),
    ("sal.receipt.manage", "Record customer receipts and order advances"),
    ("sal.allocation.manage", "Allocate receipts to sales invoices"),
    ("sal.allocation.reverse", "Reverse a customer allocation"),
)
_ALL = [code for code, _ in _PERMISSIONS] + ["sal.quotation.approve", "sal.credit.override"]
_GRANTS = {
    "ADMIN": _ALL,
    "SALES_MANAGER": [
        "sal.customer.view", "sal.customer.manage", "sal.quotation.view", "sal.quotation.manage",
        "sal.quotation.approve", "sal.order.view", "sal.order.manage", "sal.order.approve", "sal.order.close",
        "sal.account.view", "sal.credit.override",
    ],
    "SALESPERSON": [
        "sal.customer.view", "sal.quotation.view", "sal.quotation.manage", "sal.order.view", "sal.order.manage",
    ],
    "ACCOUNTS": [
        "sal.customer.view", "sal.customer.manage", "sal.quotation.view", "sal.order.view", "sal.account.view",
        "sal.invoice.manage", "sal.invoice.direct", "sal.invoice.cancel", "sal.receipt.manage",
        "sal.allocation.manage", "sal.allocation.reverse", "sal.credit.override",
    ],
    "INVENTORY": ["sal.customer.view", "sal.order.view", "sal.delivery.manage"],
    "WAREHOUSE": ["sal.customer.view", "sal.order.view", "sal.delivery.manage"],
    "MANAGEMENT": [
        "sal.customer.view", "sal.quotation.view", "sal.order.view", "sal.order.approve", "sal.account.view",
    ],
}  # fmt: skip
_SERIES = (
    ("QUOTATION", "/QT/"),
    ("SALES_ORDER", "/SO/"),
    ("DELIVERY_NOTE", "/DN/"),
    ("CUSTOMER_RECEIPT", "/RV/"),
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
    SELECT :code, N'Sales', :description
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
# GST: an invoice number has at most 16 characters, so the branch code is cut to 6 (6 + /SI/ + 5 digits = 15).
_INVOICE_SERIES = sa.text("""
    INSERT INTO [core].[number_series]
        ([company_id], [document_type], [branch_id], [principal_id], [fiscal_year_id],
         [prefix], [next_number], [padding], [suffix])
    SELECT b.[company_id], N'SALES_INVOICE', b.[id], NULL, NULL, LEFT(b.[code], 6) + N'/SI/', 1, 5, NULL
    FROM [core].[branch] b
    WHERE b.[is_active] = 1
      AND NOT EXISTS (SELECT 1 FROM [core].[number_series] ns
                      WHERE ns.[document_type] = N'SALES_INVOICE' AND ns.[branch_id] = b.[id]
                        AND ns.[principal_id] IS NULL AND ns.[fiscal_year_id] IS NULL);
""")


def upgrade() -> None:
    # ------------------------------------------------------------ customers and their branches
    op.execute("""
        IF COL_LENGTH(N'core.customer_site', N'site_code') IS NULL
        BEGIN
            ALTER TABLE [core].[customer_site] ADD [site_code] NVARCHAR(20) NULL;
            ALTER TABLE [core].[customer_site] ADD [gstin] NVARCHAR(15) NULL;
            ALTER TABLE [core].[customer_site] ADD [billing_address] NVARCHAR(500) NULL;
            ALTER TABLE [core].[customer_site] ADD [billing_state_id] BIGINT NULL;
            ALTER TABLE [core].[customer_site] ADD [email] NVARCHAR(120) NULL;
            ALTER TABLE [core].[customer_site] ADD CONSTRAINT [FK_core_customer_site_billing_state_id]
                FOREIGN KEY ([billing_state_id]) REFERENCES [core].[state]([id]);
        END
    """)
    op.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE [name] = N'UX_core_customer_site_code'
                       AND [object_id] = OBJECT_ID(N'[core].[customer_site]'))
            CREATE UNIQUE NONCLUSTERED INDEX [UX_core_customer_site_code]
                ON [core].[customer_site] ([customer_id], [site_code]) WHERE [site_code] IS NOT NULL;
    """)
    op.execute("""
        IF COL_LENGTH(N'core.customer', N'opening_balance') IS NULL
        BEGIN
            ALTER TABLE [core].[customer] ADD [opening_balance] DECIMAL(18,2) NOT NULL
                CONSTRAINT [DF_core_customer_opening_balance] DEFAULT (0);
            ALTER TABLE [core].[customer] ADD [opening_balance_date] DATE NULL;
        END
    """)

    # ------------------------------------------------------------ quotations
    op.execute("""
        IF OBJECT_ID(N'[sal].[CK_sal_quotation_status]', N'C') IS NOT NULL
            ALTER TABLE [sal].[quotation] DROP CONSTRAINT [CK_sal_quotation_status];
    """)
    op.execute("""
        ALTER TABLE [sal].[quotation] ADD CONSTRAINT [CK_sal_quotation_status] CHECK ([status] IN (N'Draft', N'Pending approval', N'Submitted', N'Sent', N'Accepted', N'Rejected', N'Expired', N'Converted'));
    """)
    op.execute("""
        IF COL_LENGTH(N'sal.quotation', N'customer_site_id') IS NULL
        BEGIN
            ALTER TABLE [sal].[quotation] ADD [customer_site_id] BIGINT NULL;
            ALTER TABLE [sal].[quotation] ADD [cgst] DECIMAL(18,2) NOT NULL
                CONSTRAINT [DF_sal_quotation_cgst] DEFAULT (0);
            ALTER TABLE [sal].[quotation] ADD [sgst] DECIMAL(18,2) NOT NULL
                CONSTRAINT [DF_sal_quotation_sgst] DEFAULT (0);
            ALTER TABLE [sal].[quotation] ADD [igst] DECIMAL(18,2) NOT NULL
                CONSTRAINT [DF_sal_quotation_igst] DEFAULT (0);
            ALTER TABLE [sal].[quotation] ADD [other_charges] DECIMAL(18,2) NOT NULL
                CONSTRAINT [DF_sal_quotation_other_charges] DEFAULT (0);
            ALTER TABLE [sal].[quotation] ADD [remarks] NVARCHAR(500) NULL;
            ALTER TABLE [sal].[quotation] ADD [submitted_at] DATETIME2(0) NULL;
            ALTER TABLE [sal].[quotation] ADD [submitted_by_user_id] BIGINT NULL;
            ALTER TABLE [sal].[quotation] ADD [approved_at] DATETIME2(0) NULL;
            ALTER TABLE [sal].[quotation] ADD [approved_by_user_id] BIGINT NULL;
            ALTER TABLE [sal].[quotation] ADD [responded_at] DATETIME2(0) NULL;
            ALTER TABLE [sal].[quotation] ADD [responded_by_user_id] BIGINT NULL;
            ALTER TABLE [sal].[quotation] ADD [response_note] NVARCHAR(300) NULL;
            ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_customer_site_id]
                FOREIGN KEY ([customer_site_id]) REFERENCES [core].[customer_site]([id]);
            ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_submitted_by_user_id]
                FOREIGN KEY ([submitted_by_user_id]) REFERENCES [core].[app_user]([id]);
            ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_approved_by_user_id]
                FOREIGN KEY ([approved_by_user_id]) REFERENCES [core].[app_user]([id]);
            ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_responded_by_user_id]
                FOREIGN KEY ([responded_by_user_id]) REFERENCES [core].[app_user]([id]);
        END
    """)
    op.execute("""
        IF COL_LENGTH(N'sal.quotation_line', N'gst_pct') IS NULL
            ALTER TABLE [sal].[quotation_line] ADD [gst_pct] DECIMAL(5,2) NOT NULL
                CONSTRAINT [DF_sal_quotation_line_gst_pct] DEFAULT (0);
    """)

    # ------------------------------------------------------------ sales orders
    op.execute("""
        IF OBJECT_ID(N'[sal].[CK_sal_sales_order_status]', N'C') IS NOT NULL
            ALTER TABLE [sal].[sales_order] DROP CONSTRAINT [CK_sal_sales_order_status];
    """)
    op.execute("""
        ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [CK_sal_sales_order_status] CHECK ([status] IN (N'Draft', N'Pending approval', N'Approved', N'Confirmed', N'Part delivered', N'Delivered', N'Part invoiced', N'Invoiced', N'Closed', N'Cancelled'));
    """)
    op.execute("""
        IF COL_LENGTH(N'sal.sales_order', N'customer_site_id') IS NULL
        BEGIN
            ALTER TABLE [sal].[sales_order] ADD [customer_site_id] BIGINT NULL;
            ALTER TABLE [sal].[sales_order] ADD [bill_to_address] NVARCHAR(500) NULL;
            ALTER TABLE [sal].[sales_order] ADD [ship_to_address] NVARCHAR(500) NULL;
            ALTER TABLE [sal].[sales_order] ADD [place_of_supply_state_id] BIGINT NULL;
            ALTER TABLE [sal].[sales_order] ADD [is_prepaid] BIT NOT NULL
                CONSTRAINT [DF_sal_sales_order_is_prepaid] DEFAULT (0);
            ALTER TABLE [sal].[sales_order] ADD [cgst] DECIMAL(18,2) NOT NULL
                CONSTRAINT [DF_sal_sales_order_cgst] DEFAULT (0);
            ALTER TABLE [sal].[sales_order] ADD [sgst] DECIMAL(18,2) NOT NULL
                CONSTRAINT [DF_sal_sales_order_sgst] DEFAULT (0);
            ALTER TABLE [sal].[sales_order] ADD [igst] DECIMAL(18,2) NOT NULL
                CONSTRAINT [DF_sal_sales_order_igst] DEFAULT (0);
            ALTER TABLE [sal].[sales_order] ADD [other_charges] DECIMAL(18,2) NOT NULL
                CONSTRAINT [DF_sal_sales_order_other_charges] DEFAULT (0);
            ALTER TABLE [sal].[sales_order] ADD [remarks] NVARCHAR(500) NULL;
            ALTER TABLE [sal].[sales_order] ADD [submitted_at] DATETIME2(0) NULL;
            ALTER TABLE [sal].[sales_order] ADD [submitted_by_user_id] BIGINT NULL;
            ALTER TABLE [sal].[sales_order] ADD [approved_at] DATETIME2(0) NULL;
            ALTER TABLE [sal].[sales_order] ADD [approved_by_user_id] BIGINT NULL;
            ALTER TABLE [sal].[sales_order] ADD [approval_note] NVARCHAR(300) NULL;
            ALTER TABLE [sal].[sales_order] ADD [closed_at] DATETIME2(0) NULL;
            ALTER TABLE [sal].[sales_order] ADD [closed_by_user_id] BIGINT NULL;
            ALTER TABLE [sal].[sales_order] ADD [close_reason] NVARCHAR(300) NULL;
            ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_customer_site_id]
                FOREIGN KEY ([customer_site_id]) REFERENCES [core].[customer_site]([id]);
            ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_place_of_supply_state_id]
                FOREIGN KEY ([place_of_supply_state_id]) REFERENCES [core].[state]([id]);
            ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_submitted_by_user_id]
                FOREIGN KEY ([submitted_by_user_id]) REFERENCES [core].[app_user]([id]);
            ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_approved_by_user_id]
                FOREIGN KEY ([approved_by_user_id]) REFERENCES [core].[app_user]([id]);
            ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_closed_by_user_id]
                FOREIGN KEY ([closed_by_user_id]) REFERENCES [core].[app_user]([id]);
        END
    """)
    op.execute("""
        IF COL_LENGTH(N'sal.sales_order_line', N'gst_pct') IS NULL
        BEGIN
            ALTER TABLE [sal].[sales_order_line] ADD [discount_pct] DECIMAL(5,2) NOT NULL
                CONSTRAINT [DF_sal_sales_order_line_discount_pct] DEFAULT (0);
            ALTER TABLE [sal].[sales_order_line] ADD [gst_pct] DECIMAL(5,2) NOT NULL
                CONSTRAINT [DF_sal_sales_order_line_gst_pct] DEFAULT (0);
            ALTER TABLE [sal].[sales_order_line] ADD [uom_id] BIGINT NULL;
            ALTER TABLE [sal].[sales_order_line] ADD CONSTRAINT [FK_sal_sales_order_line_uom_id]
                FOREIGN KEY ([uom_id]) REFERENCES [core].[uom]([id]);
        END
    """)

    # ------------------------------------------------------------ deliveries
    op.execute("""
        IF COL_LENGTH(N'sal.delivery_note', N'customer_site_id') IS NULL
        BEGIN
            ALTER TABLE [sal].[delivery_note] ADD [customer_site_id] BIGINT NULL;
            ALTER TABLE [sal].[delivery_note] ADD [ship_to_address] NVARCHAR(500) NULL;
            ALTER TABLE [sal].[delivery_note] ADD [delivery_reference] NVARCHAR(40) NULL;
            ALTER TABLE [sal].[delivery_note] ADD [recipient_phone] NVARCHAR(15) NULL;
            ALTER TABLE [sal].[delivery_note] ADD [remarks] NVARCHAR(500) NULL;
            ALTER TABLE [sal].[delivery_note] ADD [posted_by_user_id] BIGINT NULL;
            ALTER TABLE [sal].[delivery_note] ADD [cancelled_at] DATETIME2(0) NULL;
            ALTER TABLE [sal].[delivery_note] ADD [cancelled_by_user_id] BIGINT NULL;
            ALTER TABLE [sal].[delivery_note] ADD [cancel_reason] NVARCHAR(300) NULL;
            ALTER TABLE [sal].[delivery_note] ADD CONSTRAINT [FK_sal_delivery_note_customer_site_id]
                FOREIGN KEY ([customer_site_id]) REFERENCES [core].[customer_site]([id]);
            ALTER TABLE [sal].[delivery_note] ADD CONSTRAINT [FK_sal_delivery_note_posted_by_user_id]
                FOREIGN KEY ([posted_by_user_id]) REFERENCES [core].[app_user]([id]);
            ALTER TABLE [sal].[delivery_note] ADD CONSTRAINT [FK_sal_delivery_note_cancelled_by_user_id]
                FOREIGN KEY ([cancelled_by_user_id]) REFERENCES [core].[app_user]([id]);
        END
    """)
    op.execute("""
        IF COL_LENGTH(N'sal.delivery_note_line', N'qty_invoiced') IS NULL
        BEGIN
            ALTER TABLE [sal].[delivery_note_line] ADD [qty_invoiced] DECIMAL(18,3) NOT NULL
                CONSTRAINT [DF_sal_delivery_note_line_qty_invoiced] DEFAULT (0);
            ALTER TABLE [sal].[delivery_note_line] ADD [unit_price] DECIMAL(18,4) NULL;
            ALTER TABLE [sal].[delivery_note_line] ADD [discount_pct] DECIMAL(5,2) NOT NULL
                CONSTRAINT [DF_sal_delivery_note_line_discount_pct] DEFAULT (0);
            ALTER TABLE [sal].[delivery_note_line] ADD [gst_pct] DECIMAL(5,2) NOT NULL
                CONSTRAINT [DF_sal_delivery_note_line_gst_pct] DEFAULT (0);
            ALTER TABLE [sal].[delivery_note_line] ADD [description] NVARCHAR(300) NULL;
            ALTER TABLE [sal].[delivery_note_line] ADD [uom_id] BIGINT NULL;
            ALTER TABLE [sal].[delivery_note_line] ADD [bin_id] BIGINT NULL;
            ALTER TABLE [sal].[delivery_note_line] ADD [unit_cost] DECIMAL(18,4) NULL;
            ALTER TABLE [sal].[delivery_note_line] ADD CONSTRAINT [FK_sal_delivery_note_line_uom_id]
                FOREIGN KEY ([uom_id]) REFERENCES [core].[uom]([id]);
            ALTER TABLE [sal].[delivery_note_line] ADD CONSTRAINT [FK_sal_delivery_note_line_bin_id]
                FOREIGN KEY ([bin_id]) REFERENCES [inv].[bin]([id]);
        END
    """)

    # ------------------------------------------------------------ invoices
    # No GSTIN registration, HSN or GST-rate masters are set up yet, so those references become optional
    # (the GST % is kept on the line). Each column's index has to come off while it changes.
    op.execute("""
        IF COLUMNPROPERTY(OBJECT_ID(N'sal.sales_invoice'), N'gstin_registration_id', 'AllowsNull') = 0
        BEGIN
            IF EXISTS (SELECT 1 FROM sys.indexes WHERE [name] = N'IX_sal_sales_invoice_gstin_registration_id'
                       AND [object_id] = OBJECT_ID(N'[sal].[sales_invoice]'))
                DROP INDEX [IX_sal_sales_invoice_gstin_registration_id] ON [sal].[sales_invoice];
            ALTER TABLE [sal].[sales_invoice] ALTER COLUMN [gstin_registration_id] BIGINT NULL;
            CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_gstin_registration_id]
                ON [sal].[sales_invoice] ([gstin_registration_id]);
        END
    """)
    op.execute("""
        IF COLUMNPROPERTY(OBJECT_ID(N'sal.sales_invoice_line'), N'hsn_sac_id', 'AllowsNull') = 0
        BEGIN
            IF EXISTS (SELECT 1 FROM sys.indexes WHERE [name] = N'IX_sal_sales_invoice_line_hsn_sac_id'
                       AND [object_id] = OBJECT_ID(N'[sal].[sales_invoice_line]'))
                DROP INDEX [IX_sal_sales_invoice_line_hsn_sac_id] ON [sal].[sales_invoice_line];
            ALTER TABLE [sal].[sales_invoice_line] ALTER COLUMN [hsn_sac_id] BIGINT NULL;
            CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_line_hsn_sac_id]
                ON [sal].[sales_invoice_line] ([hsn_sac_id]);
        END
    """)
    op.execute("""
        IF COLUMNPROPERTY(OBJECT_ID(N'sal.sales_invoice_line'), N'gst_rate_id', 'AllowsNull') = 0
        BEGIN
            IF EXISTS (SELECT 1 FROM sys.indexes WHERE [name] = N'IX_sal_sales_invoice_line_gst_rate_id'
                       AND [object_id] = OBJECT_ID(N'[sal].[sales_invoice_line]'))
                DROP INDEX [IX_sal_sales_invoice_line_gst_rate_id] ON [sal].[sales_invoice_line];
            ALTER TABLE [sal].[sales_invoice_line] ALTER COLUMN [gst_rate_id] BIGINT NULL;
            CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_line_gst_rate_id]
                ON [sal].[sales_invoice_line] ([gst_rate_id]);
        END
    """)
    op.execute("""
        IF OBJECT_ID(N'[sal].[CK_sal_sales_invoice_source_type]', N'C') IS NOT NULL
            ALTER TABLE [sal].[sales_invoice] DROP CONSTRAINT [CK_sal_sales_invoice_source_type];
    """)
    op.execute("""
        ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [CK_sal_sales_invoice_source_type] CHECK ([source_type] IN (N'Sales order', N'Delivery', N'Direct', N'Service call', N'Counter sale', N'Contract'));
    """)
    op.execute("""
        IF COL_LENGTH(N'sal.sales_invoice', N'customer_site_id') IS NULL
        BEGIN
            ALTER TABLE [sal].[sales_invoice] ADD [customer_site_id] BIGINT NULL;
            ALTER TABLE [sal].[sales_invoice] ADD [ship_to_address] NVARCHAR(500) NULL;
            ALTER TABLE [sal].[sales_invoice] ADD [other_charges] DECIMAL(18,2) NOT NULL
                CONSTRAINT [DF_sal_sales_invoice_other_charges] DEFAULT (0);
            ALTER TABLE [sal].[sales_invoice] ADD [remarks] NVARCHAR(500) NULL;
            ALTER TABLE [sal].[sales_invoice] ADD [is_direct] BIT NOT NULL
                CONSTRAINT [DF_sal_sales_invoice_is_direct] DEFAULT (0);
            ALTER TABLE [sal].[sales_invoice] ADD [location_id] BIGINT NULL;
            ALTER TABLE [sal].[sales_invoice] ADD [posted_by_user_id] BIGINT NULL;
            ALTER TABLE [sal].[sales_invoice] ADD [credit_override_by_user_id] BIGINT NULL;
            ALTER TABLE [sal].[sales_invoice] ADD [credit_override_at] DATETIME2(0) NULL;
            ALTER TABLE [sal].[sales_invoice] ADD [cancelled_at] DATETIME2(0) NULL;
            ALTER TABLE [sal].[sales_invoice] ADD [cancelled_by_user_id] BIGINT NULL;
            ALTER TABLE [sal].[sales_invoice] ADD [cancel_reason] NVARCHAR(300) NULL;
            ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_customer_site_id]
                FOREIGN KEY ([customer_site_id]) REFERENCES [core].[customer_site]([id]);
            ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_location_id]
                FOREIGN KEY ([location_id]) REFERENCES [core].[location]([id]);
            ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_posted_by_user_id]
                FOREIGN KEY ([posted_by_user_id]) REFERENCES [core].[app_user]([id]);
            ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_credit_override_by_user_id]
                FOREIGN KEY ([credit_override_by_user_id]) REFERENCES [core].[app_user]([id]);
            ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_cancelled_by_user_id]
                FOREIGN KEY ([cancelled_by_user_id]) REFERENCES [core].[app_user]([id]);
        END
    """)
    op.execute("""
        IF COL_LENGTH(N'sal.sales_invoice_line', N'gst_pct') IS NULL
        BEGIN
            ALTER TABLE [sal].[sales_invoice_line] ADD [gst_pct] DECIMAL(5,2) NOT NULL
                CONSTRAINT [DF_sal_sales_invoice_line_gst_pct] DEFAULT (0);
            ALTER TABLE [sal].[sales_invoice_line] ADD [discount_pct] DECIMAL(5,2) NOT NULL
                CONSTRAINT [DF_sal_sales_invoice_line_discount_pct] DEFAULT (0);
            ALTER TABLE [sal].[sales_invoice_line] ADD [delivery_note_line_id] BIGINT NULL;
            ALTER TABLE [sal].[sales_invoice_line] ADD [bin_id] BIGINT NULL;
            ALTER TABLE [sal].[sales_invoice_line] ADD CONSTRAINT [FK_sal_sales_invoice_line_delivery_note_line_id]
                FOREIGN KEY ([delivery_note_line_id]) REFERENCES [sal].[delivery_note_line]([id]);
            ALTER TABLE [sal].[sales_invoice_line] ADD CONSTRAINT [FK_sal_sales_invoice_line_bin_id]
                FOREIGN KEY ([bin_id]) REFERENCES [inv].[bin]([id]);
        END
    """)

    # ------------------------------------------------------------ receipts and allocations
    op.execute("""
        IF COL_LENGTH(N'sal.receipt', N'sales_order_id') IS NULL
        BEGIN
            ALTER TABLE [sal].[receipt] ADD [sales_order_id] BIGINT NULL;
            ALTER TABLE [sal].[receipt] ADD [bank_name] NVARCHAR(100) NULL;
            ALTER TABLE [sal].[receipt] ADD [cheque_date] DATE NULL;
            ALTER TABLE [sal].[receipt] ADD [remarks] NVARCHAR(300) NULL;
            ALTER TABLE [sal].[receipt] ADD [posted_by_user_id] BIGINT NULL;
            ALTER TABLE [sal].[receipt] ADD CONSTRAINT [FK_sal_receipt_sales_order_id]
                FOREIGN KEY ([sales_order_id]) REFERENCES [sal].[sales_order]([id]);
            ALTER TABLE [sal].[receipt] ADD CONSTRAINT [FK_sal_receipt_posted_by_user_id]
                FOREIGN KEY ([posted_by_user_id]) REFERENCES [core].[app_user]([id]);
        END
    """)
    op.execute("""
        IF COL_LENGTH(N'sal.customer_allocation', N'reversed_at') IS NULL
        BEGIN
            ALTER TABLE [sal].[customer_allocation] ADD [allocated_by_user_id] BIGINT NULL;
            ALTER TABLE [sal].[customer_allocation] ADD [reversed_at] DATETIME2(0) NULL;
            ALTER TABLE [sal].[customer_allocation] ADD [reversed_by_user_id] BIGINT NULL;
            ALTER TABLE [sal].[customer_allocation] ADD [reversal_reason] NVARCHAR(300) NULL;
            ALTER TABLE [sal].[customer_allocation] ADD CONSTRAINT [FK_sal_customer_allocation_allocated_by_user_id]
                FOREIGN KEY ([allocated_by_user_id]) REFERENCES [core].[app_user]([id]);
            ALTER TABLE [sal].[customer_allocation] ADD CONSTRAINT [FK_sal_customer_allocation_reversed_by_user_id]
                FOREIGN KEY ([reversed_by_user_id]) REFERENCES [core].[app_user]([id]);
        END
    """)

    bind = op.get_bind()
    for document_type, infix in _SERIES:
        bind.execute(_BRANCH_SERIES, {"document_type": document_type, "infix": infix})
    bind.execute(_INVOICE_SERIES)
    for code, description in _PERMISSIONS:
        bind.execute(_PERMISSION, {"code": code, "description": description})
    for role, permissions in _GRANTS.items():
        for permission in permissions:
            bind.execute(_GRANT, {"role": role, "permission": permission})


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
        WHERE [document_type] IN (N'QUOTATION', N'SALES_ORDER', N'DELIVERY_NOTE', N'CUSTOMER_RECEIPT', N'SALES_INVOICE')
          AND [next_number] = 1;
    """)
    # Columns added here are left in place on downgrade: the tables were empty and the columns are harmless.
