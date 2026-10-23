/* =====================================================================
   TRISHUL Integrated System - SQL Server DDL (dictionary v2)
   Phase 1 - Call & Service
   Generated from the TRISHUL Database Dictionary. Do not edit by hand:
   change the dictionary and regenerate.
   Target: SQL Server 2019+ / Amazon RDS for SQL Server
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
/* ---------- 1. Tables (26) ---------- */

/* ===== svc: Call & Service ===== */
-- ASC / AMC / extended warranty / free-service contracts.
CREATE TABLE [svc].[service_contract] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_service_contract] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [contract_no] NVARCHAR(30) NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [customer_id] BIGINT NOT NULL,
    [contract_type] NVARCHAR(30) NOT NULL,
    [start_date] DATE NOT NULL,
    [end_date] DATE NOT NULL,
    [hours_limit] INT NULL,
    [visits_included] SMALLINT NULL,
    [visits_used] SMALLINT NOT NULL CONSTRAINT [DF_svc_service_contract_visits_used] DEFAULT (0),
    [contract_value] DECIMAL(18,2) NULL,
    [sales_invoice_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [terms] NVARCHAR(2000) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_service_contract_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_service_contract_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_service_contract_contract_type] CHECK ([contract_type] IN (N'ASC', N'AMC', N'Extended warranty', N'Free service')),
    CONSTRAINT [CK_svc_service_contract_status] CHECK ([status] IN (N'Draft', N'Active', N'Expired', N'Cancelled'))
);
GO
-- Machines covered by a contract and what is covered.
CREATE TABLE [svc].[contract_coverage] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_contract_coverage] PRIMARY KEY,
    [service_contract_id] BIGINT NOT NULL,
    [machine_unit_id] BIGINT NOT NULL,
    [covers_labour] BIT NOT NULL CONSTRAINT [DF_svc_contract_coverage_covers_labour] DEFAULT (1),
    [covers_parts] BIT NOT NULL CONSTRAINT [DF_svc_contract_coverage_covers_parts] DEFAULT (0),
    [covers_travel] BIT NOT NULL CONSTRAINT [DF_svc_contract_coverage_covers_travel] DEFAULT (1),
    [parts_discount_pct] DECIMAL(5,2) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_contract_coverage_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_contract_coverage_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Inspection checklist by model and call type.
