/* =====================================================================
   TRISHUL Integrated System - SQL Server DDL (dictionary v2)
   Phase 3 - Purchase + HR
   Generated from the TRISHUL Database Dictionary. Do not edit by hand:
   change the dictionary and regenerate.
   Target: SQL Server 2019+ / Amazon RDS for SQL Server
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
/* ---------- 1. Tables (46) ---------- */

/* ===== svc: Call & Service ===== */
-- Warranty claim to the OEM for a failed part.
CREATE TABLE [svc].[warranty_claim] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_warranty_claim] PRIMARY KEY,
    [claim_no] NVARCHAR(30) NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [service_call_id] BIGINT NOT NULL,
    [machine_unit_id] BIGINT NOT NULL,
    [failure_code_lookup_id] BIGINT NULL,
    [claim_date] DATE NOT NULL,
    [claimed_amount] DECIMAL(18,2) NULL,
    [approved_amount] DECIMAL(18,2) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [oem_claim_ref] NVARCHAR(40) NULL,
    [credit_note_ref] NVARCHAR(40) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_warranty_claim_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_warranty_claim_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_warranty_claim_status] CHECK ([status] IN (N'Draft', N'Submitted', N'Approved', N'Rejected', N'Settled'))
);
GO
-- Parts in a warranty claim.
CREATE TABLE [svc].[warranty_claim_part] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_warranty_claim_part] PRIMARY KEY,
    [warranty_claim_id] BIGINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [failed_part_serial] NVARCHAR(60) NULL,
    [is_returned_to_oem] BIT NOT NULL CONSTRAINT [DF_svc_warranty_claim_part_is_returned_to_oem] DEFAULT (0),
    [return_docket_no] NVARCHAR(40) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_warranty_claim_part_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_warranty_claim_part_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO

/* ===== pur: Purchase ===== */
-- Supplier prices and part numbers for items.
CREATE TABLE [pur].[supplier_item_price] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_supplier_item_price] PRIMARY KEY,
    [supplier_id] BIGINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [supplier_part_no] NVARCHAR(40) NULL,
    [supplier_uom] NVARCHAR(10) NULL,
    [conversion_factor] DECIMAL(12,4) NOT NULL CONSTRAINT [DF_pur_supplier_item_price_conversion_factor] DEFAULT (1),
    [price] DECIMAL(18,4) NOT NULL,
    [currency_id] BIGINT NOT NULL,
    [valid_from] DATE NULL,
    [valid_to] DATE NULL,
    [lead_time_days] SMALLINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_supplier_item_price_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_supplier_item_price_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Internal request to buy (reorder, service need, manual).
CREATE TABLE [pur].[purchase_request] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_purchase_request] PRIMARY KEY,
    [pr_no] NVARCHAR(30) NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [principal_id] BIGINT NULL,
    [requested_by_employee_id] BIGINT NOT NULL,
    [request_date] DATE NOT NULL,
    [required_by] DATE NULL,
    [source_type] NVARCHAR(30) NOT NULL,
    [service_call_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_purchase_request_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_purchase_request_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pur_purchase_request_source_type] CHECK ([source_type] IN (N'Reorder', N'Service call', N'Manual')),
    CONSTRAINT [CK_pur_purchase_request_status] CHECK ([status] IN (N'Draft', N'Pending approval', N'Approved', N'Ordered', N'Rejected'))
);
GO
-- Items requested.
CREATE TABLE [pur].[purchase_request_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_purchase_request_line] PRIMARY KEY,
    [purchase_request_id] BIGINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [remarks] NVARCHAR(200) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_purchase_request_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_purchase_request_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Purchase order to a supplier.
CREATE TABLE [pur].[purchase_order] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_purchase_order] PRIMARY KEY,
    [po_no] NVARCHAR(30) NOT NULL,
    [company_id] BIGINT NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [supplier_id] BIGINT NOT NULL,
    [principal_id] BIGINT NULL,
    [po_date] DATE NOT NULL,
    [expected_date] DATE NULL,
    [delivery_location_id] BIGINT NOT NULL,
    [payment_terms_id] BIGINT NULL,
    [place_of_supply_state_id] BIGINT NOT NULL,
    [currency_id] BIGINT NOT NULL,
    [subtotal] DECIMAL(18,2) NOT NULL,
    [tax_total] DECIMAL(18,2) NOT NULL,
    [total] DECIMAL(18,2) NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [oem_po_ref] NVARCHAR(40) NULL,
    [remarks] NVARCHAR(500) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_purchase_order_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_purchase_order_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pur_purchase_order_status] CHECK ([status] IN (N'Draft', N'Pending approval', N'Approved', N'Sent', N'Part received', N'Closed', N'Cancelled'))
);
GO
-- PO lines.
CREATE TABLE [pur].[purchase_order_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_purchase_order_line] PRIMARY KEY,
    [purchase_order_id] BIGINT NOT NULL,
    [line_no] SMALLINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [description] NVARCHAR(200) NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [uom_id] BIGINT NOT NULL,
    [unit_price] DECIMAL(18,4) NOT NULL,
    [discount_pct] DECIMAL(5,2) NULL,
    [hsn_sac_id] BIGINT NULL,
    [gst_rate_id] BIGINT NULL,
    [taxable_value] DECIMAL(18,2) NOT NULL,
    [tax_amount] DECIMAL(18,2) NOT NULL,
    [line_total] DECIMAL(18,2) NOT NULL,
    [qty_received] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_pur_purchase_order_line_qty_received] DEFAULT (0),
    [qty_invoiced] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_pur_purchase_order_line_qty_invoiced] DEFAULT (0),
    [purchase_request_line_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_purchase_order_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_purchase_order_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Goods receipt note.
CREATE TABLE [pur].[grn] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_grn] PRIMARY KEY,
    [grn_no] NVARCHAR(30) NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [supplier_id] BIGINT NOT NULL,
    [purchase_order_id] BIGINT NULL,
    [principal_id] BIGINT NULL,
    [grn_date] DATE NOT NULL,
    [location_id] BIGINT NOT NULL,
    [supplier_invoice_no] NVARCHAR(40) NULL,
    [supplier_invoice_date] DATE NULL,
    [vehicle_no] NVARCHAR(20) NULL,
    [lr_no] NVARCHAR(40) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_grn_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_grn_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pur_grn_status] CHECK ([status] IN (N'Draft', N'Posted', N'Cancelled'))
);
GO
-- Items received.
CREATE TABLE [pur].[grn_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_grn_line] PRIMARY KEY,
    [grn_id] BIGINT NOT NULL,
    [purchase_order_line_id] BIGINT NULL,
    [item_id] BIGINT NOT NULL,
    [qty_received] DECIMAL(18,3) NOT NULL,
    [qty_accepted] DECIMAL(18,3) NOT NULL,
    [qty_rejected] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_pur_grn_line_qty_rejected] DEFAULT (0),
    [bin_id] BIGINT NULL,
    [unit_cost] DECIMAL(18,4) NOT NULL,
    [rejection_reason] NVARCHAR(200) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_grn_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_grn_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Supplier bill (accounts payable).
