/* =====================================================================
   TRISHUL Integrated System - gap remediation (dictionary v2 -> v3)
   Run AFTER 00-11 (or ALL_IN_ONE.sql). Safe to re-run: every step
   checks the catalog before changing anything.

   Part 1  New schema + 22 new tables
   Part 2  Changes to existing tables (columns, CHECKs, FKs)
   Part 3  Integrity constraints missing in v2
   Part 4  Extra indexes

   See docs/Trishul_DB_Gap_Analysis.md for the reason behind each change.
   Target: SQL Server 2019+ / Amazon RDS for SQL Server (incl. Express)
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
IF SCHEMA_ID(N'rpt') IS NULL EXEC(N'CREATE SCHEMA [rpt] AUTHORIZATION [dbo]');
GO

/* =====================================================================
   PART 1 - NEW TABLES
   ===================================================================== */

/* ---------- 1.1 Skills (skill-based technician assignment) ---------- */
-- Skill master: hydraulics, electrical, compressor overhaul, OEM certifications...
IF OBJECT_ID(N'hr.skill', N'U') IS NULL
CREATE TABLE [hr].[skill] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_skill] PRIMARY KEY,
    [code] NVARCHAR(30) NOT NULL,
    [name] NVARCHAR(100) NOT NULL,
    [skill_category] NVARCHAR(30) NOT NULL,
    [principal_id] BIGINT NULL,
    [description] NVARCHAR(300) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_skill_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_skill_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_skill_skill_category] CHECK ([skill_category] IN (N'Mechanical', N'Hydraulic', N'Electrical', N'Electronics', N'Engine', N'Compressor', N'Software', N'Safety', N'Other')),
    CONSTRAINT [FK_hr_skill_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id])
);
GO
-- Skills held by each employee, with proficiency.
IF OBJECT_ID(N'hr.employee_skill', N'U') IS NULL
CREATE TABLE [hr].[employee_skill] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_employee_skill] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [skill_id] BIGINT NOT NULL,
    [proficiency] TINYINT NOT NULL CONSTRAINT [DF_hr_employee_skill_proficiency] DEFAULT (1),
    [certified_on] DATE NULL,
    [valid_until] DATE NULL,
    [certificate_attachment_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_employee_skill_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_employee_skill_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_employee_skill_proficiency] CHECK ([proficiency] BETWEEN 1 AND 5),
    CONSTRAINT [FK_hr_employee_skill_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE CASCADE,
    CONSTRAINT [FK_hr_employee_skill_skill_id] FOREIGN KEY ([skill_id]) REFERENCES [hr].[skill] ([id]),
    CONSTRAINT [FK_hr_employee_skill_certificate_attachment_id] FOREIGN KEY ([certificate_attachment_id]) REFERENCES [core].[attachment] ([id])
);
GO
-- Rule: which skill a call needs, by brand / call type / complaint category (drives auto-suggest).
IF OBJECT_ID(N'svc.skill_rule', N'U') IS NULL
CREATE TABLE [svc].[skill_rule] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_skill_rule] PRIMARY KEY,
    [principal_id] BIGINT NULL,
    [machine_model_id] BIGINT NULL,
    [call_type_lookup_id] BIGINT NULL,
    [complaint_category_lookup_id] BIGINT NULL,
    [skill_id] BIGINT NOT NULL,
    [min_proficiency] TINYINT NOT NULL CONSTRAINT [DF_svc_skill_rule_min_proficiency] DEFAULT (1),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_skill_rule_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_skill_rule_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_skill_rule_min_proficiency] CHECK ([min_proficiency] BETWEEN 1 AND 5),
    CONSTRAINT [FK_svc_skill_rule_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]),
    CONSTRAINT [FK_svc_skill_rule_machine_model_id] FOREIGN KEY ([machine_model_id]) REFERENCES [core].[machine_model] ([id]),
    CONSTRAINT [FK_svc_skill_rule_call_type_lookup_id] FOREIGN KEY ([call_type_lookup_id]) REFERENCES [core].[lookup_value] ([id]),
    CONSTRAINT [FK_svc_skill_rule_complaint_category_lookup_id] FOREIGN KEY ([complaint_category_lookup_id]) REFERENCES [core].[lookup_value] ([id]),
    CONSTRAINT [FK_svc_skill_rule_skill_id] FOREIGN KEY ([skill_id]) REFERENCES [hr].[skill] ([id])
);
GO
-- Skills a specific call needs (copied from rules, editable by the Team Lead).
IF OBJECT_ID(N'svc.call_required_skill', N'U') IS NULL
CREATE TABLE [svc].[call_required_skill] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_call_required_skill] PRIMARY KEY,
    [service_call_id] BIGINT NOT NULL,
    [skill_id] BIGINT NOT NULL,
    [min_proficiency] TINYINT NOT NULL CONSTRAINT [DF_svc_call_required_skill_min_proficiency] DEFAULT (1),
    [is_mandatory] BIT NOT NULL CONSTRAINT [DF_svc_call_required_skill_is_mandatory] DEFAULT (1),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_call_required_skill_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_call_required_skill_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [FK_svc_call_required_skill_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE CASCADE,
    CONSTRAINT [FK_svc_call_required_skill_skill_id] FOREIGN KEY ([skill_id]) REFERENCES [hr].[skill] ([id])
);
GO

/* ---------- 1.2 Call reopening on the same Call ID ---------- */
-- One row per reopen. The call keeps its call_no / OEM Call ID; this keeps the history.
IF OBJECT_ID(N'svc.call_reopen', N'U') IS NULL
CREATE TABLE [svc].[call_reopen] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_call_reopen] PRIMARY KEY,
    [service_call_id] BIGINT NOT NULL,
    [reopen_no] SMALLINT NOT NULL,
    [reopened_at] DATETIME2(0) NOT NULL,
    [reopened_by_user_id] BIGINT NULL,
    [reopen_source] NVARCHAR(30) NOT NULL,
    [reason_lookup_id] BIGINT NULL,
    [remarks] NVARCHAR(500) NULL,
    [previous_status] NVARCHAR(30) NOT NULL,
    [previous_closed_at] DATETIME2(0) NULL,
    [previous_closure_type] NVARCHAR(30) NULL,
    [previous_engineer_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_call_reopen_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    CONSTRAINT [CK_svc_call_reopen_reopen_source] CHECK ([reopen_source] IN (N'Customer', N'OEM', N'Back office', N'Engineer', N'Team Lead')),
    CONSTRAINT [FK_svc_call_reopen_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE CASCADE,
    CONSTRAINT [FK_svc_call_reopen_reopened_by_user_id] FOREIGN KEY ([reopened_by_user_id]) REFERENCES [core].[app_user] ([id]),
    CONSTRAINT [FK_svc_call_reopen_reason_lookup_id] FOREIGN KEY ([reason_lookup_id]) REFERENCES [core].[lookup_value] ([id]),
    CONSTRAINT [FK_svc_call_reopen_previous_engineer_id] FOREIGN KEY ([previous_engineer_id]) REFERENCES [core].[employee] ([id])
);
GO

/* ---------- 1.3 ASC / AMC plans, entitlements, billing schedule ---------- */
-- Sellable contract packages (ASC Silver/Gold, AMC 4-visit...). service_contract points here.
IF OBJECT_ID(N'svc.contract_plan', N'U') IS NULL
CREATE TABLE [svc].[contract_plan] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_contract_plan] PRIMARY KEY,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(100) NOT NULL,
    [principal_id] BIGINT NULL,
    [contract_type] NVARCHAR(30) NOT NULL,
    [duration_months] SMALLINT NOT NULL,
    [visits_included] SMALLINT NULL,
    [visit_frequency_months] TINYINT NULL,
    [hours_limit] INT NULL,
    [price] DECIMAL(18,2) NULL,
    [covers_labour] BIT NOT NULL CONSTRAINT [DF_svc_contract_plan_covers_labour] DEFAULT (1),
    [covers_parts] BIT NOT NULL CONSTRAINT [DF_svc_contract_plan_covers_parts] DEFAULT (0),
    [covers_travel] BIT NOT NULL CONSTRAINT [DF_svc_contract_plan_covers_travel] DEFAULT (1),
    [parts_discount_pct] DECIMAL(5,2) NULL,
    [service_priority] NVARCHAR(30) NOT NULL CONSTRAINT [DF_svc_contract_plan_service_priority] DEFAULT (N'High'),
    [response_hours] DECIMAL(5,1) NULL,
    [resolution_hours] DECIMAL(5,1) NULL,
    [terms] NVARCHAR(2000) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_contract_plan_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_contract_plan_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_contract_plan_contract_type] CHECK ([contract_type] IN (N'ASC', N'AMC', N'Extended warranty', N'Free service')),
    CONSTRAINT [CK_svc_contract_plan_service_priority] CHECK ([service_priority] IN (N'Critical', N'High', N'Normal', N'Low')),
    CONSTRAINT [CK_svc_contract_plan_visit_frequency_months] CHECK ([visit_frequency_months] IS NULL OR [visit_frequency_months] BETWEEN 1 AND 24),
    CONSTRAINT [FK_svc_contract_plan_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id])
);
GO
-- What a plan entitles the customer to (visits, free consumables, parts discount...).
IF OBJECT_ID(N'svc.contract_plan_entitlement', N'U') IS NULL
CREATE TABLE [svc].[contract_plan_entitlement] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_contract_plan_entitlement] PRIMARY KEY,
    [contract_plan_id] BIGINT NOT NULL,
    [entitlement_type] NVARCHAR(30) NOT NULL,
    [item_id] BIGINT NULL,
    [quantity] DECIMAL(18,3) NULL,
    [description] NVARCHAR(200) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_contract_plan_entitlement_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_contract_plan_entitlement_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_contract_plan_entitlement_entitlement_type] CHECK ([entitlement_type] IN (N'Visit', N'Labour', N'Parts', N'Consumable', N'Travel', N'Other')),
    CONSTRAINT [FK_svc_contract_plan_entitlement_contract_plan_id] FOREIGN KEY ([contract_plan_id]) REFERENCES [svc].[contract_plan] ([id]) ON DELETE CASCADE,
    CONSTRAINT [FK_svc_contract_plan_entitlement_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id])
);
GO
-- Instalment billing for AMC / ASC contracts (one invoice per instalment).
IF OBJECT_ID(N'svc.contract_billing_schedule', N'U') IS NULL
CREATE TABLE [svc].[contract_billing_schedule] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_contract_billing_schedule] PRIMARY KEY,
    [service_contract_id] BIGINT NOT NULL,
    [instalment_no] SMALLINT NOT NULL,
    [due_date] DATE NOT NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [sales_invoice_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL CONSTRAINT [DF_svc_contract_billing_schedule_status] DEFAULT (N'Pending'),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_contract_billing_schedule_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_contract_billing_schedule_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_contract_billing_schedule_status] CHECK ([status] IN (N'Pending', N'Invoiced', N'Paid', N'Cancelled')),
    CONSTRAINT [CK_svc_contract_billing_schedule_amount] CHECK ([amount] >= 0),
    CONSTRAINT [FK_svc_contract_billing_schedule_service_contract_id] FOREIGN KEY ([service_contract_id]) REFERENCES [svc].[service_contract] ([id]) ON DELETE CASCADE,
    CONSTRAINT [FK_svc_contract_billing_schedule_sales_invoice_id] FOREIGN KEY ([sales_invoice_id]) REFERENCES [sal].[sales_invoice] ([id])
);
GO

