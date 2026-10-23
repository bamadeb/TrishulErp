/* =====================================================================
   TRISHUL Integrated System - SQL Server DDL (dictionary v2)
   Seed data: lookup lists, roles, movement types
   Generated from the TRISHUL Database Dictionary. Do not edit by hand:
   change the dictionary and regenerate.
   Target: SQL Server 2019+ / Amazon RDS for SQL Server
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
SET XACT_ABORT ON;
BEGIN TRANSACTION;

/* Lookup lists (client to confirm values) */
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'CALL_SOURCE', N'Call Source', N'Service');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'CUSTOMER_PHONE_CALL', N'Customer phone call', 1 FROM [core].[lookup_type] WHERE [code] = N'CALL_SOURCE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'EMAIL', N'Email', 2 FROM [core].[lookup_type] WHERE [code] = N'CALL_SOURCE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'WHATSAPP', N'WhatsApp', 3 FROM [core].[lookup_type] WHERE [code] = N'CALL_SOURCE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'OEM_CUSTOMER_CARE_PER_BRAND', N'OEM Customer Care (per brand)', 4 FROM [core].[lookup_type] WHERE [code] = N'CALL_SOURCE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'SALES_PERSON', N'Sales person', 5 FROM [core].[lookup_type] WHERE [code] = N'CALL_SOURCE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'OLD_CUSTOMER', N'Old customer', 6 FROM [core].[lookup_type] WHERE [code] = N'CALL_SOURCE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'FOLLOW_UP_CALL', N'Follow-up call', 7 FROM [core].[lookup_type] WHERE [code] = N'CALL_SOURCE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'PLANNED_SERVICE', N'Planned service', 8 FROM [core].[lookup_type] WHERE [code] = N'CALL_SOURCE';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'CALL_TYPE', N'Call Type', N'Service');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'BREAKDOWN', N'Breakdown', 1 FROM [core].[lookup_type] WHERE [code] = N'CALL_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'PERIODIC_SERVICE', N'Periodic service', 2 FROM [core].[lookup_type] WHERE [code] = N'CALL_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'INSPECTION', N'Inspection', 3 FROM [core].[lookup_type] WHERE [code] = N'CALL_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'INSTALLATION', N'Installation', 4 FROM [core].[lookup_type] WHERE [code] = N'CALL_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'PDI', N'PDI', 5 FROM [core].[lookup_type] WHERE [code] = N'CALL_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'FOLLOW_UP', N'Follow-up', 6 FROM [core].[lookup_type] WHERE [code] = N'CALL_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'WARRANTY', N'Warranty', 7 FROM [core].[lookup_type] WHERE [code] = N'CALL_TYPE';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'COMPLAINT_CATEGORY', N'Complaint Category', N'Service');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'ENGINE', N'Engine', 1 FROM [core].[lookup_type] WHERE [code] = N'COMPLAINT_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'HYDRAULICS', N'Hydraulics', 2 FROM [core].[lookup_type] WHERE [code] = N'COMPLAINT_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'ELECTRICAL', N'Electrical', 3 FROM [core].[lookup_type] WHERE [code] = N'COMPLAINT_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'UNDERCARRIAGE', N'Undercarriage', 4 FROM [core].[lookup_type] WHERE [code] = N'COMPLAINT_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'TRANSMISSION', N'Transmission', 5 FROM [core].[lookup_type] WHERE [code] = N'COMPLAINT_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'CABIN_AC', N'Cabin/AC', 6 FROM [core].[lookup_type] WHERE [code] = N'COMPLAINT_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'ATTACHMENT', N'Attachment', 7 FROM [core].[lookup_type] WHERE [code] = N'COMPLAINT_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'OTHER', N'Other', 8 FROM [core].[lookup_type] WHERE [code] = N'COMPLAINT_CATEGORY';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'FAILURE_CODE', N'Failure Code', N'Service');
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'MACHINE_CONDITION', N'Machine Condition', N'Service');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'WORKING', N'Working', 1 FROM [core].[lookup_type] WHERE [code] = N'MACHINE_CONDITION';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'WORKING_WITH_ISSUE', N'Working with issue', 2 FROM [core].[lookup_type] WHERE [code] = N'MACHINE_CONDITION';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'BREAKDOWN', N'Breakdown', 3 FROM [core].[lookup_type] WHERE [code] = N'MACHINE_CONDITION';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'REASSIGN_REASON', N'Reassign Reason', N'Service');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'ENGINEER_ON_LEAVE', N'Engineer on leave', 1 FROM [core].[lookup_type] WHERE [code] = N'REASSIGN_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'CLOSER_ENGINEER_AVAILABLE', N'Closer engineer available', 2 FROM [core].[lookup_type] WHERE [code] = N'REASSIGN_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'SKILL_REQUIRED', N'Skill required', 3 FROM [core].[lookup_type] WHERE [code] = N'REASSIGN_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'WORKLOAD', N'Workload', 4 FROM [core].[lookup_type] WHERE [code] = N'REASSIGN_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'CUSTOMER_REQUEST', N'Customer request', 5 FROM [core].[lookup_type] WHERE [code] = N'REASSIGN_REASON';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'CALL_CANCEL_REASON', N'Call Cancel Reason', N'Service');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'DUPLICATE', N'Duplicate', 1 FROM [core].[lookup_type] WHERE [code] = N'CALL_CANCEL_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'CUSTOMER_CANCELLED', N'Customer cancelled', 2 FROM [core].[lookup_type] WHERE [code] = N'CALL_CANCEL_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'NOT_REACHABLE', N'Not reachable', 3 FROM [core].[lookup_type] WHERE [code] = N'CALL_CANCEL_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'RESOLVED_ON_PHONE', N'Resolved on phone', 4 FROM [core].[lookup_type] WHERE [code] = N'CALL_CANCEL_REASON';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'ADJUSTMENT_REASON', N'Adjustment Reason', N'Inventory');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'DAMAGE', N'Damage', 1 FROM [core].[lookup_type] WHERE [code] = N'ADJUSTMENT_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'COUNT_DIFFERENCE', N'Count difference', 2 FROM [core].[lookup_type] WHERE [code] = N'ADJUSTMENT_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'EXPIRY', N'Expiry', 3 FROM [core].[lookup_type] WHERE [code] = N'ADJUSTMENT_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'FOUND', N'Found', 4 FROM [core].[lookup_type] WHERE [code] = N'ADJUSTMENT_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'WRITE_OFF', N'Write-off', 5 FROM [core].[lookup_type] WHERE [code] = N'ADJUSTMENT_REASON';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'RETURN_REASON', N'Return Reason', N'Purchase / Sales');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'DAMAGED', N'Damaged', 1 FROM [core].[lookup_type] WHERE [code] = N'RETURN_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'WRONG_ITEM', N'Wrong item', 2 FROM [core].[lookup_type] WHERE [code] = N'RETURN_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'EXCESS', N'Excess', 3 FROM [core].[lookup_type] WHERE [code] = N'RETURN_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'QUALITY_ISSUE', N'Quality issue', 4 FROM [core].[lookup_type] WHERE [code] = N'RETURN_REASON';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'LEAD_APPLICATION', N'Lead Application', N'Pre-Sales');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'MINING', N'Mining', 1 FROM [core].[lookup_type] WHERE [code] = N'LEAD_APPLICATION';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'ROAD_CONSTRUCTION', N'Road construction', 2 FROM [core].[lookup_type] WHERE [code] = N'LEAD_APPLICATION';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'IRRIGATION', N'Irrigation', 3 FROM [core].[lookup_type] WHERE [code] = N'LEAD_APPLICATION';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'BUILDING', N'Building', 4 FROM [core].[lookup_type] WHERE [code] = N'LEAD_APPLICATION';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'QUARRY', N'Quarry', 5 FROM [core].[lookup_type] WHERE [code] = N'LEAD_APPLICATION';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'RENTAL', N'Rental', 6 FROM [core].[lookup_type] WHERE [code] = N'LEAD_APPLICATION';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'ACTIVITY_OUTCOME', N'Activity Outcome', N'Pre-Sales');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'INTERESTED', N'Interested', 1 FROM [core].[lookup_type] WHERE [code] = N'ACTIVITY_OUTCOME';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'DEMO_REQUESTED', N'Demo requested', 2 FROM [core].[lookup_type] WHERE [code] = N'ACTIVITY_OUTCOME';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'QUOTE_REQUESTED', N'Quote requested', 3 FROM [core].[lookup_type] WHERE [code] = N'ACTIVITY_OUTCOME';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'NOT_INTERESTED', N'Not interested', 4 FROM [core].[lookup_type] WHERE [code] = N'ACTIVITY_OUTCOME';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'CALL_BACK', N'Call back', 5 FROM [core].[lookup_type] WHERE [code] = N'ACTIVITY_OUTCOME';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'LOST_REASON', N'Lost Reason', N'Pre-Sales');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'PRICE', N'Price', 1 FROM [core].[lookup_type] WHERE [code] = N'LOST_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'FINANCE_NOT_APPROVED', N'Finance not approved', 2 FROM [core].[lookup_type] WHERE [code] = N'LOST_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'BOUGHT_COMPETITOR', N'Bought competitor', 3 FROM [core].[lookup_type] WHERE [code] = N'LOST_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'POSTPONED', N'Postponed', 4 FROM [core].[lookup_type] WHERE [code] = N'LOST_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'NO_BUDGET', N'No budget', 5 FROM [core].[lookup_type] WHERE [code] = N'LOST_REASON';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'EXPENSE_TYPE', N'Expense Type', N'HR');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'TRAVEL_KM', N'Travel (km)', 1 FROM [core].[lookup_type] WHERE [code] = N'EXPENSE_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'FUEL', N'Fuel', 2 FROM [core].[lookup_type] WHERE [code] = N'EXPENSE_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'FOOD', N'Food', 3 FROM [core].[lookup_type] WHERE [code] = N'EXPENSE_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'LODGING', N'Lodging', 4 FROM [core].[lookup_type] WHERE [code] = N'EXPENSE_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'MOBILE', N'Mobile', 5 FROM [core].[lookup_type] WHERE [code] = N'EXPENSE_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'OTHER', N'Other', 6 FROM [core].[lookup_type] WHERE [code] = N'EXPENSE_TYPE';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'EMPLOYEE_DOCUMENT_TYPE', N'Employee Document Type', N'HR');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'OFFER_LETTER', N'Offer letter', 1 FROM [core].[lookup_type] WHERE [code] = N'EMPLOYEE_DOCUMENT_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'ID_PROOF', N'ID proof', 2 FROM [core].[lookup_type] WHERE [code] = N'EMPLOYEE_DOCUMENT_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'ADDRESS_PROOF', N'Address proof', 3 FROM [core].[lookup_type] WHERE [code] = N'EMPLOYEE_DOCUMENT_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'DRIVING_LICENCE', N'Driving licence', 4 FROM [core].[lookup_type] WHERE [code] = N'EMPLOYEE_DOCUMENT_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'EDUCATION', N'Education', 5 FROM [core].[lookup_type] WHERE [code] = N'EMPLOYEE_DOCUMENT_TYPE';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'ASSET_TYPE', N'Asset Type', N'HR');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'MOBILE_PHONE', N'Mobile phone', 1 FROM [core].[lookup_type] WHERE [code] = N'ASSET_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'LAPTOP', N'Laptop', 2 FROM [core].[lookup_type] WHERE [code] = N'ASSET_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'TOOL_KIT', N'Tool kit', 3 FROM [core].[lookup_type] WHERE [code] = N'ASSET_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'SIM_CARD', N'SIM card', 4 FROM [core].[lookup_type] WHERE [code] = N'ASSET_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'VEHICLE', N'Vehicle', 5 FROM [core].[lookup_type] WHERE [code] = N'ASSET_TYPE';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'HELPDESK_CATEGORY', N'Helpdesk Category', N'HR');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'PAYROLL', N'Payroll', 1 FROM [core].[lookup_type] WHERE [code] = N'HELPDESK_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'LEAVE', N'Leave', 2 FROM [core].[lookup_type] WHERE [code] = N'HELPDESK_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'ATTENDANCE', N'Attendance', 3 FROM [core].[lookup_type] WHERE [code] = N'HELPDESK_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'REIMBURSEMENT', N'Reimbursement', 4 FROM [core].[lookup_type] WHERE [code] = N'HELPDESK_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'IT', N'IT', 5 FROM [core].[lookup_type] WHERE [code] = N'HELPDESK_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'OTHER', N'Other', 6 FROM [core].[lookup_type] WHERE [code] = N'HELPDESK_CATEGORY';

