/* =====================================================================
   TRISHUL Integrated System - SQL Server DDL (dictionary v2)
   Phase 5 - Pre-Sales core
   Generated from the TRISHUL Database Dictionary. Do not edit by hand:
   change the dictionary and regenerate.
   Target: SQL Server 2019+ / Amazon RDS for SQL Server
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
/* ---------- 1. Tables (9) ---------- */

/* ===== pre: Pre-Sales ===== */
-- Where leads come from.
CREATE TABLE [pre].[lead_source] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_lead_source] PRIMARY KEY,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(80) NOT NULL,
    [source_type] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_lead_source_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_lead_source_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pre_lead_source_source_type] CHECK ([source_type] IN (N'Referral', N'Walk in', N'Campaign', N'Service engineer', N'TATA HITACHI', N'Website', N'Old customer', N'Other'))
);
GO
-- Expos, demos, melas, digital campaigns.
CREATE TABLE [pre].[campaign] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_campaign] PRIMARY KEY,
    [name] NVARCHAR(120) NOT NULL,
    [campaign_type] NVARCHAR(30) NOT NULL,
    [branch_id] BIGINT NULL,
    [start_date] DATE NULL,
    [end_date] DATE NULL,
    [budget] DECIMAL(18,2) NULL,
    [notes] NVARCHAR(500) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_campaign_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_campaign_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pre_campaign_campaign_type] CHECK ([campaign_type] IN (N'Expo', N'Demo', N'Mela', N'Digital', N'Other'))
);
GO
-- Competitor brands.
CREATE TABLE [pre].[competitor] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_competitor] PRIMARY KEY,
    [name] NVARCHAR(80) NOT NULL,
    [notes] NVARCHAR(300) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_competitor_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_competitor_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Enquiry / referral before qualification.