/* ---------- 1.4 Customer-site machine: telemetry and alerts ---------- */
-- Raw sensor / telematics values (pressure, temperature, loaded hours...). Insert only, high volume.
IF OBJECT_ID(N'core.machine_telemetry', N'U') IS NULL
CREATE TABLE [core].[machine_telemetry] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_machine_telemetry] PRIMARY KEY,
    [machine_unit_id] BIGINT NOT NULL,
    [recorded_at] DATETIME2(0) NOT NULL,
    [metric_code] NVARCHAR(40) NOT NULL,
    [metric_value] DECIMAL(18,4) NULL,
    [unit] NVARCHAR(20) NULL,
    [external_system_id] BIGINT NULL,
    [received_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_machine_telemetry_received_at] DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT [FK_core_machine_telemetry_machine_unit_id] FOREIGN KEY ([machine_unit_id]) REFERENCES [core].[machine_unit] ([id]),
    CONSTRAINT [FK_core_machine_telemetry_external_system_id] FOREIGN KEY ([external_system_id]) REFERENCES [int].[external_system] ([id])
);
GO
-- Sensor alerts, upcoming-service reminders and delay alerts for a machine.
IF OBJECT_ID(N'svc.machine_alert', N'U') IS NULL
CREATE TABLE [svc].[machine_alert] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_machine_alert] PRIMARY KEY,
    [machine_unit_id] BIGINT NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [alert_source] NVARCHAR(30) NOT NULL,
    [alert_code] NVARCHAR(40) NOT NULL,
    [severity] NVARCHAR(30) NOT NULL,
    [message] NVARCHAR(500) NOT NULL,
    [raised_at] DATETIME2(0) NOT NULL,
    [status] NVARCHAR(30) NOT NULL CONSTRAINT [DF_svc_machine_alert_status] DEFAULT (N'Open'),
    [acknowledged_by_user_id] BIGINT NULL,
    [acknowledged_at] DATETIME2(0) NULL,
    [service_call_id] BIGINT NULL,
    [planned_service_id] BIGINT NULL,
    [closed_at] DATETIME2(0) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_machine_alert_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_machine_alert_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_machine_alert_alert_source] CHECK ([alert_source] IN (N'Sensor', N'Telematics', N'Service schedule', N'SLA delay', N'Manual')),
    CONSTRAINT [CK_svc_machine_alert_severity] CHECK ([severity] IN (N'Info', N'Warning', N'Critical')),
    CONSTRAINT [CK_svc_machine_alert_status] CHECK ([status] IN (N'Open', N'Acknowledged', N'Call raised', N'Closed', N'Ignored')),
    CONSTRAINT [FK_svc_machine_alert_machine_unit_id] FOREIGN KEY ([machine_unit_id]) REFERENCES [core].[machine_unit] ([id]),
    CONSTRAINT [FK_svc_machine_alert_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]),
    CONSTRAINT [FK_svc_machine_alert_acknowledged_by_user_id] FOREIGN KEY ([acknowledged_by_user_id]) REFERENCES [core].[app_user] ([id]),
    CONSTRAINT [FK_svc_machine_alert_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]),
    CONSTRAINT [FK_svc_machine_alert_planned_service_id] FOREIGN KEY ([planned_service_id]) REFERENCES [svc].[planned_service] ([id])
);
GO

/* ---------- 1.5 Engineer location tracking while on duty (outside trips) ---------- */
-- trip_gps_point needs a trip; this holds points between trips while the engineer is on duty.
IF OBJECT_ID(N'svc.duty_gps_point', N'U') IS NULL
CREATE TABLE [svc].[duty_gps_point] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_duty_gps_point] PRIMARY KEY,
    [duty_log_id] BIGINT NOT NULL,
    [recorded_at] DATETIME2(0) NOT NULL,
    [latitude] DECIMAL(9,6) NOT NULL,
    [longitude] DECIMAL(9,6) NOT NULL,
    [accuracy_m] DECIMAL(6,1) NULL,
    [speed_kmph] DECIMAL(5,1) NULL,
    [battery_pct] TINYINT NULL,
    [is_mock_location] BIT NOT NULL CONSTRAINT [DF_svc_duty_gps_point_is_mock_location] DEFAULT (0),
    CONSTRAINT [FK_svc_duty_gps_point_duty_log_id] FOREIGN KEY ([duty_log_id]) REFERENCES [svc].[engineer_duty_log] ([id]) ON DELETE CASCADE
);
GO

/* ---------- 1.6 Customer portal ---------- */
-- Customer logins for the portal (history, raise call, track call). Cognito handles passwords.
IF OBJECT_ID(N'core.customer_portal_user', N'U') IS NULL
CREATE TABLE [core].[customer_portal_user] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_customer_portal_user] PRIMARY KEY,
    [customer_id] BIGINT NOT NULL,
    [contact_id] BIGINT NULL,
    [cognito_sub] NVARCHAR(64) NOT NULL,
    [username] NVARCHAR(100) NOT NULL,
    [email] NVARCHAR(120) NULL,
    [mobile] NVARCHAR(15) NULL,
    [last_login_at] DATETIME2(0) NULL,
    [is_locked] BIT NOT NULL CONSTRAINT [DF_core_customer_portal_user_is_locked] DEFAULT (0),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_customer_portal_user_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_customer_portal_user_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [FK_core_customer_portal_user_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]),
    CONSTRAINT [FK_core_customer_portal_user_contact_id] FOREIGN KEY ([contact_id]) REFERENCES [core].[contact] ([id])
);
GO

/* ---------- 1.7 Inbound e-mail / WhatsApp and OEM (BYD) list imports ---------- */
-- Calls and part requests arriving by e-mail / WhatsApp (e.g. TATA Customer Care mails).
IF OBJECT_ID(N'int.inbound_message', N'U') IS NULL
CREATE TABLE [int].[inbound_message] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_int_inbound_message] PRIMARY KEY,
    [external_system_id] BIGINT NULL,
    [channel] NVARCHAR(30) NOT NULL,
    [provider_message_id] NVARCHAR(200) NULL,
    [from_address] NVARCHAR(150) NOT NULL,
    [to_address] NVARCHAR(150) NULL,
    [subject] NVARCHAR(300) NULL,
    [body] NVARCHAR(MAX) NULL,
    [received_at] DATETIME2(0) NOT NULL,
    [status] NVARCHAR(30) NOT NULL CONSTRAINT [DF_int_inbound_message_status] DEFAULT (N'New'),
    [service_call_id] BIGINT NULL,
    [service_part_request_id] BIGINT NULL,
    [processed_by_user_id] BIGINT NULL,
    [processed_at] DATETIME2(0) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_int_inbound_message_created_at] DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT [CK_int_inbound_message_channel] CHECK ([channel] IN (N'Email', N'WhatsApp', N'SMS', N'Portal')),
    CONSTRAINT [CK_int_inbound_message_status] CHECK ([status] IN (N'New', N'Linked', N'Call created', N'Ignored', N'Failed')),
    CONSTRAINT [FK_int_inbound_message_external_system_id] FOREIGN KEY ([external_system_id]) REFERENCES [int].[external_system] ([id]),
    CONSTRAINT [FK_int_inbound_message_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]),
    CONSTRAINT [FK_int_inbound_message_service_part_request_id] FOREIGN KEY ([service_part_request_id]) REFERENCES [svc].[service_part_request] ([id]),
    CONSTRAINT [FK_int_inbound_message_processed_by_user_id] FOREIGN KEY ([processed_by_user_id]) REFERENCES [core].[app_user] ([id])
);
GO
-- Staging rows of an OEM case / service list file (BYD export), matched to our calls (workflow steps 8, 16, 17).
IF OBJECT_ID(N'int.oem_ticket_import_line', N'U') IS NULL
CREATE TABLE [int].[oem_ticket_import_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_int_oem_ticket_import_line] PRIMARY KEY,
    [file_import_id] BIGINT NOT NULL,
    [row_number] INT NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [oem_call_id] NVARCHAR(40) NOT NULL,
    [oem_status] NVARCHAR(40) NULL,
    [oem_created_at] DATETIME2(0) NULL,
    [oem_closed_at] DATETIME2(0) NULL,
    [customer_name] NVARCHAR(200) NULL,
    [serial_number] NVARCHAR(40) NULL,
    [raw_row_json] NVARCHAR(MAX) NULL,
    [matched_service_call_id] BIGINT NULL,
    [match_status] NVARCHAR(30) NOT NULL CONSTRAINT [DF_int_oem_ticket_import_line_match_status] DEFAULT (N'Pending'),
    [message] NVARCHAR(500) NULL,
    [processed_at] DATETIME2(0) NULL,
    CONSTRAINT [CK_int_oem_ticket_import_line_match_status] CHECK ([match_status] IN (N'Pending', N'Matched', N'Unmatched', N'Updated', N'Error')),
    CONSTRAINT [FK_int_oem_ticket_import_line_file_import_id] FOREIGN KEY ([file_import_id]) REFERENCES [int].[file_import] ([id]) ON DELETE CASCADE,
    CONSTRAINT [FK_int_oem_ticket_import_line_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]),
    CONSTRAINT [FK_int_oem_ticket_import_line_matched_service_call_id] FOREIGN KEY ([matched_service_call_id]) REFERENCES [svc].[service_call] ([id])
);
GO

/* ---------- 1.8 Sales: OEM price check and credit-limit history ---------- */
-- Price verified against the OEM portal / price list for each quotation line (e.g. ATLAS COPCO).
IF OBJECT_ID(N'sal.quotation_price_check', N'U') IS NULL
CREATE TABLE [sal].[quotation_price_check] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_quotation_price_check] PRIMARY KEY,
    [quotation_line_id] BIGINT NOT NULL,
    [principal_id] BIGINT NULL,
    [price_source] NVARCHAR(30) NOT NULL,
    [oem_price] DECIMAL(18,4) NULL,
    [quoted_price] DECIMAL(18,4) NOT NULL,
    [variance_pct] DECIMAL(7,2) NULL,
    [is_within_tolerance] BIT NULL,
    [checked_by_user_id] BIGINT NULL,
    [checked_at] DATETIME2(0) NOT NULL,
    [remarks] NVARCHAR(300) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_quotation_price_check_created_at] DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT [CK_sal_quotation_price_check_price_source] CHECK ([price_source] IN (N'OEM portal', N'Price list', N'Supplier quote', N'Manual')),
    CONSTRAINT [FK_sal_quotation_price_check_quotation_line_id] FOREIGN KEY ([quotation_line_id]) REFERENCES [sal].[quotation_line] ([id]) ON DELETE CASCADE,
    CONSTRAINT [FK_sal_quotation_price_check_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]),
    CONSTRAINT [FK_sal_quotation_price_check_checked_by_user_id] FOREIGN KEY ([checked_by_user_id]) REFERENCES [core].[app_user] ([id])
);
GO
-- Every change to a customer's credit limit / credit status, with approver.
IF OBJECT_ID(N'sal.credit_limit_change', N'U') IS NULL
CREATE TABLE [sal].[credit_limit_change] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_credit_limit_change] PRIMARY KEY,
    [customer_id] BIGINT NOT NULL,
    [old_credit_limit] DECIMAL(18,2) NULL,
    [new_credit_limit] DECIMAL(18,2) NULL,
    [old_credit_status_id] BIGINT NULL,
    [new_credit_status_id] BIGINT NULL,
    [old_payment_terms_id] BIGINT NULL,
    [new_payment_terms_id] BIGINT NULL,
    [effective_from] DATE NOT NULL,
    [reason] NVARCHAR(300) NOT NULL,
    [approved_by_user_id] BIGINT NULL,
    [approved_at] DATETIME2(0) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_credit_limit_change_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    CONSTRAINT [FK_sal_credit_limit_change_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]),
    CONSTRAINT [FK_sal_credit_limit_change_old_credit_status_id] FOREIGN KEY ([old_credit_status_id]) REFERENCES [sal].[credit_status] ([id]),
    CONSTRAINT [FK_sal_credit_limit_change_new_credit_status_id] FOREIGN KEY ([new_credit_status_id]) REFERENCES [sal].[credit_status] ([id]),
    CONSTRAINT [FK_sal_credit_limit_change_old_payment_terms_id] FOREIGN KEY ([old_payment_terms_id]) REFERENCES [core].[payment_terms] ([id]),
    CONSTRAINT [FK_sal_credit_limit_change_new_payment_terms_id] FOREIGN KEY ([new_payment_terms_id]) REFERENCES [core].[payment_terms] ([id]),
    CONSTRAINT [FK_sal_credit_limit_change_approved_by_user_id] FOREIGN KEY ([approved_by_user_id]) REFERENCES [core].[app_user] ([id])
);
GO

