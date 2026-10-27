/* =====================================================================
   20_demo_engineer_data.sql
   DEMO ONLY - placeholder contact / joining details for the 3 service
   engineers so screens and reports have data. Replace with real values.
   - Mobiles use the dummy range 90000000xx; emails use @trishul.demo.
   - Only fills fields that are still empty, so real data entered later
     is never overwritten. Re-runnable.
   ===================================================================== */
USE [TrishulDev];
GO
SET NOCOUNT ON;

UPDATE e
SET e.[mobile]          = ISNULL(e.[mobile], d.[mobile]),
    e.[email]           = ISNULL(e.[email], d.[email]),
    e.[date_of_joining] = ISNULL(e.[date_of_joining], d.[date_of_joining]),
    e.[updated_at]      = SYSUTCDATETIME()
FROM [core].[employee] e
JOIN (VALUES
    (N'EMP0001', N'9000000001', N'aswani.sahu@trishul.demo',   CAST('2021-04-01' AS DATE)),
    (N'EMP0002', N'9000000002', N'chinmay.behera@trishul.demo', CAST('2022-07-15' AS DATE)),
    (N'EMP0003', N'9000000003', N'satyajit.tung@trishul.demo',  CAST('2023-01-10' AS DATE))
) AS d([employee_code], [mobile], [email], [date_of_joining]) ON d.[employee_code] = e.[employee_code]
WHERE e.[mobile] IS NULL OR e.[email] IS NULL OR e.[date_of_joining] IS NULL;
PRINT CONCAT(@@ROWCOUNT, N' engineer(s) given demo data.');
GO