CREATE TABLE [svc].[checklist_template] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_checklist_template] PRIMARY KEY,
    [name] NVARCHAR(120) NOT NULL,
    [principal_id] BIGINT NULL,
    [machine_model_id] BIGINT NULL,
    [call_type_lookup_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_checklist_template_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_checklist_template_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Questions in a checklist.
CREATE TABLE [svc].[checklist_template_item] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_checklist_template_item] PRIMARY KEY,
    [checklist_template_id] BIGINT NOT NULL,
    [sequence] SMALLINT NOT NULL,
    [item_text] NVARCHAR(300) NOT NULL,
    [response_type] NVARCHAR(30) NOT NULL,
    [is_mandatory] BIT NOT NULL CONSTRAINT [DF_svc_checklist_template_item_is_mandatory] DEFAULT (1),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_checklist_template_item_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_checklist_template_item_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_checklist_template_item_response_type] CHECK ([response_type] IN (N'OK Not OK', N'Number', N'Text', N'Photo'))
);
GO
-- Periodic service plan per model, e.g. 50 / 250 / 500 hours.
CREATE TABLE [svc].[service_schedule_template] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_service_schedule_template] PRIMARY KEY,
    [machine_model_id] BIGINT NOT NULL,
    [service_name] NVARCHAR(80) NOT NULL,
    [due_at_hmr] INT NULL,
    [due_after_days] SMALLINT NULL,
    [tolerance_hmr] SMALLINT NULL,
    [is_free] BIT NOT NULL CONSTRAINT [DF_svc_service_schedule_template_is_free] DEFAULT (0),
    [checklist_template_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_service_schedule_template_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_service_schedule_template_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Scheduled service due for a specific machine.
CREATE TABLE [svc].[planned_service] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_planned_service] PRIMARY KEY,
    [machine_unit_id] BIGINT NOT NULL,
    [schedule_template_id] BIGINT NOT NULL,
    [due_hmr] INT NULL,
    [due_date] DATE NULL,
    [status] NVARCHAR(30) NOT NULL,
    [service_call_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_planned_service_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_planned_service_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_planned_service_status] CHECK ([status] IN (N'Upcoming', N'Due', N'Overdue', N'Call raised', N'Done', N'Skipped'))
);
GO
-- Service call (complaint / request). Replaces the register copy and Excel sheet.
CREATE TABLE [svc].[service_call] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_service_call] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [call_no] NVARCHAR(30) NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [client_uuid] UNIQUEIDENTIFIER NULL,
    [call_source_lookup_id] BIGINT NOT NULL,
    [call_type_lookup_id] BIGINT NOT NULL,
    [complaint_category_lookup_id] BIGINT NULL,
    [complaint_description] NVARCHAR(2000) NOT NULL,
    [customer_id] BIGINT NOT NULL,
    [customer_site_id] BIGINT NULL,
    [contact_id] BIGINT NULL,
    [caller_name] NVARCHAR(100) NULL,
    [caller_phone] NVARCHAR(15) NOT NULL,
    [machine_unit_id] BIGINT NULL,
    [reported_hmr] DECIMAL(10,1) NULL,
    [is_machine_down] BIT NOT NULL CONSTRAINT [DF_svc_service_call_is_machine_down] DEFAULT (0),
    [coverage_type] NVARCHAR(30) NULL,
    [service_contract_id] BIGINT NULL,
    [planned_service_id] BIGINT NULL,
    [priority] NVARCHAR(30) NOT NULL CONSTRAINT [DF_svc_service_call_priority] DEFAULT (N'Normal'),
    [is_asc_priority] BIT NOT NULL CONSTRAINT [DF_svc_service_call_is_asc_priority] DEFAULT (0),
    [received_at] DATETIME2(0) NOT NULL,
    [received_by_user_id] BIGINT NULL,
    [source_reference] NVARCHAR(150) NULL,
    [current_status] NVARCHAR(30) NOT NULL,
    [team_id] BIGINT NULL,
    [assigned_engineer_id] BIGINT NULL,
    [oem_call_id] NVARCHAR(40) NULL,
    [sla_due_at] DATETIME2(0) NULL,
    [first_response_at] DATETIME2(0) NULL,
    [closed_at] DATETIME2(0) NULL,
    [closed_by_user_id] BIGINT NULL,
    [closure_type] NVARCHAR(30) NULL,
    [duplicate_of_call_id] BIGINT NULL,
    [customer_rating] TINYINT NULL,
    [customer_feedback] NVARCHAR(500) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_service_call_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_service_call_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_service_call_coverage_type] CHECK ([coverage_type] IN (N'Warranty', N'Contract', N'Chargeable', N'Goodwill')),
    CONSTRAINT [CK_svc_service_call_priority] CHECK ([priority] IN (N'Critical', N'High', N'Normal', N'Low')),
    CONSTRAINT [CK_svc_service_call_current_status] CHECK ([current_status] IN (N'Logged', N'Assigned', N'Call ID linked', N'Customer contacted', N'Trip started', N'Reached site', N'In progress', N'Report submitted', N'Closed', N'Cancelled')),
    CONSTRAINT [CK_svc_service_call_closure_type] CHECK ([closure_type] IN (N'Resolved', N'Cancelled', N'Duplicate', N'Not reachable'))
);
GO
-- Every status change on a call (drives the 24-hour rule and reports).
CREATE TABLE [svc].[call_status_log] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_call_status_log] PRIMARY KEY,
    [service_call_id] BIGINT NOT NULL,
    [from_status] NVARCHAR(30) NULL,
    [to_status] NVARCHAR(30) NOT NULL,
    [changed_at] DATETIME2(0) NOT NULL,
    [changed_by_user_id] BIGINT NULL,
    [reason_lookup_id] BIGINT NULL,
    [remarks] NVARCHAR(500) NULL,
    [latitude] DECIMAL(9,6) NULL,
    [longitude] DECIMAL(9,6) NULL,
    [client_uuid] UNIQUEIDENTIFIER NULL
);
GO
-- Engineer assignments and reassignments by the Team Lead.
CREATE TABLE [svc].[call_assignment] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_call_assignment] PRIMARY KEY,
    [service_call_id] BIGINT NOT NULL,
    [engineer_employee_id] BIGINT NOT NULL,
    [assignment_type] NVARCHAR(30) NOT NULL CONSTRAINT [DF_svc_call_assignment_assignment_type] DEFAULT (N'Primary'),
    [assigned_by_user_id] BIGINT NOT NULL,
    [assigned_at] DATETIME2(0) NOT NULL,
    [reason_lookup_id] BIGINT NULL,
    [distance_km_at_assignment] DECIMAL(8,2) NULL,
    [unassigned_at] DATETIME2(0) NULL,
    [is_current] BIT NOT NULL CONSTRAINT [DF_svc_call_assignment_is_current] DEFAULT (1),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_call_assignment_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_call_assignment_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_call_assignment_assignment_type] CHECK ([assignment_type] IN (N'Primary', N'Support'))
);
GO
-- Link to the call in the brand's OEM portal (E-DOST / SAP ByD for Tata Hitachi; other portals for other brands).
CREATE TABLE [svc].[oem_call_reference] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_oem_call_reference] PRIMARY KEY,
    [service_call_id] BIGINT NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [external_system_id] BIGINT NULL,
    [oem_call_id] NVARCHAR(40) NOT NULL,
    [oem_ticket_uuid] NVARCHAR(40) NULL,
    [created_in_oem_by] NVARCHAR(30) NOT NULL,
    [entered_by_user_id] BIGINT NULL,
    [entered_at] DATETIME2(0) NULL,
    [verified_by_user_id] BIGINT NULL,
    [verified_at] DATETIME2(0) NULL,
    [sync_status] NVARCHAR(30) NOT NULL CONSTRAINT [DF_svc_oem_call_reference_sync_status] DEFAULT (N'Manual'),
    [last_sync_log_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_oem_call_reference_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_oem_call_reference_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_oem_call_reference_created_in_oem_by] CHECK ([created_in_oem_by] IN (N'Back office', N'Engineer', N'API')),
    CONSTRAINT [CK_svc_oem_call_reference_sync_status] CHECK ([sync_status] IN (N'Manual', N'Pending', N'Synced', N'Failed'))
);
GO
-- Each visit to site for a call (inspection, repair, parts fitment...).
CREATE TABLE [svc].[service_visit] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_service_visit] PRIMARY KEY,
    [service_call_id] BIGINT NOT NULL,
    [visit_no] TINYINT NOT NULL,
    [client_uuid] UNIQUEIDENTIFIER NULL,
    [visit_purpose] NVARCHAR(30) NOT NULL,
    [engineer_employee_id] BIGINT NOT NULL,
    [planned_date] DATE NULL,
    [customer_contacted_at] DATETIME2(0) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [service_started_at] DATETIME2(0) NULL,
    [service_ended_at] DATETIME2(0) NULL,
    [site_latitude] DECIMAL(9,6) NULL,
    [site_longitude] DECIMAL(9,6) NULL,
    [next_action] NVARCHAR(30) NULL,
    [remarks] NVARCHAR(1000) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_service_visit_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_service_visit_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_service_visit_visit_purpose] CHECK ([visit_purpose] IN (N'Inspection', N'Repair', N'Parts fitment', N'Periodic service', N'Follow up', N'Installation')),
    CONSTRAINT [CK_svc_service_visit_status] CHECK ([status] IN (N'Planned', N'On the way', N'On site', N'Completed', N'Cancelled')),
    CONSTRAINT [CK_svc_service_visit_next_action] CHECK ([next_action] IN (N'None', N'Parts required', N'Revisit', N'Escalate'))
);
GO
-- Engineer's trip for a visit: start, end, route, km, time.
CREATE TABLE [svc].[trip] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_trip] PRIMARY KEY,
    [service_visit_id] BIGINT NOT NULL,
    [engineer_employee_id] BIGINT NOT NULL,
    [client_uuid] UNIQUEIDENTIFIER NULL,
    [trip_type] NVARCHAR(30) NOT NULL,
    [start_at] DATETIME2(0) NOT NULL,
    [start_latitude] DECIMAL(9,6) NOT NULL,
    [start_longitude] DECIMAL(9,6) NOT NULL,
    [end_at] DATETIME2(0) NULL,
    [end_latitude] DECIMAL(9,6) NULL,
    [end_longitude] DECIMAL(9,6) NULL,
    [gps_distance_km] DECIMAL(8,2) NULL,
    [map_distance_km] DECIMAL(8,2) NULL,
    [duration_minutes] INT NULL,
    [vehicle_type] NVARCHAR(30) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [route_polyline] NVARCHAR(MAX) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_trip_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_trip_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_trip_trip_type] CHECK ([trip_type] IN (N'To site', N'Return', N'Site to site')),
    CONSTRAINT [CK_svc_trip_vehicle_type] CHECK ([vehicle_type] IN (N'Own bike', N'Own car', N'Company vehicle', N'Public transport')),
    CONSTRAINT [CK_svc_trip_status] CHECK ([status] IN (N'In progress', N'Completed', N'Auto closed'))
);
GO
-- GPS points during a trip. Very high volume: partition by month.
CREATE TABLE [svc].[trip_gps_point] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_trip_gps_point] PRIMARY KEY,
    [trip_id] BIGINT NOT NULL,
    [recorded_at] DATETIME2(0) NOT NULL,
    [latitude] DECIMAL(9,6) NOT NULL,
    [longitude] DECIMAL(9,6) NOT NULL,
    [accuracy_m] DECIMAL(6,1) NULL,
    [speed_kmph] DECIMAL(5,1) NULL,
    [battery_pct] TINYINT NULL,
    [is_mock_location] BIT NOT NULL CONSTRAINT [DF_svc_trip_gps_point_is_mock_location] DEFAULT (0)
);
GO
-- Daily duty on / off for engineers (GPS runs only on duty).
CREATE TABLE [svc].[engineer_duty_log] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_engineer_duty_log] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [duty_date] DATE NOT NULL,
    [client_uuid] UNIQUEIDENTIFIER NULL,
    [duty_on_at] DATETIME2(0) NULL,
    [duty_on_latitude] DECIMAL(9,6) NULL,
    [duty_on_longitude] DECIMAL(9,6) NULL,
    [duty_off_at] DATETIME2(0) NULL,
    [duty_off_latitude] DECIMAL(9,6) NULL,
    [duty_off_longitude] DECIMAL(9,6) NULL,
    [total_km] DECIMAL(8,2) NULL,
    [calls_attended] SMALLINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_engineer_duty_log_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_engineer_duty_log_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Service report submitted at the end of a visit.
