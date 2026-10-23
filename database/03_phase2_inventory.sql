/* =====================================================================
   TRISHUL Integrated System - SQL Server DDL (dictionary v2)
   Phase 2 - Inventory
   Generated from the TRISHUL Database Dictionary. Do not edit by hand:
   change the dictionary and regenerate.
   Target: SQL Server 2019+ / Amazon RDS for SQL Server
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
/* ---------- 1. Tables (27) ---------- */

/* ===== inv: Inventory ===== */
-- Movement classes: Fast / Slow / Non-moving (FSN) or ABC.
CREATE TABLE [inv].[movement_class] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_movement_class] PRIMARY KEY,
    [code] NVARCHAR(5) NOT NULL,
    [name] NVARCHAR(40) NOT NULL,
    [criteria] NVARCHAR(300) NULL,
    [min_issues_per_year] INT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_movement_class_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_movement_class_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Rack/shelf position inside a location.
CREATE TABLE [inv].[bin] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_bin] PRIMARY KEY,
    [location_id] BIGINT NOT NULL,
    [code] NVARCHAR(20) NOT NULL,
    [rack] NVARCHAR(10) NULL,
    [shelf] NVARCHAR(10) NULL,
    [description] NVARCHAR(100) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_bin_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_bin_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Types of stock movement.
CREATE TABLE [inv].[movement_type] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_movement_type] PRIMARY KEY,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(60) NOT NULL,
    [direction] NVARCHAR(30) NOT NULL,
    [affects_cost] BIT NOT NULL CONSTRAINT [DF_inv_movement_type_affects_cost] DEFAULT (1),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_movement_type_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_movement_type_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_inv_movement_type_direction] CHECK ([direction] IN (N'In', N'Out'))
);
GO
-- Current quantity per item, location and bin.
CREATE TABLE [inv].[stock_balance] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_balance] PRIMARY KEY,
    [item_id] BIGINT NOT NULL,
    [location_id] BIGINT NOT NULL,
    [bin_id] BIGINT NULL,
    [qty_on_hand] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_inv_stock_balance_qty_on_hand] DEFAULT (0),
    [qty_reserved] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_inv_stock_balance_qty_reserved] DEFAULT (0),
    [qty_in_transit] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_inv_stock_balance_qty_in_transit] DEFAULT (0),
    [avg_cost] DECIMAL(18,4) NULL,
    [last_movement_at] DATETIME2(0) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_stock_balance_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_stock_balance_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Serial or batch number of a stock item.
CREATE TABLE [inv].[serial_batch] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_serial_batch] PRIMARY KEY,
    [item_id] BIGINT NOT NULL,
    [serial_or_batch_no] NVARCHAR(60) NOT NULL,
    [tracking_type] NVARCHAR(30) NOT NULL,
    [manufacture_date] DATE NULL,
    [expiry_date] DATE NULL,
    [current_location_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [grn_line_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_serial_batch_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_serial_batch_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_inv_serial_batch_tracking_type] CHECK ([tracking_type] IN (N'Serial', N'Batch')),
    CONSTRAINT [CK_inv_serial_batch_status] CHECK ([status] IN (N'In stock', N'Reserved', N'Issued', N'Sold', N'Returned', N'Scrapped'))
);
GO
-- Stock ledger: every quantity change. Insert only.
CREATE TABLE [inv].[stock_move] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_move] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [move_at] DATETIME2(0) NOT NULL,
    [movement_type_id] BIGINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [location_id] BIGINT NOT NULL,
    [bin_id] BIGINT NULL,
    [serial_batch_id] BIGINT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [unit_cost] DECIMAL(18,4) NULL,
    [value] DECIMAL(18,2) NULL,
    [source_document_type] NVARCHAR(40) NOT NULL,
    [source_document_id] BIGINT NOT NULL,
    [source_line_id] BIGINT NULL,
    [reference] NVARCHAR(60) NULL,
    [performed_by_user_id] BIGINT NULL
);
GO
-- Receipt layers for FIFO valuation (if FIFO is chosen).
CREATE TABLE [inv].[cost_layer] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_cost_layer] PRIMARY KEY,
    [item_id] BIGINT NOT NULL,
    [location_id] BIGINT NOT NULL,
    [stock_move_id] BIGINT NOT NULL,
    [received_at] DATETIME2(0) NOT NULL,
    [qty_received] DECIMAL(18,3) NOT NULL,
    [qty_remaining] DECIMAL(18,3) NOT NULL,
    [unit_cost] DECIMAL(18,4) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_cost_layer_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_cost_layer_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Barcodes for an item, incl. pack barcodes.
