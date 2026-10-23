/* =====================================================================
   TRISHUL Integrated System - seed data, views and security for v3
   Run AFTER 12_gap_remediation.sql. Safe to re-run.

   1  Lookup values that were missing (call sources, reopen reasons)
   2  Brands and connected systems (CONFIRM the values - see Q1, Q9)
   3  Permissions and role grants (role-based restrictions)
   4  KPI / KRI catalogue (balanced scorecard)
   5  Reporting views: receivables by age, payables by age, stock ageing,
      upcoming services, call turnaround
   6  Row-level security for the new brand-scoped tables
   7  Table descriptions for the new tables
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
SET XACT_ABORT ON;
BEGIN TRANSACTION;

/* ---------- 1. Lookups ---------- */
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order])
SELECT lt.[id], v.[code], v.[label], v.[sort_order]
FROM [core].[lookup_type] lt
CROSS JOIN (VALUES (N'SERVICE_ENGINEER', N'Service engineer (field)', 9),
                   (N'CUSTOMER_PORTAL', N'Customer portal', 10),
                   (N'MACHINE_ALERT', N'Machine alert / telematics', 11)) v([code], [label], [sort_order])
WHERE lt.[code] = N'CALL_SOURCE'
  AND NOT EXISTS (SELECT 1 FROM [core].[lookup_value] x WHERE x.[lookup_type_id] = lt.[id] AND x.[code] = v.[code]);

IF NOT EXISTS (SELECT 1 FROM [core].[lookup_type] WHERE [code] = N'REOPEN_REASON')
    INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'REOPEN_REASON', N'Call Reopen Reason', N'Service');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order])
SELECT lt.[id], v.[code], v.[label], v.[sort_order]
FROM [core].[lookup_type] lt
CROSS JOIN (VALUES (N'PROBLEM_RECURRED', N'Same problem recurred', 1),
                   (N'WORK_INCOMPLETE', N'Work incomplete', 2),
                   (N'PART_FAILED', N'Fitted part failed', 3),
                   (N'CUSTOMER_NOT_SATISFIED', N'Customer not satisfied', 4),
                   (N'OEM_REJECTED_CLOSURE', N'OEM rejected closure', 5),
                   (N'CLOSED_BY_MISTAKE', N'Closed by mistake', 6)) v([code], [label], [sort_order])
WHERE lt.[code] = N'REOPEN_REASON'
  AND NOT EXISTS (SELECT 1 FROM [core].[lookup_value] x WHERE x.[lookup_type_id] = lt.[id] AND x.[code] = v.[code]);

IF NOT EXISTS (SELECT 1 FROM [core].[lookup_type] WHERE [code] = N'PART_REJECT_REASON')
    INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'PART_REJECT_REASON', N'Part Request Reject Reason', N'Inventory');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order])
SELECT lt.[id], v.[code], v.[label], v.[sort_order]
FROM [core].[lookup_type] lt
CROSS JOIN (VALUES (N'CUSTOMER_DECLINED_QUOTE', N'Customer declined quotation', 1),
                   (N'NOT_COVERED', N'Not covered by warranty / contract', 2),
                   (N'DUPLICATE_REQUEST', N'Duplicate request', 3),
                   (N'WRONG_PART', N'Wrong part requested', 4)) v([code], [label], [sort_order])
WHERE lt.[code] = N'PART_REJECT_REASON'
  AND NOT EXISTS (SELECT 1 FROM [core].[lookup_value] x WHERE x.[lookup_type_id] = lt.[id] AND x.[code] = v.[code]);

/* ---------- 2. Brands and connected systems (CONFIRM before go-live) ---------- */
INSERT INTO [core].[principal] ([code], [name], [oem_portal_name])
SELECT v.[code], v.[name], v.[portal]
FROM (VALUES (N'TATA_HITACHI', N'Tata Hitachi', N'E-DOST (SAP ByD)'),
             (N'ATLAS_COPCO', N'Atlas Copco', N'Atlas Copco DMS')) v([code], [name], [portal])