CREATE TABLE [svc].[service_report] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_service_report] PRIMARY KEY,
    [service_visit_id] BIGINT NOT NULL,
    [report_no] NVARCHAR(30) NOT NULL,
    [client_uuid] UNIQUEIDENTIFIER NULL,
    [hmr_reading] DECIMAL(10,1) NULL,
    [machine_condition_lookup_id] BIGINT NULL,
    [complaint_observed] NVARCHAR(1000) NULL,
    [findings] NVARCHAR(2000) NULL,
    [failure_code_lookup_id] BIGINT NULL,
    [action_taken] NVARCHAR(2000) NULL,
    [is_parts_required] BIT NOT NULL CONSTRAINT [DF_svc_service_report_is_parts_required] DEFAULT (0),
    [labour_hours] DECIMAL(6,2) NULL,
    [recommendations] NVARCHAR(1000) NULL,
    [customer_signed_name] NVARCHAR(100) NULL,
    [customer_signed_mobile] NVARCHAR(15) NULL,
    [customer_signature_attachment_id] BIGINT NULL,
    [is_closure_otp_verified] BIT NOT NULL CONSTRAINT [DF_svc_service_report_is_closure_otp_verified] DEFAULT (0),
    [engineer_signature_attachment_id] BIGINT NULL,
    [pdf_attachment_id] BIGINT NULL,
    [submitted_at] DATETIME2(0) NULL,
    [is_offline_submitted] BIT NOT NULL CONSTRAINT [DF_svc_service_report_is_offline_submitted] DEFAULT (0),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_service_report_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_service_report_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Checklist answers in a service report.
