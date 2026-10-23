/* =====================================================================
   TRISHUL Integrated System - SQL Server DDL (dictionary v2)
   Extra indexes for common screens and reports
   Generated from the TRISHUL Database Dictionary. Do not edit by hand:
   change the dictionary and regenerate.
   Target: SQL Server 2019+ / Amazon RDS for SQL Server
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

/* Service call board: open calls by branch/brand/status */
CREATE NONCLUSTERED INDEX [IX_svc_service_call_board] ON [svc].[service_call] ([principal_id], [branch_id], [current_status]) INCLUDE ([received_at], [assigned_engineer_id], [sla_due_at]);
/* Engineer's own calls on the mobile app */
CREATE NONCLUSTERED INDEX [IX_svc_service_call_engineer] ON [svc].[service_call] ([assigned_engineer_id], [current_status]);
/* GPS points by trip and time (table should be partitioned by month on recorded_at in production) */
CREATE NONCLUSTERED INDEX [IX_svc_trip_gps_point_time] ON [svc].[trip_gps_point] ([trip_id], [recorded_at]);
/* Stock ledger by item and date */
CREATE NONCLUSTERED INDEX [IX_inv_stock_move_item_date] ON [inv].[stock_move] ([item_id], [location_id], [move_at]);
/* Ledger by account and date */
CREATE NONCLUSTERED INDEX [IX_acc_gl_entry_account_date] ON [acc].[gl_entry] ([gl_account_id], [entry_date]) INCLUDE ([debit], [credit], [principal_id], [branch_id]);
/* Brand-wise sales */
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_brand_date] ON [sal].[sales_invoice] ([principal_id], [invoice_date]) INCLUDE ([branch_id], [total], [status]);
GO