CREATE TABLE [inv].[item_barcode] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_item_barcode] PRIMARY KEY,
    [item_id] BIGINT NOT NULL,
    [barcode] NVARCHAR(60) NOT NULL,
    [barcode_type] NVARCHAR(30) NOT NULL,
    [pack_qty] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_inv_item_barcode_pack_qty] DEFAULT (1),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_item_barcode_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_item_barcode_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_inv_item_barcode_barcode_type] CHECK ([barcode_type] IN (N'EAN13', N'Code128', N'QR'))
);
GO
-- Stock held for a service call or sales order.
CREATE TABLE [inv].[stock_reservation] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_reservation] PRIMARY KEY,
    [item_id] BIGINT NOT NULL,
    [location_id] BIGINT NOT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [reserved_for_type] NVARCHAR(30) NOT NULL,
    [service_call_id] BIGINT NULL,
    [sales_order_id] BIGINT NULL,
    [reserved_by_user_id] BIGINT NULL,
    [reserved_until] DATETIME2(0) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_stock_reservation_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_stock_reservation_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_inv_stock_reservation_reserved_for_type] CHECK ([reserved_for_type] IN (N'Service call', N'Sales order')),
    CONSTRAINT [CK_inv_stock_reservation_status] CHECK ([status] IN (N'Active', N'Consumed', N'Released'))
);
GO
-- Parts issued from a warehouse to a service call or engineer (branches hold no stock).
CREATE TABLE [inv].[stock_issue] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_issue] PRIMARY KEY,
    [issue_no] NVARCHAR(30) NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [issue_date] DATE NOT NULL,
    [issue_type] NVARCHAR(30) NOT NULL,
    [principal_id] BIGINT NULL,
    [service_call_id] BIGINT NULL,
    [issued_to_employee_id] BIGINT NULL,
    [from_location_id] BIGINT NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_stock_issue_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_stock_issue_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_inv_stock_issue_issue_type] CHECK ([issue_type] IN (N'Service', N'Internal', N'Sample')),
    CONSTRAINT [CK_inv_stock_issue_status] CHECK ([status] IN (N'Draft', N'Issued', N'Cancelled'))
);
GO
-- Parts in an issue.
CREATE TABLE [inv].[stock_issue_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_issue_line] PRIMARY KEY,
    [stock_issue_id] BIGINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [serial_batch_id] BIGINT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [unit_cost] DECIMAL(18,4) NULL,
    [service_part_request_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_stock_issue_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_stock_issue_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Defective parts returned from the field.
CREATE TABLE [inv].[defective_return] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_defective_return] PRIMARY KEY,
    [return_no] NVARCHAR(30) NOT NULL,
    [service_call_id] BIGINT NULL,
    [warranty_claim_id] BIGINT NULL,
    [item_id] BIGINT NOT NULL,
    [serial_batch_id] BIGINT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [received_location_id] BIGINT NOT NULL,
    [received_at] DATETIME2(0) NOT NULL,
    [disposition] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_defective_return_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_defective_return_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_inv_defective_return_disposition] CHECK ([disposition] IN (N'Return to OEM', N'Scrap', N'Repair', N'Pending'))
);
GO
-- Transfer between warehouses (same GSTIN, so delivery challan + e-way bill).
CREATE TABLE [inv].[stock_transfer] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_transfer] PRIMARY KEY,
    [transfer_no] NVARCHAR(30) NOT NULL,
    [from_location_id] BIGINT NOT NULL,
    [to_location_id] BIGINT NOT NULL,
    [transfer_date] DATE NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [dispatched_at] DATETIME2(0) NULL,
    [received_at] DATETIME2(0) NULL,
    [e_way_bill_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_stock_transfer_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_stock_transfer_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_inv_stock_transfer_status] CHECK ([status] IN (N'Draft', N'Dispatched', N'Received', N'Cancelled'))
);
GO
-- Items in a transfer.
CREATE TABLE [inv].[stock_transfer_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_transfer_line] PRIMARY KEY,
    [stock_transfer_id] BIGINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [serial_batch_id] BIGINT NULL,
    [qty_sent] DECIMAL(18,3) NOT NULL,
    [qty_received] DECIMAL(18,3) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_stock_transfer_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_stock_transfer_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Stock corrections with approval.
CREATE TABLE [inv].[stock_adjustment] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_adjustment] PRIMARY KEY,
    [adjustment_no] NVARCHAR(30) NOT NULL,
    [location_id] BIGINT NOT NULL,
    [adjustment_date] DATE NOT NULL,
    [reason_lookup_id] BIGINT NOT NULL,
    [stock_count_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_stock_adjustment_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_stock_adjustment_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_inv_stock_adjustment_status] CHECK ([status] IN (N'Draft', N'Pending approval', N'Posted', N'Rejected'))
);
GO
-- Lines of an adjustment.
CREATE TABLE [inv].[stock_adjustment_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_adjustment_line] PRIMARY KEY,
    [stock_adjustment_id] BIGINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [bin_id] BIGINT NULL,
    [serial_batch_id] BIGINT NULL,
    [qty_change] DECIMAL(18,3) NOT NULL,
    [unit_cost] DECIMAL(18,4) NULL,
    [remarks] NVARCHAR(200) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_stock_adjustment_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_stock_adjustment_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Physical stock count (full or cycle).