CREATE TABLE [svc].[report_checklist_item] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_report_checklist_item] PRIMARY KEY,
    [service_report_id] BIGINT NOT NULL,
    [checklist_template_item_id] BIGINT NULL,
    [item_text] NVARCHAR(300) NOT NULL,
    [response_value] NVARCHAR(200) NULL,
    [is_ok] BIT NULL,
    [remarks] NVARCHAR(300) NULL,
    [photo_attachment_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_report_checklist_item_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_report_checklist_item_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Parts needed for a call. Captured in Phase 1; issued from stock in Phase 2.
CREATE TABLE [svc].[service_part_request] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_service_part_request] PRIMARY KEY,
    [service_call_id] BIGINT NOT NULL,
    [service_visit_id] BIGINT NULL,
    [item_id] BIGINT NULL,
    [part_description] NVARCHAR(200) NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [uom_id] BIGINT NULL,
    [is_chargeable] BIT NOT NULL CONSTRAINT [DF_svc_service_part_request_is_chargeable] DEFAULT (1),
    [status] NVARCHAR(30) NOT NULL,
    [requested_by_employee_id] BIGINT NULL,
    [required_by_date] DATE NULL,
    [stock_reservation_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_service_part_request_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_service_part_request_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_service_part_request_status] CHECK ([status] IN (N'Requested', N'Approved', N'Reserved', N'Issued', N'Fitted', N'Returned', N'Cancelled'))
);
GO
-- Chargeable items on a call, billed in Phase 4.
CREATE TABLE [svc].[service_charge] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_service_charge] PRIMARY KEY,
    [service_call_id] BIGINT NOT NULL,
    [charge_type] NVARCHAR(30) NOT NULL,
    [description] NVARCHAR(200) NOT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [rate] DECIMAL(18,4) NOT NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [is_billable] BIT NOT NULL CONSTRAINT [DF_svc_service_charge_is_billable] DEFAULT (1),
    [sales_invoice_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_service_charge_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_service_charge_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_service_charge_charge_type] CHECK ([charge_type] IN (N'Labour', N'Travel', N'Parts', N'Other'))
);
GO
-- Response and closure targets per brand (default 24 hours).
CREATE TABLE [svc].[sla_rule] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_sla_rule] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [principal_id] BIGINT NULL,
    [call_type_lookup_id] BIGINT NULL,
    [priority] NVARCHAR(30) NULL,
    [response_hours] DECIMAL(5,1) NULL,
    [resolution_hours] DECIMAL(5,1) NOT NULL CONSTRAINT [DF_svc_sla_rule_resolution_hours] DEFAULT (24),
    [clock_type] NVARCHAR(30) NOT NULL CONSTRAINT [DF_svc_sla_rule_clock_type] DEFAULT (N'Calendar'),
    [alert_before_minutes] INT NULL,
    [escalate_to_role_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_sla_rule_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_sla_rule_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_sla_rule_priority] CHECK ([priority] IN (N'Critical', N'High', N'Normal', N'Low')),
    CONSTRAINT [CK_svc_sla_rule_clock_type] CHECK ([clock_type] IN (N'Calendar', N'Working hours'))
);
GO
-- Warnings, breaches and escalations raised on calls.
CREATE TABLE [svc].[sla_event] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_sla_event] PRIMARY KEY,
    [service_call_id] BIGINT NOT NULL,
    [sla_rule_id] BIGINT NULL,
    [event_type] NVARCHAR(30) NOT NULL,
    [event_at] DATETIME2(0) NOT NULL,
    [notified_user_id] BIGINT NULL,
    CONSTRAINT [CK_svc_sla_event_event_type] CHECK ([event_type] IN (N'Warning', N'Breached', N'Escalated'))
);
GO

/* ===== int: Integration ===== */
-- Connected systems. Credentials stay in AWS Secrets Manager.
CREATE TABLE [int].[external_system] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_int_external_system] PRIMARY KEY,
    [code] NVARCHAR(20) NOT NULL,
    [principal_id] BIGINT NULL,
    [name] NVARCHAR(100) NOT NULL,
    [base_url] NVARCHAR(300) NULL,
    [auth_type] NVARCHAR(30) NOT NULL,
    [credential_secret_name] NVARCHAR(100) NULL,
    [is_enabled] BIT NOT NULL CONSTRAINT [DF_int_external_system_is_enabled] DEFAULT (0),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_int_external_system_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_int_external_system_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_int_external_system_auth_type] CHECK ([auth_type] IN (N'Basic', N'OAuth2', N'API key', N'Certificate', N'None'))
);
GO
-- Our ID to external ID mapping (replaces the byd_* columns; works for every OEM portal).
CREATE TABLE [int].[sync_mapping] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_int_sync_mapping] PRIMARY KEY,
    [external_system_id] BIGINT NOT NULL,
    [entity_type] NVARCHAR(50) NOT NULL,
    [internal_id] BIGINT NOT NULL,
    [external_id] NVARCHAR(100) NOT NULL,
    [external_uuid] NVARCHAR(64) NULL,
    [last_synced_at] DATETIME2(0) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_int_sync_mapping_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_int_sync_mapping_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Every API call to or from an external system, with retry state.