/* ---------- 1.9 HR: vehicles ---------- */
-- Company / own vehicles used for field travel; trips and km claims link here.
IF OBJECT_ID(N'hr.vehicle', N'U') IS NULL
CREATE TABLE [hr].[vehicle] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_vehicle] PRIMARY KEY,
    [registration_number] NVARCHAR(20) NOT NULL,
    [vehicle_type] NVARCHAR(30) NOT NULL,
    [ownership] NVARCHAR(30) NOT NULL,
    [employee_id] BIGINT NULL,
    [asset_id] BIGINT NULL,
    [fuel_type] NVARCHAR(30) NULL,
    [rate_per_km] DECIMAL(6,2) NULL,
    [insurance_valid_until] DATE NULL,
    [puc_valid_until] DATE NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_vehicle_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_vehicle_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_vehicle_vehicle_type] CHECK ([vehicle_type] IN (N'Bike', N'Car', N'Van', N'Pickup', N'Truck')),
    CONSTRAINT [CK_hr_vehicle_ownership] CHECK ([ownership] IN (N'Company', N'Own', N'Hired')),
    CONSTRAINT [CK_hr_vehicle_fuel_type] CHECK ([fuel_type] IS NULL OR [fuel_type] IN (N'Petrol', N'Diesel', N'CNG', N'Electric')),
    CONSTRAINT [FK_hr_vehicle_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]),
    CONSTRAINT [FK_hr_vehicle_asset_id] FOREIGN KEY ([asset_id]) REFERENCES [hr].[asset] ([id])
);
GO

/* ---------- 1.10 Finance: cash mismatch control ---------- */
-- Daily cash count vs system cash receipts per branch / collector; flags gaps.
IF OBJECT_ID(N'acc.cash_reconciliation', N'U') IS NULL
CREATE TABLE [acc].[cash_reconciliation] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_cash_reconciliation] PRIMARY KEY,
    [branch_id] BIGINT NOT NULL,
    [recon_date] DATE NOT NULL,
    [collector_employee_id] BIGINT NULL,
    [bank_account_id] BIGINT NULL,
    [expected_amount] DECIMAL(18,2) NOT NULL,
    [counted_amount] DECIMAL(18,2) NOT NULL,
    [deposited_amount] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_acc_cash_reconciliation_deposited_amount] DEFAULT (0),
    [difference_amount] AS ([counted_amount] - [expected_amount]) PERSISTED,
    [status] NVARCHAR(30) NOT NULL CONSTRAINT [DF_acc_cash_reconciliation_status] DEFAULT (N'Open'),
    [reason] NVARCHAR(300) NULL,
    [approved_by_user_id] BIGINT NULL,
    [approved_at] DATETIME2(0) NULL,
    [bank_txn_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_cash_reconciliation_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_cash_reconciliation_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_acc_cash_reconciliation_status] CHECK ([status] IN (N'Open', N'Matched', N'Mismatch', N'Approved', N'Escalated')),
    CONSTRAINT [FK_acc_cash_reconciliation_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]),
    CONSTRAINT [FK_acc_cash_reconciliation_collector_employee_id] FOREIGN KEY ([collector_employee_id]) REFERENCES [core].[employee] ([id]),
    CONSTRAINT [FK_acc_cash_reconciliation_bank_account_id] FOREIGN KEY ([bank_account_id]) REFERENCES [acc].[bank_account] ([id]),
    CONSTRAINT [FK_acc_cash_reconciliation_approved_by_user_id] FOREIGN KEY ([approved_by_user_id]) REFERENCES [core].[app_user] ([id]),
    CONSTRAINT [FK_acc_cash_reconciliation_bank_txn_id] FOREIGN KEY ([bank_txn_id]) REFERENCES [acc].[bank_txn] ([id])
);
GO

/* ---------- 1.11 Management & compliance: OEM ratings ---------- */
-- Ratings / audit scores given by each OEM to the dealership (per branch, per period).
IF OBJECT_ID(N'core.oem_rating', N'U') IS NULL
CREATE TABLE [core].[oem_rating] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_oem_rating] PRIMARY KEY,
    [principal_id] BIGINT NOT NULL,
    [branch_id] BIGINT NULL,
    [period_month] DATE NOT NULL,
    [rating_category] NVARCHAR(60) NOT NULL,
    [score] DECIMAL(7,2) NOT NULL,
    [max_score] DECIMAL(7,2) NULL,
    [rank_position] SMALLINT NULL,
    [remarks] NVARCHAR(500) NULL,
    [attachment_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_oem_rating_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_oem_rating_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [FK_core_oem_rating_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]),
    CONSTRAINT [FK_core_oem_rating_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]),
    CONSTRAINT [FK_core_oem_rating_attachment_id] FOREIGN KEY ([attachment_id]) REFERENCES [core].[attachment] ([id])
);
GO

/* ---------- 1.12 Reporting: KPI / KRI and balanced scorecard ---------- */
-- KPI / KRI catalogue, grouped by balanced-scorecard perspective.
IF OBJECT_ID(N'rpt.kpi_definition', N'U') IS NULL
CREATE TABLE [rpt].[kpi_definition] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_rpt_kpi_definition] PRIMARY KEY,
    [code] NVARCHAR(40) NOT NULL,
    [name] NVARCHAR(120) NOT NULL,
    [kpi_kind] NVARCHAR(10) NOT NULL,
    [perspective] NVARCHAR(30) NOT NULL,
    [module] NVARCHAR(20) NOT NULL,
    [unit] NVARCHAR(20) NULL,
    [direction] NVARCHAR(30) NOT NULL,
    [frequency] NVARCHAR(20) NOT NULL,
    [calculation_note] NVARCHAR(500) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_rpt_kpi_definition_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_rpt_kpi_definition_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_rpt_kpi_definition_kpi_kind] CHECK ([kpi_kind] IN (N'KPI', N'KRI')),
    CONSTRAINT [CK_rpt_kpi_definition_perspective] CHECK ([perspective] IN (N'Financial', N'Customer', N'Internal process', N'Learning and growth')),
    CONSTRAINT [CK_rpt_kpi_definition_direction] CHECK ([direction] IN (N'Higher is better', N'Lower is better')),
    CONSTRAINT [CK_rpt_kpi_definition_frequency] CHECK ([frequency] IN (N'Daily', N'Weekly', N'Monthly', N'Quarterly', N'Yearly'))
);
GO
-- Targets per KPI, period and scope (company / branch / brand / team / employee).
IF OBJECT_ID(N'rpt.kpi_target', N'U') IS NULL
CREATE TABLE [rpt].[kpi_target] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_rpt_kpi_target] PRIMARY KEY,
    [kpi_definition_id] BIGINT NOT NULL,
    [period_start] DATE NOT NULL,
    [period_end] DATE NOT NULL,
    [scope_type] NVARCHAR(20) NOT NULL,
    [branch_id] BIGINT NULL,
    [principal_id] BIGINT NULL,
    [team_id] BIGINT NULL,
    [employee_id] BIGINT NULL,
    [target_value] DECIMAL(18,4) NOT NULL,
    [threshold_red] DECIMAL(18,4) NULL,
    [threshold_amber] DECIMAL(18,4) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_rpt_kpi_target_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_rpt_kpi_target_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_rpt_kpi_target_scope_type] CHECK ([scope_type] IN (N'Company', N'Branch', N'Principal', N'Team', N'Employee')),
    CONSTRAINT [CK_rpt_kpi_target_period] CHECK ([period_end] >= [period_start]),
    CONSTRAINT [FK_rpt_kpi_target_kpi_definition_id] FOREIGN KEY ([kpi_definition_id]) REFERENCES [rpt].[kpi_definition] ([id]),
    CONSTRAINT [FK_rpt_kpi_target_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]),
    CONSTRAINT [FK_rpt_kpi_target_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]),
    CONSTRAINT [FK_rpt_kpi_target_team_id] FOREIGN KEY ([team_id]) REFERENCES [core].[team] ([id]),
    CONSTRAINT [FK_rpt_kpi_target_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id])
);
GO
-- Calculated KPI values (written by the nightly job; insert only).
IF OBJECT_ID(N'rpt.kpi_actual', N'U') IS NULL
CREATE TABLE [rpt].[kpi_actual] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_rpt_kpi_actual] PRIMARY KEY,
    [kpi_definition_id] BIGINT NOT NULL,
    [period_start] DATE NOT NULL,
    [period_end] DATE NOT NULL,
    [scope_type] NVARCHAR(20) NOT NULL,
    [branch_id] BIGINT NULL,
    [principal_id] BIGINT NULL,
    [team_id] BIGINT NULL,
    [employee_id] BIGINT NULL,
    [actual_value] DECIMAL(18,4) NOT NULL,
    [calculated_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_rpt_kpi_actual_calculated_at] DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT [CK_rpt_kpi_actual_scope_type] CHECK ([scope_type] IN (N'Company', N'Branch', N'Principal', N'Team', N'Employee')),
    CONSTRAINT [FK_rpt_kpi_actual_kpi_definition_id] FOREIGN KEY ([kpi_definition_id]) REFERENCES [rpt].[kpi_definition] ([id]),
    CONSTRAINT [FK_rpt_kpi_actual_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]),
    CONSTRAINT [FK_rpt_kpi_actual_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]),
    CONSTRAINT [FK_rpt_kpi_actual_team_id] FOREIGN KEY ([team_id]) REFERENCES [core].[team] ([id]),
    CONSTRAINT [FK_rpt_kpi_actual_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id])
);
GO