CREATE TABLE [inv].[stock_count] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_count] PRIMARY KEY,
    [count_no] NVARCHAR(30) NOT NULL,
    [location_id] BIGINT NOT NULL,
    [count_date] DATE NOT NULL,
    [count_type] NVARCHAR(30) NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_stock_count_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_stock_count_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_inv_stock_count_count_type] CHECK ([count_type] IN (N'Full', N'Cycle')),
    CONSTRAINT [CK_inv_stock_count_status] CHECK ([status] IN (N'Open', N'Counted', N'Adjusted', N'Cancelled'))
);
GO
-- Counted quantities.
CREATE TABLE [inv].[stock_count_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_count_line] PRIMARY KEY,
    [stock_count_id] BIGINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [bin_id] BIGINT NULL,
    [system_qty] DECIMAL(18,3) NOT NULL,
    [counted_qty] DECIMAL(18,3) NULL,
    [counted_by_user_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_stock_count_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_stock_count_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO

/* ===== acc: Accounting & GST ===== */
-- Journal header: one per posting document.
CREATE TABLE [acc].[journal] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_journal] PRIMARY KEY,
    [journal_no] NVARCHAR(30) NOT NULL,
    [company_id] BIGINT NOT NULL,
    [branch_id] BIGINT NULL,
    [journal_date] DATE NOT NULL,
    [fiscal_year_id] BIGINT NOT NULL,
    [journal_type] NVARCHAR(30) NOT NULL,
    [source_document_type] NVARCHAR(40) NULL,
    [source_document_id] BIGINT NULL,
    [narration] NVARCHAR(500) NULL,
    [total_debit] DECIMAL(18,2) NOT NULL,
    [total_credit] DECIMAL(18,2) NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [reversed_journal_id] BIGINT NULL,
    [posted_by_user_id] BIGINT NULL,
    [posted_at] DATETIME2(0) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_journal_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_journal_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_acc_journal_journal_type] CHECK ([journal_type] IN (N'Sales', N'Purchase', N'Receipt', N'Payment', N'Payroll', N'Stock', N'Manual', N'Opening', N'Contra')),
    CONSTRAINT [CK_acc_journal_status] CHECK ([status] IN (N'Draft', N'Posted', N'Reversed'))
);
GO
-- Ledger lines (double entry).
CREATE TABLE [acc].[gl_entry] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_gl_entry] PRIMARY KEY,
    [journal_id] BIGINT NOT NULL,
    [line_no] SMALLINT NOT NULL,
    [entry_date] DATE NOT NULL,
    [gl_account_id] BIGINT NOT NULL,
    [debit] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_acc_gl_entry_debit] DEFAULT (0),
    [credit] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_acc_gl_entry_credit] DEFAULT (0),
    [cost_centre_id] BIGINT NULL,
    [principal_id] BIGINT NULL,
    [branch_id] BIGINT NULL,
    [party_type] NVARCHAR(30) NULL,
    [customer_id] BIGINT NULL,
    [supplier_id] BIGINT NULL,
    [employee_id] BIGINT NULL,
    [narration] NVARCHAR(300) NULL,
    CONSTRAINT [CK_acc_gl_entry_party_type] CHECK ([party_type] IN (N'Customer', N'Supplier', N'Employee'))
);
GO
-- Opening balances by account and party at go-live.
CREATE TABLE [acc].[opening_balance] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_opening_balance] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [fiscal_year_id] BIGINT NOT NULL,
    [gl_account_id] BIGINT NOT NULL,
    [party_type] NVARCHAR(30) NULL,
    [customer_id] BIGINT NULL,
    [supplier_id] BIGINT NULL,
    [reference_document_no] NVARCHAR(40) NULL,
    [document_date] DATE NULL,
    [due_date] DATE NULL,
    [debit] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_acc_opening_balance_debit] DEFAULT (0),
    [credit] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_acc_opening_balance_credit] DEFAULT (0),
    [journal_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_opening_balance_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_opening_balance_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_acc_opening_balance_party_type] CHECK ([party_type] IN (N'Customer', N'Supplier', N'Employee'))
);
GO
-- Company bank and cash accounts.
CREATE TABLE [acc].[bank_account] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_bank_account] PRIMARY KEY,
    [gl_account_id] BIGINT NOT NULL,
    [bank_name] NVARCHAR(100) NOT NULL,
    [account_name] NVARCHAR(150) NULL,
    [account_number] NVARCHAR(30) NULL,
    [ifsc] NVARCHAR(11) NULL,
    [branch_name] NVARCHAR(100) NULL,
    [account_type] NVARCHAR(30) NOT NULL,
    [currency_id] BIGINT NOT NULL,
    [last_reconciled_date] DATE NULL,
    [reconciled_balance] DECIMAL(18,2) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_bank_account_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_bank_account_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_acc_bank_account_account_type] CHECK ([account_type] IN (N'Current', N'Cash credit', N'Overdraft', N'Savings', N'Cash'))
);
GO
-- Imported bank statement lines for reconciliation.
CREATE TABLE [acc].[bank_statement_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_bank_statement_line] PRIMARY KEY,
    [bank_account_id] BIGINT NOT NULL,
    [statement_date] DATE NOT NULL,
    [description] NVARCHAR(300) NULL,
    [reference] NVARCHAR(60) NULL,
    [debit] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_acc_bank_statement_line_debit] DEFAULT (0),
    [credit] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_acc_bank_statement_line_credit] DEFAULT (0),
    [balance] DECIMAL(18,2) NULL,
    [file_import_id] BIGINT NULL
);
GO
-- Bank / cash book entries.
CREATE TABLE [acc].[bank_txn] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_bank_txn] PRIMARY KEY,
    [bank_account_id] BIGINT NOT NULL,
    [txn_date] DATE NOT NULL,
    [value_date] DATE NULL,
    [txn_type] NVARCHAR(30) NOT NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [reference_no] NVARCHAR(60) NULL,
    [journal_id] BIGINT NULL,
    [source_document_type] NVARCHAR(40) NULL,
    [source_document_id] BIGINT NULL,
    [is_reconciled] BIT NOT NULL CONSTRAINT [DF_acc_bank_txn_is_reconciled] DEFAULT (0),
    [reconciled_on] DATE NULL,
    [bank_statement_line_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_bank_txn_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_bank_txn_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_acc_bank_txn_txn_type] CHECK ([txn_type] IN (N'Receipt', N'Payment', N'Transfer', N'Charges', N'Interest'))
);
GO
-- Monthly budget per account and cost centre.
CREATE TABLE [acc].[budget] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_budget] PRIMARY KEY,
    [fiscal_year_id] BIGINT NOT NULL,
    [gl_account_id] BIGINT NOT NULL,
    [cost_centre_id] BIGINT NULL,
    [period_month] DATE NOT NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_budget_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_budget_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- GST split per document line (for GSTR reports).