WHERE NOT EXISTS (SELECT 1 FROM [core].[principal] p WHERE p.[code] = v.[code]);

INSERT INTO [int].[external_system] ([code], [principal_id], [name], [auth_type], [is_enabled])
SELECT v.[code], p.[id], v.[name], N'None', 0
FROM (VALUES (N'TH_EDOST_BYD', N'TATA_HITACHI', N'Tata Hitachi E-DOST / SAP ByD'),
             (N'ATLAS_DMS', N'ATLAS_COPCO', N'Atlas Copco dealer portal (DMS)'),
             (N'TALLY', NULL, N'Tally Prime (billing and stock)'),
             (N'WHATSAPP', NULL, N'WhatsApp Business API'),
             (N'EMAIL', NULL, N'E-mail (Amazon SES / mailbox)'),
             (N'GREY8', NULL, N'Grey8 HR'),
             (N'MAPS', NULL, N'Maps / distance API'),
             (N'GST_IRP', NULL, N'GST e-invoice / e-way bill portal')) v([code], [principal_code], [name])
LEFT JOIN [core].[principal] p ON p.[code] = v.[principal_code]
WHERE NOT EXISTS (SELECT 1 FROM [int].[external_system] e WHERE e.[code] = v.[code]);

/* ---------- 3. Permissions and role grants ---------- */
INSERT INTO [core].[permission] ([code], [module], [description])
SELECT v.[code], v.[module], v.[description]
FROM (VALUES
    (N'svc.call.create',            N'Service',   N'Log a service call (office)'),
    (N'svc.call.create_field',      N'Service',   N'Log a new call from the field (mobile)'),
    (N'svc.call.assign',            N'Service',   N'Assign / reassign engineer (Team Lead)'),
    (N'svc.call.oem_id.enter',      N'Service',   N'Enter the OEM (E-DOST / BYD) Call ID'),
    (N'svc.call.oem_id.verify',     N'Service',   N'Verify an OEM Call ID entered by an engineer'),
    (N'svc.call.close',             N'Service',   N'Close a call'),
    (N'svc.call.reopen',            N'Service',   N'Reopen a closed call on the same Call ID'),
    (N'svc.call.cancel',            N'Service',   N'Cancel a call'),
    (N'svc.report.submit',          N'Service',   N'Submit a service report'),
    (N'svc.part_request.create',    N'Service',   N'Raise a part request'),
    (N'svc.part_request.review',    N'Inventory', N'Review part request against stock'),
    (N'svc.contract.manage',        N'Service',   N'Create / renew ASC and AMC contracts'),
    (N'svc.import.oem_list',        N'Service',   N'Import OEM case / service lists'),
    (N'inv.stock.adjust',           N'Inventory', N'Post stock adjustments'),
    (N'inv.stock.issue',            N'Inventory', N'Issue / dispatch parts'),
    (N'pur.po.approve',             N'Purchase',  N'Approve purchase orders'),
    (N'sal.quotation.approve',      N'Sales',     N'Approve quotation discounts'),
    (N'sal.credit.override',        N'Sales',     N'Release credit hold / override credit limit'),
    (N'sal.payment.confirm',        N'Sales',     N'Confirm customer payment'),
    (N'sal.invoice.post',           N'Sales',     N'Post invoices (push to Tally)'),
    (N'acc.cash.reconcile',         N'Accounts',  N'Approve cash reconciliation'),
    (N'acc.period.lock',            N'Accounts',  N'Lock accounting periods'),
    (N'hr.attendance.regularize',   N'HR',        N'Approve attendance regularisation'),
    (N'rpt.dashboard.view',         N'Reports',   N'View management dashboards')
) v([code], [module], [description])
WHERE NOT EXISTS (SELECT 1 FROM [core].[permission] p WHERE p.[code] = v.[code]);

