/* =====================================================================
   TRISHUL Integrated System - SQL Server DDL (dictionary v2)
   Phase 4 - Sales
   Generated from the TRISHUL Database Dictionary. Do not edit by hand:
   change the dictionary and regenerate.
   Target: SQL Server 2019+ / Amazon RDS for SQL Server
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
/* ---------- 1. Tables (23) ---------- */

/* ===== sal: Sales ===== */
-- Customer credit status.
CREATE TABLE [sal].[credit_status] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_credit_status] PRIMARY KEY,
    [code] NVARCHAR(10) NOT NULL,
    [description] NVARCHAR(100) NOT NULL,
    [disallow_invoicing] BIT NOT NULL CONSTRAINT [DF_sal_credit_status_disallow_invoicing] DEFAULT (0),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_credit_status_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_credit_status_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Price lists (retail, dealer, government, service labour).
CREATE TABLE [sal].[price_list] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_price_list] PRIMARY KEY,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(80) NOT NULL,
    [principal_id] BIGINT NULL,
    [price_list_type] NVARCHAR(30) NOT NULL,
    [currency_id] BIGINT NOT NULL,
    [includes_tax] BIT NOT NULL CONSTRAINT [DF_sal_price_list_includes_tax] DEFAULT (0),
    [valid_from] DATE NULL,
    [valid_to] DATE NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_price_list_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_price_list_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_price_list_price_list_type] CHECK ([price_list_type] IN (N'Retail', N'Dealer', N'Government', N'Service labour'))
);
GO
-- Item price in a price list.
CREATE TABLE [sal].[price_list_item] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_price_list_item] PRIMARY KEY,
    [price_list_id] BIGINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [unit_price] DECIMAL(18,4) NOT NULL,
    [min_qty] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_sal_price_list_item_min_qty] DEFAULT (1),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_price_list_item_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_price_list_item_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Quotation for machines, parts or service.
CREATE TABLE [sal].[quotation] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_quotation] PRIMARY KEY,
    [quotation_no] NVARCHAR(30) NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [customer_id] BIGINT NOT NULL,
    [contact_id] BIGINT NULL,
    [opportunity_id] BIGINT NULL,
    [service_call_id] BIGINT NULL,
    [quotation_type] NVARCHAR(30) NOT NULL,
    [quotation_date] DATE NOT NULL,
    [valid_until] DATE NULL,
    [salesperson_employee_id] BIGINT NULL,
    [price_list_id] BIGINT NULL,
    [place_of_supply_state_id] BIGINT NOT NULL,
    [subtotal] DECIMAL(18,2) NOT NULL,
    [discount_total] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_quotation_discount_total] DEFAULT (0),
    [tax_total] DECIMAL(18,2) NOT NULL,
    [total] DECIMAL(18,2) NOT NULL,
    [current_version] SMALLINT NOT NULL CONSTRAINT [DF_sal_quotation_current_version] DEFAULT (1),
    [status] NVARCHAR(30) NOT NULL,
    [terms] NVARCHAR(2000) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_quotation_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_quotation_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_quotation_quotation_type] CHECK ([quotation_type] IN (N'Machine', N'Parts', N'Service')),
    CONSTRAINT [CK_sal_quotation_status] CHECK ([status] IN (N'Draft', N'Pending approval', N'Sent', N'Accepted', N'Rejected', N'Expired'))
);
GO
-- Each revision sent to the customer.
CREATE TABLE [sal].[quotation_version] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_quotation_version] PRIMARY KEY,
    [quotation_id] BIGINT NOT NULL,
    [version_no] SMALLINT NOT NULL,
    [total] DECIMAL(18,2) NOT NULL,
    [change_note] NVARCHAR(500) NULL,
    [pdf_attachment_id] BIGINT NULL,
    [sent_at] DATETIME2(0) NULL,
    [sent_via] NVARCHAR(30) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_quotation_version_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_quotation_version_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_quotation_version_sent_via] CHECK ([sent_via] IN (N'Email', N'WhatsApp', N'Print'))
);
GO
-- Quotation lines (per version).
CREATE TABLE [sal].[quotation_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_quotation_line] PRIMARY KEY,
    [quotation_id] BIGINT NOT NULL,
    [version_no] SMALLINT NOT NULL,
    [line_no] SMALLINT NOT NULL,
    [item_id] BIGINT NULL,
    [machine_model_id] BIGINT NULL,
    [description] NVARCHAR(300) NOT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [uom_id] BIGINT NULL,
    [unit_price] DECIMAL(18,4) NOT NULL,
    [discount_pct] DECIMAL(5,2) NULL,
    [discount_amount] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_quotation_line_discount_amount] DEFAULT (0),
    [hsn_sac_id] BIGINT NULL,
    [gst_rate_id] BIGINT NULL,
    [taxable_value] DECIMAL(18,2) NOT NULL,
    [tax_amount] DECIMAL(18,2) NOT NULL,
    [line_total] DECIMAL(18,2) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_quotation_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_quotation_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Confirmed customer order.