CREATE TABLE [pur].[supplier_invoice] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_supplier_invoice] PRIMARY KEY,
    [invoice_no] NVARCHAR(30) NOT NULL,
    [supplier_invoice_no] NVARCHAR(40) NOT NULL,
    [supplier_invoice_date] DATE NOT NULL,
    [supplier_id] BIGINT NOT NULL,
    [principal_id] BIGINT NULL,
    [branch_id] BIGINT NOT NULL,
    [purchase_order_id] BIGINT NULL,
    [grn_id] BIGINT NULL,
    [place_of_supply_state_id] BIGINT NOT NULL,
    [is_reverse_charge] BIT NOT NULL CONSTRAINT [DF_pur_supplier_invoice_is_reverse_charge] DEFAULT (0),
    [taxable_value] DECIMAL(18,2) NOT NULL,
    [cgst] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_pur_supplier_invoice_cgst] DEFAULT (0),
    [sgst] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_pur_supplier_invoice_sgst] DEFAULT (0),
    [igst] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_pur_supplier_invoice_igst] DEFAULT (0),
    [cess] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_pur_supplier_invoice_cess] DEFAULT (0),
    [tds_amount] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_pur_supplier_invoice_tds_amount] DEFAULT (0),
    [round_off] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_pur_supplier_invoice_round_off] DEFAULT (0),
    [total] DECIMAL(18,2) NOT NULL,
    [due_date] DATE NULL,
    [amount_paid] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_pur_supplier_invoice_amount_paid] DEFAULT (0),
    [status] NVARCHAR(30) NOT NULL,
    [journal_id] BIGINT NULL,
    [oem_invoice_ref] NVARCHAR(40) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_supplier_invoice_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_supplier_invoice_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pur_supplier_invoice_status] CHECK ([status] IN (N'Draft', N'Posted', N'Part paid', N'Paid', N'Cancelled'))
);
GO
-- Supplier bill lines.
CREATE TABLE [pur].[supplier_invoice_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_supplier_invoice_line] PRIMARY KEY,
    [supplier_invoice_id] BIGINT NOT NULL,
    [grn_line_id] BIGINT NULL,
    [purchase_order_line_id] BIGINT NULL,
    [item_id] BIGINT NULL,
    [gl_account_id] BIGINT NULL,
    [description] NVARCHAR(200) NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [unit_price] DECIMAL(18,4) NOT NULL,
    [hsn_sac_id] BIGINT NULL,
    [gst_rate_id] BIGINT NULL,
    [taxable_value] DECIMAL(18,2) NOT NULL,
    [tax_amount] DECIMAL(18,2) NOT NULL,
    [line_total] DECIMAL(18,2) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_supplier_invoice_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_supplier_invoice_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Payment made to a supplier.
CREATE TABLE [pur].[supplier_payment] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_supplier_payment] PRIMARY KEY,
    [payment_no] NVARCHAR(30) NOT NULL,
    [supplier_id] BIGINT NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [payment_date] DATE NOT NULL,
    [payment_mode] NVARCHAR(30) NOT NULL,
    [bank_account_id] BIGINT NULL,
    [cheque_id] BIGINT NULL,
    [reference_no] NVARCHAR(40) NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [tds_deducted] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_pur_supplier_payment_tds_deducted] DEFAULT (0),
    [status] NVARCHAR(30) NOT NULL,
    [journal_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_supplier_payment_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_supplier_payment_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pur_supplier_payment_payment_mode] CHECK ([payment_mode] IN (N'NEFT', N'RTGS', N'Cheque', N'Cash', N'UPI')),
    CONSTRAINT [CK_pur_supplier_payment_status] CHECK ([status] IN (N'Draft', N'Posted', N'Cancelled'))
);
GO
-- Purchase return / debit note to supplier.
CREATE TABLE [pur].[debit_note] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_debit_note] PRIMARY KEY,
    [debit_note_no] NVARCHAR(30) NOT NULL,
    [supplier_id] BIGINT NOT NULL,
    [supplier_invoice_id] BIGINT NULL,
    [grn_id] BIGINT NULL,
    [note_date] DATE NOT NULL,
    [reason_lookup_id] BIGINT NULL,
    [taxable_value] DECIMAL(18,2) NOT NULL,
    [tax_amount] DECIMAL(18,2) NOT NULL,
    [total] DECIMAL(18,2) NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [journal_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_debit_note_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_debit_note_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pur_debit_note_status] CHECK ([status] IN (N'Draft', N'Posted', N'Cancelled'))
);
GO
-- Returned items.
CREATE TABLE [pur].[debit_note_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_debit_note_line] PRIMARY KEY,
    [debit_note_id] BIGINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [serial_batch_id] BIGINT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [unit_price] DECIMAL(18,4) NOT NULL,
    [gst_rate_id] BIGINT NULL,
    [tax_amount] DECIMAL(18,2) NOT NULL,
    [line_total] DECIMAL(18,2) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_debit_note_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_debit_note_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Matches payments and debit notes to supplier bills.
CREATE TABLE [pur].[supplier_allocation] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_supplier_allocation] PRIMARY KEY,
    [supplier_invoice_id] BIGINT NOT NULL,
    [supplier_payment_id] BIGINT NULL,
    [debit_note_id] BIGINT NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [allocated_on] DATE NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_supplier_allocation_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_supplier_allocation_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO

/* ===== hr: HR & Payroll ===== */
-- Departments.
CREATE TABLE [hr].[department] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_department] PRIMARY KEY,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(80) NOT NULL,
    [parent_department_id] BIGINT NULL,
    [head_employee_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_department_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_department_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Designations and grades.
CREATE TABLE [hr].[designation] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_designation] PRIMARY KEY,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(80) NOT NULL,
    [grade] NVARCHAR(10) NULL,
    [department_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_designation_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_designation_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Personal, statutory and bank details (1:1 with employee).
CREATE TABLE [hr].[employee_profile] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_employee_profile] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [date_of_birth] DATE NULL,
    [gender] NVARCHAR(30) NULL,
    [personal_email] NVARCHAR(120) NULL,
    [current_address] NVARCHAR(500) NULL,
    [permanent_address] NVARCHAR(500) NULL,
    [emergency_contact_name] NVARCHAR(100) NULL,
    [emergency_contact_phone] NVARCHAR(15) NULL,
    [pan] NVARCHAR(10) NULL,
    [aadhaar_masked] NVARCHAR(14) NULL,
    [uan] NVARCHAR(12) NULL,
    [esic_no] NVARCHAR(17) NULL,
    [bank_name] NVARCHAR(100) NULL,
    [bank_account_no] NVARCHAR(30) NULL,
    [ifsc] NVARCHAR(11) NULL,
    [is_pf_applicable] BIT NOT NULL CONSTRAINT [DF_hr_employee_profile_is_pf_applicable] DEFAULT (1),
    [is_esi_applicable] BIT NOT NULL CONSTRAINT [DF_hr_employee_profile_is_esi_applicable] DEFAULT (0),
    [pt_state_id] BIGINT NULL,
    [tax_regime] NVARCHAR(30) NOT NULL CONSTRAINT [DF_hr_employee_profile_tax_regime] DEFAULT (N'New'),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_employee_profile_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_employee_profile_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_employee_profile_gender] CHECK ([gender] IN (N'Male', N'Female', N'Other')),
    CONSTRAINT [CK_hr_employee_profile_tax_regime] CHECK ([tax_regime] IN (N'Old', N'New'))
);
GO
-- Joining, confirmation, transfer, promotion, exit.
CREATE TABLE [hr].[employment_history] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_employment_history] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [event_type] NVARCHAR(30) NOT NULL,
    [effective_date] DATE NOT NULL,
    [from_branch_id] BIGINT NULL,
    [to_branch_id] BIGINT NULL,
    [from_designation_id] BIGINT NULL,
    [to_designation_id] BIGINT NULL,
    [remarks] NVARCHAR(500) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_employment_history_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_employment_history_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_employment_history_event_type] CHECK ([event_type] IN (N'Joined', N'Confirmed', N'Transferred', N'Promoted', N'Resigned', N'Terminated', N'Retired'))
);
GO
-- Employee documents (offer letter, ID proof, licence).
CREATE TABLE [hr].[employee_document] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_employee_document] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [document_type_lookup_id] BIGINT NOT NULL,
    [document_number_masked] NVARCHAR(30) NULL,
    [attachment_id] BIGINT NOT NULL,
    [valid_until] DATE NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_employee_document_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_employee_document_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Onboarding and offboarding checklist.
CREATE TABLE [hr].[onboarding_task] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_onboarding_task] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [task_type] NVARCHAR(30) NOT NULL,
    [task_name] NVARCHAR(200) NOT NULL,
    [owner_employee_id] BIGINT NULL,
    [due_date] DATE NULL,
    [completed_at] DATETIME2(0) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_onboarding_task_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_onboarding_task_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_onboarding_task_task_type] CHECK ([task_type] IN (N'Onboarding', N'Offboarding')),
    CONSTRAINT [CK_hr_onboarding_task_status] CHECK ([status] IN (N'Pending', N'Done', N'Not applicable'))
);
GO
-- Work shifts.
CREATE TABLE [hr].[shift] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_shift] PRIMARY KEY,
    [code] NVARCHAR(10) NOT NULL,
    [name] NVARCHAR(60) NOT NULL,
    [start_time] TIME(0) NOT NULL,
    [end_time] TIME(0) NOT NULL,
    [grace_minutes] SMALLINT NOT NULL CONSTRAINT [DF_hr_shift_grace_minutes] DEFAULT (10),
    [half_day_hours] DECIMAL(4,2) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_shift_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_shift_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Shift and weekly off per employee.