INSERT INTO [core].[role_permission] ([role_id], [permission_id])
SELECT r.[id], p.[id]
FROM (VALUES
    (N'BACK_OFFICE', N'svc.call.create'), (N'BACK_OFFICE', N'svc.call.oem_id.enter'), (N'BACK_OFFICE', N'svc.call.oem_id.verify'),
    (N'BACK_OFFICE', N'svc.call.close'), (N'BACK_OFFICE', N'svc.call.reopen'), (N'BACK_OFFICE', N'svc.import.oem_list'),
    (N'TEAM_LEAD', N'svc.call.create'), (N'TEAM_LEAD', N'svc.call.assign'), (N'TEAM_LEAD', N'svc.call.close'),
    (N'TEAM_LEAD', N'svc.call.reopen'), (N'TEAM_LEAD', N'svc.call.cancel'), (N'TEAM_LEAD', N'svc.call.oem_id.verify'),
    (N'TEAM_LEAD', N'svc.contract.manage'), (N'TEAM_LEAD', N'rpt.dashboard.view'),
    (N'SERVICE_ENGINEER', N'svc.call.create_field'), (N'SERVICE_ENGINEER', N'svc.call.oem_id.enter'),
    (N'SERVICE_ENGINEER', N'svc.report.submit'), (N'SERVICE_ENGINEER', N'svc.part_request.create'),
    (N'WAREHOUSE', N'svc.part_request.review'), (N'WAREHOUSE', N'inv.stock.issue'), (N'WAREHOUSE', N'inv.stock.adjust'),
    (N'PURCHASE', N'pur.po.approve'),
    (N'SALES_MANAGER', N'sal.quotation.approve'), (N'SALES_MANAGER', N'sal.credit.override'), (N'SALES_MANAGER', N'rpt.dashboard.view'),
    (N'ACCOUNTS', N'sal.payment.confirm'), (N'ACCOUNTS', N'sal.invoice.post'), (N'ACCOUNTS', N'sal.credit.override'),
    (N'ACCOUNTS', N'acc.cash.reconcile'), (N'ACCOUNTS', N'acc.period.lock'),
    (N'HR', N'hr.attendance.regularize'),
    (N'MANAGEMENT', N'rpt.dashboard.view')
) v([role_code], [permission_code])
JOIN [core].[role] r ON r.[code] = v.[role_code]
JOIN [core].[permission] p ON p.[code] = v.[permission_code]
WHERE NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);

-- ADMIN gets every permission.
INSERT INTO [core].[role_permission] ([role_id], [permission_id])
SELECT r.[id], p.[id]
FROM [core].[role] r CROSS JOIN [core].[permission] p
WHERE r.[code] = N'ADMIN'
  AND NOT EXISTS (SELECT 1 FROM [core].[role_permission] rp WHERE rp.[role_id] = r.[id] AND rp.[permission_id] = p.[id]);

IF NOT EXISTS (SELECT 1 FROM [core].[role] WHERE [code] = N'INVENTORY')
    INSERT INTO [core].[role] ([code], [name], [description], [is_system])
    VALUES (N'INVENTORY', N'Inventory person', N'Reviews part requests and stock availability (workflow step 11)', 1);
IF NOT EXISTS (SELECT 1 FROM [core].[role] WHERE [code] = N'COORDINATOR')
    INSERT INTO [core].[role] ([code], [name], [description], [is_system])
    VALUES (N'COORDINATOR', N'Service coordinator', N'Creates OEM cases and imports OEM lists (workflow steps 8, 16)', 1);