CREATE TABLE [acc].[doc_tax_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_doc_tax_line] PRIMARY KEY,
    [document_type] NVARCHAR(40) NOT NULL,
    [document_id] BIGINT NOT NULL,
    [document_line_id] BIGINT NULL,
    [gst_rate_id] BIGINT NOT NULL,
    [tax_component] NVARCHAR(30) NOT NULL,
    [taxable_value] DECIMAL(18,2) NOT NULL,
    [rate] DECIMAL(5,2) NOT NULL,
    [tax_amount] DECIMAL(18,2) NOT NULL,
    [is_itc_eligible] BIT NULL,
    [gl_account_id] BIGINT NULL,
    CONSTRAINT [CK_acc_doc_tax_line_tax_component] CHECK ([tax_component] IN (N'CGST', N'SGST', N'IGST', N'Cess'))
);
GO
-- TDS deducted by us or deducted from us.
CREATE TABLE [acc].[tds_entry] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_tds_entry] PRIMARY KEY,
    [tds_section_id] BIGINT NOT NULL,
    [direction] NVARCHAR(30) NOT NULL,
    [supplier_id] BIGINT NULL,
    [customer_id] BIGINT NULL,
    [employee_id] BIGINT NULL,
    [document_type] NVARCHAR(40) NULL,
    [document_id] BIGINT NULL,
    [base_amount] DECIMAL(18,2) NOT NULL,
    [tds_rate] DECIMAL(5,2) NOT NULL,
    [tds_amount] DECIMAL(18,2) NOT NULL,
    [deduction_date] DATE NOT NULL,
    [challan_no] NVARCHAR(20) NULL,
    [challan_date] DATE NULL,
    [quarter] NVARCHAR(7) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_tds_entry_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_tds_entry_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_acc_tds_entry_direction] CHECK ([direction] IN (N'Deducted by us', N'Deducted from us'))
);
GO