/* ---------- 1.13 Unique keys and FK indexes for the new tables ---------- */
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_hr_skill_code') CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_skill_code] ON [hr].[skill] ([code]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_hr_skill_principal_id') CREATE NONCLUSTERED INDEX [IX_hr_skill_principal_id] ON [hr].[skill] ([principal_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_hr_employee_skill_k1') CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_employee_skill_k1] ON [hr].[employee_skill] ([employee_id], [skill_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_hr_employee_skill_skill_id') CREATE NONCLUSTERED INDEX [IX_hr_employee_skill_skill_id] ON [hr].[employee_skill] ([skill_id]) INCLUDE ([employee_id], [proficiency]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_hr_employee_skill_certificate_attachment_id') CREATE NONCLUSTERED INDEX [IX_hr_employee_skill_certificate_attachment_id] ON [hr].[employee_skill] ([certificate_attachment_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_skill_rule_skill_id') CREATE NONCLUSTERED INDEX [IX_svc_skill_rule_skill_id] ON [svc].[skill_rule] ([skill_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_skill_rule_match') CREATE NONCLUSTERED INDEX [IX_svc_skill_rule_match] ON [svc].[skill_rule] ([principal_id], [call_type_lookup_id], [complaint_category_lookup_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_skill_rule_machine_model_id') CREATE NONCLUSTERED INDEX [IX_svc_skill_rule_machine_model_id] ON [svc].[skill_rule] ([machine_model_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_skill_rule_call_type_lookup_id') CREATE NONCLUSTERED INDEX [IX_svc_skill_rule_call_type_lookup_id] ON [svc].[skill_rule] ([call_type_lookup_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_skill_rule_complaint_category_lookup_id') CREATE NONCLUSTERED INDEX [IX_svc_skill_rule_complaint_category_lookup_id] ON [svc].[skill_rule] ([complaint_category_lookup_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_svc_call_required_skill_k1') CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_call_required_skill_k1] ON [svc].[call_required_skill] ([service_call_id], [skill_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_call_required_skill_skill_id') CREATE NONCLUSTERED INDEX [IX_svc_call_required_skill_skill_id] ON [svc].[call_required_skill] ([skill_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_svc_call_reopen_k1') CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_call_reopen_k1] ON [svc].[call_reopen] ([service_call_id], [reopen_no]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_call_reopen_reopened_by_user_id') CREATE NONCLUSTERED INDEX [IX_svc_call_reopen_reopened_by_user_id] ON [svc].[call_reopen] ([reopened_by_user_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_call_reopen_reason_lookup_id') CREATE NONCLUSTERED INDEX [IX_svc_call_reopen_reason_lookup_id] ON [svc].[call_reopen] ([reason_lookup_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_call_reopen_previous_engineer_id') CREATE NONCLUSTERED INDEX [IX_svc_call_reopen_previous_engineer_id] ON [svc].[call_reopen] ([previous_engineer_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_svc_contract_plan_code') CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_contract_plan_code] ON [svc].[contract_plan] ([code]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_contract_plan_principal_id') CREATE NONCLUSTERED INDEX [IX_svc_contract_plan_principal_id] ON [svc].[contract_plan] ([principal_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_contract_plan_entitlement_contract_plan_id') CREATE NONCLUSTERED INDEX [IX_svc_contract_plan_entitlement_contract_plan_id] ON [svc].[contract_plan_entitlement] ([contract_plan_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_contract_plan_entitlement_item_id') CREATE NONCLUSTERED INDEX [IX_svc_contract_plan_entitlement_item_id] ON [svc].[contract_plan_entitlement] ([item_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_svc_contract_billing_schedule_k1') CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_contract_billing_schedule_k1] ON [svc].[contract_billing_schedule] ([service_contract_id], [instalment_no]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_contract_billing_schedule_sales_invoice_id') CREATE NONCLUSTERED INDEX [IX_svc_contract_billing_schedule_sales_invoice_id] ON [svc].[contract_billing_schedule] ([sales_invoice_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_contract_billing_schedule_due') CREATE NONCLUSTERED INDEX [IX_svc_contract_billing_schedule_due] ON [svc].[contract_billing_schedule] ([status], [due_date]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_core_machine_telemetry_time') CREATE NONCLUSTERED INDEX [IX_core_machine_telemetry_time] ON [core].[machine_telemetry] ([machine_unit_id], [metric_code], [recorded_at]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_core_machine_telemetry_external_system_id') CREATE NONCLUSTERED INDEX [IX_core_machine_telemetry_external_system_id] ON [core].[machine_telemetry] ([external_system_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_machine_alert_machine_unit_id') CREATE NONCLUSTERED INDEX [IX_svc_machine_alert_machine_unit_id] ON [svc].[machine_alert] ([machine_unit_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_machine_alert_open') CREATE NONCLUSTERED INDEX [IX_svc_machine_alert_open] ON [svc].[machine_alert] ([status], [raised_at]) INCLUDE ([principal_id], [severity]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_machine_alert_principal_id') CREATE NONCLUSTERED INDEX [IX_svc_machine_alert_principal_id] ON [svc].[machine_alert] ([principal_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_machine_alert_acknowledged_by_user_id') CREATE NONCLUSTERED INDEX [IX_svc_machine_alert_acknowledged_by_user_id] ON [svc].[machine_alert] ([acknowledged_by_user_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_machine_alert_service_call_id') CREATE NONCLUSTERED INDEX [IX_svc_machine_alert_service_call_id] ON [svc].[machine_alert] ([service_call_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_machine_alert_planned_service_id') CREATE NONCLUSTERED INDEX [IX_svc_machine_alert_planned_service_id] ON [svc].[machine_alert] ([planned_service_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_duty_gps_point_time') CREATE NONCLUSTERED INDEX [IX_svc_duty_gps_point_time] ON [svc].[duty_gps_point] ([duty_log_id], [recorded_at]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_core_customer_portal_user_cognito_sub') CREATE UNIQUE NONCLUSTERED INDEX [UX_core_customer_portal_user_cognito_sub] ON [core].[customer_portal_user] ([cognito_sub]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_core_customer_portal_user_username') CREATE UNIQUE NONCLUSTERED INDEX [UX_core_customer_portal_user_username] ON [core].[customer_portal_user] ([username]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_core_customer_portal_user_customer_id') CREATE NONCLUSTERED INDEX [IX_core_customer_portal_user_customer_id] ON [core].[customer_portal_user] ([customer_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_core_customer_portal_user_contact_id') CREATE NONCLUSTERED INDEX [IX_core_customer_portal_user_contact_id] ON [core].[customer_portal_user] ([contact_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_int_inbound_message_provider_message_id') CREATE UNIQUE NONCLUSTERED INDEX [UX_int_inbound_message_provider_message_id] ON [int].[inbound_message] ([channel], [provider_message_id]) WHERE [provider_message_id] IS NOT NULL;
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_int_inbound_message_status') CREATE NONCLUSTERED INDEX [IX_int_inbound_message_status] ON [int].[inbound_message] ([status], [received_at]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_int_inbound_message_external_system_id') CREATE NONCLUSTERED INDEX [IX_int_inbound_message_external_system_id] ON [int].[inbound_message] ([external_system_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_int_inbound_message_service_call_id') CREATE NONCLUSTERED INDEX [IX_int_inbound_message_service_call_id] ON [int].[inbound_message] ([service_call_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_int_inbound_message_service_part_request_id') CREATE NONCLUSTERED INDEX [IX_int_inbound_message_service_part_request_id] ON [int].[inbound_message] ([service_part_request_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_int_inbound_message_processed_by_user_id') CREATE NONCLUSTERED INDEX [IX_int_inbound_message_processed_by_user_id] ON [int].[inbound_message] ([processed_by_user_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_int_oem_ticket_import_line_k1') CREATE UNIQUE NONCLUSTERED INDEX [UX_int_oem_ticket_import_line_k1] ON [int].[oem_ticket_import_line] ([file_import_id], [row_number]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_int_oem_ticket_import_line_oem_call_id') CREATE NONCLUSTERED INDEX [IX_int_oem_ticket_import_line_oem_call_id] ON [int].[oem_ticket_import_line] ([principal_id], [oem_call_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_int_oem_ticket_import_line_matched_service_call_id') CREATE NONCLUSTERED INDEX [IX_int_oem_ticket_import_line_matched_service_call_id] ON [int].[oem_ticket_import_line] ([matched_service_call_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sal_quotation_price_check_quotation_line_id') CREATE NONCLUSTERED INDEX [IX_sal_quotation_price_check_quotation_line_id] ON [sal].[quotation_price_check] ([quotation_line_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sal_quotation_price_check_principal_id') CREATE NONCLUSTERED INDEX [IX_sal_quotation_price_check_principal_id] ON [sal].[quotation_price_check] ([principal_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sal_quotation_price_check_checked_by_user_id') CREATE NONCLUSTERED INDEX [IX_sal_quotation_price_check_checked_by_user_id] ON [sal].[quotation_price_check] ([checked_by_user_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sal_credit_limit_change_customer_id') CREATE NONCLUSTERED INDEX [IX_sal_credit_limit_change_customer_id] ON [sal].[credit_limit_change] ([customer_id], [effective_from]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sal_credit_limit_change_old_credit_status_id') CREATE NONCLUSTERED INDEX [IX_sal_credit_limit_change_old_credit_status_id] ON [sal].[credit_limit_change] ([old_credit_status_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sal_credit_limit_change_new_credit_status_id') CREATE NONCLUSTERED INDEX [IX_sal_credit_limit_change_new_credit_status_id] ON [sal].[credit_limit_change] ([new_credit_status_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sal_credit_limit_change_old_payment_terms_id') CREATE NONCLUSTERED INDEX [IX_sal_credit_limit_change_old_payment_terms_id] ON [sal].[credit_limit_change] ([old_payment_terms_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sal_credit_limit_change_new_payment_terms_id') CREATE NONCLUSTERED INDEX [IX_sal_credit_limit_change_new_payment_terms_id] ON [sal].[credit_limit_change] ([new_payment_terms_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sal_credit_limit_change_approved_by_user_id') CREATE NONCLUSTERED INDEX [IX_sal_credit_limit_change_approved_by_user_id] ON [sal].[credit_limit_change] ([approved_by_user_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_hr_vehicle_registration_number') CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_vehicle_registration_number] ON [hr].[vehicle] ([registration_number]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_hr_vehicle_employee_id') CREATE NONCLUSTERED INDEX [IX_hr_vehicle_employee_id] ON [hr].[vehicle] ([employee_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_hr_vehicle_asset_id') CREATE NONCLUSTERED INDEX [IX_hr_vehicle_asset_id] ON [hr].[vehicle] ([asset_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_acc_cash_reconciliation_k1') CREATE UNIQUE NONCLUSTERED INDEX [UX_acc_cash_reconciliation_k1] ON [acc].[cash_reconciliation] ([branch_id], [recon_date], [collector_employee_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_acc_cash_reconciliation_collector_employee_id') CREATE NONCLUSTERED INDEX [IX_acc_cash_reconciliation_collector_employee_id] ON [acc].[cash_reconciliation] ([collector_employee_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_acc_cash_reconciliation_bank_account_id') CREATE NONCLUSTERED INDEX [IX_acc_cash_reconciliation_bank_account_id] ON [acc].[cash_reconciliation] ([bank_account_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_acc_cash_reconciliation_approved_by_user_id') CREATE NONCLUSTERED INDEX [IX_acc_cash_reconciliation_approved_by_user_id] ON [acc].[cash_reconciliation] ([approved_by_user_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_acc_cash_reconciliation_bank_txn_id') CREATE NONCLUSTERED INDEX [IX_acc_cash_reconciliation_bank_txn_id] ON [acc].[cash_reconciliation] ([bank_txn_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_core_oem_rating_k1') CREATE UNIQUE NONCLUSTERED INDEX [UX_core_oem_rating_k1] ON [core].[oem_rating] ([principal_id], [branch_id], [period_month], [rating_category]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_core_oem_rating_branch_id') CREATE NONCLUSTERED INDEX [IX_core_oem_rating_branch_id] ON [core].[oem_rating] ([branch_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_core_oem_rating_attachment_id') CREATE NONCLUSTERED INDEX [IX_core_oem_rating_attachment_id] ON [core].[oem_rating] ([attachment_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_rpt_kpi_definition_code') CREATE UNIQUE NONCLUSTERED INDEX [UX_rpt_kpi_definition_code] ON [rpt].[kpi_definition] ([code]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rpt_kpi_target_lookup') CREATE NONCLUSTERED INDEX [IX_rpt_kpi_target_lookup] ON [rpt].[kpi_target] ([kpi_definition_id], [period_start], [scope_type]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rpt_kpi_target_branch_id') CREATE NONCLUSTERED INDEX [IX_rpt_kpi_target_branch_id] ON [rpt].[kpi_target] ([branch_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rpt_kpi_target_principal_id') CREATE NONCLUSTERED INDEX [IX_rpt_kpi_target_principal_id] ON [rpt].[kpi_target] ([principal_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rpt_kpi_target_team_id') CREATE NONCLUSTERED INDEX [IX_rpt_kpi_target_team_id] ON [rpt].[kpi_target] ([team_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rpt_kpi_target_employee_id') CREATE NONCLUSTERED INDEX [IX_rpt_kpi_target_employee_id] ON [rpt].[kpi_target] ([employee_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rpt_kpi_actual_lookup') CREATE NONCLUSTERED INDEX [IX_rpt_kpi_actual_lookup] ON [rpt].[kpi_actual] ([kpi_definition_id], [period_start], [scope_type]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rpt_kpi_actual_branch_id') CREATE NONCLUSTERED INDEX [IX_rpt_kpi_actual_branch_id] ON [rpt].[kpi_actual] ([branch_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rpt_kpi_actual_principal_id') CREATE NONCLUSTERED INDEX [IX_rpt_kpi_actual_principal_id] ON [rpt].[kpi_actual] ([principal_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rpt_kpi_actual_team_id') CREATE NONCLUSTERED INDEX [IX_rpt_kpi_actual_team_id] ON [rpt].[kpi_actual] ([team_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rpt_kpi_actual_employee_id') CREATE NONCLUSTERED INDEX [IX_rpt_kpi_actual_employee_id] ON [rpt].[kpi_actual] ([employee_id]);
GO

/* =====================================================================
   PART 2 - CHANGES TO EXISTING TABLES
   Column adds run in one batch; FKs/CHECKs that use them run in the next.
   ===================================================================== */

/* ---------- 2.1 New columns ---------- */
-- core
IF COL_LENGTH(N'core.employee', N'mobile_platform') IS NULL
    ALTER TABLE [core].[employee] ADD [mobile_platform] NVARCHAR(30) NULL;
IF COL_LENGTH(N'core.machine_unit', N'telematics_device_id') IS NULL
    ALTER TABLE [core].[machine_unit] ADD [telematics_device_id] NVARCHAR(60) NULL;
IF COL_LENGTH(N'core.machine_meter_reading', N'meter_type') IS NULL
    ALTER TABLE [core].[machine_meter_reading] ADD [meter_type] NVARCHAR(30) NOT NULL CONSTRAINT [DF_core_machine_meter_reading_meter_type] DEFAULT (N'HMR');
IF COL_LENGTH(N'core.attachment', N'verification_status') IS NULL
    ALTER TABLE [core].[attachment] ADD [verification_status] NVARCHAR(30) NOT NULL CONSTRAINT [DF_core_attachment_verification_status] DEFAULT (N'Not required');
IF COL_LENGTH(N'core.attachment', N'verified_by_user_id') IS NULL
    ALTER TABLE [core].[attachment] ADD [verified_by_user_id] BIGINT NULL, [verified_at] DATETIME2(0) NULL, [verification_remarks] NVARCHAR(300) NULL;
IF COL_LENGTH(N'core.approval_rule', N'approval_type') IS NULL
    ALTER TABLE [core].[approval_rule] ADD [approval_type] NVARCHAR(30) NOT NULL CONSTRAINT [DF_core_approval_rule_approval_type] DEFAULT (N'Value');
IF COL_LENGTH(N'core.approval_rule', N'min_discount_pct') IS NULL
    ALTER TABLE [core].[approval_rule] ADD [min_discount_pct] DECIMAL(5,2) NULL, [max_discount_pct] DECIMAL(5,2) NULL;

-- svc.service_call: reopen, warranty check, OEM completion
IF COL_LENGTH(N'svc.service_call', N'reopen_count') IS NULL
    ALTER TABLE [svc].[service_call] ADD [reopen_count] SMALLINT NOT NULL CONSTRAINT [DF_svc_service_call_reopen_count] DEFAULT (0);
IF COL_LENGTH(N'svc.service_call', N'last_reopened_at') IS NULL
    ALTER TABLE [svc].[service_call] ADD [last_reopened_at] DATETIME2(0) NULL;
IF COL_LENGTH(N'svc.service_call', N'warranty_checked_at') IS NULL
    ALTER TABLE [svc].[service_call] ADD [warranty_checked_at] DATETIME2(0) NULL, [warranty_checked_by_user_id] BIGINT NULL, [coverage_remarks] NVARCHAR(300) NULL;
IF COL_LENGTH(N'svc.service_call', N'completed_at') IS NULL
    ALTER TABLE [svc].[service_call] ADD [completed_at] DATETIME2(0) NULL;

-- svc.oem_call_reference: allow history (new OEM Call ID after a reopen)
IF COL_LENGTH(N'svc.oem_call_reference', N'is_current') IS NULL
    ALTER TABLE [svc].[oem_call_reference] ADD [is_current] BIT NOT NULL CONSTRAINT [DF_svc_oem_call_reference_is_current] DEFAULT (1);

-- svc.service_part_request: parts -> quotation -> stock / purchase -> dispatch to site
IF COL_LENGTH(N'svc.service_part_request', N'request_channel') IS NULL
    ALTER TABLE [svc].[service_part_request] ADD [request_channel] NVARCHAR(30) NULL;
IF COL_LENGTH(N'svc.service_part_request', N'reviewed_by_user_id') IS NULL
    ALTER TABLE [svc].[service_part_request] ADD [reviewed_by_user_id] BIGINT NULL, [reviewed_at] DATETIME2(0) NULL;
IF COL_LENGTH(N'svc.service_part_request', N'available_qty') IS NULL
    ALTER TABLE [svc].[service_part_request] ADD [available_qty] DECIMAL(18,3) NULL, [fulfilment_source] NVARCHAR(30) NULL, [expected_available_date] DATE NULL;
IF COL_LENGTH(N'svc.service_part_request', N'quotation_id') IS NULL
    ALTER TABLE [svc].[service_part_request] ADD [quotation_id] BIGINT NULL, [purchase_request_id] BIGINT NULL;

-- svc.planned_service: contract (3/6/9/12-month) schedules, not only HMR templates
IF COL_LENGTH(N'svc.planned_service', N'service_contract_id') IS NULL
    ALTER TABLE [svc].[planned_service] ADD [service_contract_id] BIGINT NULL, [plan_label] NVARCHAR(40) NULL;

-- svc.service_contract: plan, frequency, renewal, enrolment, billing
IF COL_LENGTH(N'svc.service_contract', N'contract_plan_id') IS NULL
    ALTER TABLE [svc].[service_contract] ADD [contract_plan_id] BIGINT NULL;
IF COL_LENGTH(N'svc.service_contract', N'visit_frequency_months') IS NULL
    ALTER TABLE [svc].[service_contract] ADD [visit_frequency_months] TINYINT NULL, [billing_frequency] NVARCHAR(30) NULL;
IF COL_LENGTH(N'svc.service_contract', N'renewed_from_contract_id') IS NULL
    ALTER TABLE [svc].[service_contract] ADD [renewed_from_contract_id] BIGINT NULL;
IF COL_LENGTH(N'svc.service_contract', N'enrolled_on') IS NULL
    ALTER TABLE [svc].[service_contract] ADD [enrolled_on] DATE NULL, [enrolled_by_employee_id] BIGINT NULL;

-- svc.trip: vehicle used
IF COL_LENGTH(N'svc.trip', N'vehicle_id') IS NULL
    ALTER TABLE [svc].[trip] ADD [vehicle_id] BIGINT NULL;

-- svc.warranty_claim: manual / Excel claims
IF COL_LENGTH(N'svc.warranty_claim', N'claim_source') IS NULL
    ALTER TABLE [svc].[warranty_claim] ADD [claim_source] NVARCHAR(30) NOT NULL CONSTRAINT [DF_svc_warranty_claim_claim_source] DEFAULT (N'Manual');
IF COL_LENGTH(N'svc.warranty_claim', N'file_import_id') IS NULL
    ALTER TABLE [svc].[warranty_claim] ADD [file_import_id] BIGINT NULL;

-- inv
IF COL_LENGTH(N'inv.stock_issue', N'dispatch_mode') IS NULL
    ALTER TABLE [inv].[stock_issue] ADD [dispatch_mode] NVARCHAR(30) NULL, [courier_name] NVARCHAR(100) NULL, [docket_no] NVARCHAR(40) NULL,
        [dispatched_at] DATETIME2(0) NULL, [delivered_at] DATETIME2(0) NULL, [delivered_to_site_id] BIGINT NULL;
IF COL_LENGTH(N'inv.stock_transfer', N'delivery_challan_no') IS NULL
    ALTER TABLE [inv].[stock_transfer] ADD [delivery_challan_no] NVARCHAR(30) NULL;
IF COL_LENGTH(N'inv.stock_transfer_line', N'hsn_sac_id') IS NULL
    ALTER TABLE [inv].[stock_transfer_line] ADD [hsn_sac_id] BIGINT NULL, [unit_value] DECIMAL(18,4) NULL, [taxable_value] DECIMAL(18,2) NULL;

-- pur
IF COL_LENGTH(N'pur.purchase_request', N'sales_order_id') IS NULL
    ALTER TABLE [pur].[purchase_request] ADD [sales_order_id] BIGINT NULL;
IF COL_LENGTH(N'pur.purchase_order', N'po_type') IS NULL
    ALTER TABLE [pur].[purchase_order] ADD [po_type] NVARCHAR(30) NOT NULL CONSTRAINT [DF_pur_purchase_order_po_type] DEFAULT (N'Local');
IF COL_LENGTH(N'pur.grn', N'grn_type') IS NULL
    ALTER TABLE [pur].[grn] ADD [grn_type] NVARCHAR(30) NOT NULL CONSTRAINT [DF_pur_grn_grn_type] DEFAULT (N'Regular');
IF COL_LENGTH(N'pur.grn', N'expected_arrival_date') IS NULL
    ALTER TABLE [pur].[grn] ADD [expected_arrival_date] DATE NULL;
IF COL_LENGTH(N'pur.supplier_allocation', N'opening_balance_id') IS NULL
    ALTER TABLE [pur].[supplier_allocation] ADD [opening_balance_id] BIGINT NULL;

-- sal
IF COL_LENGTH(N'sal.sales_order', N'service_call_id') IS NULL
    ALTER TABLE [sal].[sales_order] ADD [service_call_id] BIGINT NULL;
IF COL_LENGTH(N'sal.sales_order', N'credit_check_status') IS NULL
    ALTER TABLE [sal].[sales_order] ADD [credit_check_status] NVARCHAR(30) NOT NULL CONSTRAINT [DF_sal_sales_order_credit_check_status] DEFAULT (N'Not checked');
IF COL_LENGTH(N'sal.sales_order', N'credit_approved_by_user_id') IS NULL
    ALTER TABLE [sal].[sales_order] ADD [credit_approved_by_user_id] BIGINT NULL, [credit_approved_at] DATETIME2(0) NULL;
IF COL_LENGTH(N'sal.sales_order', N'is_payment_confirmed') IS NULL
    ALTER TABLE [sal].[sales_order] ADD [is_payment_confirmed] BIT NOT NULL CONSTRAINT [DF_sal_sales_order_is_payment_confirmed] DEFAULT (0);
IF COL_LENGTH(N'sal.sales_order', N'payment_confirmed_by_user_id') IS NULL
    ALTER TABLE [sal].[sales_order] ADD [payment_confirmed_by_user_id] BIGINT NULL, [payment_confirmed_at] DATETIME2(0) NULL;
IF COL_LENGTH(N'sal.delivery_note', N'service_call_id') IS NULL
    ALTER TABLE [sal].[delivery_note] ADD [service_call_id] BIGINT NULL;
IF COL_LENGTH(N'sal.delivery_note', N'dispatched_at') IS NULL
    ALTER TABLE [sal].[delivery_note] ADD [dispatched_at] DATETIME2(0) NULL, [lr_no] NVARCHAR(40) NULL, [courier_docket_no] NVARCHAR(40) NULL,
        [delivered_at] DATETIME2(0) NULL, [received_by_name] NVARCHAR(100) NULL, [pod_attachment_id] BIGINT NULL;
IF COL_LENGTH(N'sal.receipt', N'confirmed_by_user_id') IS NULL
    ALTER TABLE [sal].[receipt] ADD [confirmed_by_user_id] BIGINT NULL, [confirmed_at] DATETIME2(0) NULL;
IF COL_LENGTH(N'sal.receipt', N'collected_by_employee_id') IS NULL
    ALTER TABLE [sal].[receipt] ADD [collected_by_employee_id] BIGINT NULL;
IF COL_LENGTH(N'sal.sales_invoice_line', N'unit_cost') IS NULL
    ALTER TABLE [sal].[sales_invoice_line] ADD [unit_cost] DECIMAL(18,4) NULL;
IF COL_LENGTH(N'sal.customer_allocation', N'opening_balance_id') IS NULL
    ALTER TABLE [sal].[customer_allocation] ADD [opening_balance_id] BIGINT NULL;
GO

/* ---------- 2.2 Make allocation targets nullable (allocate against opening bills too) ---------- */
IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'sal.customer_allocation') AND name = N'sales_invoice_id' AND is_nullable = 0)
BEGIN
    ALTER TABLE [sal].[customer_allocation] DROP CONSTRAINT [FK_sal_customer_allocation_sales_invoice_id];
    DROP INDEX [IX_sal_customer_allocation_sales_invoice_id] ON [sal].[customer_allocation];
    ALTER TABLE [sal].[customer_allocation] ALTER COLUMN [sales_invoice_id] BIGINT NULL;
    ALTER TABLE [sal].[customer_allocation] ADD CONSTRAINT [FK_sal_customer_allocation_sales_invoice_id] FOREIGN KEY ([sales_invoice_id]) REFERENCES [sal].[sales_invoice] ([id]);
    CREATE NONCLUSTERED INDEX [IX_sal_customer_allocation_sales_invoice_id] ON [sal].[customer_allocation] ([sales_invoice_id]);
END
GO
IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'pur.supplier_allocation') AND name = N'supplier_invoice_id' AND is_nullable = 0)
BEGIN
    ALTER TABLE [pur].[supplier_allocation] DROP CONSTRAINT [FK_pur_supplier_allocation_supplier_invoice_id];
    DROP INDEX [IX_pur_supplier_allocation_supplier_invoice_id] ON [pur].[supplier_allocation];
    ALTER TABLE [pur].[supplier_allocation] ALTER COLUMN [supplier_invoice_id] BIGINT NULL;
    ALTER TABLE [pur].[supplier_allocation] ADD CONSTRAINT [FK_pur_supplier_allocation_supplier_invoice_id] FOREIGN KEY ([supplier_invoice_id]) REFERENCES [pur].[supplier_invoice] ([id]);
    CREATE NONCLUSTERED INDEX [IX_pur_supplier_allocation_supplier_invoice_id] ON [pur].[supplier_allocation] ([supplier_invoice_id]);
END
GO
/* planned_service.schedule_template_id becomes optional (contract-driven plans have no HMR template) */
IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'svc.planned_service') AND name = N'schedule_template_id' AND is_nullable = 0)
BEGIN
    ALTER TABLE [svc].[planned_service] DROP CONSTRAINT [FK_svc_planned_service_schedule_template_id];
    DROP INDEX [IX_svc_planned_service_schedule_template_id] ON [svc].[planned_service];
    ALTER TABLE [svc].[planned_service] ALTER COLUMN [schedule_template_id] BIGINT NULL;
    ALTER TABLE [svc].[planned_service] ADD CONSTRAINT [FK_svc_planned_service_schedule_template_id] FOREIGN KEY ([schedule_template_id]) REFERENCES [svc].[service_schedule_template] ([id]);
    CREATE NONCLUSTERED INDEX [IX_svc_planned_service_schedule_template_id] ON [svc].[planned_service] ([schedule_template_id]);
END
GO
/* oem_call_reference: one CURRENT OEM Call ID per call (history kept), OEM ID unique per brand */
IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_svc_oem_call_reference_service_call_id' AND object_id = OBJECT_ID(N'svc.oem_call_reference'))
    DROP INDEX [UX_svc_oem_call_reference_service_call_id] ON [svc].[oem_call_reference];
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_svc_oem_call_reference_current')
    CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_oem_call_reference_current] ON [svc].[oem_call_reference] ([service_call_id]) WHERE [is_current] = 1;
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_oem_call_reference_service_call_id')
    CREATE NONCLUSTERED INDEX [IX_svc_oem_call_reference_service_call_id] ON [svc].[oem_call_reference] ([service_call_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_svc_oem_call_reference_oem_call_id')
    CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_oem_call_reference_oem_call_id] ON [svc].[oem_call_reference] ([principal_id], [oem_call_id]);
GO

/* ---------- 2.3 Widened status / type lists (supersets of v2, existing rows stay valid) ---------- */
IF OBJECT_ID(N'[svc].[CK_svc_service_call_current_status]', N'C') IS NOT NULL
    ALTER TABLE [svc].[service_call] DROP CONSTRAINT [CK_svc_service_call_current_status];
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [CK_svc_service_call_current_status] CHECK ([current_status] IN (
    N'Logged', N'Assigned', N'Call ID linked', N'Customer contacted', N'Trip started', N'Reached site', N'In progress',
    N'Report submitted', N'Awaiting parts', N'Parts ready', N'Revisit scheduled', N'Closed', N'Pending OEM closure',
    N'Completed', N'Reopened', N'Cancelled'));
GO
IF OBJECT_ID(N'[svc].[CK_svc_service_part_request_status]', N'C') IS NOT NULL
    ALTER TABLE [svc].[service_part_request] DROP CONSTRAINT [CK_svc_service_part_request_status];
ALTER TABLE [svc].[service_part_request] ADD CONSTRAINT [CK_svc_service_part_request_status] CHECK ([status] IN (
    N'Requested', N'Under review', N'Quoted', N'Customer approved', N'Approved', N'Reserved', N'Ordered', N'Issued',
    N'Dispatched', N'Delivered to site', N'Fitted', N'Returned', N'Rejected', N'Cancelled'));
GO
IF OBJECT_ID(N'[core].[CK_core_machine_model_product_line]', N'C') IS NOT NULL
    ALTER TABLE [core].[machine_model] DROP CONSTRAINT [CK_core_machine_model_product_line];
ALTER TABLE [core].[machine_model] ADD CONSTRAINT [CK_core_machine_model_product_line] CHECK ([product_line] IN (
    N'Excavator', N'Backhoe loader', N'Wheel loader', N'Mini excavator', N'Air compressor', N'Dryer', N'Generator',
    N'Vacuum pump', N'Blower', N'Air treatment', N'Other'));
GO
IF OBJECT_ID(N'[pur].[CK_pur_purchase_request_source_type]', N'C') IS NOT NULL
    ALTER TABLE [pur].[purchase_request] DROP CONSTRAINT [CK_pur_purchase_request_source_type];
ALTER TABLE [pur].[purchase_request] ADD CONSTRAINT [CK_pur_purchase_request_source_type] CHECK ([source_type] IN (N'Reorder', N'Service call', N'Sales order', N'Manual'));
GO
IF OBJECT_ID(N'[pur].[CK_pur_grn_status]', N'C') IS NOT NULL
    ALTER TABLE [pur].[grn] DROP CONSTRAINT [CK_pur_grn_status];
ALTER TABLE [pur].[grn] ADD CONSTRAINT [CK_pur_grn_status] CHECK ([status] IN (N'Draft', N'In transit', N'Posted', N'Cancelled'));
GO
IF OBJECT_ID(N'[inv].[CK_inv_stock_issue_status]', N'C') IS NOT NULL
    ALTER TABLE [inv].[stock_issue] DROP CONSTRAINT [CK_inv_stock_issue_status];
ALTER TABLE [inv].[stock_issue] ADD CONSTRAINT [CK_inv_stock_issue_status] CHECK ([status] IN (N'Draft', N'Issued', N'Dispatched', N'Delivered', N'Cancelled'));
GO
IF OBJECT_ID(N'[sal].[CK_sal_receipt_status]', N'C') IS NOT NULL
    ALTER TABLE [sal].[receipt] DROP CONSTRAINT [CK_sal_receipt_status];
ALTER TABLE [sal].[receipt] ADD CONSTRAINT [CK_sal_receipt_status] CHECK ([status] IN (N'Draft', N'Pending confirmation', N'Posted', N'Bounced', N'Cancelled'));
GO
IF OBJECT_ID(N'[int].[CK_int_file_import_import_type]', N'C') IS NOT NULL
    ALTER TABLE [int].[file_import] DROP CONSTRAINT [CK_int_file_import_import_type];
ALTER TABLE [int].[file_import] ADD CONSTRAINT [CK_int_file_import_import_type] CHECK ([import_type] IN (
    N'Customers', N'Machines', N'Items', N'Open calls', N'Registered products', N'Service tickets', N'OEM case list',
    N'OEM service list', N'Warranty claims', N'Price list', N'Stock count', N'Employees', N'Suppliers',
    N'ASC enrolments', N'Bank statement', N'Opening balances'));
GO

/* ---------- 2.4 CHECKs on the new columns ---------- */
IF OBJECT_ID(N'[core].[CK_core_employee_mobile_platform]', N'C') IS NULL
    ALTER TABLE [core].[employee] ADD CONSTRAINT [CK_core_employee_mobile_platform] CHECK ([mobile_platform] IS NULL OR [mobile_platform] IN (N'Android', N'iOS'));
IF OBJECT_ID(N'[core].[CK_core_machine_meter_reading_meter_type]', N'C') IS NULL
    ALTER TABLE [core].[machine_meter_reading] ADD CONSTRAINT [CK_core_machine_meter_reading_meter_type] CHECK ([meter_type] IN (N'HMR', N'Running hours', N'Loaded hours', N'Odometer'));
IF OBJECT_ID(N'[core].[CK_core_attachment_verification_status]', N'C') IS NULL
    ALTER TABLE [core].[attachment] ADD CONSTRAINT [CK_core_attachment_verification_status] CHECK ([verification_status] IN (N'Not required', N'Pending', N'Verified', N'Rejected'));
IF OBJECT_ID(N'[core].[CK_core_approval_rule_approval_type]', N'C') IS NULL
    ALTER TABLE [core].[approval_rule] ADD CONSTRAINT [CK_core_approval_rule_approval_type] CHECK ([approval_type] IN (N'Value', N'Discount', N'Credit', N'Price override', N'Other'));
IF OBJECT_ID(N'[svc].[CK_svc_service_part_request_request_channel]', N'C') IS NULL
    ALTER TABLE [svc].[service_part_request] ADD CONSTRAINT [CK_svc_service_part_request_request_channel] CHECK ([request_channel] IS NULL OR [request_channel] IN (N'App', N'WhatsApp', N'Email', N'Phone'));
IF OBJECT_ID(N'[svc].[CK_svc_service_part_request_fulfilment_source]', N'C') IS NULL
    ALTER TABLE [svc].[service_part_request] ADD CONSTRAINT [CK_svc_service_part_request_fulfilment_source] CHECK ([fulfilment_source] IS NULL OR [fulfilment_source] IN (N'Stock', N'Inter-warehouse transfer', N'Purchase', N'OEM order'));
IF OBJECT_ID(N'[svc].[CK_svc_planned_service_source]', N'C') IS NULL
    ALTER TABLE [svc].[planned_service] ADD CONSTRAINT [CK_svc_planned_service_source] CHECK ([schedule_template_id] IS NOT NULL OR [service_contract_id] IS NOT NULL);
IF OBJECT_ID(N'[svc].[CK_svc_service_contract_billing_frequency]', N'C') IS NULL
    ALTER TABLE [svc].[service_contract] ADD CONSTRAINT [CK_svc_service_contract_billing_frequency] CHECK ([billing_frequency] IS NULL OR [billing_frequency] IN (N'One time', N'Monthly', N'Quarterly', N'Half yearly', N'Yearly'));
IF OBJECT_ID(N'[svc].[CK_svc_warranty_claim_claim_source]', N'C') IS NULL
    ALTER TABLE [svc].[warranty_claim] ADD CONSTRAINT [CK_svc_warranty_claim_claim_source] CHECK ([claim_source] IN (N'Manual', N'Excel import', N'OEM portal'));
IF OBJECT_ID(N'[inv].[CK_inv_stock_issue_dispatch_mode]', N'C') IS NULL
    ALTER TABLE [inv].[stock_issue] ADD CONSTRAINT [CK_inv_stock_issue_dispatch_mode] CHECK ([dispatch_mode] IS NULL OR [dispatch_mode] IN (N'Engineer carry', N'Hand delivery', N'Courier', N'Transport'));
IF OBJECT_ID(N'[pur].[CK_pur_purchase_order_po_type]', N'C') IS NULL
    ALTER TABLE [pur].[purchase_order] ADD CONSTRAINT [CK_pur_purchase_order_po_type] CHECK ([po_type] IN (N'OEM', N'Local', N'Import'));
IF OBJECT_ID(N'[pur].[CK_pur_grn_grn_type]', N'C') IS NULL
    ALTER TABLE [pur].[grn] ADD CONSTRAINT [CK_pur_grn_grn_type] CHECK ([grn_type] IN (N'Regular', N'Transit'));
IF OBJECT_ID(N'[sal].[CK_sal_sales_order_credit_check_status]', N'C') IS NULL
    ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [CK_sal_sales_order_credit_check_status] CHECK ([credit_check_status] IN (N'Not checked', N'Within limit', N'On hold', N'Approved override'));
GO

/* ---------- 2.5 FKs and FK indexes for the new columns ---------- */
IF OBJECT_ID(N'[core].[FK_core_attachment_verified_by_user_id]', N'F') IS NULL
    ALTER TABLE [core].[attachment] ADD CONSTRAINT [FK_core_attachment_verified_by_user_id] FOREIGN KEY ([verified_by_user_id]) REFERENCES [core].[app_user] ([id]);
IF OBJECT_ID(N'[svc].[FK_svc_service_call_warranty_checked_by_user_id]', N'F') IS NULL
    ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_warranty_checked_by_user_id] FOREIGN KEY ([warranty_checked_by_user_id]) REFERENCES [core].[app_user] ([id]);
IF OBJECT_ID(N'[svc].[FK_svc_service_part_request_reviewed_by_user_id]', N'F') IS NULL
    ALTER TABLE [svc].[service_part_request] ADD CONSTRAINT [FK_svc_service_part_request_reviewed_by_user_id] FOREIGN KEY ([reviewed_by_user_id]) REFERENCES [core].[app_user] ([id]);
IF OBJECT_ID(N'[svc].[FK_svc_service_part_request_quotation_id]', N'F') IS NULL
    ALTER TABLE [svc].[service_part_request] ADD CONSTRAINT [FK_svc_service_part_request_quotation_id] FOREIGN KEY ([quotation_id]) REFERENCES [sal].[quotation] ([id]);
IF OBJECT_ID(N'[svc].[FK_svc_service_part_request_purchase_request_id]', N'F') IS NULL
    ALTER TABLE [svc].[service_part_request] ADD CONSTRAINT [FK_svc_service_part_request_purchase_request_id] FOREIGN KEY ([purchase_request_id]) REFERENCES [pur].[purchase_request] ([id]);
IF OBJECT_ID(N'[svc].[FK_svc_planned_service_service_contract_id]', N'F') IS NULL
    ALTER TABLE [svc].[planned_service] ADD CONSTRAINT [FK_svc_planned_service_service_contract_id] FOREIGN KEY ([service_contract_id]) REFERENCES [svc].[service_contract] ([id]);
IF OBJECT_ID(N'[svc].[FK_svc_service_contract_contract_plan_id]', N'F') IS NULL
    ALTER TABLE [svc].[service_contract] ADD CONSTRAINT [FK_svc_service_contract_contract_plan_id] FOREIGN KEY ([contract_plan_id]) REFERENCES [svc].[contract_plan] ([id]);
IF OBJECT_ID(N'[svc].[FK_svc_service_contract_renewed_from_contract_id]', N'F') IS NULL
    ALTER TABLE [svc].[service_contract] ADD CONSTRAINT [FK_svc_service_contract_renewed_from_contract_id] FOREIGN KEY ([renewed_from_contract_id]) REFERENCES [svc].[service_contract] ([id]);
IF OBJECT_ID(N'[svc].[FK_svc_service_contract_enrolled_by_employee_id]', N'F') IS NULL
    ALTER TABLE [svc].[service_contract] ADD CONSTRAINT [FK_svc_service_contract_enrolled_by_employee_id] FOREIGN KEY ([enrolled_by_employee_id]) REFERENCES [core].[employee] ([id]);
IF OBJECT_ID(N'[svc].[FK_svc_trip_vehicle_id]', N'F') IS NULL
    ALTER TABLE [svc].[trip] ADD CONSTRAINT [FK_svc_trip_vehicle_id] FOREIGN KEY ([vehicle_id]) REFERENCES [hr].[vehicle] ([id]);
IF OBJECT_ID(N'[svc].[FK_svc_warranty_claim_file_import_id]', N'F') IS NULL
    ALTER TABLE [svc].[warranty_claim] ADD CONSTRAINT [FK_svc_warranty_claim_file_import_id] FOREIGN KEY ([file_import_id]) REFERENCES [int].[file_import] ([id]);
IF OBJECT_ID(N'[inv].[FK_inv_stock_issue_delivered_to_site_id]', N'F') IS NULL
    ALTER TABLE [inv].[stock_issue] ADD CONSTRAINT [FK_inv_stock_issue_delivered_to_site_id] FOREIGN KEY ([delivered_to_site_id]) REFERENCES [core].[customer_site] ([id]);
IF OBJECT_ID(N'[inv].[FK_inv_stock_transfer_line_hsn_sac_id]', N'F') IS NULL
    ALTER TABLE [inv].[stock_transfer_line] ADD CONSTRAINT [FK_inv_stock_transfer_line_hsn_sac_id] FOREIGN KEY ([hsn_sac_id]) REFERENCES [core].[hsn_sac] ([id]);
IF OBJECT_ID(N'[pur].[FK_pur_purchase_request_sales_order_id]', N'F') IS NULL
    ALTER TABLE [pur].[purchase_request] ADD CONSTRAINT [FK_pur_purchase_request_sales_order_id] FOREIGN KEY ([sales_order_id]) REFERENCES [sal].[sales_order] ([id]);
IF OBJECT_ID(N'[pur].[FK_pur_supplier_allocation_opening_balance_id]', N'F') IS NULL
    ALTER TABLE [pur].[supplier_allocation] ADD CONSTRAINT [FK_pur_supplier_allocation_opening_balance_id] FOREIGN KEY ([opening_balance_id]) REFERENCES [acc].[opening_balance] ([id]);
IF OBJECT_ID(N'[sal].[FK_sal_sales_order_service_call_id]', N'F') IS NULL
    ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]);
IF OBJECT_ID(N'[sal].[FK_sal_sales_order_credit_approved_by_user_id]', N'F') IS NULL
    ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_credit_approved_by_user_id] FOREIGN KEY ([credit_approved_by_user_id]) REFERENCES [core].[app_user] ([id]);
IF OBJECT_ID(N'[sal].[FK_sal_sales_order_payment_confirmed_by_user_id]', N'F') IS NULL
    ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_payment_confirmed_by_user_id] FOREIGN KEY ([payment_confirmed_by_user_id]) REFERENCES [core].[app_user] ([id]);
IF OBJECT_ID(N'[sal].[FK_sal_delivery_note_service_call_id]', N'F') IS NULL
    ALTER TABLE [sal].[delivery_note] ADD CONSTRAINT [FK_sal_delivery_note_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]);
IF OBJECT_ID(N'[sal].[FK_sal_delivery_note_pod_attachment_id]', N'F') IS NULL
    ALTER TABLE [sal].[delivery_note] ADD CONSTRAINT [FK_sal_delivery_note_pod_attachment_id] FOREIGN KEY ([pod_attachment_id]) REFERENCES [core].[attachment] ([id]);
IF OBJECT_ID(N'[sal].[FK_sal_receipt_confirmed_by_user_id]', N'F') IS NULL
    ALTER TABLE [sal].[receipt] ADD CONSTRAINT [FK_sal_receipt_confirmed_by_user_id] FOREIGN KEY ([confirmed_by_user_id]) REFERENCES [core].[app_user] ([id]);
IF OBJECT_ID(N'[sal].[FK_sal_receipt_collected_by_employee_id]', N'F') IS NULL
    ALTER TABLE [sal].[receipt] ADD CONSTRAINT [FK_sal_receipt_collected_by_employee_id] FOREIGN KEY ([collected_by_employee_id]) REFERENCES [core].[employee] ([id]);
IF OBJECT_ID(N'[sal].[FK_sal_customer_allocation_opening_balance_id]', N'F') IS NULL
    ALTER TABLE [sal].[customer_allocation] ADD CONSTRAINT [FK_sal_customer_allocation_opening_balance_id] FOREIGN KEY ([opening_balance_id]) REFERENCES [acc].[opening_balance] ([id]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_core_attachment_verified_by_user_id') CREATE NONCLUSTERED INDEX [IX_core_attachment_verified_by_user_id] ON [core].[attachment] ([verified_by_user_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_core_attachment_entity') CREATE NONCLUSTERED INDEX [IX_core_attachment_entity] ON [core].[attachment] ([entity_type], [entity_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_service_call_warranty_checked_by_user_id') CREATE NONCLUSTERED INDEX [IX_svc_service_call_warranty_checked_by_user_id] ON [svc].[service_call] ([warranty_checked_by_user_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_service_part_request_reviewed_by_user_id') CREATE NONCLUSTERED INDEX [IX_svc_service_part_request_reviewed_by_user_id] ON [svc].[service_part_request] ([reviewed_by_user_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_service_part_request_quotation_id') CREATE NONCLUSTERED INDEX [IX_svc_service_part_request_quotation_id] ON [svc].[service_part_request] ([quotation_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_service_part_request_purchase_request_id') CREATE NONCLUSTERED INDEX [IX_svc_service_part_request_purchase_request_id] ON [svc].[service_part_request] ([purchase_request_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_planned_service_service_contract_id') CREATE NONCLUSTERED INDEX [IX_svc_planned_service_service_contract_id] ON [svc].[planned_service] ([service_contract_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_service_contract_contract_plan_id') CREATE NONCLUSTERED INDEX [IX_svc_service_contract_contract_plan_id] ON [svc].[service_contract] ([contract_plan_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_service_contract_renewed_from_contract_id') CREATE NONCLUSTERED INDEX [IX_svc_service_contract_renewed_from_contract_id] ON [svc].[service_contract] ([renewed_from_contract_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_service_contract_enrolled_by_employee_id') CREATE NONCLUSTERED INDEX [IX_svc_service_contract_enrolled_by_employee_id] ON [svc].[service_contract] ([enrolled_by_employee_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_trip_vehicle_id') CREATE NONCLUSTERED INDEX [IX_svc_trip_vehicle_id] ON [svc].[trip] ([vehicle_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_warranty_claim_file_import_id') CREATE NONCLUSTERED INDEX [IX_svc_warranty_claim_file_import_id] ON [svc].[warranty_claim] ([file_import_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_inv_stock_issue_delivered_to_site_id') CREATE NONCLUSTERED INDEX [IX_inv_stock_issue_delivered_to_site_id] ON [inv].[stock_issue] ([delivered_to_site_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_inv_stock_transfer_line_hsn_sac_id') CREATE NONCLUSTERED INDEX [IX_inv_stock_transfer_line_hsn_sac_id] ON [inv].[stock_transfer_line] ([hsn_sac_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_pur_purchase_request_sales_order_id') CREATE NONCLUSTERED INDEX [IX_pur_purchase_request_sales_order_id] ON [pur].[purchase_request] ([sales_order_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_pur_supplier_allocation_opening_balance_id') CREATE NONCLUSTERED INDEX [IX_pur_supplier_allocation_opening_balance_id] ON [pur].[supplier_allocation] ([opening_balance_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sal_sales_order_service_call_id') CREATE NONCLUSTERED INDEX [IX_sal_sales_order_service_call_id] ON [sal].[sales_order] ([service_call_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sal_sales_order_credit_approved_by_user_id') CREATE NONCLUSTERED INDEX [IX_sal_sales_order_credit_approved_by_user_id] ON [sal].[sales_order] ([credit_approved_by_user_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sal_sales_order_payment_confirmed_by_user_id') CREATE NONCLUSTERED INDEX [IX_sal_sales_order_payment_confirmed_by_user_id] ON [sal].[sales_order] ([payment_confirmed_by_user_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sal_delivery_note_service_call_id') CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_service_call_id] ON [sal].[delivery_note] ([service_call_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sal_delivery_note_pod_attachment_id') CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_pod_attachment_id] ON [sal].[delivery_note] ([pod_attachment_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sal_receipt_confirmed_by_user_id') CREATE NONCLUSTERED INDEX [IX_sal_receipt_confirmed_by_user_id] ON [sal].[receipt] ([confirmed_by_user_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sal_receipt_collected_by_employee_id') CREATE NONCLUSTERED INDEX [IX_sal_receipt_collected_by_employee_id] ON [sal].[receipt] ([collected_by_employee_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sal_customer_allocation_opening_balance_id') CREATE NONCLUSTERED INDEX [IX_sal_customer_allocation_opening_balance_id] ON [sal].[customer_allocation] ([opening_balance_id]);
GO

/* =====================================================================
   PART 3 - INTEGRITY CONSTRAINTS MISSING IN v2
   ===================================================================== */
-- A contact belongs to exactly one customer or one supplier.
IF OBJECT_ID(N'[core].[CK_core_contact_owner]', N'C') IS NULL
    ALTER TABLE [core].[contact] ADD CONSTRAINT [CK_core_contact_owner] CHECK (([customer_id] IS NOT NULL AND [supplier_id] IS NULL) OR ([customer_id] IS NULL AND [supplier_id] IS NOT NULL));
-- Only one current PRIMARY engineer per call.
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_svc_call_assignment_current_primary')
    CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_call_assignment_current_primary] ON [svc].[call_assignment] ([service_call_id]) WHERE [is_current] = 1 AND [assignment_type] = N'Primary';
-- Double entry: each ledger line is either a debit or a credit, never negative.
IF OBJECT_ID(N'[acc].[CK_acc_gl_entry_amounts]', N'C') IS NULL
    ALTER TABLE [acc].[gl_entry] ADD CONSTRAINT [CK_acc_gl_entry_amounts] CHECK ([debit] >= 0 AND [credit] >= 0 AND ([debit] = 0 OR [credit] = 0) AND ([debit] + [credit]) > 0);
IF OBJECT_ID(N'[acc].[CK_acc_journal_balanced]', N'C') IS NULL
    ALTER TABLE [acc].[journal] ADD CONSTRAINT [CK_acc_journal_balanced] CHECK ([total_debit] = [total_credit]);
IF OBJECT_ID(N'[acc].[CK_acc_opening_balance_amounts]', N'C') IS NULL
    ALTER TABLE [acc].[opening_balance] ADD CONSTRAINT [CK_acc_opening_balance_amounts] CHECK ([debit] >= 0 AND [credit] >= 0 AND ([debit] = 0 OR [credit] = 0));
-- Negative-stock guard (see clarification Q12 before go-live).
IF OBJECT_ID(N'[inv].[CK_inv_stock_balance_non_negative]', N'C') IS NULL
    ALTER TABLE [inv].[stock_balance] ADD CONSTRAINT [CK_inv_stock_balance_non_negative] CHECK ([qty_on_hand] >= 0 AND [qty_reserved] >= 0 AND [qty_in_transit] >= 0);
-- Negative-billing guard on invoice lines.
IF OBJECT_ID(N'[sal].[CK_sal_sales_invoice_line_amounts]', N'C') IS NULL
    ALTER TABLE [sal].[sales_invoice_line] ADD CONSTRAINT [CK_sal_sales_invoice_line_amounts] CHECK ([quantity] > 0 AND [unit_price] >= 0 AND [discount_amount] >= 0 AND [taxable_value] >= 0 AND [line_total] >= 0);
IF OBJECT_ID(N'[sal].[CK_sal_sales_invoice_amounts]', N'C') IS NULL
    ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [CK_sal_sales_invoice_amounts] CHECK ([taxable_value] >= 0 AND [total] >= 0 AND [amount_received] >= 0);
-- An allocation settles exactly one bill (invoice or opening bill) from a receipt / payment or a note.
IF OBJECT_ID(N'[sal].[CK_sal_customer_allocation_target]', N'C') IS NULL
    ALTER TABLE [sal].[customer_allocation] ADD CONSTRAINT [CK_sal_customer_allocation_target] CHECK (
        (([sales_invoice_id] IS NOT NULL AND [opening_balance_id] IS NULL) OR ([sales_invoice_id] IS NULL AND [opening_balance_id] IS NOT NULL))
        AND ([receipt_id] IS NOT NULL OR [credit_note_id] IS NOT NULL) AND [amount] > 0);
IF OBJECT_ID(N'[pur].[CK_pur_supplier_allocation_target]', N'C') IS NULL
    ALTER TABLE [pur].[supplier_allocation] ADD CONSTRAINT [CK_pur_supplier_allocation_target] CHECK (
        (([supplier_invoice_id] IS NOT NULL AND [opening_balance_id] IS NULL) OR ([supplier_invoice_id] IS NULL AND [opening_balance_id] IS NOT NULL))
        AND ([supplier_payment_id] IS NOT NULL OR [debit_note_id] IS NOT NULL) AND [amount] > 0);
-- Attendance regularisation must request a valid attendance status.
IF OBJECT_ID(N'[hr].[CK_hr_attendance_regularization_requested_status]', N'C') IS NULL
    ALTER TABLE [hr].[attendance_regularization] ADD CONSTRAINT [CK_hr_attendance_regularization_requested_status] CHECK ([requested_status] IN (N'Present', N'Absent', N'Half day', N'Leave', N'Holiday', N'Week off', N'On duty'));
-- Contract and date sanity.
IF OBJECT_ID(N'[svc].[CK_svc_service_contract_dates]', N'C') IS NULL
    ALTER TABLE [svc].[service_contract] ADD CONSTRAINT [CK_svc_service_contract_dates] CHECK ([end_date] >= [start_date]);
IF OBJECT_ID(N'[acc].[CK_acc_fiscal_year_dates]', N'C') IS NULL
    ALTER TABLE [acc].[fiscal_year] ADD CONSTRAINT [CK_acc_fiscal_year_dates] CHECK ([end_date] > [start_date]);
IF OBJECT_ID(N'[svc].[CK_svc_service_call_customer_rating]', N'C') IS NULL
    ALTER TABLE [svc].[service_call] ADD CONSTRAINT [CK_svc_service_call_customer_rating] CHECK ([customer_rating] IS NULL OR [customer_rating] BETWEEN 1 AND 5);
GO

/* =====================================================================
   PART 4 - EXTRA INDEXES (ageing, schedules, OEM ID lookups)
   ===================================================================== */
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sal_sales_invoice_customer_open')
    CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_customer_open] ON [sal].[sales_invoice] ([customer_id], [status]) INCLUDE ([invoice_date], [due_date], [total], [branch_id], [principal_id]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_pur_supplier_invoice_supplier_open')
    CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_supplier_open] ON [pur].[supplier_invoice] ([supplier_id], [status]) INCLUDE ([supplier_invoice_date], [due_date], [total]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_planned_service_due')
    CREATE NONCLUSTERED INDEX [IX_svc_planned_service_due] ON [svc].[planned_service] ([status], [due_date]) INCLUDE ([machine_unit_id], [due_hmr]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_service_call_oem_call_id')
    CREATE NONCLUSTERED INDEX [IX_svc_service_call_oem_call_id] ON [svc].[service_call] ([oem_call_id]) WHERE [oem_call_id] IS NOT NULL;
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_svc_service_call_sla_open')
    CREATE NONCLUSTERED INDEX [IX_svc_service_call_sla_open] ON [svc].[service_call] ([sla_due_at]) INCLUDE ([current_status], [assigned_engineer_id]) WHERE [closed_at] IS NULL;
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_inv_cost_layer_open')
    CREATE NONCLUSTERED INDEX [IX_inv_cost_layer_open] ON [inv].[cost_layer] ([item_id], [location_id], [received_at]) INCLUDE ([qty_remaining], [unit_cost]) WHERE [qty_remaining] > 0;
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_core_machine_unit_warranty_end')
    CREATE NONCLUSTERED INDEX [IX_core_machine_unit_warranty_end] ON [core].[machine_unit] ([warranty_end_date]) INCLUDE ([customer_id], [principal_id]);
GO