/* Roles */
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'ADMIN', N'Administrator', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'BACK_OFFICE', N'Back office', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'TEAM_LEAD', N'Service Team Lead', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'SERVICE_ENGINEER', N'Service engineer', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'SALESPERSON', N'Salesperson', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'SALES_MANAGER', N'Sales manager', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'BRAND_MANAGER', N'Brand manager', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'WAREHOUSE', N'Warehouse / stores', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'PURCHASE', N'Purchase', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'ACCOUNTS', N'Accounts', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'HR', N'HR', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'MANAGEMENT', N'Management (read only)', 1);

/* Stock movement types (used from Phase 2) */
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'GRN', N'Goods receipt', N'In');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'ISSUE_SERVICE', N'Issue to service call', N'Out');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'ISSUE_INTERNAL', N'Internal issue', N'Out');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'SALE', N'Sales delivery', N'Out');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'SALES_RETURN', N'Sales return', N'In');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'PURCHASE_RETURN', N'Purchase return', N'Out');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'TRANSFER_OUT', N'Transfer out', N'Out');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'TRANSFER_IN', N'Transfer in', N'In');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'ADJUST_IN', N'Adjustment +', N'In');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'ADJUST_OUT', N'Adjustment -', N'Out');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'DEFECTIVE_IN', N'Defective part received', N'In');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'OPENING', N'Opening stock', N'In');

/* Currency */
INSERT INTO [core].[currency] ([code], [name], [symbol], [decimals]) VALUES (N'INR', N'Indian Rupee', N'₹', 2);

COMMIT TRANSACTION;
GO
