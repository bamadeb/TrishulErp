/* =====================================================================
   TRISHUL Integrated System - SQL Server DDL (dictionary v2)
   Phase 6 - Pre-Sales completion
   Generated from the TRISHUL Database Dictionary. Do not edit by hand:
   change the dictionary and regenerate.
   Target: SQL Server 2019+ / Amazon RDS for SQL Server
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
/* ---------- 1. Tables (8) ---------- */

/* ===== pre: Pre-Sales ===== */
-- Pre-sale SOP stages up to order advance.
CREATE TABLE [pre].[sop_stage] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_sop_stage] PRIMARY KEY,
    [principal_id] BIGINT NULL,
    [sequence] SMALLINT NOT NULL,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(80) NOT NULL,
    [expected_days] SMALLINT NULL,
    [is_mandatory] BIT NOT NULL CONSTRAINT [DF_pre_sop_stage_is_mandatory] DEFAULT (1),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_sop_stage_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_sop_stage_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Tasks required in each SOP stage.
CREATE TABLE [pre].[sop_checklist_item] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_sop_checklist_item] PRIMARY KEY,
    [sop_stage_id] BIGINT NOT NULL,
    [sequence] SMALLINT NOT NULL,
    [item_text] NVARCHAR(300) NOT NULL,
    [requires_attachment] BIT NOT NULL CONSTRAINT [DF_pre_sop_checklist_item_requires_attachment] DEFAULT (0),
    [is_mandatory] BIT NOT NULL CONSTRAINT [DF_pre_sop_checklist_item_is_mandatory] DEFAULT (1),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_sop_checklist_item_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_sop_checklist_item_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Completion of SOP tasks per opportunity.
CREATE TABLE [pre].[sop_progress] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_sop_progress] PRIMARY KEY,
    [opportunity_id] BIGINT NOT NULL,
    [sop_checklist_item_id] BIGINT NOT NULL,
    [is_done] BIT NOT NULL CONSTRAINT [DF_pre_sop_progress_is_done] DEFAULT (0),
    [done_at] DATETIME2(0) NULL,
    [done_by_user_id] BIGINT NULL,
    [attachment_id] BIGINT NULL,
    [remarks] NVARCHAR(300) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_sop_progress_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_sop_progress_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Banks / NBFCs financing machines.
CREATE TABLE [pre].[financer] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_financer] PRIMARY KEY,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(120) NOT NULL,
    [financer_type] NVARCHAR(30) NOT NULL,
    [contact_person] NVARCHAR(100) NULL,
    [phone] NVARCHAR(15) NULL,
    [email] NVARCHAR(120) NULL,
    [branch_address] NVARCHAR(500) NULL,
    [is_empanelled] BIT NOT NULL CONSTRAINT [DF_pre_financer_is_empanelled] DEFAULT (1),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_financer_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_financer_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pre_financer_financer_type] CHECK ([financer_type] IN (N'Bank', N'NBFC', N'OEM captive'))
);
GO
-- Loan application for a deal.
CREATE TABLE [pre].[finance_application] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_finance_application] PRIMARY KEY,
    [application_no] NVARCHAR(30) NOT NULL,
    [opportunity_id] BIGINT NOT NULL,
    [customer_id] BIGINT NOT NULL,
    [financer_id] BIGINT NOT NULL,
    [loan_amount] DECIMAL(18,2) NOT NULL,
    [down_payment] DECIMAL(18,2) NULL,
    [tenure_months] SMALLINT NULL,
    [interest_rate] DECIMAL(5,2) NULL,
    [applied_on] DATE NULL,
    [status] NVARCHAR(30) NOT NULL,
    [sanctioned_amount] DECIMAL(18,2) NULL,
    [sanctioned_on] DATE NULL,
    [disbursed_amount] DECIMAL(18,2) NULL,
    [disbursed_on] DATE NULL,
    [financer_reference] NVARCHAR(60) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_finance_application_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_finance_application_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pre_finance_application_status] CHECK ([status] IN (N'Docs pending', N'Submitted', N'Sanctioned', N'Rejected', N'Disbursed'))
);
GO
-- Booking advance received at the end of the SOP.
CREATE TABLE [pre].[order_advance] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_order_advance] PRIMARY KEY,
    [opportunity_id] BIGINT NOT NULL,
    [customer_id] BIGINT NOT NULL,
    [receipt_id] BIGINT NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [received_on] DATE NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_order_advance_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_order_advance_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pre_order_advance_status] CHECK ([status] IN (N'Received', N'Adjusted', N'Refunded'))
);
GO
-- Daily pipeline totals for trend and ageing reports.
CREATE TABLE [pre].[pipeline_snapshot] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_pipeline_snapshot] PRIMARY KEY,
    [snapshot_date] DATE NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [salesperson_employee_id] BIGINT NULL,
    [sop_stage_id] BIGINT NOT NULL,
    [opportunity_count] INT NOT NULL,
    [pipeline_value] DECIMAL(18,2) NOT NULL,
    [weighted_value] DECIMAL(18,2) NULL,
    [avg_age_days] DECIMAL(6,1) NULL
);
GO
-- Monthly targets per salesperson and model.
CREATE TABLE [pre].[sales_target] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_sales_target] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [period_month] DATE NOT NULL,
    [machine_model_id] BIGINT NULL,
    [target_units] SMALLINT NULL,
    [target_value] DECIMAL(18,2) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_sales_target_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_sales_target_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO

/* ---------- 2. Unique keys (6) ---------- */
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_sop_stage_k1] ON [pre].[sop_stage] ([principal_id], [sequence]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_sop_stage_k2] ON [pre].[sop_stage] ([principal_id], [code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_sop_progress_k1] ON [pre].[sop_progress] ([opportunity_id], [sop_checklist_item_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_financer_code] ON [pre].[financer] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_finance_application_application_no] ON [pre].[finance_application] ([application_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_sales_target_k1] ON [pre].[sales_target] ([employee_id], [principal_id], [period_month], [machine_model_id]);
GO

/* ---------- 3. Foreign keys (25) ----------
   Includes links from earlier-phase columns to tables created in this phase. */
ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_finance_application_id] FOREIGN KEY ([finance_application_id]) REFERENCES [pre].[finance_application] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[receipt] ADD CONSTRAINT [FK_sal_receipt_financer_id] FOREIGN KEY ([financer_id]) REFERENCES [pre].[financer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_current_sop_stage_id] FOREIGN KEY ([current_sop_stage_id]) REFERENCES [pre].[sop_stage] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity_stage_log] ADD CONSTRAINT [FK_pre_opportunity_stage_log_from_stage_id] FOREIGN KEY ([from_stage_id]) REFERENCES [pre].[sop_stage] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity_stage_log] ADD CONSTRAINT [FK_pre_opportunity_stage_log_to_stage_id] FOREIGN KEY ([to_stage_id]) REFERENCES [pre].[sop_stage] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sop_stage] ADD CONSTRAINT [FK_pre_sop_stage_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sop_checklist_item] ADD CONSTRAINT [FK_pre_sop_checklist_item_sop_stage_id] FOREIGN KEY ([sop_stage_id]) REFERENCES [pre].[sop_stage] ([id]) ON DELETE CASCADE;
ALTER TABLE [pre].[sop_progress] ADD CONSTRAINT [FK_pre_sop_progress_opportunity_id] FOREIGN KEY ([opportunity_id]) REFERENCES [pre].[opportunity] ([id]) ON DELETE CASCADE;
ALTER TABLE [pre].[sop_progress] ADD CONSTRAINT [FK_pre_sop_progress_sop_checklist_item_id] FOREIGN KEY ([sop_checklist_item_id]) REFERENCES [pre].[sop_checklist_item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sop_progress] ADD CONSTRAINT [FK_pre_sop_progress_done_by_user_id] FOREIGN KEY ([done_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sop_progress] ADD CONSTRAINT [FK_pre_sop_progress_attachment_id] FOREIGN KEY ([attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[finance_application] ADD CONSTRAINT [FK_pre_finance_application_opportunity_id] FOREIGN KEY ([opportunity_id]) REFERENCES [pre].[opportunity] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[finance_application] ADD CONSTRAINT [FK_pre_finance_application_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[finance_application] ADD CONSTRAINT [FK_pre_finance_application_financer_id] FOREIGN KEY ([financer_id]) REFERENCES [pre].[financer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[order_advance] ADD CONSTRAINT [FK_pre_order_advance_opportunity_id] FOREIGN KEY ([opportunity_id]) REFERENCES [pre].[opportunity] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[order_advance] ADD CONSTRAINT [FK_pre_order_advance_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[order_advance] ADD CONSTRAINT [FK_pre_order_advance_receipt_id] FOREIGN KEY ([receipt_id]) REFERENCES [sal].[receipt] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[pipeline_snapshot] ADD CONSTRAINT [FK_pre_pipeline_snapshot_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[pipeline_snapshot] ADD CONSTRAINT [FK_pre_pipeline_snapshot_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[pipeline_snapshot] ADD CONSTRAINT [FK_pre_pipeline_snapshot_salesperson_employee_id] FOREIGN KEY ([salesperson_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[pipeline_snapshot] ADD CONSTRAINT [FK_pre_pipeline_snapshot_sop_stage_id] FOREIGN KEY ([sop_stage_id]) REFERENCES [pre].[sop_stage] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sales_target] ADD CONSTRAINT [FK_pre_sales_target_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sales_target] ADD CONSTRAINT [FK_pre_sales_target_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sales_target] ADD CONSTRAINT [FK_pre_sales_target_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sales_target] ADD CONSTRAINT [FK_pre_sales_target_machine_model_id] FOREIGN KEY ([machine_model_id]) REFERENCES [core].[machine_model] ([id]) ON DELETE NO ACTION;
GO

/* ---------- 4. Foreign-key indexes (25) ---------- */
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_finance_application_id] ON [sal].[sales_order] ([finance_application_id]);
CREATE NONCLUSTERED INDEX [IX_sal_receipt_financer_id] ON [sal].[receipt] ([financer_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_current_sop_stage_id] ON [pre].[opportunity] ([current_sop_stage_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_stage_log_from_stage_id] ON [pre].[opportunity_stage_log] ([from_stage_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_stage_log_to_stage_id] ON [pre].[opportunity_stage_log] ([to_stage_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sop_stage_principal_id] ON [pre].[sop_stage] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sop_checklist_item_sop_stage_id] ON [pre].[sop_checklist_item] ([sop_stage_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sop_progress_opportunity_id] ON [pre].[sop_progress] ([opportunity_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sop_progress_sop_checklist_item_id] ON [pre].[sop_progress] ([sop_checklist_item_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sop_progress_done_by_user_id] ON [pre].[sop_progress] ([done_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sop_progress_attachment_id] ON [pre].[sop_progress] ([attachment_id]);
CREATE NONCLUSTERED INDEX [IX_pre_finance_application_opportunity_id] ON [pre].[finance_application] ([opportunity_id]);
CREATE NONCLUSTERED INDEX [IX_pre_finance_application_customer_id] ON [pre].[finance_application] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_pre_finance_application_financer_id] ON [pre].[finance_application] ([financer_id]);
CREATE NONCLUSTERED INDEX [IX_pre_order_advance_opportunity_id] ON [pre].[order_advance] ([opportunity_id]);
CREATE NONCLUSTERED INDEX [IX_pre_order_advance_customer_id] ON [pre].[order_advance] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_pre_order_advance_receipt_id] ON [pre].[order_advance] ([receipt_id]);
CREATE NONCLUSTERED INDEX [IX_pre_pipeline_snapshot_principal_id] ON [pre].[pipeline_snapshot] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_pre_pipeline_snapshot_branch_id] ON [pre].[pipeline_snapshot] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_pre_pipeline_snapshot_salesperson_employee_id] ON [pre].[pipeline_snapshot] ([salesperson_employee_id]);
CREATE NONCLUSTERED INDEX [IX_pre_pipeline_snapshot_sop_stage_id] ON [pre].[pipeline_snapshot] ([sop_stage_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sales_target_employee_id] ON [pre].[sales_target] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sales_target_principal_id] ON [pre].[sales_target] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sales_target_branch_id] ON [pre].[sales_target] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sales_target_machine_model_id] ON [pre].[sales_target] ([machine_model_id]);
GO