CREATE TABLE [sal].[sales_order] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_sales_order] PRIMARY KEY,
    [order_no] NVARCHAR(30) NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [customer_id] BIGINT NOT NULL,
    [quotation_id] BIGINT NULL,
    [order_date] DATE NOT NULL,
    [customer_po_no] NVARCHAR(40) NULL,
    [customer_po_date] DATE NULL,
    [salesperson_employee_id] BIGINT NULL,
    [delivery_site_id] BIGINT NULL,
    [expected_delivery_date] DATE NULL,
    [payment_terms_id] BIGINT NULL,
    [finance_mode] NVARCHAR(30) NOT NULL CONSTRAINT [DF_sal_sales_order_finance_mode] DEFAULT (N'Cash'),
    [finance_application_id] BIGINT NULL,
    [subtotal] DECIMAL(18,2) NOT NULL,
    [tax_total] DECIMAL(18,2) NOT NULL,
    [total] DECIMAL(18,2) NOT NULL,
    [advance_received] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_order_advance_received] DEFAULT (0),
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_sales_order_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_sales_order_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_sales_order_finance_mode] CHECK ([finance_mode] IN (N'Cash', N'Financed')),
    CONSTRAINT [CK_sal_sales_order_status] CHECK ([status] IN (N'Draft', N'Confirmed', N'Part delivered', N'Delivered', N'Invoiced', N'Cancelled'))
);
GO
-- Order lines.
CREATE TABLE [sal].[sales_order_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_sales_order_line] PRIMARY KEY,
    [sales_order_id] BIGINT NOT NULL,
    [line_no] SMALLINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [description] NVARCHAR(300) NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [unit_price] DECIMAL(18,4) NOT NULL,
    [discount_amount] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_order_line_discount_amount] DEFAULT (0),
    [hsn_sac_id] BIGINT NULL,
    [gst_rate_id] BIGINT NULL,
    [taxable_value] DECIMAL(18,2) NOT NULL,
    [tax_amount] DECIMAL(18,2) NOT NULL,
    [line_total] DECIMAL(18,2) NOT NULL,
    [qty_delivered] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_sal_sales_order_line_qty_delivered] DEFAULT (0),
    [qty_invoiced] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_sal_sales_order_line_qty_invoiced] DEFAULT (0),
    [allocated_machine_unit_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_sales_order_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_sales_order_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Old machine taken in exchange.
CREATE TABLE [sal].[exchange_machine] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_exchange_machine] PRIMARY KEY,
    [sales_order_id] BIGINT NOT NULL,
    [customer_id] BIGINT NOT NULL,
    [make] NVARCHAR(40) NOT NULL,
    [model] NVARCHAR(60) NULL,
    [serial_number] NVARCHAR(40) NULL,
    [year_of_manufacture] SMALLINT NULL,
    [hmr] DECIMAL(10,1) NULL,
    [evaluated_value] DECIMAL(18,2) NULL,
    [agreed_value] DECIMAL(18,2) NULL,
    [evaluated_by_employee_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_exchange_machine_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_exchange_machine_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_exchange_machine_status] CHECK ([status] IN (N'Evaluated', N'Agreed', N'Received', N'Cancelled'))
);
GO
-- Delivery of goods / machine.
CREATE TABLE [sal].[delivery_note] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_delivery_note] PRIMARY KEY,
    [delivery_no] NVARCHAR(30) NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [sales_order_id] BIGINT NULL,
    [customer_id] BIGINT NOT NULL,
    [delivery_date] DATE NOT NULL,
    [from_location_id] BIGINT NOT NULL,
    [delivery_site_id] BIGINT NULL,
    [vehicle_no] NVARCHAR(20) NULL,
    [transporter] NVARCHAR(100) NULL,
    [e_way_bill_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_delivery_note_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_delivery_note_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_delivery_note_status] CHECK ([status] IN (N'Draft', N'Dispatched', N'Delivered', N'Cancelled'))
);
GO
-- Delivered items.
CREATE TABLE [sal].[delivery_note_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_delivery_note_line] PRIMARY KEY,
    [delivery_note_id] BIGINT NOT NULL,
    [sales_order_line_id] BIGINT NULL,
    [item_id] BIGINT NOT NULL,
    [serial_batch_id] BIGINT NULL,
    [machine_unit_id] BIGINT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_delivery_note_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_delivery_note_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Pre-delivery inspection, installation and commissioning.
CREATE TABLE [sal].[pdi_installation] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_pdi_installation] PRIMARY KEY,
    [machine_unit_id] BIGINT NOT NULL,
    [delivery_note_id] BIGINT NULL,
    [service_call_id] BIGINT NULL,
    [record_type] NVARCHAR(30) NOT NULL,
    [done_by_employee_id] BIGINT NOT NULL,
    [done_at] DATETIME2(0) NOT NULL,
    [hmr] DECIMAL(10,1) NULL,
    [report_attachment_id] BIGINT NULL,
    [customer_signature_attachment_id] BIGINT NULL,
    [remarks] NVARCHAR(1000) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_pdi_installation_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_pdi_installation_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_pdi_installation_record_type] CHECK ([record_type] IN (N'PDI', N'Installation', N'Commissioning'))
);
GO
-- GST tax invoice to customer.
CREATE TABLE [sal].[sales_invoice] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_sales_invoice] PRIMARY KEY,
    [invoice_no] NVARCHAR(16) NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [company_id] BIGINT NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [gstin_registration_id] BIGINT NOT NULL,
    [customer_id] BIGINT NOT NULL,
    [bill_to_address] NVARCHAR(500) NULL,
    [ship_to_site_id] BIGINT NULL,
    [place_of_supply_state_id] BIGINT NOT NULL,
    [invoice_type] NVARCHAR(30) NOT NULL,
    [source_type] NVARCHAR(30) NOT NULL,
    [sales_order_id] BIGINT NULL,
    [service_call_id] BIGINT NULL,
    [delivery_note_id] BIGINT NULL,
    [invoice_date] DATE NOT NULL,
    [due_date] DATE NULL,
    [is_reverse_charge] BIT NOT NULL CONSTRAINT [DF_sal_sales_invoice_is_reverse_charge] DEFAULT (0),
    [taxable_value] DECIMAL(18,2) NOT NULL,
    [cgst] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_invoice_cgst] DEFAULT (0),
    [sgst] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_invoice_sgst] DEFAULT (0),
    [igst] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_invoice_igst] DEFAULT (0),
    [cess] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_invoice_cess] DEFAULT (0),
    [round_off] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_invoice_round_off] DEFAULT (0),
    [total] DECIMAL(18,2) NOT NULL,
    [amount_received] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_invoice_amount_received] DEFAULT (0),
    [status] NVARCHAR(30) NOT NULL,
    [e_invoice_id] BIGINT NULL,
    [journal_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_sales_invoice_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_sales_invoice_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_sales_invoice_invoice_type] CHECK ([invoice_type] IN (N'Tax invoice', N'Bill of supply', N'Export')),
    CONSTRAINT [CK_sal_sales_invoice_source_type] CHECK ([source_type] IN (N'Sales order', N'Service call', N'Counter sale', N'Contract')),
    CONSTRAINT [CK_sal_sales_invoice_status] CHECK ([status] IN (N'Draft', N'Posted', N'Part paid', N'Paid', N'Cancelled'))
);
GO
-- Invoice lines.
CREATE TABLE [sal].[sales_invoice_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_sales_invoice_line] PRIMARY KEY,
    [sales_invoice_id] BIGINT NOT NULL,
    [line_no] SMALLINT NOT NULL,
    [item_id] BIGINT NULL,
    [machine_unit_id] BIGINT NULL,
    [serial_batch_id] BIGINT NULL,
    [sales_order_line_id] BIGINT NULL,
    [service_charge_id] BIGINT NULL,
    [description] NVARCHAR(300) NOT NULL,
    [hsn_sac_id] BIGINT NOT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [uom_id] BIGINT NULL,
    [unit_price] DECIMAL(18,4) NOT NULL,
    [discount_amount] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_invoice_line_discount_amount] DEFAULT (0),
    [taxable_value] DECIMAL(18,2) NOT NULL,
    [gst_rate_id] BIGINT NOT NULL,
    [cgst_amount] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_invoice_line_cgst_amount] DEFAULT (0),
    [sgst_amount] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_invoice_line_sgst_amount] DEFAULT (0),
    [igst_amount] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_invoice_line_igst_amount] DEFAULT (0),
    [line_total] DECIMAL(18,2) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_sales_invoice_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_sales_invoice_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Money received from customer, incl. advances and finance disbursement. Brand-neutral: split by brand through allocations to invoices.