CREATE TABLE [hr].[employee_shift] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_employee_shift] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [shift_id] BIGINT NOT NULL,
    [weekly_off_days] NVARCHAR(20) NULL,
    [from_date] DATE NOT NULL,
    [to_date] DATE NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_employee_shift_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_employee_shift_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Holiday calendar.
CREATE TABLE [hr].[holiday] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_holiday] PRIMARY KEY,
    [branch_id] BIGINT NULL,
    [holiday_date] DATE NOT NULL,
    [name] NVARCHAR(80) NOT NULL,
    [holiday_type] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_holiday_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_holiday_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_holiday_holiday_type] CHECK ([holiday_type] IN (N'National', N'Festival', N'Optional'))
);
GO
-- Daily attendance (app, biometric, or engineer duty log).
CREATE TABLE [hr].[attendance] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_attendance] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [attendance_date] DATE NOT NULL,
    [shift_id] BIGINT NULL,
    [check_in_at] DATETIME2(0) NULL,
    [check_in_latitude] DECIMAL(9,6) NULL,
    [check_in_longitude] DECIMAL(9,6) NULL,
    [check_out_at] DATETIME2(0) NULL,
    [check_out_latitude] DECIMAL(9,6) NULL,
    [check_out_longitude] DECIMAL(9,6) NULL,
    [source] NVARCHAR(30) NOT NULL,
    [duty_log_id] BIGINT NULL,
    [worked_hours] DECIMAL(4,2) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [is_regularized] BIT NOT NULL CONSTRAINT [DF_hr_attendance_is_regularized] DEFAULT (0),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_attendance_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_attendance_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_attendance_source] CHECK ([source] IN (N'App', N'Biometric', N'Duty log', N'Manual')),
    CONSTRAINT [CK_hr_attendance_status] CHECK ([status] IN (N'Present', N'Absent', N'Half day', N'Leave', N'Holiday', N'Week off', N'On duty'))
);
GO
-- Requests to correct attendance.
CREATE TABLE [hr].[attendance_regularization] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_attendance_regularization] PRIMARY KEY,
    [attendance_id] BIGINT NOT NULL,
    [employee_id] BIGINT NOT NULL,
    [requested_status] NVARCHAR(20) NOT NULL,
    [reason] NVARCHAR(300) NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [approver_user_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_attendance_regularization_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_attendance_regularization_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_attendance_regularization_status] CHECK ([status] IN (N'Pending', N'Approved', N'Rejected'))
);
GO
-- Leave types.
CREATE TABLE [hr].[leave_type] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_leave_type] PRIMARY KEY,
    [code] NVARCHAR(10) NOT NULL,
    [name] NVARCHAR(60) NOT NULL,
    [annual_quota] DECIMAL(5,1) NULL,
    [carry_forward_max] DECIMAL(5,1) NULL,
    [is_paid] BIT NOT NULL CONSTRAINT [DF_hr_leave_type_is_paid] DEFAULT (1),
    [is_encashable] BIT NOT NULL CONSTRAINT [DF_hr_leave_type_is_encashable] DEFAULT (0),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_leave_type_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_leave_type_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Leave balance per employee per year.
CREATE TABLE [hr].[leave_balance] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_leave_balance] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [leave_type_id] BIGINT NOT NULL,
    [leave_year] SMALLINT NOT NULL,
    [opening] DECIMAL(5,1) NOT NULL CONSTRAINT [DF_hr_leave_balance_opening] DEFAULT (0),
    [accrued] DECIMAL(5,1) NOT NULL CONSTRAINT [DF_hr_leave_balance_accrued] DEFAULT (0),
    [availed] DECIMAL(5,1) NOT NULL CONSTRAINT [DF_hr_leave_balance_availed] DEFAULT (0),
    [encashed] DECIMAL(5,1) NOT NULL CONSTRAINT [DF_hr_leave_balance_encashed] DEFAULT (0),
    [closing] DECIMAL(5,1) NOT NULL CONSTRAINT [DF_hr_leave_balance_closing] DEFAULT (0),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_leave_balance_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_leave_balance_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Leave applications.
CREATE TABLE [hr].[leave_request] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_leave_request] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [leave_type_id] BIGINT NOT NULL,
    [from_date] DATE NOT NULL,
    [to_date] DATE NOT NULL,
    [is_half_day] BIT NOT NULL CONSTRAINT [DF_hr_leave_request_is_half_day] DEFAULT (0),
    [days] DECIMAL(4,1) NOT NULL,
    [reason] NVARCHAR(300) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [approver_user_id] BIGINT NULL,
    [acted_at] DATETIME2(0) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_leave_request_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_leave_request_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_leave_request_status] CHECK ([status] IN (N'Pending', N'Approved', N'Rejected', N'Cancelled'))
);
GO
-- Earnings, deductions and employer contributions.
CREATE TABLE [hr].[salary_component] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_salary_component] PRIMARY KEY,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(80) NOT NULL,
    [component_type] NVARCHAR(30) NOT NULL,
    [calculation_type] NVARCHAR(30) NOT NULL,
    [is_taxable] BIT NOT NULL CONSTRAINT [DF_hr_salary_component_is_taxable] DEFAULT (1),
    [is_pf_wage] BIT NOT NULL CONSTRAINT [DF_hr_salary_component_is_pf_wage] DEFAULT (0),
    [is_esi_wage] BIT NOT NULL CONSTRAINT [DF_hr_salary_component_is_esi_wage] DEFAULT (0),
    [gl_account_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_salary_component_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_salary_component_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_salary_component_component_type] CHECK ([component_type] IN (N'Earning', N'Deduction', N'Employer contribution')),
    CONSTRAINT [CK_hr_salary_component_calculation_type] CHECK ([calculation_type] IN (N'Fixed', N'Percent of basic', N'Formula', N'Statutory'))
);
GO
-- Employee salary structure with effective dates.
CREATE TABLE [hr].[salary_structure] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_salary_structure] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [effective_from] DATE NOT NULL,
    [effective_to] DATE NULL,
    [annual_ctc] DECIMAL(18,2) NOT NULL,
    [monthly_gross] DECIMAL(18,2) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_salary_structure_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_salary_structure_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Components in a structure.
CREATE TABLE [hr].[salary_structure_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_salary_structure_line] PRIMARY KEY,
    [salary_structure_id] BIGINT NOT NULL,
    [salary_component_id] BIGINT NOT NULL,
    [monthly_amount] DECIMAL(18,2) NULL,
    [percentage] DECIMAL(5,2) NULL,
    [formula] NVARCHAR(300) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_salary_structure_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_salary_structure_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- PF, ESI, PT, LWF, TDS rates and ceilings.
CREATE TABLE [hr].[statutory_config] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_statutory_config] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [config_type] NVARCHAR(30) NOT NULL,
    [state_id] BIGINT NULL,
    [effective_from] DATE NOT NULL,
    [employee_rate] DECIMAL(5,2) NULL,
    [employer_rate] DECIMAL(5,2) NULL,
    [wage_ceiling] DECIMAL(18,2) NULL,
    [slab_json] NVARCHAR(MAX) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_statutory_config_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_statutory_config_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_statutory_config_config_type] CHECK ([config_type] IN (N'PF', N'ESI', N'PT', N'LWF', N'TDS'))
);
GO
-- Monthly payroll run.
CREATE TABLE [hr].[payroll_run] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_payroll_run] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [branch_id] BIGINT NULL,
    [period_month] DATE NOT NULL,
    [run_date] DATE NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [total_gross] DECIMAL(18,2) NULL,
    [total_deductions] DECIMAL(18,2) NULL,
    [total_net] DECIMAL(18,2) NULL,
    [journal_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_payroll_run_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_payroll_run_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_payroll_run_status] CHECK ([status] IN (N'Draft', N'Processed', N'Approved', N'Paid', N'Locked'))
);
GO
-- Payslip per employee per run.
CREATE TABLE [hr].[payslip] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_payslip] PRIMARY KEY,
    [payroll_run_id] BIGINT NOT NULL,
    [employee_id] BIGINT NOT NULL,
    [paid_days] DECIMAL(4,1) NOT NULL,
    [lop_days] DECIMAL(4,1) NOT NULL CONSTRAINT [DF_hr_payslip_lop_days] DEFAULT (0),
    [gross] DECIMAL(18,2) NOT NULL,
    [total_deductions] DECIMAL(18,2) NOT NULL,
    [net_pay] DECIMAL(18,2) NOT NULL,
    [pdf_attachment_id] BIGINT NULL,
    [payment_reference] NVARCHAR(40) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_payslip_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_payslip_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Component amounts in a payslip.