CREATE TABLE [int].[sync_log] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_int_sync_log] PRIMARY KEY,
    [external_system_id] BIGINT NOT NULL,
    [entity_type] NVARCHAR(50) NULL,
    [entity_id] BIGINT NULL,
    [direction] NVARCHAR(30) NOT NULL,
    [operation] NVARCHAR(30) NOT NULL,
    [request_payload] NVARCHAR(MAX) NULL,
    [response_payload] NVARCHAR(MAX) NULL,
    [http_status] SMALLINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [attempt_count] TINYINT NOT NULL CONSTRAINT [DF_int_sync_log_attempt_count] DEFAULT (1),
    [next_retry_at] DATETIME2(0) NULL,
    [error_message] NVARCHAR(1000) NULL,
    [started_at] DATETIME2(0) NOT NULL,
    [finished_at] DATETIME2(0) NULL,
    CONSTRAINT [CK_int_sync_log_direction] CHECK ([direction] IN (N'Outbound', N'Inbound')),
    CONSTRAINT [CK_int_sync_log_operation] CHECK ([operation] IN (N'Create', N'Update', N'Read', N'Delete')),
    CONSTRAINT [CK_int_sync_log_status] CHECK ([status] IN (N'Success', N'Failed', N'Retrying'))
);
GO
-- Excel/CSV imports (masters, ByD exports, bank statements).
CREATE TABLE [int].[file_import] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_int_file_import] PRIMARY KEY,
    [external_system_id] BIGINT NULL,
    [import_type] NVARCHAR(30) NOT NULL,
    [file_name] NVARCHAR(200) NOT NULL,
    [s3_key] NVARCHAR(500) NOT NULL,
    [uploaded_by_user_id] BIGINT NOT NULL,
    [uploaded_at] DATETIME2(0) NOT NULL,
    [total_rows] INT NULL,
    [success_rows] INT NULL,
    [error_rows] INT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [error_report_attachment_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_int_file_import_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_int_file_import_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_int_file_import_import_type] CHECK ([import_type] IN (N'Customers', N'Machines', N'Items', N'Open calls', N'Registered products', N'Service tickets', N'Bank statement', N'Opening balances')),
    CONSTRAINT [CK_int_file_import_status] CHECK ([status] IN (N'Uploaded', N'Validating', N'Imported', N'Failed'))
);
GO
-- Row-level import errors.
CREATE TABLE [int].[file_import_error] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_int_file_import_error] PRIMARY KEY,
    [file_import_id] BIGINT NOT NULL,
    [row_number] INT NOT NULL,
    [column_name] NVARCHAR(60) NULL,
    [error_message] NVARCHAR(500) NOT NULL,
    [raw_row_json] NVARCHAR(MAX) NULL
);
GO
-- Inbound events (WhatsApp replies, ByD notifications).
CREATE TABLE [int].[webhook_event] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_int_webhook_event] PRIMARY KEY,
    [external_system_id] BIGINT NOT NULL,
    [event_type] NVARCHAR(60) NOT NULL,
    [payload] NVARCHAR(MAX) NOT NULL,
    [received_at] DATETIME2(0) NOT NULL,
    [processed_at] DATETIME2(0) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [error_message] NVARCHAR(500) NULL,
    CONSTRAINT [CK_int_webhook_event_status] CHECK ([status] IN (N'Received', N'Processed', N'Failed', N'Ignored'))
);
GO