CREATE TABLE [sal].[receipt] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_receipt] PRIMARY KEY,
    [receipt_no] NVARCHAR(30) NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [customer_id] BIGINT NOT NULL,
    [receipt_date] DATE NOT NULL,
    [receipt_type] NVARCHAR(30) NOT NULL,
    [payment_mode] NVARCHAR(30) NOT NULL,
    [bank_account_id] BIGINT NULL,
    [cheque_id] BIGINT NULL,
    [financer_id] BIGINT NULL,
    [reference_no] NVARCHAR(40) NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [tds_deducted] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_receipt_tds_deducted] DEFAULT (0),
    [status] NVARCHAR(30) NOT NULL,
    [journal_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_receipt_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_receipt_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_receipt_receipt_type] CHECK ([receipt_type] IN (N'Against invoice', N'Advance', N'Order advance')),
    CONSTRAINT [CK_sal_receipt_payment_mode] CHECK ([payment_mode] IN (N'Cash', N'Cheque', N'NEFT', N'RTGS', N'UPI', N'Finance disbursement')),
    CONSTRAINT [CK_sal_receipt_status] CHECK ([status] IN (N'Draft', N'Posted', N'Bounced', N'Cancelled'))
);
GO
-- Sales return / price adjustment.
CREATE TABLE [sal].[credit_note] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_credit_note] PRIMARY KEY,
    [credit_note_no] NVARCHAR(16) NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [customer_id] BIGINT NOT NULL,
    [sales_invoice_id] BIGINT NULL,
    [note_date] DATE NOT NULL,
    [note_type] NVARCHAR(30) NOT NULL,
    [reason_lookup_id] BIGINT NULL,
    [taxable_value] DECIMAL(18,2) NOT NULL,
    [tax_amount] DECIMAL(18,2) NOT NULL,
    [total] DECIMAL(18,2) NOT NULL,
    [e_invoice_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [journal_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_credit_note_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_credit_note_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_credit_note_note_type] CHECK ([note_type] IN (N'Sales return', N'Price adjustment', N'Discount')),
    CONSTRAINT [CK_sal_credit_note_status] CHECK ([status] IN (N'Draft', N'Posted', N'Cancelled'))
);
GO
-- Credit note lines.
CREATE TABLE [sal].[credit_note_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_credit_note_line] PRIMARY KEY,
    [credit_note_id] BIGINT NOT NULL,
    [sales_invoice_line_id] BIGINT NULL,
    [item_id] BIGINT NULL,
    [serial_batch_id] BIGINT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [unit_price] DECIMAL(18,4) NOT NULL,
    [tax_amount] DECIMAL(18,2) NOT NULL,
    [line_total] DECIMAL(18,2) NOT NULL,
    [return_location_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_credit_note_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_credit_note_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Matches receipts and credit notes to invoices.
CREATE TABLE [sal].[customer_allocation] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_customer_allocation] PRIMARY KEY,
    [sales_invoice_id] BIGINT NOT NULL,
    [receipt_id] BIGINT NULL,
    [credit_note_id] BIGINT NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [allocated_on] DATE NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_customer_allocation_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_customer_allocation_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Credit holds when limit or overdue is exceeded.
CREATE TABLE [sal].[credit_hold] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_credit_hold] PRIMARY KEY,
    [customer_id] BIGINT NOT NULL,
    [hold_at] DATETIME2(0) NOT NULL,
    [reason] NVARCHAR(30) NOT NULL,
    [outstanding_amount] DECIMAL(18,2) NULL,
    [credit_limit] DECIMAL(18,2) NULL,
    [released_by_user_id] BIGINT NULL,
    [released_at] DATETIME2(0) NULL,
    [release_remarks] NVARCHAR(300) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_credit_hold_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_credit_hold_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_credit_hold_reason] CHECK ([reason] IN (N'Over limit', N'Overdue', N'Manual'))
);
GO
-- Salesperson incentive per invoice, paid via payroll.
CREATE TABLE [sal].[sales_incentive] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_sales_incentive] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [period_month] DATE NOT NULL,
    [sales_invoice_id] BIGINT NOT NULL,
    [basis_amount] DECIMAL(18,2) NOT NULL,
    [incentive_pct] DECIMAL(5,2) NULL,
    [incentive_amount] DECIMAL(18,2) NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [payroll_run_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_sales_incentive_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_sales_incentive_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_sales_incentive_status] CHECK ([status] IN (N'Calculated', N'Approved', N'Paid'))
);
GO