/* ---------- 2. Unique keys (13) ---------- */
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_movement_class_code] ON [inv].[movement_class] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_bin_k1] ON [inv].[bin] ([location_id], [code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_movement_type_code] ON [inv].[movement_type] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_stock_balance_k1] ON [inv].[stock_balance] ([item_id], [location_id], [bin_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_serial_batch_k1] ON [inv].[serial_batch] ([item_id], [serial_or_batch_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_item_barcode_barcode] ON [inv].[item_barcode] ([barcode]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_stock_issue_issue_no] ON [inv].[stock_issue] ([issue_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_defective_return_return_no] ON [inv].[defective_return] ([return_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_stock_transfer_transfer_no] ON [inv].[stock_transfer] ([transfer_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_stock_adjustment_adjustment_no] ON [inv].[stock_adjustment] ([adjustment_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_stock_count_count_no] ON [inv].[stock_count] ([count_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_acc_journal_journal_no] ON [acc].[journal] ([journal_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_acc_bank_account_gl_account_id] ON [acc].[bank_account] ([gl_account_id]);
GO

/* ---------- 3. Foreign keys (88) ----------
   Includes links from earlier-phase columns to tables created in this phase. */
ALTER TABLE [core].[item] ADD CONSTRAINT [FK_core_item_movement_class_id] FOREIGN KEY ([movement_class_id]) REFERENCES [inv].[movement_class] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_part_request] ADD CONSTRAINT [FK_svc_service_part_request_stock_reservation_id] FOREIGN KEY ([stock_reservation_id]) REFERENCES [inv].[stock_reservation] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[bin] ADD CONSTRAINT [FK_inv_bin_location_id] FOREIGN KEY ([location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_balance] ADD CONSTRAINT [FK_inv_stock_balance_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_balance] ADD CONSTRAINT [FK_inv_stock_balance_location_id] FOREIGN KEY ([location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_balance] ADD CONSTRAINT [FK_inv_stock_balance_bin_id] FOREIGN KEY ([bin_id]) REFERENCES [inv].[bin] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[serial_batch] ADD CONSTRAINT [FK_inv_serial_batch_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[serial_batch] ADD CONSTRAINT [FK_inv_serial_batch_current_location_id] FOREIGN KEY ([current_location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_move] ADD CONSTRAINT [FK_inv_stock_move_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_move] ADD CONSTRAINT [FK_inv_stock_move_movement_type_id] FOREIGN KEY ([movement_type_id]) REFERENCES [inv].[movement_type] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_move] ADD CONSTRAINT [FK_inv_stock_move_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_move] ADD CONSTRAINT [FK_inv_stock_move_location_id] FOREIGN KEY ([location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_move] ADD CONSTRAINT [FK_inv_stock_move_bin_id] FOREIGN KEY ([bin_id]) REFERENCES [inv].[bin] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_move] ADD CONSTRAINT [FK_inv_stock_move_serial_batch_id] FOREIGN KEY ([serial_batch_id]) REFERENCES [inv].[serial_batch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_move] ADD CONSTRAINT [FK_inv_stock_move_performed_by_user_id] FOREIGN KEY ([performed_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[cost_layer] ADD CONSTRAINT [FK_inv_cost_layer_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[cost_layer] ADD CONSTRAINT [FK_inv_cost_layer_location_id] FOREIGN KEY ([location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[cost_layer] ADD CONSTRAINT [FK_inv_cost_layer_stock_move_id] FOREIGN KEY ([stock_move_id]) REFERENCES [inv].[stock_move] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[item_barcode] ADD CONSTRAINT [FK_inv_item_barcode_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_reservation] ADD CONSTRAINT [FK_inv_stock_reservation_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_reservation] ADD CONSTRAINT [FK_inv_stock_reservation_location_id] FOREIGN KEY ([location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_reservation] ADD CONSTRAINT [FK_inv_stock_reservation_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_reservation] ADD CONSTRAINT [FK_inv_stock_reservation_reserved_by_user_id] FOREIGN KEY ([reserved_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_issue] ADD CONSTRAINT [FK_inv_stock_issue_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_issue] ADD CONSTRAINT [FK_inv_stock_issue_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_issue] ADD CONSTRAINT [FK_inv_stock_issue_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_issue] ADD CONSTRAINT [FK_inv_stock_issue_issued_to_employee_id] FOREIGN KEY ([issued_to_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_issue] ADD CONSTRAINT [FK_inv_stock_issue_from_location_id] FOREIGN KEY ([from_location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_issue_line] ADD CONSTRAINT [FK_inv_stock_issue_line_stock_issue_id] FOREIGN KEY ([stock_issue_id]) REFERENCES [inv].[stock_issue] ([id]) ON DELETE CASCADE;
ALTER TABLE [inv].[stock_issue_line] ADD CONSTRAINT [FK_inv_stock_issue_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_issue_line] ADD CONSTRAINT [FK_inv_stock_issue_line_serial_batch_id] FOREIGN KEY ([serial_batch_id]) REFERENCES [inv].[serial_batch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_issue_line] ADD CONSTRAINT [FK_inv_stock_issue_line_service_part_request_id] FOREIGN KEY ([service_part_request_id]) REFERENCES [svc].[service_part_request] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[defective_return] ADD CONSTRAINT [FK_inv_defective_return_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[defective_return] ADD CONSTRAINT [FK_inv_defective_return_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[defective_return] ADD CONSTRAINT [FK_inv_defective_return_serial_batch_id] FOREIGN KEY ([serial_batch_id]) REFERENCES [inv].[serial_batch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[defective_return] ADD CONSTRAINT [FK_inv_defective_return_received_location_id] FOREIGN KEY ([received_location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_transfer] ADD CONSTRAINT [FK_inv_stock_transfer_from_location_id] FOREIGN KEY ([from_location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_transfer] ADD CONSTRAINT [FK_inv_stock_transfer_to_location_id] FOREIGN KEY ([to_location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_transfer_line] ADD CONSTRAINT [FK_inv_stock_transfer_line_stock_transfer_id] FOREIGN KEY ([stock_transfer_id]) REFERENCES [inv].[stock_transfer] ([id]) ON DELETE CASCADE;
ALTER TABLE [inv].[stock_transfer_line] ADD CONSTRAINT [FK_inv_stock_transfer_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_transfer_line] ADD CONSTRAINT [FK_inv_stock_transfer_line_serial_batch_id] FOREIGN KEY ([serial_batch_id]) REFERENCES [inv].[serial_batch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_adjustment] ADD CONSTRAINT [FK_inv_stock_adjustment_location_id] FOREIGN KEY ([location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_adjustment] ADD CONSTRAINT [FK_inv_stock_adjustment_reason_lookup_id] FOREIGN KEY ([reason_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_adjustment] ADD CONSTRAINT [FK_inv_stock_adjustment_stock_count_id] FOREIGN KEY ([stock_count_id]) REFERENCES [inv].[stock_count] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_adjustment_line] ADD CONSTRAINT [FK_inv_stock_adjustment_line_stock_adjustment_id] FOREIGN KEY ([stock_adjustment_id]) REFERENCES [inv].[stock_adjustment] ([id]) ON DELETE CASCADE;
ALTER TABLE [inv].[stock_adjustment_line] ADD CONSTRAINT [FK_inv_stock_adjustment_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_adjustment_line] ADD CONSTRAINT [FK_inv_stock_adjustment_line_bin_id] FOREIGN KEY ([bin_id]) REFERENCES [inv].[bin] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_adjustment_line] ADD CONSTRAINT [FK_inv_stock_adjustment_line_serial_batch_id] FOREIGN KEY ([serial_batch_id]) REFERENCES [inv].[serial_batch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_count] ADD CONSTRAINT [FK_inv_stock_count_location_id] FOREIGN KEY ([location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_count_line] ADD CONSTRAINT [FK_inv_stock_count_line_stock_count_id] FOREIGN KEY ([stock_count_id]) REFERENCES [inv].[stock_count] ([id]) ON DELETE CASCADE;
ALTER TABLE [inv].[stock_count_line] ADD CONSTRAINT [FK_inv_stock_count_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_count_line] ADD CONSTRAINT [FK_inv_stock_count_line_bin_id] FOREIGN KEY ([bin_id]) REFERENCES [inv].[bin] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_count_line] ADD CONSTRAINT [FK_inv_stock_count_line_counted_by_user_id] FOREIGN KEY ([counted_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[journal] ADD CONSTRAINT [FK_acc_journal_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[journal] ADD CONSTRAINT [FK_acc_journal_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[journal] ADD CONSTRAINT [FK_acc_journal_fiscal_year_id] FOREIGN KEY ([fiscal_year_id]) REFERENCES [acc].[fiscal_year] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[journal] ADD CONSTRAINT [FK_acc_journal_reversed_journal_id] FOREIGN KEY ([reversed_journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[journal] ADD CONSTRAINT [FK_acc_journal_posted_by_user_id] FOREIGN KEY ([posted_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[gl_entry] ADD CONSTRAINT [FK_acc_gl_entry_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE CASCADE;
ALTER TABLE [acc].[gl_entry] ADD CONSTRAINT [FK_acc_gl_entry_gl_account_id] FOREIGN KEY ([gl_account_id]) REFERENCES [acc].[gl_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[gl_entry] ADD CONSTRAINT [FK_acc_gl_entry_cost_centre_id] FOREIGN KEY ([cost_centre_id]) REFERENCES [acc].[cost_centre] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[gl_entry] ADD CONSTRAINT [FK_acc_gl_entry_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[gl_entry] ADD CONSTRAINT [FK_acc_gl_entry_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[gl_entry] ADD CONSTRAINT [FK_acc_gl_entry_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[gl_entry] ADD CONSTRAINT [FK_acc_gl_entry_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[gl_entry] ADD CONSTRAINT [FK_acc_gl_entry_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[opening_balance] ADD CONSTRAINT [FK_acc_opening_balance_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[opening_balance] ADD CONSTRAINT [FK_acc_opening_balance_fiscal_year_id] FOREIGN KEY ([fiscal_year_id]) REFERENCES [acc].[fiscal_year] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[opening_balance] ADD CONSTRAINT [FK_acc_opening_balance_gl_account_id] FOREIGN KEY ([gl_account_id]) REFERENCES [acc].[gl_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[opening_balance] ADD CONSTRAINT [FK_acc_opening_balance_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[opening_balance] ADD CONSTRAINT [FK_acc_opening_balance_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[opening_balance] ADD CONSTRAINT [FK_acc_opening_balance_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[bank_account] ADD CONSTRAINT [FK_acc_bank_account_gl_account_id] FOREIGN KEY ([gl_account_id]) REFERENCES [acc].[gl_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[bank_account] ADD CONSTRAINT [FK_acc_bank_account_currency_id] FOREIGN KEY ([currency_id]) REFERENCES [core].[currency] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[bank_statement_line] ADD CONSTRAINT [FK_acc_bank_statement_line_bank_account_id] FOREIGN KEY ([bank_account_id]) REFERENCES [acc].[bank_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[bank_statement_line] ADD CONSTRAINT [FK_acc_bank_statement_line_file_import_id] FOREIGN KEY ([file_import_id]) REFERENCES [int].[file_import] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[bank_txn] ADD CONSTRAINT [FK_acc_bank_txn_bank_account_id] FOREIGN KEY ([bank_account_id]) REFERENCES [acc].[bank_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[bank_txn] ADD CONSTRAINT [FK_acc_bank_txn_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[bank_txn] ADD CONSTRAINT [FK_acc_bank_txn_bank_statement_line_id] FOREIGN KEY ([bank_statement_line_id]) REFERENCES [acc].[bank_statement_line] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[budget] ADD CONSTRAINT [FK_acc_budget_fiscal_year_id] FOREIGN KEY ([fiscal_year_id]) REFERENCES [acc].[fiscal_year] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[budget] ADD CONSTRAINT [FK_acc_budget_gl_account_id] FOREIGN KEY ([gl_account_id]) REFERENCES [acc].[gl_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[budget] ADD CONSTRAINT [FK_acc_budget_cost_centre_id] FOREIGN KEY ([cost_centre_id]) REFERENCES [acc].[cost_centre] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[doc_tax_line] ADD CONSTRAINT [FK_acc_doc_tax_line_gst_rate_id] FOREIGN KEY ([gst_rate_id]) REFERENCES [acc].[gst_rate] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[doc_tax_line] ADD CONSTRAINT [FK_acc_doc_tax_line_gl_account_id] FOREIGN KEY ([gl_account_id]) REFERENCES [acc].[gl_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[tds_entry] ADD CONSTRAINT [FK_acc_tds_entry_tds_section_id] FOREIGN KEY ([tds_section_id]) REFERENCES [acc].[tds_section] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[tds_entry] ADD CONSTRAINT [FK_acc_tds_entry_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[tds_entry] ADD CONSTRAINT [FK_acc_tds_entry_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[tds_entry] ADD CONSTRAINT [FK_acc_tds_entry_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
GO

/* ---------- 4. Foreign-key indexes (87) ---------- */
CREATE NONCLUSTERED INDEX [IX_core_item_movement_class_id] ON [core].[item] ([movement_class_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_part_request_stock_reservation_id] ON [svc].[service_part_request] ([stock_reservation_id]);
CREATE NONCLUSTERED INDEX [IX_inv_bin_location_id] ON [inv].[bin] ([location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_balance_item_id] ON [inv].[stock_balance] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_balance_location_id] ON [inv].[stock_balance] ([location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_balance_bin_id] ON [inv].[stock_balance] ([bin_id]);
CREATE NONCLUSTERED INDEX [IX_inv_serial_batch_item_id] ON [inv].[serial_batch] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_serial_batch_current_location_id] ON [inv].[serial_batch] ([current_location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_move_company_id] ON [inv].[stock_move] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_move_movement_type_id] ON [inv].[stock_move] ([movement_type_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_move_item_id] ON [inv].[stock_move] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_move_location_id] ON [inv].[stock_move] ([location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_move_bin_id] ON [inv].[stock_move] ([bin_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_move_serial_batch_id] ON [inv].[stock_move] ([serial_batch_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_move_performed_by_user_id] ON [inv].[stock_move] ([performed_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_inv_cost_layer_item_id] ON [inv].[cost_layer] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_cost_layer_location_id] ON [inv].[cost_layer] ([location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_cost_layer_stock_move_id] ON [inv].[cost_layer] ([stock_move_id]);
CREATE NONCLUSTERED INDEX [IX_inv_item_barcode_item_id] ON [inv].[item_barcode] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_reservation_item_id] ON [inv].[stock_reservation] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_reservation_location_id] ON [inv].[stock_reservation] ([location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_reservation_service_call_id] ON [inv].[stock_reservation] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_reservation_reserved_by_user_id] ON [inv].[stock_reservation] ([reserved_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_issue_branch_id] ON [inv].[stock_issue] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_issue_principal_id] ON [inv].[stock_issue] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_issue_service_call_id] ON [inv].[stock_issue] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_issue_issued_to_employee_id] ON [inv].[stock_issue] ([issued_to_employee_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_issue_from_location_id] ON [inv].[stock_issue] ([from_location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_issue_line_stock_issue_id] ON [inv].[stock_issue_line] ([stock_issue_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_issue_line_item_id] ON [inv].[stock_issue_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_issue_line_serial_batch_id] ON [inv].[stock_issue_line] ([serial_batch_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_issue_line_service_part_request_id] ON [inv].[stock_issue_line] ([service_part_request_id]);
CREATE NONCLUSTERED INDEX [IX_inv_defective_return_service_call_id] ON [inv].[defective_return] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_inv_defective_return_item_id] ON [inv].[defective_return] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_defective_return_serial_batch_id] ON [inv].[defective_return] ([serial_batch_id]);
CREATE NONCLUSTERED INDEX [IX_inv_defective_return_received_location_id] ON [inv].[defective_return] ([received_location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_transfer_from_location_id] ON [inv].[stock_transfer] ([from_location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_transfer_to_location_id] ON [inv].[stock_transfer] ([to_location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_transfer_line_stock_transfer_id] ON [inv].[stock_transfer_line] ([stock_transfer_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_transfer_line_item_id] ON [inv].[stock_transfer_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_transfer_line_serial_batch_id] ON [inv].[stock_transfer_line] ([serial_batch_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_adjustment_location_id] ON [inv].[stock_adjustment] ([location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_adjustment_reason_lookup_id] ON [inv].[stock_adjustment] ([reason_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_adjustment_stock_count_id] ON [inv].[stock_adjustment] ([stock_count_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_adjustment_line_stock_adjustment_id] ON [inv].[stock_adjustment_line] ([stock_adjustment_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_adjustment_line_item_id] ON [inv].[stock_adjustment_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_adjustment_line_bin_id] ON [inv].[stock_adjustment_line] ([bin_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_adjustment_line_serial_batch_id] ON [inv].[stock_adjustment_line] ([serial_batch_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_count_location_id] ON [inv].[stock_count] ([location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_count_line_stock_count_id] ON [inv].[stock_count_line] ([stock_count_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_count_line_item_id] ON [inv].[stock_count_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_count_line_bin_id] ON [inv].[stock_count_line] ([bin_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_count_line_counted_by_user_id] ON [inv].[stock_count_line] ([counted_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_acc_journal_company_id] ON [acc].[journal] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_acc_journal_branch_id] ON [acc].[journal] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_acc_journal_fiscal_year_id] ON [acc].[journal] ([fiscal_year_id]);
CREATE NONCLUSTERED INDEX [IX_acc_journal_reversed_journal_id] ON [acc].[journal] ([reversed_journal_id]);
CREATE NONCLUSTERED INDEX [IX_acc_journal_posted_by_user_id] ON [acc].[journal] ([posted_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gl_entry_journal_id] ON [acc].[gl_entry] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gl_entry_gl_account_id] ON [acc].[gl_entry] ([gl_account_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gl_entry_cost_centre_id] ON [acc].[gl_entry] ([cost_centre_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gl_entry_principal_id] ON [acc].[gl_entry] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gl_entry_branch_id] ON [acc].[gl_entry] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gl_entry_customer_id] ON [acc].[gl_entry] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gl_entry_supplier_id] ON [acc].[gl_entry] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gl_entry_employee_id] ON [acc].[gl_entry] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_acc_opening_balance_company_id] ON [acc].[opening_balance] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_acc_opening_balance_fiscal_year_id] ON [acc].[opening_balance] ([fiscal_year_id]);
CREATE NONCLUSTERED INDEX [IX_acc_opening_balance_gl_account_id] ON [acc].[opening_balance] ([gl_account_id]);
CREATE NONCLUSTERED INDEX [IX_acc_opening_balance_customer_id] ON [acc].[opening_balance] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_acc_opening_balance_supplier_id] ON [acc].[opening_balance] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_acc_opening_balance_journal_id] ON [acc].[opening_balance] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_acc_bank_account_currency_id] ON [acc].[bank_account] ([currency_id]);
CREATE NONCLUSTERED INDEX [IX_acc_bank_statement_line_bank_account_id] ON [acc].[bank_statement_line] ([bank_account_id]);
CREATE NONCLUSTERED INDEX [IX_acc_bank_statement_line_file_import_id] ON [acc].[bank_statement_line] ([file_import_id]);
CREATE NONCLUSTERED INDEX [IX_acc_bank_txn_bank_account_id] ON [acc].[bank_txn] ([bank_account_id]);
CREATE NONCLUSTERED INDEX [IX_acc_bank_txn_journal_id] ON [acc].[bank_txn] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_acc_bank_txn_bank_statement_line_id] ON [acc].[bank_txn] ([bank_statement_line_id]);
CREATE NONCLUSTERED INDEX [IX_acc_budget_fiscal_year_id] ON [acc].[budget] ([fiscal_year_id]);
CREATE NONCLUSTERED INDEX [IX_acc_budget_gl_account_id] ON [acc].[budget] ([gl_account_id]);
CREATE NONCLUSTERED INDEX [IX_acc_budget_cost_centre_id] ON [acc].[budget] ([cost_centre_id]);
CREATE NONCLUSTERED INDEX [IX_acc_doc_tax_line_gst_rate_id] ON [acc].[doc_tax_line] ([gst_rate_id]);
CREATE NONCLUSTERED INDEX [IX_acc_doc_tax_line_gl_account_id] ON [acc].[doc_tax_line] ([gl_account_id]);
CREATE NONCLUSTERED INDEX [IX_acc_tds_entry_tds_section_id] ON [acc].[tds_entry] ([tds_section_id]);
CREATE NONCLUSTERED INDEX [IX_acc_tds_entry_supplier_id] ON [acc].[tds_entry] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_acc_tds_entry_customer_id] ON [acc].[tds_entry] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_acc_tds_entry_employee_id] ON [acc].[tds_entry] ([employee_id]);
GO
