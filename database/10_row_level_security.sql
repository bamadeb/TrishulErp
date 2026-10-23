/* =====================================================================
   TRISHUL Integrated System - SQL Server DDL (dictionary v2)
   Row-level security by brand and branch (created OFF; switch ON after testing)
   Generated from the TRISHUL Database Dictionary. Do not edit by hand:
   change the dictionary and regenerate.
   Target: SQL Server 2019+ / Amazon RDS for SQL Server
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
/*
   How it works
   - The API sets the signed-in user on every connection:
       EXEC sys.sp_set_session_context @key = N'app_user_id', @value = <id>, @read_only = 1;
   - A row is visible when the user is allowed its brand (core.user_principal_access)
     AND its branch (core.user_role with branch_id NULL = all branches, a matching branch,
     or the branch's parent warehouse).
   - Rows with no brand (common items) or no branch are visible to everyone.
   - Users holding the ADMIN, MANAGEMENT or ACCOUNTS role see everything.
   - core and int tables are not filtered (masters and integration jobs), except core.machine_unit.
*/
CREATE FUNCTION [rls].[fn_can_see] (@principal_id BIGINT, @branch_id BIGINT)
RETURNS TABLE
WITH SCHEMABINDING
AS
RETURN
    SELECT 1 AS [ok]
    WHERE
        EXISTS (SELECT 1 FROM [core].[user_role] ur JOIN [core].[role] r ON r.[id] = ur.[role_id]
                WHERE ur.[app_user_id] = CAST(SESSION_CONTEXT(N'app_user_id') AS BIGINT)
                  AND r.[code] IN (N'ADMIN', N'MANAGEMENT', N'ACCOUNTS'))
        OR (
            (@principal_id IS NULL OR EXISTS (
                SELECT 1 FROM [core].[user_principal_access] upa
                WHERE upa.[app_user_id] = CAST(SESSION_CONTEXT(N'app_user_id') AS BIGINT)
                  AND upa.[principal_id] = @principal_id))
            AND
            (@branch_id IS NULL OR EXISTS (
                SELECT 1 FROM [core].[user_role] ur
                JOIN [core].[branch] b ON b.[id] = @branch_id
                WHERE ur.[app_user_id] = CAST(SESSION_CONTEXT(N'app_user_id') AS BIGINT)
                  AND (ur.[branch_id] IS NULL OR ur.[branch_id] = b.[id] OR ur.[branch_id] = b.[parent_warehouse_id])))
        );
GO

CREATE SECURITY POLICY [rls].[brand_branch_policy]
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], NULL) ON [core].[machine_unit],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], NULL) ON [svc].[service_contract],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], NULL) ON [svc].[checklist_template],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [svc].[service_call],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], NULL) ON [svc].[oem_call_reference],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], NULL) ON [svc].[sla_rule],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], NULL) ON [svc].[warranty_claim],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [inv].[stock_issue],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [pur].[purchase_request],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [pur].[purchase_order],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [pur].[grn],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [pur].[supplier_invoice],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], NULL) ON [sal].[price_list],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [sal].[quotation],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [sal].[sales_order],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [sal].[delivery_note],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [sal].[sales_invoice],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], NULL) ON [sal].[credit_note],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [pre].[lead],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [pre].[opportunity],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], NULL) ON [pre].[sop_stage],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [pre].[pipeline_snapshot],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [pre].[sales_target],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [acc].[cost_centre],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [acc].[gl_entry]
WITH (STATE = OFF);
GO

-- Enable after testing:
-- ALTER SECURITY POLICY [rls].[brand_branch_policy] WITH (STATE = ON);