/* ===== acc: Accounting & GST ===== */
-- Cheques and post-dated cheques received or issued.
CREATE TABLE [acc].[cheque] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_cheque] PRIMARY KEY,
    [cheque_no] NVARCHAR(10) NOT NULL,
    [bank_name] NVARCHAR(100) NULL,
    [cheque_date] DATE NOT NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [direction] NVARCHAR(30) NOT NULL,
    [customer_id] BIGINT NULL,
    [supplier_id] BIGINT NULL,
    [bank_account_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [deposit_date] DATE NULL,
    [clearing_date] DATE NULL,
    [bounce_reason] NVARCHAR(200) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_cheque_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_cheque_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_acc_cheque_direction] CHECK ([direction] IN (N'Received', N'Issued')),
    CONSTRAINT [CK_acc_cheque_status] CHECK ([status] IN (N'PDC', N'In hand', N'Deposited', N'Cleared', N'Bounced', N'Cancelled'))
);
GO
-- IRN and QR from the GST e-invoice portal.
CREATE TABLE [acc].[e_invoice] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_e_invoice] PRIMARY KEY,
    [sales_invoice_id] BIGINT NULL,
    [credit_note_id] BIGINT NULL,
    [irn] NVARCHAR(64) NOT NULL,
    [ack_no] NVARCHAR(20) NULL,
    [ack_date] DATETIME2(0) NULL,
    [signed_qr_code] NVARCHAR(MAX) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [cancel_reason] NVARCHAR(200) NULL,
    [cancelled_at] DATETIME2(0) NULL,
    [request_json] NVARCHAR(MAX) NULL,
    [response_json] NVARCHAR(MAX) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_e_invoice_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_e_invoice_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_acc_e_invoice_status] CHECK ([status] IN (N'Generated', N'Cancelled', N'Failed'))
);
GO
-- E-way bills for invoices, deliveries and transfers.
CREATE TABLE [acc].[e_way_bill] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_e_way_bill] PRIMARY KEY,
    [ewb_no] NVARCHAR(12) NOT NULL,
    [ewb_date] DATETIME2(0) NOT NULL,
    [valid_until] DATETIME2(0) NULL,
    [document_type] NVARCHAR(30) NOT NULL,
    [sales_invoice_id] BIGINT NULL,
    [delivery_note_id] BIGINT NULL,
    [stock_transfer_id] BIGINT NULL,
    [from_pincode] NVARCHAR(6) NULL,
    [to_pincode] NVARCHAR(6) NULL,
    [distance_km] SMALLINT NULL,
    [vehicle_no] NVARCHAR(20) NULL,
    [transporter_gstin] NVARCHAR(15) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_e_way_bill_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_e_way_bill_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_acc_e_way_bill_document_type] CHECK ([document_type] IN (N'Invoice', N'Delivery challan', N'Stock transfer')),
    CONSTRAINT [CK_acc_e_way_bill_status] CHECK ([status] IN (N'Active', N'Cancelled', N'Expired'))
);
GO