/* ---------- 4. KPI / KRI catalogue ---------- */
INSERT INTO [rpt].[kpi_definition] ([code], [name], [kpi_kind], [perspective], [module], [unit], [direction], [frequency], [calculation_note])
SELECT v.* FROM (VALUES
    (N'FIN_SALES_VS_TARGET',   N'Sales achievement vs target',          N'KPI', N'Financial',           N'Sales',   N'%',    N'Higher is better', N'Monthly',   N'Invoiced value / pre.sales_target value'),
    (N'FIN_COLLECTION_EFF',    N'Collection efficiency',                N'KPI', N'Financial',           N'Accounts',N'%',    N'Higher is better', N'Monthly',   N'Receipts in period / receivables due in period'),
    (N'FIN_DSO',               N'Days sales outstanding',               N'KRI', N'Financial',           N'Accounts',N'days', N'Lower is better',  N'Monthly',   N'Receivables / average daily sales'),
    (N'FIN_OVERDUE_90',        N'Receivables overdue > 90 days',        N'KRI', N'Financial',           N'Accounts',N'INR',  N'Lower is better',  N'Monthly',   N'acc.v_receivables_ageing buckets 91+'),
    (N'FIN_CASH_MISMATCH',     N'Cash mismatch amount',                 N'KRI', N'Financial',           N'Accounts',N'INR',  N'Lower is better',  N'Daily',     N'SUM(ABS(difference_amount)) in acc.cash_reconciliation'),
    (N'CUS_SLA_MET',           N'Calls closed within SLA',              N'KPI', N'Customer',            N'Service', N'%',    N'Higher is better', N'Monthly',   N'closed_at <= sla_due_at'),
    (N'CUS_FEEDBACK',          N'Average customer rating',              N'KPI', N'Customer',            N'Service', N'1-5',  N'Higher is better', N'Monthly',   N'AVG(customer_rating)'),
    (N'CUS_REOPEN_RATE',       N'Call reopen rate',                     N'KRI', N'Customer',            N'Service', N'%',    N'Lower is better',  N'Monthly',   N'Calls with reopen_count > 0 / calls closed'),
    (N'OPS_FIRST_TIME_FIX',    N'First-visit fix rate',                 N'KPI', N'Internal process',    N'Service', N'%',    N'Higher is better', N'Monthly',   N'Calls completed with one visit / calls completed'),
    (N'OPS_RESPONSE_HRS',      N'Average response time',                N'KPI', N'Internal process',    N'Service', N'hours',N'Lower is better',  N'Monthly',   N'first_response_at - received_at'),
    (N'OPS_PARTS_WAIT_DAYS',   N'Average parts waiting time',           N'KRI', N'Internal process',    N'Inventory',N'days',N'Lower is better',  N'Monthly',   N'Part request created -> Delivered to site'),
    (N'OPS_STOCK_AGED_180',    N'Stock value older than 180 days',      N'KRI', N'Internal process',    N'Inventory',N'INR', N'Lower is better',  N'Monthly',   N'inv.v_stock_ageing buckets 181+'),
    (N'OPS_STOCK_ACCURACY',    N'Stock count accuracy',                 N'KPI', N'Internal process',    N'Inventory',N'%',   N'Higher is better', N'Monthly',   N'Lines with counted_qty = system_qty / lines counted'),
    (N'LRN_CERTIFIED_ENGINEERS',N'Engineers with valid OEM certification',N'KPI',N'Learning and growth', N'HR',      N'%',    N'Higher is better', N'Quarterly', N'hr.employee_skill / core.employee_principal valid_until >= today'),
    (N'LRN_ATTENDANCE',        N'Attendance rate',                      N'KPI', N'Learning and growth', N'HR',      N'%',    N'Higher is better', N'Monthly',   N'Present days / working days')
) v([code], [name], [kpi_kind], [perspective], [module], [unit], [direction], [frequency], [calculation_note])
WHERE NOT EXISTS (SELECT 1 FROM [rpt].[kpi_definition] k WHERE k.[code] = v.[code]);

COMMIT TRANSACTION;
GO