CREATE TABLE [hr].[payslip_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_payslip_line] PRIMARY KEY,
    [payslip_id] BIGINT NOT NULL,
    [salary_component_id] BIGINT NOT NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_payslip_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_payslip_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Loans and salary advances.
CREATE TABLE [hr].[employee_loan] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_employee_loan] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [loan_type] NVARCHAR(30) NOT NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [sanctioned_on] DATE NOT NULL,
    [emi_amount] DECIMAL(18,2) NOT NULL,
    [installments] SMALLINT NOT NULL,
    [balance] DECIMAL(18,2) NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_employee_loan_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_employee_loan_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_employee_loan_loan_type] CHECK ([loan_type] IN (N'Loan', N'Salary advance')),
    CONSTRAINT [CK_hr_employee_loan_status] CHECK ([status] IN (N'Active', N'Closed'))
);
GO
-- Expense claims (travel km from trips, food, lodging).
CREATE TABLE [hr].[expense_claim] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_expense_claim] PRIMARY KEY,
    [claim_no] NVARCHAR(30) NOT NULL,
    [employee_id] BIGINT NOT NULL,
    [claim_date] DATE NOT NULL,
    [period_from] DATE NULL,
    [period_to] DATE NULL,
    [total_amount] DECIMAL(18,2) NOT NULL,
    [approved_amount] DECIMAL(18,2) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [paid_via] NVARCHAR(30) NULL,
    [payroll_run_id] BIGINT NULL,
    [journal_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_expense_claim_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_expense_claim_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_expense_claim_status] CHECK ([status] IN (N'Draft', N'Submitted', N'Approved', N'Rejected', N'Paid')),
    CONSTRAINT [CK_hr_expense_claim_paid_via] CHECK ([paid_via] IN (N'Payroll', N'Direct'))
);
GO
-- Claim lines; travel lines link to trips.
CREATE TABLE [hr].[expense_claim_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_expense_claim_line] PRIMARY KEY,
    [expense_claim_id] BIGINT NOT NULL,
    [expense_type_lookup_id] BIGINT NOT NULL,
    [expense_date] DATE NOT NULL,
    [trip_id] BIGINT NULL,
    [km] DECIMAL(8,2) NULL,
    [rate_per_km] DECIMAL(6,2) NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [receipt_attachment_id] BIGINT NULL,
    [remarks] NVARCHAR(300) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_expense_claim_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_expense_claim_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Company assets given to employees (phone, laptop, tool kit, SIM).
CREATE TABLE [hr].[asset] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_asset] PRIMARY KEY,
    [asset_tag] NVARCHAR(30) NOT NULL,
    [asset_type_lookup_id] BIGINT NOT NULL,
    [description] NVARCHAR(200) NULL,
    [serial_no] NVARCHAR(60) NULL,
    [purchase_date] DATE NULL,
    [purchase_value] DECIMAL(18,2) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_asset_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_asset_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_asset_status] CHECK ([status] IN (N'In store', N'Assigned', N'Repair', N'Retired'))
);
GO
-- Who holds which asset.
CREATE TABLE [hr].[asset_assignment] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_asset_assignment] PRIMARY KEY,
    [asset_id] BIGINT NOT NULL,
    [employee_id] BIGINT NOT NULL,
    [assigned_on] DATE NOT NULL,
    [returned_on] DATE NULL,
    [condition_on_return] NVARCHAR(200) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_asset_assignment_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_asset_assignment_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Periodic performance reviews.
CREATE TABLE [hr].[performance_review] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_performance_review] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [review_period] NVARCHAR(20) NOT NULL,
    [reviewer_employee_id] BIGINT NULL,
    [rating] DECIMAL(3,1) NULL,
    [goals_json] NVARCHAR(MAX) NULL,
    [comments] NVARCHAR(2000) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_performance_review_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_performance_review_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_performance_review_status] CHECK ([status] IN (N'Draft', N'Self review', N'Manager review', N'Closed'))
);
GO
-- Open positions.
CREATE TABLE [hr].[job_opening] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_job_opening] PRIMARY KEY,
    [title] NVARCHAR(120) NOT NULL,
    [designation_id] BIGINT NULL,
    [branch_id] BIGINT NULL,
    [openings] SMALLINT NOT NULL CONSTRAINT [DF_hr_job_opening_openings] DEFAULT (1),
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_job_opening_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_job_opening_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_job_opening_status] CHECK ([status] IN (N'Open', N'On hold', N'Closed'))
);
GO
-- Applicants for an opening.
CREATE TABLE [hr].[candidate] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_candidate] PRIMARY KEY,
    [job_opening_id] BIGINT NOT NULL,
    [name] NVARCHAR(120) NOT NULL,
    [phone] NVARCHAR(15) NOT NULL,
    [email] NVARCHAR(120) NULL,
    [resume_attachment_id] BIGINT NULL,
    [stage] NVARCHAR(30) NOT NULL,
    [joined_employee_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_candidate_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_candidate_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_candidate_stage] CHECK ([stage] IN (N'Applied', N'Screening', N'Interview', N'Offered', N'Joined', N'Rejected'))
);
GO
-- Exit settlement.
CREATE TABLE [hr].[full_final_settlement] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_full_final_settlement] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [last_working_day] DATE NOT NULL,
    [leave_encashment] DECIMAL(18,2) NULL,
    [gratuity] DECIMAL(18,2) NULL,
    [notice_recovery] DECIMAL(18,2) NULL,
    [loan_recovery] DECIMAL(18,2) NULL,
    [net_payable] DECIMAL(18,2) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [paid_on] DATE NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_full_final_settlement_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_full_final_settlement_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_full_final_settlement_status] CHECK ([status] IN (N'Draft', N'Approved', N'Paid'))
);
GO
-- Employee queries to HR / admin.
CREATE TABLE [hr].[helpdesk_ticket] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_helpdesk_ticket] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [category_lookup_id] BIGINT NULL,
    [subject] NVARCHAR(200) NOT NULL,
    [description] NVARCHAR(2000) NULL,
    [assigned_to_employee_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [resolved_at] DATETIME2(0) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_helpdesk_ticket_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_helpdesk_ticket_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_helpdesk_ticket_status] CHECK ([status] IN (N'Open', N'In progress', N'Resolved', N'Closed'))
);
GO

