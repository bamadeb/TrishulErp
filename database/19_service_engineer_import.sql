/* =====================================================================
   19_service_engineer_import.sql
   Imports the service engineers from the sample call sheet into
   core.employee (3 engineers; sheet repeats them per call).
   Creates the masters they need:
   - Branch BHADRAK (Trishul, Odisha / Bhadrak district)
   - Department SERVICE, designation SERVICE_ENG
   Placeholders to fill later: mobile (NULL), employee_type 'Permanent',
   date_of_joining.
   core.employee.mobile is made nullable (unique only when entered) so
   staff can be loaded before their numbers are known. Re-runnable.
   ===================================================================== */
USE [TrishulDev];
GO
SET NOCOUNT ON;

IF EXISTS (SELECT 1 FROM sys.columns WHERE [object_id] = OBJECT_ID(N'core.employee') AND [name] = N'mobile' AND [is_nullable] = 0)
BEGIN
    DROP INDEX [UX_core_employee_mobile] ON [core].[employee];
    ALTER TABLE [core].[employee] ALTER COLUMN [mobile] NVARCHAR(15) NULL;
    CREATE UNIQUE NONCLUSTERED INDEX [UX_core_employee_mobile] ON [core].[employee] ([mobile]) WHERE [mobile] IS NOT NULL;
END
GO

DECLARE @company_id  BIGINT = (SELECT [id] FROM [core].[company] WHERE [code] = N'TRISHUL');
DECLARE @state_id    BIGINT = (SELECT [id] FROM [core].[state] WHERE [gst_state_code] = N'21');
DECLARE @district_id BIGINT = (SELECT [id] FROM [core].[district] WHERE [state_id] = @state_id AND [name] = N'Bhadrak');

IF NOT EXISTS (SELECT 1 FROM [core].[branch] WHERE [code] = N'BHADRAK')
    INSERT INTO [core].[branch] ([company_id], [code], [name], [branch_type], [state_id], [district_id])
    VALUES (@company_id, N'BHADRAK', N'Bhadrak', N'Branch', @state_id, @district_id);

IF NOT EXISTS (SELECT 1 FROM [hr].[department] WHERE [code] = N'SERVICE')
    INSERT INTO [hr].[department] ([code], [name]) VALUES (N'SERVICE', N'Service');

DECLARE @branch_id     BIGINT = (SELECT [id] FROM [core].[branch] WHERE [code] = N'BHADRAK');
DECLARE @department_id BIGINT = (SELECT [id] FROM [hr].[department] WHERE [code] = N'SERVICE');

IF NOT EXISTS (SELECT 1 FROM [hr].[designation] WHERE [code] = N'SERVICE_ENG')
    INSERT INTO [hr].[designation] ([code], [name], [department_id]) VALUES (N'SERVICE_ENG', N'Service Engineer', @department_id);

DECLARE @designation_id BIGINT = (SELECT [id] FROM [hr].[designation] WHERE [code] = N'SERVICE_ENG');

INSERT INTO [core].[employee] ([company_id], [employee_code], [first_name], [last_name], [mobile], [branch_id], [department_id], [designation_id], [employee_type])
SELECT @company_id, v.[employee_code], v.[first_name], v.[last_name], NULL, @branch_id, @department_id, @designation_id, N'Permanent'
FROM (VALUES
    (N'EMP0001', N'ASWANI KUMAR', N'SAHU'),
    (N'EMP0002', N'CHINMAY',      N'BEHERA'),
    (N'EMP0003', N'SATYAJIT',     N'TUNG')
) AS v([employee_code], [first_name], [last_name])
WHERE NOT EXISTS (SELECT 1 FROM [core].[employee] e WHERE e.[employee_code] = v.[employee_code]
                                                       OR (e.[first_name] = v.[first_name] AND e.[last_name] = v.[last_name]));
PRINT CONCAT(@@ROWCOUNT, N' engineer(s) imported.');
GO