/* ---------- 5. Reporting views ---------- */
-- Receivables by age: open invoices + open opening-balance bills, net of allocations.
CREATE OR ALTER VIEW [acc].[v_receivables_ageing]
AS
WITH [today] AS (
    SELECT CAST(SYSDATETIMEOFFSET() AT TIME ZONE N'India Standard Time' AS DATE) AS [as_of]
),
[open_items] AS (
    SELECT si.[customer_id], si.[branch_id], si.[principal_id], CAST(N'Invoice' AS NVARCHAR(20)) AS [item_type],
           si.[id] AS [item_id], CAST(si.[invoice_no] AS NVARCHAR(40)) AS [document_no], si.[invoice_date] AS [document_date],
           COALESCE(si.[due_date], si.[invoice_date]) AS [due_date], si.[total] AS [document_amount],
           si.[total] - COALESCE(a.[allocated], 0) AS [outstanding]
    FROM [sal].[sales_invoice] si
    OUTER APPLY (SELECT SUM(ca.[amount]) AS [allocated] FROM [sal].[customer_allocation] ca
                 WHERE ca.[sales_invoice_id] = si.[id] AND ca.[is_active] = 1) a
    WHERE si.[status] IN (N'Posted', N'Part paid') AND si.[is_active] = 1
    UNION ALL
    SELECT ob.[customer_id], NULL, NULL, N'Opening bill', ob.[id], ob.[reference_document_no], ob.[document_date],
           COALESCE(ob.[due_date], ob.[document_date]), ob.[debit],
           ob.[debit] - COALESCE(a.[allocated], 0)
    FROM [acc].[opening_balance] ob
    OUTER APPLY (SELECT SUM(ca.[amount]) AS [allocated] FROM [sal].[customer_allocation] ca
                 WHERE ca.[opening_balance_id] = ob.[id] AND ca.[is_active] = 1) a
    WHERE ob.[party_type] = N'Customer' AND ob.[customer_id] IS NOT NULL AND ob.[debit] > 0 AND ob.[is_active] = 1
)
SELECT oi.[customer_id], c.[code] AS [customer_code], c.[name] AS [customer_name], oi.[branch_id], oi.[principal_id],
       oi.[item_type], oi.[item_id], oi.[document_no], oi.[document_date], oi.[due_date], oi.[document_amount], oi.[outstanding],
       DATEDIFF(DAY, oi.[due_date], t.[as_of]) AS [days_overdue],
       CASE WHEN DATEDIFF(DAY, oi.[due_date], t.[as_of]) <= 0   THEN N'Not due'
            WHEN DATEDIFF(DAY, oi.[due_date], t.[as_of]) <= 30  THEN N'1-30'
            WHEN DATEDIFF(DAY, oi.[due_date], t.[as_of]) <= 60  THEN N'31-60'
            WHEN DATEDIFF(DAY, oi.[due_date], t.[as_of]) <= 90  THEN N'61-90'
            WHEN DATEDIFF(DAY, oi.[due_date], t.[as_of]) <= 180 THEN N'91-180'
            ELSE N'180+' END AS [age_bucket],
       c.[credit_limit], c.[credit_status_id]