CREATE TABLE [pre].[lead] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_lead] PRIMARY KEY,
    [lead_no] NVARCHAR(30) NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [client_uuid] UNIQUEIDENTIFIER NULL,
    [principal_id] BIGINT NULL,
    [lead_source_id] BIGINT NOT NULL,
    [campaign_id] BIGINT NULL,
    [referred_by_customer_id] BIGINT NULL,
    [referred_by_employee_id] BIGINT NULL,
    [prospect_name] NVARCHAR(120) NOT NULL,
    [company_name] NVARCHAR(200) NULL,
    [phone] NVARCHAR(15) NOT NULL,
    [alternate_phone] NVARCHAR(15) NULL,
    [email] NVARCHAR(120) NULL,
    [district_id] BIGINT NULL,
    [pincode_id] BIGINT NULL,
    [interested_model_id] BIGINT NULL,
    [quantity] SMALLINT NULL,
    [application_lookup_id] BIGINT NULL,
    [expected_purchase_month] DATE NULL,
    [assigned_to_employee_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [lost_reason_lookup_id] BIGINT NULL,
    [converted_customer_id] BIGINT NULL,
    [captured_latitude] DECIMAL(9,6) NULL,
    [captured_longitude] DECIMAL(9,6) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_lead_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_lead_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pre_lead_status] CHECK ([status] IN (N'New', N'Contacted', N'Qualified', N'Converted', N'Lost'))
);
GO
-- Qualified deal moving through the SOP stages.
CREATE TABLE [pre].[opportunity] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_opportunity] PRIMARY KEY,
    [opportunity_no] NVARCHAR(30) NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [lead_id] BIGINT NULL,
    [customer_id] BIGINT NOT NULL,
    [contact_id] BIGINT NULL,
    [machine_model_id] BIGINT NULL,
    [quantity] SMALLINT NOT NULL CONSTRAINT [DF_pre_opportunity_quantity] DEFAULT (1),
    [estimated_value] DECIMAL(18,2) NULL,
    [probability_pct] DECIMAL(5,2) NULL,
    [expected_close_date] DATE NULL,
    [salesperson_employee_id] BIGINT NOT NULL,
    [current_sop_stage_id] BIGINT NULL,
    [stage_entered_at] DATETIME2(0) NULL,
    [finance_mode] NVARCHAR(30) NULL,
    [is_exchange_offered] BIT NOT NULL CONSTRAINT [DF_pre_opportunity_is_exchange_offered] DEFAULT (0),
    [competitor_id] BIGINT NULL,
    [competitor_price] DECIMAL(18,2) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [won_sales_order_id] BIGINT NULL,
    [lost_reason_lookup_id] BIGINT NULL,
    [lost_to_competitor_id] BIGINT NULL,
    [closed_at] DATETIME2(0) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_opportunity_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_opportunity_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pre_opportunity_finance_mode] CHECK ([finance_mode] IN (N'Cash', N'Financed')),
    CONSTRAINT [CK_pre_opportunity_status] CHECK ([status] IN (N'Open', N'Won', N'Lost', N'On hold'))
);
GO
-- Stage changes for pipeline ageing.
CREATE TABLE [pre].[opportunity_stage_log] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_opportunity_stage_log] PRIMARY KEY,
    [opportunity_id] BIGINT NOT NULL,
    [from_stage_id] BIGINT NULL,
    [to_stage_id] BIGINT NOT NULL,
    [changed_at] DATETIME2(0) NOT NULL,
    [changed_by_user_id] BIGINT NULL,
    [days_in_previous_stage] SMALLINT NULL,
    [remarks] NVARCHAR(300) NULL
);
GO
-- Calls, visits, demos, meetings by salespeople.
CREATE TABLE [pre].[sales_activity] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_sales_activity] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [client_uuid] UNIQUEIDENTIFIER NULL,
    [lead_id] BIGINT NULL,
    [opportunity_id] BIGINT NULL,
    [customer_id] BIGINT NULL,
    [activity_type] NVARCHAR(30) NOT NULL,
    [planned_at] DATETIME2(0) NULL,
    [started_at] DATETIME2(0) NULL,
    [ended_at] DATETIME2(0) NULL,
    [outcome_lookup_id] BIGINT NULL,
    [notes] NVARCHAR(1000) NULL,
    [next_follow_up_at] DATETIME2(0) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_sales_activity_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_sales_activity_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pre_sales_activity_activity_type] CHECK ([activity_type] IN (N'Call', N'Visit', N'Demo', N'Meeting', N'WhatsApp', N'Email'))
);
GO
-- Live-location check-in/out to verify visits.
CREATE TABLE [pre].[location_check] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_location_check] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [sales_activity_id] BIGINT NULL,
    [check_type] NVARCHAR(30) NOT NULL,
    [captured_at] DATETIME2(0) NOT NULL,
    [latitude] DECIMAL(9,6) NOT NULL,
    [longitude] DECIMAL(9,6) NOT NULL,
    [accuracy_m] DECIMAL(6,1) NULL,
    [target_latitude] DECIMAL(9,6) NULL,
    [target_longitude] DECIMAL(9,6) NULL,
    [distance_from_target_m] INT NULL,
    [is_within_geofence] BIT NULL,
    [is_mock_location] BIT NOT NULL CONSTRAINT [DF_pre_location_check_is_mock_location] DEFAULT (0),
    [photo_attachment_id] BIGINT NULL,
    CONSTRAINT [CK_pre_location_check_check_type] CHECK ([check_type] IN (N'Check in', N'Check out'))
);
GO
-- WhatsApp messages with leads and customers.
CREATE TABLE [pre].[whatsapp_log] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_whatsapp_log] PRIMARY KEY,
    [direction] NVARCHAR(30) NOT NULL,
    [phone] NVARCHAR(15) NOT NULL,
    [customer_id] BIGINT NULL,
    [lead_id] BIGINT NULL,
    [opportunity_id] BIGINT NULL,
    [employee_id] BIGINT NULL,
    [template_name] NVARCHAR(100) NULL,
    [message_text] NVARCHAR(4000) NULL,
    [media_attachment_id] BIGINT NULL,
    [provider_message_id] NVARCHAR(100) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [sent_at] DATETIME2(0) NULL,
    [read_at] DATETIME2(0) NULL,
    CONSTRAINT [CK_pre_whatsapp_log_direction] CHECK ([direction] IN (N'Outbound', N'Inbound')),
    CONSTRAINT [CK_pre_whatsapp_log_status] CHECK ([status] IN (N'Sent', N'Delivered', N'Read', N'Failed', N'Received'))
);
GO