/* ---------- 2. Unique keys (12) ---------- */
CREATE UNIQUE NONCLUSTERED INDEX [UX_sal_credit_status_code] ON [sal].[credit_status] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_sal_price_list_code] ON [sal].[price_list] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_sal_price_list_item_k1] ON [sal].[price_list_item] ([price_list_id], [item_id], [min_qty]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_sal_quotation_quotation_no] ON [sal].[quotation] ([quotation_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_sal_quotation_version_k1] ON [sal].[quotation_version] ([quotation_id], [version_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_sal_sales_order_order_no] ON [sal].[sales_order] ([order_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_sal_delivery_note_delivery_no] ON [sal].[delivery_note] ([delivery_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_sal_sales_invoice_invoice_no] ON [sal].[sales_invoice] ([invoice_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_sal_receipt_receipt_no] ON [sal].[receipt] ([receipt_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_sal_credit_note_credit_note_no] ON [sal].[credit_note] ([credit_note_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_acc_e_invoice_irn] ON [acc].[e_invoice] ([irn]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_acc_e_way_bill_ewb_no] ON [acc].[e_way_bill] ([ewb_no]);
GO

/* ---------- 3. Foreign keys (113) ----------
   Includes links from earlier-phase columns to tables created in this phase. */
ALTER TABLE [core].[customer] ADD CONSTRAINT [FK_core_customer_credit_status_id] FOREIGN KEY ([credit_status_id]) REFERENCES [sal].[credit_status] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[machine_unit] ADD CONSTRAINT [FK_core_machine_unit_sale_invoice_id] FOREIGN KEY ([sale_invoice_id]) REFERENCES [sal].[sales_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_contract] ADD CONSTRAINT [FK_svc_service_contract_sales_invoice_id] FOREIGN KEY ([sales_invoice_id]) REFERENCES [sal].[sales_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_charge] ADD CONSTRAINT [FK_svc_service_charge_sales_invoice_id] FOREIGN KEY ([sales_invoice_id]) REFERENCES [sal].[sales_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_reservation] ADD CONSTRAINT [FK_inv_stock_reservation_sales_order_id] FOREIGN KEY ([sales_order_id]) REFERENCES [sal].[sales_order] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_transfer] ADD CONSTRAINT [FK_inv_stock_transfer_e_way_bill_id] FOREIGN KEY ([e_way_bill_id]) REFERENCES [acc].[e_way_bill] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_payment] ADD CONSTRAINT [FK_pur_supplier_payment_cheque_id] FOREIGN KEY ([cheque_id]) REFERENCES [acc].[cheque] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[price_list] ADD CONSTRAINT [FK_sal_price_list_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[price_list] ADD CONSTRAINT [FK_sal_price_list_currency_id] FOREIGN KEY ([currency_id]) REFERENCES [core].[currency] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[price_list_item] ADD CONSTRAINT [FK_sal_price_list_item_price_list_id] FOREIGN KEY ([price_list_id]) REFERENCES [sal].[price_list] ([id]) ON DELETE CASCADE;
ALTER TABLE [sal].[price_list_item] ADD CONSTRAINT [FK_sal_price_list_item_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_contact_id] FOREIGN KEY ([contact_id]) REFERENCES [core].[contact] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_salesperson_employee_id] FOREIGN KEY ([salesperson_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_price_list_id] FOREIGN KEY ([price_list_id]) REFERENCES [sal].[price_list] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_place_of_supply_state_id] FOREIGN KEY ([place_of_supply_state_id]) REFERENCES [core].[state] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation_version] ADD CONSTRAINT [FK_sal_quotation_version_quotation_id] FOREIGN KEY ([quotation_id]) REFERENCES [sal].[quotation] ([id]) ON DELETE CASCADE;
ALTER TABLE [sal].[quotation_version] ADD CONSTRAINT [FK_sal_quotation_version_pdf_attachment_id] FOREIGN KEY ([pdf_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation_line] ADD CONSTRAINT [FK_sal_quotation_line_quotation_id] FOREIGN KEY ([quotation_id]) REFERENCES [sal].[quotation] ([id]) ON DELETE CASCADE;
ALTER TABLE [sal].[quotation_line] ADD CONSTRAINT [FK_sal_quotation_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation_line] ADD CONSTRAINT [FK_sal_quotation_line_machine_model_id] FOREIGN KEY ([machine_model_id]) REFERENCES [core].[machine_model] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation_line] ADD CONSTRAINT [FK_sal_quotation_line_uom_id] FOREIGN KEY ([uom_id]) REFERENCES [core].[uom] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation_line] ADD CONSTRAINT [FK_sal_quotation_line_hsn_sac_id] FOREIGN KEY ([hsn_sac_id]) REFERENCES [core].[hsn_sac] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation_line] ADD CONSTRAINT [FK_sal_quotation_line_gst_rate_id] FOREIGN KEY ([gst_rate_id]) REFERENCES [acc].[gst_rate] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_quotation_id] FOREIGN KEY ([quotation_id]) REFERENCES [sal].[quotation] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_salesperson_employee_id] FOREIGN KEY ([salesperson_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_delivery_site_id] FOREIGN KEY ([delivery_site_id]) REFERENCES [core].[customer_site] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_payment_terms_id] FOREIGN KEY ([payment_terms_id]) REFERENCES [core].[payment_terms] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order_line] ADD CONSTRAINT [FK_sal_sales_order_line_sales_order_id] FOREIGN KEY ([sales_order_id]) REFERENCES [sal].[sales_order] ([id]) ON DELETE CASCADE;
ALTER TABLE [sal].[sales_order_line] ADD CONSTRAINT [FK_sal_sales_order_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order_line] ADD CONSTRAINT [FK_sal_sales_order_line_hsn_sac_id] FOREIGN KEY ([hsn_sac_id]) REFERENCES [core].[hsn_sac] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order_line] ADD CONSTRAINT [FK_sal_sales_order_line_gst_rate_id] FOREIGN KEY ([gst_rate_id]) REFERENCES [acc].[gst_rate] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order_line] ADD CONSTRAINT [FK_sal_sales_order_line_allocated_machine_unit_id] FOREIGN KEY ([allocated_machine_unit_id]) REFERENCES [core].[machine_unit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[exchange_machine] ADD CONSTRAINT [FK_sal_exchange_machine_sales_order_id] FOREIGN KEY ([sales_order_id]) REFERENCES [sal].[sales_order] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[exchange_machine] ADD CONSTRAINT [FK_sal_exchange_machine_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[exchange_machine] ADD CONSTRAINT [FK_sal_exchange_machine_evaluated_by_employee_id] FOREIGN KEY ([evaluated_by_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note] ADD CONSTRAINT [FK_sal_delivery_note_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note] ADD CONSTRAINT [FK_sal_delivery_note_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note] ADD CONSTRAINT [FK_sal_delivery_note_sales_order_id] FOREIGN KEY ([sales_order_id]) REFERENCES [sal].[sales_order] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note] ADD CONSTRAINT [FK_sal_delivery_note_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note] ADD CONSTRAINT [FK_sal_delivery_note_from_location_id] FOREIGN KEY ([from_location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note] ADD CONSTRAINT [FK_sal_delivery_note_delivery_site_id] FOREIGN KEY ([delivery_site_id]) REFERENCES [core].[customer_site] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note] ADD CONSTRAINT [FK_sal_delivery_note_e_way_bill_id] FOREIGN KEY ([e_way_bill_id]) REFERENCES [acc].[e_way_bill] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note_line] ADD CONSTRAINT [FK_sal_delivery_note_line_delivery_note_id] FOREIGN KEY ([delivery_note_id]) REFERENCES [sal].[delivery_note] ([id]) ON DELETE CASCADE;
ALTER TABLE [sal].[delivery_note_line] ADD CONSTRAINT [FK_sal_delivery_note_line_sales_order_line_id] FOREIGN KEY ([sales_order_line_id]) REFERENCES [sal].[sales_order_line] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note_line] ADD CONSTRAINT [FK_sal_delivery_note_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note_line] ADD CONSTRAINT [FK_sal_delivery_note_line_serial_batch_id] FOREIGN KEY ([serial_batch_id]) REFERENCES [inv].[serial_batch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note_line] ADD CONSTRAINT [FK_sal_delivery_note_line_machine_unit_id] FOREIGN KEY ([machine_unit_id]) REFERENCES [core].[machine_unit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[pdi_installation] ADD CONSTRAINT [FK_sal_pdi_installation_machine_unit_id] FOREIGN KEY ([machine_unit_id]) REFERENCES [core].[machine_unit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[pdi_installation] ADD CONSTRAINT [FK_sal_pdi_installation_delivery_note_id] FOREIGN KEY ([delivery_note_id]) REFERENCES [sal].[delivery_note] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[pdi_installation] ADD CONSTRAINT [FK_sal_pdi_installation_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[pdi_installation] ADD CONSTRAINT [FK_sal_pdi_installation_done_by_employee_id] FOREIGN KEY ([done_by_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[pdi_installation] ADD CONSTRAINT [FK_sal_pdi_installation_report_attachment_id] FOREIGN KEY ([report_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[pdi_installation] ADD CONSTRAINT [FK_sal_pdi_installation_customer_signature_attachment_id] FOREIGN KEY ([customer_signature_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_gstin_registration_id] FOREIGN KEY ([gstin_registration_id]) REFERENCES [acc].[gstin_registration] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_ship_to_site_id] FOREIGN KEY ([ship_to_site_id]) REFERENCES [core].[customer_site] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_place_of_supply_state_id] FOREIGN KEY ([place_of_supply_state_id]) REFERENCES [core].[state] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_sales_order_id] FOREIGN KEY ([sales_order_id]) REFERENCES [sal].[sales_order] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_delivery_note_id] FOREIGN KEY ([delivery_note_id]) REFERENCES [sal].[delivery_note] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_e_invoice_id] FOREIGN KEY ([e_invoice_id]) REFERENCES [acc].[e_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice_line] ADD CONSTRAINT [FK_sal_sales_invoice_line_sales_invoice_id] FOREIGN KEY ([sales_invoice_id]) REFERENCES [sal].[sales_invoice] ([id]) ON DELETE CASCADE;
ALTER TABLE [sal].[sales_invoice_line] ADD CONSTRAINT [FK_sal_sales_invoice_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice_line] ADD CONSTRAINT [FK_sal_sales_invoice_line_machine_unit_id] FOREIGN KEY ([machine_unit_id]) REFERENCES [core].[machine_unit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice_line] ADD CONSTRAINT [FK_sal_sales_invoice_line_serial_batch_id] FOREIGN KEY ([serial_batch_id]) REFERENCES [inv].[serial_batch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice_line] ADD CONSTRAINT [FK_sal_sales_invoice_line_sales_order_line_id] FOREIGN KEY ([sales_order_line_id]) REFERENCES [sal].[sales_order_line] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice_line] ADD CONSTRAINT [FK_sal_sales_invoice_line_service_charge_id] FOREIGN KEY ([service_charge_id]) REFERENCES [svc].[service_charge] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice_line] ADD CONSTRAINT [FK_sal_sales_invoice_line_hsn_sac_id] FOREIGN KEY ([hsn_sac_id]) REFERENCES [core].[hsn_sac] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice_line] ADD CONSTRAINT [FK_sal_sales_invoice_line_uom_id] FOREIGN KEY ([uom_id]) REFERENCES [core].[uom] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice_line] ADD CONSTRAINT [FK_sal_sales_invoice_line_gst_rate_id] FOREIGN KEY ([gst_rate_id]) REFERENCES [acc].[gst_rate] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[receipt] ADD CONSTRAINT [FK_sal_receipt_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[receipt] ADD CONSTRAINT [FK_sal_receipt_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[receipt] ADD CONSTRAINT [FK_sal_receipt_bank_account_id] FOREIGN KEY ([bank_account_id]) REFERENCES [acc].[bank_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[receipt] ADD CONSTRAINT [FK_sal_receipt_cheque_id] FOREIGN KEY ([cheque_id]) REFERENCES [acc].[cheque] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[receipt] ADD CONSTRAINT [FK_sal_receipt_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_note] ADD CONSTRAINT [FK_sal_credit_note_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_note] ADD CONSTRAINT [FK_sal_credit_note_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_note] ADD CONSTRAINT [FK_sal_credit_note_sales_invoice_id] FOREIGN KEY ([sales_invoice_id]) REFERENCES [sal].[sales_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_note] ADD CONSTRAINT [FK_sal_credit_note_reason_lookup_id] FOREIGN KEY ([reason_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_note] ADD CONSTRAINT [FK_sal_credit_note_e_invoice_id] FOREIGN KEY ([e_invoice_id]) REFERENCES [acc].[e_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_note] ADD CONSTRAINT [FK_sal_credit_note_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_note_line] ADD CONSTRAINT [FK_sal_credit_note_line_credit_note_id] FOREIGN KEY ([credit_note_id]) REFERENCES [sal].[credit_note] ([id]) ON DELETE CASCADE;
ALTER TABLE [sal].[credit_note_line] ADD CONSTRAINT [FK_sal_credit_note_line_sales_invoice_line_id] FOREIGN KEY ([sales_invoice_line_id]) REFERENCES [sal].[sales_invoice_line] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_note_line] ADD CONSTRAINT [FK_sal_credit_note_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_note_line] ADD CONSTRAINT [FK_sal_credit_note_line_serial_batch_id] FOREIGN KEY ([serial_batch_id]) REFERENCES [inv].[serial_batch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_note_line] ADD CONSTRAINT [FK_sal_credit_note_line_return_location_id] FOREIGN KEY ([return_location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[customer_allocation] ADD CONSTRAINT [FK_sal_customer_allocation_sales_invoice_id] FOREIGN KEY ([sales_invoice_id]) REFERENCES [sal].[sales_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[customer_allocation] ADD CONSTRAINT [FK_sal_customer_allocation_receipt_id] FOREIGN KEY ([receipt_id]) REFERENCES [sal].[receipt] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[customer_allocation] ADD CONSTRAINT [FK_sal_customer_allocation_credit_note_id] FOREIGN KEY ([credit_note_id]) REFERENCES [sal].[credit_note] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_hold] ADD CONSTRAINT [FK_sal_credit_hold_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_hold] ADD CONSTRAINT [FK_sal_credit_hold_released_by_user_id] FOREIGN KEY ([released_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_incentive] ADD CONSTRAINT [FK_sal_sales_incentive_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_incentive] ADD CONSTRAINT [FK_sal_sales_incentive_sales_invoice_id] FOREIGN KEY ([sales_invoice_id]) REFERENCES [sal].[sales_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_incentive] ADD CONSTRAINT [FK_sal_sales_incentive_payroll_run_id] FOREIGN KEY ([payroll_run_id]) REFERENCES [hr].[payroll_run] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[cheque] ADD CONSTRAINT [FK_acc_cheque_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[cheque] ADD CONSTRAINT [FK_acc_cheque_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[cheque] ADD CONSTRAINT [FK_acc_cheque_bank_account_id] FOREIGN KEY ([bank_account_id]) REFERENCES [acc].[bank_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[e_invoice] ADD CONSTRAINT [FK_acc_e_invoice_sales_invoice_id] FOREIGN KEY ([sales_invoice_id]) REFERENCES [sal].[sales_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[e_invoice] ADD CONSTRAINT [FK_acc_e_invoice_credit_note_id] FOREIGN KEY ([credit_note_id]) REFERENCES [sal].[credit_note] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[e_way_bill] ADD CONSTRAINT [FK_acc_e_way_bill_sales_invoice_id] FOREIGN KEY ([sales_invoice_id]) REFERENCES [sal].[sales_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[e_way_bill] ADD CONSTRAINT [FK_acc_e_way_bill_delivery_note_id] FOREIGN KEY ([delivery_note_id]) REFERENCES [sal].[delivery_note] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[e_way_bill] ADD CONSTRAINT [FK_acc_e_way_bill_stock_transfer_id] FOREIGN KEY ([stock_transfer_id]) REFERENCES [inv].[stock_transfer] ([id]) ON DELETE NO ACTION;
GO

/* ---------- 4. Foreign-key indexes (113) ---------- */
CREATE NONCLUSTERED INDEX [IX_core_customer_credit_status_id] ON [core].[customer] ([credit_status_id]);
CREATE NONCLUSTERED INDEX [IX_core_machine_unit_sale_invoice_id] ON [core].[machine_unit] ([sale_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_contract_sales_invoice_id] ON [svc].[service_contract] ([sales_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_charge_sales_invoice_id] ON [svc].[service_charge] ([sales_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_reservation_sales_order_id] ON [inv].[stock_reservation] ([sales_order_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_transfer_e_way_bill_id] ON [inv].[stock_transfer] ([e_way_bill_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_payment_cheque_id] ON [pur].[supplier_payment] ([cheque_id]);
CREATE NONCLUSTERED INDEX [IX_sal_price_list_principal_id] ON [sal].[price_list] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_sal_price_list_currency_id] ON [sal].[price_list] ([currency_id]);
CREATE NONCLUSTERED INDEX [IX_sal_price_list_item_price_list_id] ON [sal].[price_list_item] ([price_list_id]);
CREATE NONCLUSTERED INDEX [IX_sal_price_list_item_item_id] ON [sal].[price_list_item] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_principal_id] ON [sal].[quotation] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_branch_id] ON [sal].[quotation] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_customer_id] ON [sal].[quotation] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_contact_id] ON [sal].[quotation] ([contact_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_service_call_id] ON [sal].[quotation] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_salesperson_employee_id] ON [sal].[quotation] ([salesperson_employee_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_price_list_id] ON [sal].[quotation] ([price_list_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_place_of_supply_state_id] ON [sal].[quotation] ([place_of_supply_state_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_version_quotation_id] ON [sal].[quotation_version] ([quotation_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_version_pdf_attachment_id] ON [sal].[quotation_version] ([pdf_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_line_quotation_id] ON [sal].[quotation_line] ([quotation_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_line_item_id] ON [sal].[quotation_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_line_machine_model_id] ON [sal].[quotation_line] ([machine_model_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_line_uom_id] ON [sal].[quotation_line] ([uom_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_line_hsn_sac_id] ON [sal].[quotation_line] ([hsn_sac_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_line_gst_rate_id] ON [sal].[quotation_line] ([gst_rate_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_principal_id] ON [sal].[sales_order] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_branch_id] ON [sal].[sales_order] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_customer_id] ON [sal].[sales_order] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_quotation_id] ON [sal].[sales_order] ([quotation_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_salesperson_employee_id] ON [sal].[sales_order] ([salesperson_employee_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_delivery_site_id] ON [sal].[sales_order] ([delivery_site_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_payment_terms_id] ON [sal].[sales_order] ([payment_terms_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_line_sales_order_id] ON [sal].[sales_order_line] ([sales_order_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_line_item_id] ON [sal].[sales_order_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_line_hsn_sac_id] ON [sal].[sales_order_line] ([hsn_sac_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_line_gst_rate_id] ON [sal].[sales_order_line] ([gst_rate_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_line_allocated_machine_unit_id] ON [sal].[sales_order_line] ([allocated_machine_unit_id]);
CREATE NONCLUSTERED INDEX [IX_sal_exchange_machine_sales_order_id] ON [sal].[exchange_machine] ([sales_order_id]);
CREATE NONCLUSTERED INDEX [IX_sal_exchange_machine_customer_id] ON [sal].[exchange_machine] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_sal_exchange_machine_evaluated_by_employee_id] ON [sal].[exchange_machine] ([evaluated_by_employee_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_principal_id] ON [sal].[delivery_note] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_branch_id] ON [sal].[delivery_note] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_sales_order_id] ON [sal].[delivery_note] ([sales_order_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_customer_id] ON [sal].[delivery_note] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_from_location_id] ON [sal].[delivery_note] ([from_location_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_delivery_site_id] ON [sal].[delivery_note] ([delivery_site_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_e_way_bill_id] ON [sal].[delivery_note] ([e_way_bill_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_line_delivery_note_id] ON [sal].[delivery_note_line] ([delivery_note_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_line_sales_order_line_id] ON [sal].[delivery_note_line] ([sales_order_line_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_line_item_id] ON [sal].[delivery_note_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_line_serial_batch_id] ON [sal].[delivery_note_line] ([serial_batch_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_line_machine_unit_id] ON [sal].[delivery_note_line] ([machine_unit_id]);
CREATE NONCLUSTERED INDEX [IX_sal_pdi_installation_machine_unit_id] ON [sal].[pdi_installation] ([machine_unit_id]);
CREATE NONCLUSTERED INDEX [IX_sal_pdi_installation_delivery_note_id] ON [sal].[pdi_installation] ([delivery_note_id]);
CREATE NONCLUSTERED INDEX [IX_sal_pdi_installation_service_call_id] ON [sal].[pdi_installation] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_sal_pdi_installation_done_by_employee_id] ON [sal].[pdi_installation] ([done_by_employee_id]);
CREATE NONCLUSTERED INDEX [IX_sal_pdi_installation_report_attachment_id] ON [sal].[pdi_installation] ([report_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_sal_pdi_installation_customer_signature_attachment_id] ON [sal].[pdi_installation] ([customer_signature_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_principal_id] ON [sal].[sales_invoice] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_company_id] ON [sal].[sales_invoice] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_branch_id] ON [sal].[sales_invoice] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_gstin_registration_id] ON [sal].[sales_invoice] ([gstin_registration_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_customer_id] ON [sal].[sales_invoice] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_ship_to_site_id] ON [sal].[sales_invoice] ([ship_to_site_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_place_of_supply_state_id] ON [sal].[sales_invoice] ([place_of_supply_state_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_sales_order_id] ON [sal].[sales_invoice] ([sales_order_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_service_call_id] ON [sal].[sales_invoice] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_delivery_note_id] ON [sal].[sales_invoice] ([delivery_note_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_e_invoice_id] ON [sal].[sales_invoice] ([e_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_journal_id] ON [sal].[sales_invoice] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_line_sales_invoice_id] ON [sal].[sales_invoice_line] ([sales_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_line_item_id] ON [sal].[sales_invoice_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_line_machine_unit_id] ON [sal].[sales_invoice_line] ([machine_unit_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_line_serial_batch_id] ON [sal].[sales_invoice_line] ([serial_batch_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_line_sales_order_line_id] ON [sal].[sales_invoice_line] ([sales_order_line_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_line_service_charge_id] ON [sal].[sales_invoice_line] ([service_charge_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_line_hsn_sac_id] ON [sal].[sales_invoice_line] ([hsn_sac_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_line_uom_id] ON [sal].[sales_invoice_line] ([uom_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_line_gst_rate_id] ON [sal].[sales_invoice_line] ([gst_rate_id]);
CREATE NONCLUSTERED INDEX [IX_sal_receipt_branch_id] ON [sal].[receipt] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_sal_receipt_customer_id] ON [sal].[receipt] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_sal_receipt_bank_account_id] ON [sal].[receipt] ([bank_account_id]);
CREATE NONCLUSTERED INDEX [IX_sal_receipt_cheque_id] ON [sal].[receipt] ([cheque_id]);
CREATE NONCLUSTERED INDEX [IX_sal_receipt_journal_id] ON [sal].[receipt] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_principal_id] ON [sal].[credit_note] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_customer_id] ON [sal].[credit_note] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_sales_invoice_id] ON [sal].[credit_note] ([sales_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_reason_lookup_id] ON [sal].[credit_note] ([reason_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_e_invoice_id] ON [sal].[credit_note] ([e_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_journal_id] ON [sal].[credit_note] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_line_credit_note_id] ON [sal].[credit_note_line] ([credit_note_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_line_sales_invoice_line_id] ON [sal].[credit_note_line] ([sales_invoice_line_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_line_item_id] ON [sal].[credit_note_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_line_serial_batch_id] ON [sal].[credit_note_line] ([serial_batch_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_line_return_location_id] ON [sal].[credit_note_line] ([return_location_id]);
CREATE NONCLUSTERED INDEX [IX_sal_customer_allocation_sales_invoice_id] ON [sal].[customer_allocation] ([sales_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_sal_customer_allocation_receipt_id] ON [sal].[customer_allocation] ([receipt_id]);
CREATE NONCLUSTERED INDEX [IX_sal_customer_allocation_credit_note_id] ON [sal].[customer_allocation] ([credit_note_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_hold_customer_id] ON [sal].[credit_hold] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_hold_released_by_user_id] ON [sal].[credit_hold] ([released_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_incentive_employee_id] ON [sal].[sales_incentive] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_incentive_sales_invoice_id] ON [sal].[sales_incentive] ([sales_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_incentive_payroll_run_id] ON [sal].[sales_incentive] ([payroll_run_id]);
CREATE NONCLUSTERED INDEX [IX_acc_cheque_customer_id] ON [acc].[cheque] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_acc_cheque_supplier_id] ON [acc].[cheque] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_acc_cheque_bank_account_id] ON [acc].[cheque] ([bank_account_id]);
CREATE NONCLUSTERED INDEX [IX_acc_e_invoice_sales_invoice_id] ON [acc].[e_invoice] ([sales_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_acc_e_invoice_credit_note_id] ON [acc].[e_invoice] ([credit_note_id]);
CREATE NONCLUSTERED INDEX [IX_acc_e_way_bill_sales_invoice_id] ON [acc].[e_way_bill] ([sales_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_acc_e_way_bill_delivery_note_id] ON [acc].[e_way_bill] ([delivery_note_id]);
CREATE NONCLUSTERED INDEX [IX_acc_e_way_bill_stock_transfer_id] ON [acc].[e_way_bill] ([stock_transfer_id]);
GO