FROM [open_items] oi
CROSS JOIN [today] t
JOIN [core].[customer] c ON c.[id] = oi.[customer_id]
WHERE oi.[outstanding] > 0;
GO
-- Payables by age (same logic for suppliers).
CREATE OR ALTER VIEW [acc].[v_payables_ageing]
AS
WITH [today] AS (
    SELECT CAST(SYSDATETIMEOFFSET() AT TIME ZONE N'India Standard Time' AS DATE) AS [as_of]
),
[open_items] AS (
    SELECT pi.[supplier_id], pi.[branch_id], pi.[principal_id], CAST(N'Bill' AS NVARCHAR(20)) AS [item_type], pi.[id] AS [item_id],
           CAST(pi.[supplier_invoice_no] AS NVARCHAR(40)) AS [document_no], pi.[supplier_invoice_date] AS [document_date],
           COALESCE(pi.[due_date], pi.[supplier_invoice_date]) AS [due_date], pi.[total] AS [document_amount],
           pi.[total] - COALESCE(a.[allocated], 0) AS [outstanding]
    FROM [pur].[supplier_invoice] pi
    OUTER APPLY (SELECT SUM(sa.[amount]) AS [allocated] FROM [pur].[supplier_allocation] sa
                 WHERE sa.[supplier_invoice_id] = pi.[id] AND sa.[is_active] = 1) a
    WHERE pi.[status] IN (N'Posted', N'Part paid') AND pi.[is_active] = 1
    UNION ALL
    SELECT ob.[supplier_id], NULL, NULL, N'Opening bill', ob.[id], ob.[reference_document_no], ob.[document_date],
           COALESCE(ob.[due_date], ob.[document_date]), ob.[credit], ob.[credit] - COALESCE(a.[allocated], 0)
    FROM [acc].[opening_balance] ob
    OUTER APPLY (SELECT SUM(sa.[amount]) AS [allocated] FROM [pur].[supplier_allocation] sa
                 WHERE sa.[opening_balance_id] = ob.[id] AND sa.[is_active] = 1) a
    WHERE ob.[party_type] = N'Supplier' AND ob.[supplier_id] IS NOT NULL AND ob.[credit] > 0 AND ob.[is_active] = 1
)
SELECT oi.[supplier_id], s.[code] AS [supplier_code], s.[name] AS [supplier_name], oi.[branch_id], oi.[principal_id],
       oi.[item_type], oi.[item_id], oi.[document_no], oi.[document_date], oi.[due_date], oi.[document_amount], oi.[outstanding],
       DATEDIFF(DAY, oi.[due_date], t.[as_of]) AS [days_overdue],
       CASE WHEN DATEDIFF(DAY, oi.[due_date], t.[as_of]) <= 0   THEN N'Not due'
            WHEN DATEDIFF(DAY, oi.[due_date], t.[as_of]) <= 30  THEN N'1-30'
            WHEN DATEDIFF(DAY, oi.[due_date], t.[as_of]) <= 60  THEN N'31-60'
            WHEN DATEDIFF(DAY, oi.[due_date], t.[as_of]) <= 90  THEN N'61-90'
            WHEN DATEDIFF(DAY, oi.[due_date], t.[as_of]) <= 180 THEN N'91-180'
            ELSE N'180+' END AS [age_bucket]
FROM [open_items] oi
CROSS JOIN [today] t
JOIN [core].[supplier] s ON s.[id] = oi.[supplier_id]
WHERE oi.[outstanding] > 0;
GO
-- Stock ageing from FIFO receipt layers, plus reserved quantity per item/location.
CREATE OR ALTER VIEW [inv].[v_stock_ageing]
AS
SELECT cl.[item_id], i.[item_code], i.[description] AS [item_description], i.[principal_id],
       cl.[location_id], l.[branch_id] AS [warehouse_id], cl.[received_at], cl.[qty_remaining], cl.[unit_cost],
       CAST(cl.[qty_remaining] * cl.[unit_cost] AS DECIMAL(18,2)) AS [stock_value],
       DATEDIFF(DAY, cl.[received_at], SYSUTCDATETIME()) AS [age_days],
       CASE WHEN DATEDIFF(DAY, cl.[received_at], SYSUTCDATETIME()) <= 90  THEN N'0-90'
            WHEN DATEDIFF(DAY, cl.[received_at], SYSUTCDATETIME()) <= 180 THEN N'91-180'
            WHEN DATEDIFF(DAY, cl.[received_at], SYSUTCDATETIME()) <= 365 THEN N'181-365'
            ELSE N'365+' END AS [age_bucket],
       COALESCE(r.[qty_reserved], 0) AS [qty_reserved_at_location]
FROM [inv].[cost_layer] cl
JOIN [core].[item] i ON i.[id] = cl.[item_id]
JOIN [core].[location] l ON l.[id] = cl.[location_id]
OUTER APPLY (SELECT SUM(sb.[qty_reserved]) AS [qty_reserved] FROM [inv].[stock_balance] sb
             WHERE sb.[item_id] = cl.[item_id] AND sb.[location_id] = cl.[location_id]) r