/* ---------- 2. Unique keys (6) ---------- */
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_lead_source_code] ON [pre].[lead_source] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_competitor_name] ON [pre].[competitor] ([name]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_lead_lead_no] ON [pre].[lead] ([lead_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_lead_client_uuid] ON [pre].[lead] ([client_uuid]) WHERE [client_uuid] IS NOT NULL;
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_opportunity_opportunity_no] ON [pre].[opportunity] ([opportunity_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_sales_activity_client_uuid] ON [pre].[sales_activity] ([client_uuid]) WHERE [client_uuid] IS NOT NULL;
GO

/* ---------- 3. Foreign keys (41) ----------
   Includes links from earlier-phase columns to tables created in this phase. */
ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_opportunity_id] FOREIGN KEY ([opportunity_id]) REFERENCES [pre].[opportunity] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[campaign] ADD CONSTRAINT [FK_pre_campaign_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_lead_source_id] FOREIGN KEY ([lead_source_id]) REFERENCES [pre].[lead_source] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_campaign_id] FOREIGN KEY ([campaign_id]) REFERENCES [pre].[campaign] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_referred_by_customer_id] FOREIGN KEY ([referred_by_customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_referred_by_employee_id] FOREIGN KEY ([referred_by_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_district_id] FOREIGN KEY ([district_id]) REFERENCES [core].[district] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_pincode_id] FOREIGN KEY ([pincode_id]) REFERENCES [core].[pincode] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_interested_model_id] FOREIGN KEY ([interested_model_id]) REFERENCES [core].[machine_model] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_application_lookup_id] FOREIGN KEY ([application_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_assigned_to_employee_id] FOREIGN KEY ([assigned_to_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_lost_reason_lookup_id] FOREIGN KEY ([lost_reason_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_converted_customer_id] FOREIGN KEY ([converted_customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_lead_id] FOREIGN KEY ([lead_id]) REFERENCES [pre].[lead] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_contact_id] FOREIGN KEY ([contact_id]) REFERENCES [core].[contact] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_machine_model_id] FOREIGN KEY ([machine_model_id]) REFERENCES [core].[machine_model] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_salesperson_employee_id] FOREIGN KEY ([salesperson_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_competitor_id] FOREIGN KEY ([competitor_id]) REFERENCES [pre].[competitor] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_won_sales_order_id] FOREIGN KEY ([won_sales_order_id]) REFERENCES [sal].[sales_order] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_lost_reason_lookup_id] FOREIGN KEY ([lost_reason_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_lost_to_competitor_id] FOREIGN KEY ([lost_to_competitor_id]) REFERENCES [pre].[competitor] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity_stage_log] ADD CONSTRAINT [FK_pre_opportunity_stage_log_opportunity_id] FOREIGN KEY ([opportunity_id]) REFERENCES [pre].[opportunity] ([id]) ON DELETE CASCADE;
ALTER TABLE [pre].[opportunity_stage_log] ADD CONSTRAINT [FK_pre_opportunity_stage_log_changed_by_user_id] FOREIGN KEY ([changed_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sales_activity] ADD CONSTRAINT [FK_pre_sales_activity_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sales_activity] ADD CONSTRAINT [FK_pre_sales_activity_lead_id] FOREIGN KEY ([lead_id]) REFERENCES [pre].[lead] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sales_activity] ADD CONSTRAINT [FK_pre_sales_activity_opportunity_id] FOREIGN KEY ([opportunity_id]) REFERENCES [pre].[opportunity] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sales_activity] ADD CONSTRAINT [FK_pre_sales_activity_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sales_activity] ADD CONSTRAINT [FK_pre_sales_activity_outcome_lookup_id] FOREIGN KEY ([outcome_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[location_check] ADD CONSTRAINT [FK_pre_location_check_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[location_check] ADD CONSTRAINT [FK_pre_location_check_sales_activity_id] FOREIGN KEY ([sales_activity_id]) REFERENCES [pre].[sales_activity] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[location_check] ADD CONSTRAINT [FK_pre_location_check_photo_attachment_id] FOREIGN KEY ([photo_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[whatsapp_log] ADD CONSTRAINT [FK_pre_whatsapp_log_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[whatsapp_log] ADD CONSTRAINT [FK_pre_whatsapp_log_lead_id] FOREIGN KEY ([lead_id]) REFERENCES [pre].[lead] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[whatsapp_log] ADD CONSTRAINT [FK_pre_whatsapp_log_opportunity_id] FOREIGN KEY ([opportunity_id]) REFERENCES [pre].[opportunity] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[whatsapp_log] ADD CONSTRAINT [FK_pre_whatsapp_log_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[whatsapp_log] ADD CONSTRAINT [FK_pre_whatsapp_log_media_attachment_id] FOREIGN KEY ([media_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
GO

/* ---------- 4. Foreign-key indexes (41) ---------- */
CREATE NONCLUSTERED INDEX [IX_sal_quotation_opportunity_id] ON [sal].[quotation] ([opportunity_id]);
CREATE NONCLUSTERED INDEX [IX_pre_campaign_branch_id] ON [pre].[campaign] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_branch_id] ON [pre].[lead] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_principal_id] ON [pre].[lead] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_lead_source_id] ON [pre].[lead] ([lead_source_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_campaign_id] ON [pre].[lead] ([campaign_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_referred_by_customer_id] ON [pre].[lead] ([referred_by_customer_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_referred_by_employee_id] ON [pre].[lead] ([referred_by_employee_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_district_id] ON [pre].[lead] ([district_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_pincode_id] ON [pre].[lead] ([pincode_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_interested_model_id] ON [pre].[lead] ([interested_model_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_application_lookup_id] ON [pre].[lead] ([application_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_assigned_to_employee_id] ON [pre].[lead] ([assigned_to_employee_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_lost_reason_lookup_id] ON [pre].[lead] ([lost_reason_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_converted_customer_id] ON [pre].[lead] ([converted_customer_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_principal_id] ON [pre].[opportunity] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_branch_id] ON [pre].[opportunity] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_lead_id] ON [pre].[opportunity] ([lead_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_customer_id] ON [pre].[opportunity] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_contact_id] ON [pre].[opportunity] ([contact_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_machine_model_id] ON [pre].[opportunity] ([machine_model_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_salesperson_employee_id] ON [pre].[opportunity] ([salesperson_employee_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_competitor_id] ON [pre].[opportunity] ([competitor_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_won_sales_order_id] ON [pre].[opportunity] ([won_sales_order_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_lost_reason_lookup_id] ON [pre].[opportunity] ([lost_reason_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_lost_to_competitor_id] ON [pre].[opportunity] ([lost_to_competitor_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_stage_log_opportunity_id] ON [pre].[opportunity_stage_log] ([opportunity_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_stage_log_changed_by_user_id] ON [pre].[opportunity_stage_log] ([changed_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sales_activity_employee_id] ON [pre].[sales_activity] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sales_activity_lead_id] ON [pre].[sales_activity] ([lead_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sales_activity_opportunity_id] ON [pre].[sales_activity] ([opportunity_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sales_activity_customer_id] ON [pre].[sales_activity] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sales_activity_outcome_lookup_id] ON [pre].[sales_activity] ([outcome_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_pre_location_check_employee_id] ON [pre].[location_check] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_pre_location_check_sales_activity_id] ON [pre].[location_check] ([sales_activity_id]);
CREATE NONCLUSTERED INDEX [IX_pre_location_check_photo_attachment_id] ON [pre].[location_check] ([photo_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_pre_whatsapp_log_customer_id] ON [pre].[whatsapp_log] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_pre_whatsapp_log_lead_id] ON [pre].[whatsapp_log] ([lead_id]);
CREATE NONCLUSTERED INDEX [IX_pre_whatsapp_log_opportunity_id] ON [pre].[whatsapp_log] ([opportunity_id]);
CREATE NONCLUSTERED INDEX [IX_pre_whatsapp_log_employee_id] ON [pre].[whatsapp_log] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_pre_whatsapp_log_media_attachment_id] ON [pre].[whatsapp_log] ([media_attachment_id]);
GO