/* ---------- 2. Unique keys (21) ---------- */
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_warranty_claim_claim_no] ON [svc].[warranty_claim] ([claim_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pur_supplier_item_price_k1] ON [pur].[supplier_item_price] ([supplier_id], [item_id], [valid_from]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pur_purchase_request_pr_no] ON [pur].[purchase_request] ([pr_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pur_purchase_order_po_no] ON [pur].[purchase_order] ([po_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pur_grn_grn_no] ON [pur].[grn] ([grn_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pur_supplier_invoice_invoice_no] ON [pur].[supplier_invoice] ([invoice_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pur_supplier_invoice_k1] ON [pur].[supplier_invoice] ([supplier_id], [supplier_invoice_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pur_supplier_payment_payment_no] ON [pur].[supplier_payment] ([payment_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pur_debit_note_debit_note_no] ON [pur].[debit_note] ([debit_note_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_department_code] ON [hr].[department] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_designation_code] ON [hr].[designation] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_employee_profile_employee_id] ON [hr].[employee_profile] ([employee_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_shift_code] ON [hr].[shift] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_attendance_k1] ON [hr].[attendance] ([employee_id], [attendance_date]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_leave_type_code] ON [hr].[leave_type] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_leave_balance_k1] ON [hr].[leave_balance] ([employee_id], [leave_type_id], [leave_year]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_salary_component_code] ON [hr].[salary_component] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_payslip_k1] ON [hr].[payslip] ([payroll_run_id], [employee_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_expense_claim_claim_no] ON [hr].[expense_claim] ([claim_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_asset_asset_tag] ON [hr].[asset] ([asset_tag]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_full_final_settlement_employee_id] ON [hr].[full_final_settlement] ([employee_id]);
GO

/* ---------- 3. Foreign keys (137) ----------
   Includes links from earlier-phase columns to tables created in this phase. */
ALTER TABLE [core].[employee] ADD CONSTRAINT [FK_core_employee_department_id] FOREIGN KEY ([department_id]) REFERENCES [hr].[department] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[employee] ADD CONSTRAINT [FK_core_employee_designation_id] FOREIGN KEY ([designation_id]) REFERENCES [hr].[designation] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[warranty_claim] ADD CONSTRAINT [FK_svc_warranty_claim_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[warranty_claim] ADD CONSTRAINT [FK_svc_warranty_claim_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[warranty_claim] ADD CONSTRAINT [FK_svc_warranty_claim_machine_unit_id] FOREIGN KEY ([machine_unit_id]) REFERENCES [core].[machine_unit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[warranty_claim] ADD CONSTRAINT [FK_svc_warranty_claim_failure_code_lookup_id] FOREIGN KEY ([failure_code_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[warranty_claim_part] ADD CONSTRAINT [FK_svc_warranty_claim_part_warranty_claim_id] FOREIGN KEY ([warranty_claim_id]) REFERENCES [svc].[warranty_claim] ([id]) ON DELETE CASCADE;
ALTER TABLE [svc].[warranty_claim_part] ADD CONSTRAINT [FK_svc_warranty_claim_part_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[serial_batch] ADD CONSTRAINT [FK_inv_serial_batch_grn_line_id] FOREIGN KEY ([grn_line_id]) REFERENCES [pur].[grn_line] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[defective_return] ADD CONSTRAINT [FK_inv_defective_return_warranty_claim_id] FOREIGN KEY ([warranty_claim_id]) REFERENCES [svc].[warranty_claim] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_item_price] ADD CONSTRAINT [FK_pur_supplier_item_price_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_item_price] ADD CONSTRAINT [FK_pur_supplier_item_price_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_item_price] ADD CONSTRAINT [FK_pur_supplier_item_price_currency_id] FOREIGN KEY ([currency_id]) REFERENCES [core].[currency] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_request] ADD CONSTRAINT [FK_pur_purchase_request_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_request] ADD CONSTRAINT [FK_pur_purchase_request_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_request] ADD CONSTRAINT [FK_pur_purchase_request_requested_by_employee_id] FOREIGN KEY ([requested_by_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_request] ADD CONSTRAINT [FK_pur_purchase_request_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_request_line] ADD CONSTRAINT [FK_pur_purchase_request_line_purchase_request_id] FOREIGN KEY ([purchase_request_id]) REFERENCES [pur].[purchase_request] ([id]) ON DELETE CASCADE;
ALTER TABLE [pur].[purchase_request_line] ADD CONSTRAINT [FK_pur_purchase_request_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order] ADD CONSTRAINT [FK_pur_purchase_order_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order] ADD CONSTRAINT [FK_pur_purchase_order_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order] ADD CONSTRAINT [FK_pur_purchase_order_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order] ADD CONSTRAINT [FK_pur_purchase_order_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order] ADD CONSTRAINT [FK_pur_purchase_order_delivery_location_id] FOREIGN KEY ([delivery_location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order] ADD CONSTRAINT [FK_pur_purchase_order_payment_terms_id] FOREIGN KEY ([payment_terms_id]) REFERENCES [core].[payment_terms] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order] ADD CONSTRAINT [FK_pur_purchase_order_place_of_supply_state_id] FOREIGN KEY ([place_of_supply_state_id]) REFERENCES [core].[state] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order] ADD CONSTRAINT [FK_pur_purchase_order_currency_id] FOREIGN KEY ([currency_id]) REFERENCES [core].[currency] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order_line] ADD CONSTRAINT [FK_pur_purchase_order_line_purchase_order_id] FOREIGN KEY ([purchase_order_id]) REFERENCES [pur].[purchase_order] ([id]) ON DELETE CASCADE;
ALTER TABLE [pur].[purchase_order_line] ADD CONSTRAINT [FK_pur_purchase_order_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order_line] ADD CONSTRAINT [FK_pur_purchase_order_line_uom_id] FOREIGN KEY ([uom_id]) REFERENCES [core].[uom] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order_line] ADD CONSTRAINT [FK_pur_purchase_order_line_hsn_sac_id] FOREIGN KEY ([hsn_sac_id]) REFERENCES [core].[hsn_sac] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order_line] ADD CONSTRAINT [FK_pur_purchase_order_line_gst_rate_id] FOREIGN KEY ([gst_rate_id]) REFERENCES [acc].[gst_rate] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order_line] ADD CONSTRAINT [FK_pur_purchase_order_line_purchase_request_line_id] FOREIGN KEY ([purchase_request_line_id]) REFERENCES [pur].[purchase_request_line] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[grn] ADD CONSTRAINT [FK_pur_grn_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[grn] ADD CONSTRAINT [FK_pur_grn_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[grn] ADD CONSTRAINT [FK_pur_grn_purchase_order_id] FOREIGN KEY ([purchase_order_id]) REFERENCES [pur].[purchase_order] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[grn] ADD CONSTRAINT [FK_pur_grn_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[grn] ADD CONSTRAINT [FK_pur_grn_location_id] FOREIGN KEY ([location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[grn_line] ADD CONSTRAINT [FK_pur_grn_line_grn_id] FOREIGN KEY ([grn_id]) REFERENCES [pur].[grn] ([id]) ON DELETE CASCADE;
ALTER TABLE [pur].[grn_line] ADD CONSTRAINT [FK_pur_grn_line_purchase_order_line_id] FOREIGN KEY ([purchase_order_line_id]) REFERENCES [pur].[purchase_order_line] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[grn_line] ADD CONSTRAINT [FK_pur_grn_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[grn_line] ADD CONSTRAINT [FK_pur_grn_line_bin_id] FOREIGN KEY ([bin_id]) REFERENCES [inv].[bin] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice] ADD CONSTRAINT [FK_pur_supplier_invoice_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice] ADD CONSTRAINT [FK_pur_supplier_invoice_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice] ADD CONSTRAINT [FK_pur_supplier_invoice_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice] ADD CONSTRAINT [FK_pur_supplier_invoice_purchase_order_id] FOREIGN KEY ([purchase_order_id]) REFERENCES [pur].[purchase_order] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice] ADD CONSTRAINT [FK_pur_supplier_invoice_grn_id] FOREIGN KEY ([grn_id]) REFERENCES [pur].[grn] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice] ADD CONSTRAINT [FK_pur_supplier_invoice_place_of_supply_state_id] FOREIGN KEY ([place_of_supply_state_id]) REFERENCES [core].[state] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice] ADD CONSTRAINT [FK_pur_supplier_invoice_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice_line] ADD CONSTRAINT [FK_pur_supplier_invoice_line_supplier_invoice_id] FOREIGN KEY ([supplier_invoice_id]) REFERENCES [pur].[supplier_invoice] ([id]) ON DELETE CASCADE;
ALTER TABLE [pur].[supplier_invoice_line] ADD CONSTRAINT [FK_pur_supplier_invoice_line_grn_line_id] FOREIGN KEY ([grn_line_id]) REFERENCES [pur].[grn_line] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice_line] ADD CONSTRAINT [FK_pur_supplier_invoice_line_purchase_order_line_id] FOREIGN KEY ([purchase_order_line_id]) REFERENCES [pur].[purchase_order_line] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice_line] ADD CONSTRAINT [FK_pur_supplier_invoice_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice_line] ADD CONSTRAINT [FK_pur_supplier_invoice_line_gl_account_id] FOREIGN KEY ([gl_account_id]) REFERENCES [acc].[gl_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice_line] ADD CONSTRAINT [FK_pur_supplier_invoice_line_hsn_sac_id] FOREIGN KEY ([hsn_sac_id]) REFERENCES [core].[hsn_sac] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice_line] ADD CONSTRAINT [FK_pur_supplier_invoice_line_gst_rate_id] FOREIGN KEY ([gst_rate_id]) REFERENCES [acc].[gst_rate] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_payment] ADD CONSTRAINT [FK_pur_supplier_payment_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_payment] ADD CONSTRAINT [FK_pur_supplier_payment_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_payment] ADD CONSTRAINT [FK_pur_supplier_payment_bank_account_id] FOREIGN KEY ([bank_account_id]) REFERENCES [acc].[bank_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_payment] ADD CONSTRAINT [FK_pur_supplier_payment_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[debit_note] ADD CONSTRAINT [FK_pur_debit_note_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[debit_note] ADD CONSTRAINT [FK_pur_debit_note_supplier_invoice_id] FOREIGN KEY ([supplier_invoice_id]) REFERENCES [pur].[supplier_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[debit_note] ADD CONSTRAINT [FK_pur_debit_note_grn_id] FOREIGN KEY ([grn_id]) REFERENCES [pur].[grn] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[debit_note] ADD CONSTRAINT [FK_pur_debit_note_reason_lookup_id] FOREIGN KEY ([reason_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[debit_note] ADD CONSTRAINT [FK_pur_debit_note_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[debit_note_line] ADD CONSTRAINT [FK_pur_debit_note_line_debit_note_id] FOREIGN KEY ([debit_note_id]) REFERENCES [pur].[debit_note] ([id]) ON DELETE CASCADE;
ALTER TABLE [pur].[debit_note_line] ADD CONSTRAINT [FK_pur_debit_note_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[debit_note_line] ADD CONSTRAINT [FK_pur_debit_note_line_serial_batch_id] FOREIGN KEY ([serial_batch_id]) REFERENCES [inv].[serial_batch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[debit_note_line] ADD CONSTRAINT [FK_pur_debit_note_line_gst_rate_id] FOREIGN KEY ([gst_rate_id]) REFERENCES [acc].[gst_rate] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_allocation] ADD CONSTRAINT [FK_pur_supplier_allocation_supplier_invoice_id] FOREIGN KEY ([supplier_invoice_id]) REFERENCES [pur].[supplier_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_allocation] ADD CONSTRAINT [FK_pur_supplier_allocation_supplier_payment_id] FOREIGN KEY ([supplier_payment_id]) REFERENCES [pur].[supplier_payment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_allocation] ADD CONSTRAINT [FK_pur_supplier_allocation_debit_note_id] FOREIGN KEY ([debit_note_id]) REFERENCES [pur].[debit_note] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[department] ADD CONSTRAINT [FK_hr_department_parent_department_id] FOREIGN KEY ([parent_department_id]) REFERENCES [hr].[department] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[department] ADD CONSTRAINT [FK_hr_department_head_employee_id] FOREIGN KEY ([head_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[designation] ADD CONSTRAINT [FK_hr_designation_department_id] FOREIGN KEY ([department_id]) REFERENCES [hr].[department] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employee_profile] ADD CONSTRAINT [FK_hr_employee_profile_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employee_profile] ADD CONSTRAINT [FK_hr_employee_profile_pt_state_id] FOREIGN KEY ([pt_state_id]) REFERENCES [core].[state] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employment_history] ADD CONSTRAINT [FK_hr_employment_history_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employment_history] ADD CONSTRAINT [FK_hr_employment_history_from_branch_id] FOREIGN KEY ([from_branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employment_history] ADD CONSTRAINT [FK_hr_employment_history_to_branch_id] FOREIGN KEY ([to_branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employment_history] ADD CONSTRAINT [FK_hr_employment_history_from_designation_id] FOREIGN KEY ([from_designation_id]) REFERENCES [hr].[designation] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employment_history] ADD CONSTRAINT [FK_hr_employment_history_to_designation_id] FOREIGN KEY ([to_designation_id]) REFERENCES [hr].[designation] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employee_document] ADD CONSTRAINT [FK_hr_employee_document_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employee_document] ADD CONSTRAINT [FK_hr_employee_document_document_type_lookup_id] FOREIGN KEY ([document_type_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employee_document] ADD CONSTRAINT [FK_hr_employee_document_attachment_id] FOREIGN KEY ([attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[onboarding_task] ADD CONSTRAINT [FK_hr_onboarding_task_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[onboarding_task] ADD CONSTRAINT [FK_hr_onboarding_task_owner_employee_id] FOREIGN KEY ([owner_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employee_shift] ADD CONSTRAINT [FK_hr_employee_shift_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employee_shift] ADD CONSTRAINT [FK_hr_employee_shift_shift_id] FOREIGN KEY ([shift_id]) REFERENCES [hr].[shift] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[holiday] ADD CONSTRAINT [FK_hr_holiday_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[attendance] ADD CONSTRAINT [FK_hr_attendance_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[attendance] ADD CONSTRAINT [FK_hr_attendance_shift_id] FOREIGN KEY ([shift_id]) REFERENCES [hr].[shift] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[attendance] ADD CONSTRAINT [FK_hr_attendance_duty_log_id] FOREIGN KEY ([duty_log_id]) REFERENCES [svc].[engineer_duty_log] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[attendance_regularization] ADD CONSTRAINT [FK_hr_attendance_regularization_attendance_id] FOREIGN KEY ([attendance_id]) REFERENCES [hr].[attendance] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[attendance_regularization] ADD CONSTRAINT [FK_hr_attendance_regularization_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[attendance_regularization] ADD CONSTRAINT [FK_hr_attendance_regularization_approver_user_id] FOREIGN KEY ([approver_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[leave_balance] ADD CONSTRAINT [FK_hr_leave_balance_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[leave_balance] ADD CONSTRAINT [FK_hr_leave_balance_leave_type_id] FOREIGN KEY ([leave_type_id]) REFERENCES [hr].[leave_type] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[leave_request] ADD CONSTRAINT [FK_hr_leave_request_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[leave_request] ADD CONSTRAINT [FK_hr_leave_request_leave_type_id] FOREIGN KEY ([leave_type_id]) REFERENCES [hr].[leave_type] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[leave_request] ADD CONSTRAINT [FK_hr_leave_request_approver_user_id] FOREIGN KEY ([approver_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[salary_component] ADD CONSTRAINT [FK_hr_salary_component_gl_account_id] FOREIGN KEY ([gl_account_id]) REFERENCES [acc].[gl_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[salary_structure] ADD CONSTRAINT [FK_hr_salary_structure_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[salary_structure_line] ADD CONSTRAINT [FK_hr_salary_structure_line_salary_structure_id] FOREIGN KEY ([salary_structure_id]) REFERENCES [hr].[salary_structure] ([id]) ON DELETE CASCADE;
ALTER TABLE [hr].[salary_structure_line] ADD CONSTRAINT [FK_hr_salary_structure_line_salary_component_id] FOREIGN KEY ([salary_component_id]) REFERENCES [hr].[salary_component] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[statutory_config] ADD CONSTRAINT [FK_hr_statutory_config_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[statutory_config] ADD CONSTRAINT [FK_hr_statutory_config_state_id] FOREIGN KEY ([state_id]) REFERENCES [core].[state] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[payroll_run] ADD CONSTRAINT [FK_hr_payroll_run_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[payroll_run] ADD CONSTRAINT [FK_hr_payroll_run_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[payroll_run] ADD CONSTRAINT [FK_hr_payroll_run_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[payslip] ADD CONSTRAINT [FK_hr_payslip_payroll_run_id] FOREIGN KEY ([payroll_run_id]) REFERENCES [hr].[payroll_run] ([id]) ON DELETE CASCADE;
ALTER TABLE [hr].[payslip] ADD CONSTRAINT [FK_hr_payslip_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[payslip] ADD CONSTRAINT [FK_hr_payslip_pdf_attachment_id] FOREIGN KEY ([pdf_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[payslip_line] ADD CONSTRAINT [FK_hr_payslip_line_payslip_id] FOREIGN KEY ([payslip_id]) REFERENCES [hr].[payslip] ([id]) ON DELETE CASCADE;
ALTER TABLE [hr].[payslip_line] ADD CONSTRAINT [FK_hr_payslip_line_salary_component_id] FOREIGN KEY ([salary_component_id]) REFERENCES [hr].[salary_component] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employee_loan] ADD CONSTRAINT [FK_hr_employee_loan_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[expense_claim] ADD CONSTRAINT [FK_hr_expense_claim_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[expense_claim] ADD CONSTRAINT [FK_hr_expense_claim_payroll_run_id] FOREIGN KEY ([payroll_run_id]) REFERENCES [hr].[payroll_run] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[expense_claim] ADD CONSTRAINT [FK_hr_expense_claim_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[expense_claim_line] ADD CONSTRAINT [FK_hr_expense_claim_line_expense_claim_id] FOREIGN KEY ([expense_claim_id]) REFERENCES [hr].[expense_claim] ([id]) ON DELETE CASCADE;
ALTER TABLE [hr].[expense_claim_line] ADD CONSTRAINT [FK_hr_expense_claim_line_expense_type_lookup_id] FOREIGN KEY ([expense_type_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[expense_claim_line] ADD CONSTRAINT [FK_hr_expense_claim_line_trip_id] FOREIGN KEY ([trip_id]) REFERENCES [svc].[trip] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[expense_claim_line] ADD CONSTRAINT [FK_hr_expense_claim_line_receipt_attachment_id] FOREIGN KEY ([receipt_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[asset] ADD CONSTRAINT [FK_hr_asset_asset_type_lookup_id] FOREIGN KEY ([asset_type_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[asset_assignment] ADD CONSTRAINT [FK_hr_asset_assignment_asset_id] FOREIGN KEY ([asset_id]) REFERENCES [hr].[asset] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[asset_assignment] ADD CONSTRAINT [FK_hr_asset_assignment_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[performance_review] ADD CONSTRAINT [FK_hr_performance_review_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[performance_review] ADD CONSTRAINT [FK_hr_performance_review_reviewer_employee_id] FOREIGN KEY ([reviewer_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[job_opening] ADD CONSTRAINT [FK_hr_job_opening_designation_id] FOREIGN KEY ([designation_id]) REFERENCES [hr].[designation] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[job_opening] ADD CONSTRAINT [FK_hr_job_opening_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[candidate] ADD CONSTRAINT [FK_hr_candidate_job_opening_id] FOREIGN KEY ([job_opening_id]) REFERENCES [hr].[job_opening] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[candidate] ADD CONSTRAINT [FK_hr_candidate_resume_attachment_id] FOREIGN KEY ([resume_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[candidate] ADD CONSTRAINT [FK_hr_candidate_joined_employee_id] FOREIGN KEY ([joined_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[full_final_settlement] ADD CONSTRAINT [FK_hr_full_final_settlement_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[helpdesk_ticket] ADD CONSTRAINT [FK_hr_helpdesk_ticket_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[helpdesk_ticket] ADD CONSTRAINT [FK_hr_helpdesk_ticket_category_lookup_id] FOREIGN KEY ([category_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[helpdesk_ticket] ADD CONSTRAINT [FK_hr_helpdesk_ticket_assigned_to_employee_id] FOREIGN KEY ([assigned_to_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
GO

/* ---------- 4. Foreign-key indexes (135) ---------- */
CREATE NONCLUSTERED INDEX [IX_core_employee_department_id] ON [core].[employee] ([department_id]);
CREATE NONCLUSTERED INDEX [IX_core_employee_designation_id] ON [core].[employee] ([designation_id]);
CREATE NONCLUSTERED INDEX [IX_svc_warranty_claim_principal_id] ON [svc].[warranty_claim] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_svc_warranty_claim_service_call_id] ON [svc].[warranty_claim] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_svc_warranty_claim_machine_unit_id] ON [svc].[warranty_claim] ([machine_unit_id]);
CREATE NONCLUSTERED INDEX [IX_svc_warranty_claim_failure_code_lookup_id] ON [svc].[warranty_claim] ([failure_code_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_svc_warranty_claim_part_warranty_claim_id] ON [svc].[warranty_claim_part] ([warranty_claim_id]);
CREATE NONCLUSTERED INDEX [IX_svc_warranty_claim_part_item_id] ON [svc].[warranty_claim_part] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_serial_batch_grn_line_id] ON [inv].[serial_batch] ([grn_line_id]);
CREATE NONCLUSTERED INDEX [IX_inv_defective_return_warranty_claim_id] ON [inv].[defective_return] ([warranty_claim_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_item_price_supplier_id] ON [pur].[supplier_item_price] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_item_price_item_id] ON [pur].[supplier_item_price] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_item_price_currency_id] ON [pur].[supplier_item_price] ([currency_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_request_branch_id] ON [pur].[purchase_request] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_request_principal_id] ON [pur].[purchase_request] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_request_requested_by_employee_id] ON [pur].[purchase_request] ([requested_by_employee_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_request_service_call_id] ON [pur].[purchase_request] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_request_line_purchase_request_id] ON [pur].[purchase_request_line] ([purchase_request_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_request_line_item_id] ON [pur].[purchase_request_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_company_id] ON [pur].[purchase_order] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_branch_id] ON [pur].[purchase_order] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_supplier_id] ON [pur].[purchase_order] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_principal_id] ON [pur].[purchase_order] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_delivery_location_id] ON [pur].[purchase_order] ([delivery_location_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_payment_terms_id] ON [pur].[purchase_order] ([payment_terms_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_place_of_supply_state_id] ON [pur].[purchase_order] ([place_of_supply_state_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_currency_id] ON [pur].[purchase_order] ([currency_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_line_purchase_order_id] ON [pur].[purchase_order_line] ([purchase_order_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_line_item_id] ON [pur].[purchase_order_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_line_uom_id] ON [pur].[purchase_order_line] ([uom_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_line_hsn_sac_id] ON [pur].[purchase_order_line] ([hsn_sac_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_line_gst_rate_id] ON [pur].[purchase_order_line] ([gst_rate_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_line_purchase_request_line_id] ON [pur].[purchase_order_line] ([purchase_request_line_id]);
CREATE NONCLUSTERED INDEX [IX_pur_grn_branch_id] ON [pur].[grn] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_pur_grn_supplier_id] ON [pur].[grn] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_pur_grn_purchase_order_id] ON [pur].[grn] ([purchase_order_id]);
CREATE NONCLUSTERED INDEX [IX_pur_grn_principal_id] ON [pur].[grn] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_pur_grn_location_id] ON [pur].[grn] ([location_id]);
CREATE NONCLUSTERED INDEX [IX_pur_grn_line_grn_id] ON [pur].[grn_line] ([grn_id]);
CREATE NONCLUSTERED INDEX [IX_pur_grn_line_purchase_order_line_id] ON [pur].[grn_line] ([purchase_order_line_id]);
CREATE NONCLUSTERED INDEX [IX_pur_grn_line_item_id] ON [pur].[grn_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_pur_grn_line_bin_id] ON [pur].[grn_line] ([bin_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_supplier_id] ON [pur].[supplier_invoice] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_principal_id] ON [pur].[supplier_invoice] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_branch_id] ON [pur].[supplier_invoice] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_purchase_order_id] ON [pur].[supplier_invoice] ([purchase_order_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_grn_id] ON [pur].[supplier_invoice] ([grn_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_place_of_supply_state_id] ON [pur].[supplier_invoice] ([place_of_supply_state_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_journal_id] ON [pur].[supplier_invoice] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_line_supplier_invoice_id] ON [pur].[supplier_invoice_line] ([supplier_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_line_grn_line_id] ON [pur].[supplier_invoice_line] ([grn_line_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_line_purchase_order_line_id] ON [pur].[supplier_invoice_line] ([purchase_order_line_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_line_item_id] ON [pur].[supplier_invoice_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_line_gl_account_id] ON [pur].[supplier_invoice_line] ([gl_account_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_line_hsn_sac_id] ON [pur].[supplier_invoice_line] ([hsn_sac_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_line_gst_rate_id] ON [pur].[supplier_invoice_line] ([gst_rate_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_payment_supplier_id] ON [pur].[supplier_payment] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_payment_branch_id] ON [pur].[supplier_payment] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_payment_bank_account_id] ON [pur].[supplier_payment] ([bank_account_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_payment_journal_id] ON [pur].[supplier_payment] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_pur_debit_note_supplier_id] ON [pur].[debit_note] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_pur_debit_note_supplier_invoice_id] ON [pur].[debit_note] ([supplier_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_pur_debit_note_grn_id] ON [pur].[debit_note] ([grn_id]);
CREATE NONCLUSTERED INDEX [IX_pur_debit_note_reason_lookup_id] ON [pur].[debit_note] ([reason_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_pur_debit_note_journal_id] ON [pur].[debit_note] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_pur_debit_note_line_debit_note_id] ON [pur].[debit_note_line] ([debit_note_id]);
CREATE NONCLUSTERED INDEX [IX_pur_debit_note_line_item_id] ON [pur].[debit_note_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_pur_debit_note_line_serial_batch_id] ON [pur].[debit_note_line] ([serial_batch_id]);
CREATE NONCLUSTERED INDEX [IX_pur_debit_note_line_gst_rate_id] ON [pur].[debit_note_line] ([gst_rate_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_allocation_supplier_invoice_id] ON [pur].[supplier_allocation] ([supplier_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_allocation_supplier_payment_id] ON [pur].[supplier_allocation] ([supplier_payment_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_allocation_debit_note_id] ON [pur].[supplier_allocation] ([debit_note_id]);
CREATE NONCLUSTERED INDEX [IX_hr_department_parent_department_id] ON [hr].[department] ([parent_department_id]);
CREATE NONCLUSTERED INDEX [IX_hr_department_head_employee_id] ON [hr].[department] ([head_employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_designation_department_id] ON [hr].[designation] ([department_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employee_profile_pt_state_id] ON [hr].[employee_profile] ([pt_state_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employment_history_employee_id] ON [hr].[employment_history] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employment_history_from_branch_id] ON [hr].[employment_history] ([from_branch_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employment_history_to_branch_id] ON [hr].[employment_history] ([to_branch_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employment_history_from_designation_id] ON [hr].[employment_history] ([from_designation_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employment_history_to_designation_id] ON [hr].[employment_history] ([to_designation_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employee_document_employee_id] ON [hr].[employee_document] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employee_document_document_type_lookup_id] ON [hr].[employee_document] ([document_type_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employee_document_attachment_id] ON [hr].[employee_document] ([attachment_id]);
CREATE NONCLUSTERED INDEX [IX_hr_onboarding_task_employee_id] ON [hr].[onboarding_task] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_onboarding_task_owner_employee_id] ON [hr].[onboarding_task] ([owner_employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employee_shift_employee_id] ON [hr].[employee_shift] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employee_shift_shift_id] ON [hr].[employee_shift] ([shift_id]);
CREATE NONCLUSTERED INDEX [IX_hr_holiday_branch_id] ON [hr].[holiday] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_hr_attendance_employee_id] ON [hr].[attendance] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_attendance_shift_id] ON [hr].[attendance] ([shift_id]);
CREATE NONCLUSTERED INDEX [IX_hr_attendance_duty_log_id] ON [hr].[attendance] ([duty_log_id]);
CREATE NONCLUSTERED INDEX [IX_hr_attendance_regularization_attendance_id] ON [hr].[attendance_regularization] ([attendance_id]);
CREATE NONCLUSTERED INDEX [IX_hr_attendance_regularization_employee_id] ON [hr].[attendance_regularization] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_attendance_regularization_approver_user_id] ON [hr].[attendance_regularization] ([approver_user_id]);
CREATE NONCLUSTERED INDEX [IX_hr_leave_balance_employee_id] ON [hr].[leave_balance] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_leave_balance_leave_type_id] ON [hr].[leave_balance] ([leave_type_id]);
CREATE NONCLUSTERED INDEX [IX_hr_leave_request_employee_id] ON [hr].[leave_request] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_leave_request_leave_type_id] ON [hr].[leave_request] ([leave_type_id]);
CREATE NONCLUSTERED INDEX [IX_hr_leave_request_approver_user_id] ON [hr].[leave_request] ([approver_user_id]);
CREATE NONCLUSTERED INDEX [IX_hr_salary_component_gl_account_id] ON [hr].[salary_component] ([gl_account_id]);
CREATE NONCLUSTERED INDEX [IX_hr_salary_structure_employee_id] ON [hr].[salary_structure] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_salary_structure_line_salary_structure_id] ON [hr].[salary_structure_line] ([salary_structure_id]);
CREATE NONCLUSTERED INDEX [IX_hr_salary_structure_line_salary_component_id] ON [hr].[salary_structure_line] ([salary_component_id]);
CREATE NONCLUSTERED INDEX [IX_hr_statutory_config_company_id] ON [hr].[statutory_config] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_hr_statutory_config_state_id] ON [hr].[statutory_config] ([state_id]);
CREATE NONCLUSTERED INDEX [IX_hr_payroll_run_company_id] ON [hr].[payroll_run] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_hr_payroll_run_branch_id] ON [hr].[payroll_run] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_hr_payroll_run_journal_id] ON [hr].[payroll_run] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_hr_payslip_payroll_run_id] ON [hr].[payslip] ([payroll_run_id]);
CREATE NONCLUSTERED INDEX [IX_hr_payslip_employee_id] ON [hr].[payslip] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_payslip_pdf_attachment_id] ON [hr].[payslip] ([pdf_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_hr_payslip_line_payslip_id] ON [hr].[payslip_line] ([payslip_id]);
CREATE NONCLUSTERED INDEX [IX_hr_payslip_line_salary_component_id] ON [hr].[payslip_line] ([salary_component_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employee_loan_employee_id] ON [hr].[employee_loan] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_expense_claim_employee_id] ON [hr].[expense_claim] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_expense_claim_payroll_run_id] ON [hr].[expense_claim] ([payroll_run_id]);
CREATE NONCLUSTERED INDEX [IX_hr_expense_claim_journal_id] ON [hr].[expense_claim] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_hr_expense_claim_line_expense_claim_id] ON [hr].[expense_claim_line] ([expense_claim_id]);
CREATE NONCLUSTERED INDEX [IX_hr_expense_claim_line_expense_type_lookup_id] ON [hr].[expense_claim_line] ([expense_type_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_hr_expense_claim_line_trip_id] ON [hr].[expense_claim_line] ([trip_id]);
CREATE NONCLUSTERED INDEX [IX_hr_expense_claim_line_receipt_attachment_id] ON [hr].[expense_claim_line] ([receipt_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_hr_asset_asset_type_lookup_id] ON [hr].[asset] ([asset_type_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_hr_asset_assignment_asset_id] ON [hr].[asset_assignment] ([asset_id]);
CREATE NONCLUSTERED INDEX [IX_hr_asset_assignment_employee_id] ON [hr].[asset_assignment] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_performance_review_employee_id] ON [hr].[performance_review] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_performance_review_reviewer_employee_id] ON [hr].[performance_review] ([reviewer_employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_job_opening_designation_id] ON [hr].[job_opening] ([designation_id]);
CREATE NONCLUSTERED INDEX [IX_hr_job_opening_branch_id] ON [hr].[job_opening] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_hr_candidate_job_opening_id] ON [hr].[candidate] ([job_opening_id]);
CREATE NONCLUSTERED INDEX [IX_hr_candidate_resume_attachment_id] ON [hr].[candidate] ([resume_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_hr_candidate_joined_employee_id] ON [hr].[candidate] ([joined_employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_helpdesk_ticket_employee_id] ON [hr].[helpdesk_ticket] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_helpdesk_ticket_category_lookup_id] ON [hr].[helpdesk_ticket] ([category_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_hr_helpdesk_ticket_assigned_to_employee_id] ON [hr].[helpdesk_ticket] ([assigned_to_employee_id]);
GO