WHERE cl.[qty_remaining] > 0 AND cl.[is_active] = 1;
GO
-- Upcoming / overdue services (HMR templates and 3/6/9/12-month contract visits).
CREATE OR ALTER VIEW [svc].[v_upcoming_service]
AS
SELECT ps.[id] AS [planned_service_id], ps.[status], ps.[due_date], ps.[due_hmr], ps.[plan_label],
       mu.[id] AS [machine_unit_id], mu.[serial_number], mu.[principal_id], mu.[current_hmr],
       mm.[model_code], c.[id] AS [customer_id], c.[name] AS [customer_name], cs.[site_name],
       sc.[contract_no], sc.[contract_type], sst.[service_name],
       DATEDIFF(DAY, CAST(SYSUTCDATETIME() AS DATE), ps.[due_date]) AS [days_to_due]
FROM [svc].[planned_service] ps
JOIN [core].[machine_unit] mu ON mu.[id] = ps.[machine_unit_id]
JOIN [core].[machine_model] mm ON mm.[id] = mu.[model_id]
LEFT JOIN [core].[customer] c ON c.[id] = mu.[customer_id]
LEFT JOIN [core].[customer_site] cs ON cs.[id] = mu.[customer_site_id]
LEFT JOIN [svc].[service_contract] sc ON sc.[id] = ps.[service_contract_id]
LEFT JOIN [svc].[service_schedule_template] sst ON sst.[id] = ps.[schedule_template_id]
WHERE ps.[status] IN (N'Upcoming', N'Due', N'Overdue') AND ps.[is_active] = 1;
GO
-- Call turnaround: response, closure and SLA result per call (daily service report source).
CREATE OR ALTER VIEW [svc].[v_call_turnaround]
AS
SELECT sc.[id] AS [service_call_id], sc.[call_no], sc.[oem_call_id], sc.[principal_id], sc.[branch_id],
       sc.[customer_id], sc.[assigned_engineer_id], sc.[current_status], sc.[priority], sc.[is_asc_priority],
       sc.[received_at], sc.[first_response_at], sc.[closed_at], sc.[completed_at], sc.[sla_due_at], sc.[reopen_count],
       DATEDIFF(MINUTE, sc.[received_at], sc.[first_response_at]) / 60.0 AS [response_hours],
       DATEDIFF(MINUTE, sc.[received_at], sc.[closed_at]) / 60.0 AS [closure_hours],
       CASE WHEN sc.[sla_due_at] IS NULL THEN NULL
            WHEN COALESCE(sc.[closed_at], SYSUTCDATETIME()) <= sc.[sla_due_at] THEN CAST(1 AS BIT)
            ELSE CAST(0 AS BIT) END AS [is_sla_met],
       v.[visit_count]
FROM [svc].[service_call] sc
OUTER APPLY (SELECT COUNT(*) AS [visit_count] FROM [svc].[service_visit] sv
             WHERE sv.[service_call_id] = sc.[id] AND sv.[status] <> N'Cancelled') v;
GO

/* ---------- 6. Row-level security for new brand / branch scoped tables ---------- */
IF NOT EXISTS (SELECT 1 FROM sys.security_predicates WHERE target_object_id = OBJECT_ID(N'svc.machine_alert'))
    ALTER SECURITY POLICY [rls].[brand_branch_policy] ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], NULL) ON [svc].[machine_alert];
IF NOT EXISTS (SELECT 1 FROM sys.security_predicates WHERE target_object_id = OBJECT_ID(N'svc.contract_plan'))
    ALTER SECURITY POLICY [rls].[brand_branch_policy] ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], NULL) ON [svc].[contract_plan];
IF NOT EXISTS (SELECT 1 FROM sys.security_predicates WHERE target_object_id = OBJECT_ID(N'core.oem_rating'))
    ALTER SECURITY POLICY [rls].[brand_branch_policy] ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [core].[oem_rating];