/* ---------- 2. Unique keys (16) ---------- */
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_service_contract_contract_no] ON [svc].[service_contract] ([contract_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_contract_coverage_k1] ON [svc].[contract_coverage] ([service_contract_id], [machine_unit_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_service_call_call_no] ON [svc].[service_call] ([call_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_service_call_client_uuid] ON [svc].[service_call] ([client_uuid]) WHERE [client_uuid] IS NOT NULL;
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_call_status_log_client_uuid] ON [svc].[call_status_log] ([client_uuid]) WHERE [client_uuid] IS NOT NULL;
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_oem_call_reference_service_call_id] ON [svc].[oem_call_reference] ([service_call_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_service_visit_client_uuid] ON [svc].[service_visit] ([client_uuid]) WHERE [client_uuid] IS NOT NULL;
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_service_visit_k1] ON [svc].[service_visit] ([service_call_id], [visit_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_trip_client_uuid] ON [svc].[trip] ([client_uuid]) WHERE [client_uuid] IS NOT NULL;
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_engineer_duty_log_client_uuid] ON [svc].[engineer_duty_log] ([client_uuid]) WHERE [client_uuid] IS NOT NULL;
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_engineer_duty_log_k1] ON [svc].[engineer_duty_log] ([employee_id], [duty_date]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_service_report_service_visit_id] ON [svc].[service_report] ([service_visit_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_service_report_report_no] ON [svc].[service_report] ([report_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_service_report_client_uuid] ON [svc].[service_report] ([client_uuid]) WHERE [client_uuid] IS NOT NULL;
CREATE UNIQUE NONCLUSTERED INDEX [UX_int_external_system_code] ON [int].[external_system] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_int_sync_mapping_k1] ON [int].[sync_mapping] ([external_system_id], [entity_type], [internal_id]);
GO

/* ---------- 3. Foreign keys (81) ----------
   Includes links from earlier-phase columns to tables created in this phase. */
ALTER TABLE [core].[machine_meter_reading] ADD CONSTRAINT [FK_core_machine_meter_reading_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_contract] ADD CONSTRAINT [FK_svc_service_contract_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_contract] ADD CONSTRAINT [FK_svc_service_contract_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_contract] ADD CONSTRAINT [FK_svc_service_contract_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[contract_coverage] ADD CONSTRAINT [FK_svc_contract_coverage_service_contract_id] FOREIGN KEY ([service_contract_id]) REFERENCES [svc].[service_contract] ([id]) ON DELETE CASCADE;
ALTER TABLE [svc].[contract_coverage] ADD CONSTRAINT [FK_svc_contract_coverage_machine_unit_id] FOREIGN KEY ([machine_unit_id]) REFERENCES [core].[machine_unit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[checklist_template] ADD CONSTRAINT [FK_svc_checklist_template_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[checklist_template] ADD CONSTRAINT [FK_svc_checklist_template_machine_model_id] FOREIGN KEY ([machine_model_id]) REFERENCES [core].[machine_model] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[checklist_template] ADD CONSTRAINT [FK_svc_checklist_template_call_type_lookup_id] FOREIGN KEY ([call_type_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[checklist_template_item] ADD CONSTRAINT [FK_svc_checklist_template_item_checklist_template_id] FOREIGN KEY ([checklist_template_id]) REFERENCES [svc].[checklist_template] ([id]) ON DELETE CASCADE;
ALTER TABLE [svc].[service_schedule_template] ADD CONSTRAINT [FK_svc_service_schedule_template_machine_model_id] FOREIGN KEY ([machine_model_id]) REFERENCES [core].[machine_model] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_schedule_template] ADD CONSTRAINT [FK_svc_service_schedule_template_checklist_template_id] FOREIGN KEY ([checklist_template_id]) REFERENCES [svc].[checklist_template] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[planned_service] ADD CONSTRAINT [FK_svc_planned_service_machine_unit_id] FOREIGN KEY ([machine_unit_id]) REFERENCES [core].[machine_unit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[planned_service] ADD CONSTRAINT [FK_svc_planned_service_schedule_template_id] FOREIGN KEY ([schedule_template_id]) REFERENCES [svc].[service_schedule_template] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[planned_service] ADD CONSTRAINT [FK_svc_planned_service_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_call_source_lookup_id] FOREIGN KEY ([call_source_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_call_type_lookup_id] FOREIGN KEY ([call_type_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_complaint_category_lookup_id] FOREIGN KEY ([complaint_category_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_customer_site_id] FOREIGN KEY ([customer_site_id]) REFERENCES [core].[customer_site] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_contact_id] FOREIGN KEY ([contact_id]) REFERENCES [core].[contact] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_machine_unit_id] FOREIGN KEY ([machine_unit_id]) REFERENCES [core].[machine_unit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_service_contract_id] FOREIGN KEY ([service_contract_id]) REFERENCES [svc].[service_contract] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_planned_service_id] FOREIGN KEY ([planned_service_id]) REFERENCES [svc].[planned_service] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_received_by_user_id] FOREIGN KEY ([received_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_team_id] FOREIGN KEY ([team_id]) REFERENCES [core].[team] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_assigned_engineer_id] FOREIGN KEY ([assigned_engineer_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_closed_by_user_id] FOREIGN KEY ([closed_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_duplicate_of_call_id] FOREIGN KEY ([duplicate_of_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[call_status_log] ADD CONSTRAINT [FK_svc_call_status_log_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE CASCADE;
ALTER TABLE [svc].[call_status_log] ADD CONSTRAINT [FK_svc_call_status_log_changed_by_user_id] FOREIGN KEY ([changed_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[call_status_log] ADD CONSTRAINT [FK_svc_call_status_log_reason_lookup_id] FOREIGN KEY ([reason_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[call_assignment] ADD CONSTRAINT [FK_svc_call_assignment_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE CASCADE;
ALTER TABLE [svc].[call_assignment] ADD CONSTRAINT [FK_svc_call_assignment_engineer_employee_id] FOREIGN KEY ([engineer_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[call_assignment] ADD CONSTRAINT [FK_svc_call_assignment_assigned_by_user_id] FOREIGN KEY ([assigned_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[call_assignment] ADD CONSTRAINT [FK_svc_call_assignment_reason_lookup_id] FOREIGN KEY ([reason_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[oem_call_reference] ADD CONSTRAINT [FK_svc_oem_call_reference_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[oem_call_reference] ADD CONSTRAINT [FK_svc_oem_call_reference_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[oem_call_reference] ADD CONSTRAINT [FK_svc_oem_call_reference_external_system_id] FOREIGN KEY ([external_system_id]) REFERENCES [int].[external_system] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[oem_call_reference] ADD CONSTRAINT [FK_svc_oem_call_reference_entered_by_user_id] FOREIGN KEY ([entered_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[oem_call_reference] ADD CONSTRAINT [FK_svc_oem_call_reference_verified_by_user_id] FOREIGN KEY ([verified_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[oem_call_reference] ADD CONSTRAINT [FK_svc_oem_call_reference_last_sync_log_id] FOREIGN KEY ([last_sync_log_id]) REFERENCES [int].[sync_log] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_visit] ADD CONSTRAINT [FK_svc_service_visit_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE CASCADE;
ALTER TABLE [svc].[service_visit] ADD CONSTRAINT [FK_svc_service_visit_engineer_employee_id] FOREIGN KEY ([engineer_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[trip] ADD CONSTRAINT [FK_svc_trip_service_visit_id] FOREIGN KEY ([service_visit_id]) REFERENCES [svc].[service_visit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[trip] ADD CONSTRAINT [FK_svc_trip_engineer_employee_id] FOREIGN KEY ([engineer_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[trip_gps_point] ADD CONSTRAINT [FK_svc_trip_gps_point_trip_id] FOREIGN KEY ([trip_id]) REFERENCES [svc].[trip] ([id]) ON DELETE CASCADE;
ALTER TABLE [svc].[engineer_duty_log] ADD CONSTRAINT [FK_svc_engineer_duty_log_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_report] ADD CONSTRAINT [FK_svc_service_report_service_visit_id] FOREIGN KEY ([service_visit_id]) REFERENCES [svc].[service_visit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_report] ADD CONSTRAINT [FK_svc_service_report_machine_condition_lookup_id] FOREIGN KEY ([machine_condition_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_report] ADD CONSTRAINT [FK_svc_service_report_failure_code_lookup_id] FOREIGN KEY ([failure_code_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_report] ADD CONSTRAINT [FK_svc_service_report_customer_signature_attachment_id] FOREIGN KEY ([customer_signature_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_report] ADD CONSTRAINT [FK_svc_service_report_engineer_signature_attachment_id] FOREIGN KEY ([engineer_signature_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_report] ADD CONSTRAINT [FK_svc_service_report_pdf_attachment_id] FOREIGN KEY ([pdf_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[report_checklist_item] ADD CONSTRAINT [FK_svc_report_checklist_item_service_report_id] FOREIGN KEY ([service_report_id]) REFERENCES [svc].[service_report] ([id]) ON DELETE CASCADE;
ALTER TABLE [svc].[report_checklist_item] ADD CONSTRAINT [FK_svc_report_checklist_item_checklist_template_item_id] FOREIGN KEY ([checklist_template_item_id]) REFERENCES [svc].[checklist_template_item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[report_checklist_item] ADD CONSTRAINT [FK_svc_report_checklist_item_photo_attachment_id] FOREIGN KEY ([photo_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_part_request] ADD CONSTRAINT [FK_svc_service_part_request_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_part_request] ADD CONSTRAINT [FK_svc_service_part_request_service_visit_id] FOREIGN KEY ([service_visit_id]) REFERENCES [svc].[service_visit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_part_request] ADD CONSTRAINT [FK_svc_service_part_request_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_part_request] ADD CONSTRAINT [FK_svc_service_part_request_uom_id] FOREIGN KEY ([uom_id]) REFERENCES [core].[uom] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_part_request] ADD CONSTRAINT [FK_svc_service_part_request_requested_by_employee_id] FOREIGN KEY ([requested_by_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_charge] ADD CONSTRAINT [FK_svc_service_charge_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[sla_rule] ADD CONSTRAINT [FK_svc_sla_rule_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[sla_rule] ADD CONSTRAINT [FK_svc_sla_rule_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[sla_rule] ADD CONSTRAINT [FK_svc_sla_rule_call_type_lookup_id] FOREIGN KEY ([call_type_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[sla_rule] ADD CONSTRAINT [FK_svc_sla_rule_escalate_to_role_id] FOREIGN KEY ([escalate_to_role_id]) REFERENCES [core].[role] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[sla_event] ADD CONSTRAINT [FK_svc_sla_event_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE CASCADE;
ALTER TABLE [svc].[sla_event] ADD CONSTRAINT [FK_svc_sla_event_sla_rule_id] FOREIGN KEY ([sla_rule_id]) REFERENCES [svc].[sla_rule] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[sla_event] ADD CONSTRAINT [FK_svc_sla_event_notified_user_id] FOREIGN KEY ([notified_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [int].[external_system] ADD CONSTRAINT [FK_int_external_system_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [int].[sync_mapping] ADD CONSTRAINT [FK_int_sync_mapping_external_system_id] FOREIGN KEY ([external_system_id]) REFERENCES [int].[external_system] ([id]) ON DELETE NO ACTION;
ALTER TABLE [int].[sync_log] ADD CONSTRAINT [FK_int_sync_log_external_system_id] FOREIGN KEY ([external_system_id]) REFERENCES [int].[external_system] ([id]) ON DELETE NO ACTION;
ALTER TABLE [int].[file_import] ADD CONSTRAINT [FK_int_file_import_external_system_id] FOREIGN KEY ([external_system_id]) REFERENCES [int].[external_system] ([id]) ON DELETE NO ACTION;
ALTER TABLE [int].[file_import] ADD CONSTRAINT [FK_int_file_import_uploaded_by_user_id] FOREIGN KEY ([uploaded_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [int].[file_import] ADD CONSTRAINT [FK_int_file_import_error_report_attachment_id] FOREIGN KEY ([error_report_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [int].[file_import_error] ADD CONSTRAINT [FK_int_file_import_error_file_import_id] FOREIGN KEY ([file_import_id]) REFERENCES [int].[file_import] ([id]) ON DELETE CASCADE;
ALTER TABLE [int].[webhook_event] ADD CONSTRAINT [FK_int_webhook_event_external_system_id] FOREIGN KEY ([external_system_id]) REFERENCES [int].[external_system] ([id]) ON DELETE NO ACTION;
GO

/* ---------- 4. Foreign-key indexes (79) ---------- */
CREATE NONCLUSTERED INDEX [IX_core_machine_meter_reading_service_call_id] ON [core].[machine_meter_reading] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_contract_company_id] ON [svc].[service_contract] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_contract_principal_id] ON [svc].[service_contract] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_contract_customer_id] ON [svc].[service_contract] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_svc_contract_coverage_service_contract_id] ON [svc].[contract_coverage] ([service_contract_id]);
CREATE NONCLUSTERED INDEX [IX_svc_contract_coverage_machine_unit_id] ON [svc].[contract_coverage] ([machine_unit_id]);
CREATE NONCLUSTERED INDEX [IX_svc_checklist_template_principal_id] ON [svc].[checklist_template] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_svc_checklist_template_machine_model_id] ON [svc].[checklist_template] ([machine_model_id]);
CREATE NONCLUSTERED INDEX [IX_svc_checklist_template_call_type_lookup_id] ON [svc].[checklist_template] ([call_type_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_svc_checklist_template_item_checklist_template_id] ON [svc].[checklist_template_item] ([checklist_template_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_schedule_template_machine_model_id] ON [svc].[service_schedule_template] ([machine_model_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_schedule_template_checklist_template_id] ON [svc].[service_schedule_template] ([checklist_template_id]);
CREATE NONCLUSTERED INDEX [IX_svc_planned_service_machine_unit_id] ON [svc].[planned_service] ([machine_unit_id]);
CREATE NONCLUSTERED INDEX [IX_svc_planned_service_schedule_template_id] ON [svc].[planned_service] ([schedule_template_id]);
CREATE NONCLUSTERED INDEX [IX_svc_planned_service_service_call_id] ON [svc].[planned_service] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_company_id] ON [svc].[service_call] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_branch_id] ON [svc].[service_call] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_principal_id] ON [svc].[service_call] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_call_source_lookup_id] ON [svc].[service_call] ([call_source_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_call_type_lookup_id] ON [svc].[service_call] ([call_type_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_complaint_category_lookup_id] ON [svc].[service_call] ([complaint_category_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_customer_id] ON [svc].[service_call] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_customer_site_id] ON [svc].[service_call] ([customer_site_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_contact_id] ON [svc].[service_call] ([contact_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_machine_unit_id] ON [svc].[service_call] ([machine_unit_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_service_contract_id] ON [svc].[service_call] ([service_contract_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_planned_service_id] ON [svc].[service_call] ([planned_service_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_received_by_user_id] ON [svc].[service_call] ([received_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_team_id] ON [svc].[service_call] ([team_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_assigned_engineer_id] ON [svc].[service_call] ([assigned_engineer_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_closed_by_user_id] ON [svc].[service_call] ([closed_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_duplicate_of_call_id] ON [svc].[service_call] ([duplicate_of_call_id]);
CREATE NONCLUSTERED INDEX [IX_svc_call_status_log_service_call_id] ON [svc].[call_status_log] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_svc_call_status_log_changed_by_user_id] ON [svc].[call_status_log] ([changed_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_svc_call_status_log_reason_lookup_id] ON [svc].[call_status_log] ([reason_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_svc_call_assignment_service_call_id] ON [svc].[call_assignment] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_svc_call_assignment_engineer_employee_id] ON [svc].[call_assignment] ([engineer_employee_id]);
CREATE NONCLUSTERED INDEX [IX_svc_call_assignment_assigned_by_user_id] ON [svc].[call_assignment] ([assigned_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_svc_call_assignment_reason_lookup_id] ON [svc].[call_assignment] ([reason_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_svc_oem_call_reference_principal_id] ON [svc].[oem_call_reference] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_svc_oem_call_reference_external_system_id] ON [svc].[oem_call_reference] ([external_system_id]);
CREATE NONCLUSTERED INDEX [IX_svc_oem_call_reference_entered_by_user_id] ON [svc].[oem_call_reference] ([entered_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_svc_oem_call_reference_verified_by_user_id] ON [svc].[oem_call_reference] ([verified_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_svc_oem_call_reference_last_sync_log_id] ON [svc].[oem_call_reference] ([last_sync_log_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_visit_service_call_id] ON [svc].[service_visit] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_visit_engineer_employee_id] ON [svc].[service_visit] ([engineer_employee_id]);
CREATE NONCLUSTERED INDEX [IX_svc_trip_service_visit_id] ON [svc].[trip] ([service_visit_id]);
CREATE NONCLUSTERED INDEX [IX_svc_trip_engineer_employee_id] ON [svc].[trip] ([engineer_employee_id]);
CREATE NONCLUSTERED INDEX [IX_svc_trip_gps_point_trip_id] ON [svc].[trip_gps_point] ([trip_id]);
CREATE NONCLUSTERED INDEX [IX_svc_engineer_duty_log_employee_id] ON [svc].[engineer_duty_log] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_report_machine_condition_lookup_id] ON [svc].[service_report] ([machine_condition_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_report_failure_code_lookup_id] ON [svc].[service_report] ([failure_code_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_report_customer_signature_attachment_id] ON [svc].[service_report] ([customer_signature_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_report_engineer_signature_attachment_id] ON [svc].[service_report] ([engineer_signature_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_report_pdf_attachment_id] ON [svc].[service_report] ([pdf_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_svc_report_checklist_item_service_report_id] ON [svc].[report_checklist_item] ([service_report_id]);
CREATE NONCLUSTERED INDEX [IX_svc_report_checklist_item_checklist_template_item_id] ON [svc].[report_checklist_item] ([checklist_template_item_id]);
CREATE NONCLUSTERED INDEX [IX_svc_report_checklist_item_photo_attachment_id] ON [svc].[report_checklist_item] ([photo_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_part_request_service_call_id] ON [svc].[service_part_request] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_part_request_service_visit_id] ON [svc].[service_part_request] ([service_visit_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_part_request_item_id] ON [svc].[service_part_request] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_part_request_uom_id] ON [svc].[service_part_request] ([uom_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_part_request_requested_by_employee_id] ON [svc].[service_part_request] ([requested_by_employee_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_charge_service_call_id] ON [svc].[service_charge] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_svc_sla_rule_company_id] ON [svc].[sla_rule] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_svc_sla_rule_principal_id] ON [svc].[sla_rule] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_svc_sla_rule_call_type_lookup_id] ON [svc].[sla_rule] ([call_type_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_svc_sla_rule_escalate_to_role_id] ON [svc].[sla_rule] ([escalate_to_role_id]);
CREATE NONCLUSTERED INDEX [IX_svc_sla_event_service_call_id] ON [svc].[sla_event] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_svc_sla_event_sla_rule_id] ON [svc].[sla_event] ([sla_rule_id]);
CREATE NONCLUSTERED INDEX [IX_svc_sla_event_notified_user_id] ON [svc].[sla_event] ([notified_user_id]);
CREATE NONCLUSTERED INDEX [IX_int_external_system_principal_id] ON [int].[external_system] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_int_sync_mapping_external_system_id] ON [int].[sync_mapping] ([external_system_id]);
CREATE NONCLUSTERED INDEX [IX_int_sync_log_external_system_id] ON [int].[sync_log] ([external_system_id]);
CREATE NONCLUSTERED INDEX [IX_int_file_import_external_system_id] ON [int].[file_import] ([external_system_id]);
CREATE NONCLUSTERED INDEX [IX_int_file_import_uploaded_by_user_id] ON [int].[file_import] ([uploaded_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_int_file_import_error_report_attachment_id] ON [int].[file_import] ([error_report_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_int_file_import_error_file_import_id] ON [int].[file_import_error] ([file_import_id]);
CREATE NONCLUSTERED INDEX [IX_int_webhook_event_external_system_id] ON [int].[webhook_event] ([external_system_id]);
GO