IF NOT EXISTS (SELECT 1 FROM sys.security_predicates WHERE target_object_id = OBJECT_ID(N'int.oem_ticket_import_line'))
    ALTER SECURITY POLICY [rls].[brand_branch_policy] ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], NULL) ON [int].[oem_ticket_import_line];
IF NOT EXISTS (SELECT 1 FROM sys.security_predicates WHERE target_object_id = OBJECT_ID(N'acc.cash_reconciliation'))
    ALTER SECURITY POLICY [rls].[brand_branch_policy] ADD FILTER PREDICATE [rls].[fn_can_see](NULL, [branch_id]) ON [acc].[cash_reconciliation];
GO

/* ---------- 7. Descriptions for the new tables ---------- */
DECLARE @d TABLE ([s] SYSNAME, [t] SYSNAME, [text] NVARCHAR(400));
INSERT INTO @d VALUES
 (N'hr',   N'skill',                     N'Skill master used for skill-based engineer assignment.'),
 (N'hr',   N'employee_skill',            N'Skills held by an employee, with proficiency 1-5 and certification validity.'),
 (N'svc',  N'skill_rule',                N'Which skill a call needs by brand / model / call type / complaint category.'),
 (N'svc',  N'call_required_skill',       N'Skills required for a specific call.'),
 (N'svc',  N'call_reopen',               N'History of reopening a call on the same Call ID.'),
 (N'svc',  N'contract_plan',             N'ASC / AMC packages that contracts are sold from.'),
 (N'svc',  N'contract_plan_entitlement', N'Entitlements included in a contract plan.'),
 (N'svc',  N'contract_billing_schedule', N'Instalment billing of AMC / ASC contracts.'),
 (N'core', N'machine_telemetry',         N'Raw sensor / telematics values from machines at customer sites. Insert only.'),
 (N'svc',  N'machine_alert',             N'Sensor, upcoming-service and delay alerts for a machine.'),
 (N'svc',  N'duty_gps_point',            N'Engineer GPS points while on duty but outside a trip.'),
 (N'core', N'customer_portal_user',      N'Customer portal logins (Cognito).'),
 (N'int',  N'inbound_message',           N'Inbound e-mail / WhatsApp messages turned into calls or part requests.'),
 (N'int',  N'oem_ticket_import_line',    N'Rows of imported OEM case / service lists, matched to calls.'),
 (N'sal',  N'quotation_price_check',     N'OEM price verification per quotation line.'),
 (N'sal',  N'credit_limit_change',       N'History of customer credit limit / status / terms changes.'),
 (N'hr',   N'vehicle',                   N'Vehicles used by field staff.'),
 (N'acc',  N'cash_reconciliation',       N'Daily cash count vs system receipts (cash mismatch control).'),
 (N'core', N'oem_rating',                N'Ratings / audit scores given by OEMs to the dealership.'),
 (N'rpt',  N'kpi_definition',            N'KPI / KRI catalogue grouped by balanced-scorecard perspective.'),
 (N'rpt',  N'kpi_target',                N'KPI targets per period and scope.'),
 (N'rpt',  N'kpi_actual',                N'Calculated KPI values per period and scope.');
DECLARE @s SYSNAME, @t SYSNAME, @text NVARCHAR(400);
DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT [s], [t], [text] FROM @d;
OPEN c;
FETCH NEXT FROM c INTO @s, @t, @text;
WHILE @@FETCH_STATUS = 0
BEGIN
    IF NOT EXISTS (SELECT 1 FROM sys.extended_properties ep
                   WHERE ep.[major_id] = OBJECT_ID(QUOTENAME(@s) + N'.' + QUOTENAME(@t)) AND ep.[minor_id] = 0 AND ep.[name] = N'MS_Description')
        EXEC sys.sp_addextendedproperty N'MS_Description', @text, N'SCHEMA', @s, N'TABLE', @t;
    FETCH NEXT FROM c INTO @s, @t, @text;
END
CLOSE c;
DEALLOCATE c;
GO
