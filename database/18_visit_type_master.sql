/* =====================================================================
   18_visit_type_master.sql
   - Adds the "Type of visit" master (lookup VISIT_TYPE) from the sample
     call sheet: MSI, M/W, G/W, ASC, PAID, SPE, VWO, FSC, ASI.
   - Adds svc.service_call.visit_type_lookup_id so each call records it.
     Kept separate from coverage_type (Warranty / Contract / Chargeable /
     Goodwill), which stays the billing roll-up.
   - Labels = codes as used by back office; expand once meanings are
     confirmed. Re-runnable.
   ===================================================================== */
USE [TrishulDev];
GO
SET NOCOUNT ON;

IF NOT EXISTS (SELECT 1 FROM [core].[lookup_type] WHERE [code] = N'VISIT_TYPE')
    INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'VISIT_TYPE', N'Type of Visit', N'Service');

INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order])
SELECT t.[id], v.[code], v.[label], v.[sort_order]
FROM [core].[lookup_type] t
CROSS JOIN (VALUES
    (N'MSI',  N'MSI',  1),
    (N'M/W',  N'M/W',  2),
    (N'G/W',  N'G/W',  3),
    (N'ASC',  N'ASC',  4),
    (N'PAID', N'Paid', 5),
    (N'SPE',  N'SPE',  6),
    (N'VWO',  N'VWO',  7),
    (N'FSC',  N'FSC',  8),
    (N'ASI',  N'ASI',  9)
) AS v([code], [label], [sort_order])
WHERE t.[code] = N'VISIT_TYPE'
  AND NOT EXISTS (SELECT 1 FROM [core].[lookup_value] x WHERE x.[lookup_type_id] = t.[id] AND x.[code] = v.[code]);
PRINT CONCAT(@@ROWCOUNT, N' visit type(s) added.');
GO

-- Provisional descriptions + coverage roll-up (to be confirmed by back office).
-- COVERAGE_TYPE codes match svc.service_call.coverage_type values; each
-- visit type points to its coverage via parent_value_id.
IF NOT EXISTS (SELECT 1 FROM [core].[lookup_type] WHERE [code] = N'COVERAGE_TYPE')
    INSERT INTO [core].[lookup_type] ([code], [name], [module], [is_editable]) VALUES (N'COVERAGE_TYPE', N'Coverage Type', N'Service', 0);

INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order])
SELECT t.[id], v.[code], v.[code], v.[sort_order]
FROM [core].[lookup_type] t
CROSS JOIN (VALUES (N'Warranty', 1), (N'Contract', 2), (N'Chargeable', 3), (N'Goodwill', 4)) AS v([code], [sort_order])
WHERE t.[code] = N'COVERAGE_TYPE'
  AND NOT EXISTS (SELECT 1 FROM [core].[lookup_value] x WHERE x.[lookup_type_id] = t.[id] AND x.[code] = v.[code]);

UPDATE vt
SET vt.[label] = m.[label],
    vt.[parent_value_id] = cv.[id],
    vt.[updated_at] = SYSUTCDATETIME()
FROM [core].[lookup_value] vt
JOIN [core].[lookup_type] t ON t.[id] = vt.[lookup_type_id] AND t.[code] = N'VISIT_TYPE'
JOIN (VALUES
    (N'M/W',  N'M/W - Manufacturer warranty',      N'Warranty'),
    (N'G/W',  N'G/W - Goodwill warranty',          N'Goodwill'),
    (N'ASC',  N'ASC - Annual service contract',    N'Contract'),
    (N'PAID', N'Paid - Chargeable visit',          N'Chargeable'),
    (N'FSC',  N'FSC - Free service coupon',        N'Warranty'),
    (N'MSI',  N'MSI - Machine service inspection', NULL)
) AS m([code], [label], [coverage]) ON m.[code] = vt.[code]
LEFT JOIN [core].[lookup_value] cv
    ON cv.[code] = m.[coverage]
   AND cv.[lookup_type_id] = (SELECT [id] FROM [core].[lookup_type] WHERE [code] = N'COVERAGE_TYPE')
WHERE vt.[label] <> m.[label] OR ISNULL(vt.[parent_value_id], 0) <> ISNULL(cv.[id], 0);
PRINT CONCAT(@@ROWCOUNT, N' visit type(s) described.');
GO

IF COL_LENGTH(N'svc.service_call', N'visit_type_lookup_id') IS NULL
    ALTER TABLE [svc].[service_call] ADD [visit_type_lookup_id] BIGINT NULL;
GO
IF OBJECT_ID(N'[svc].[FK_svc_service_call_visit_type_lookup_id]', N'F') IS NULL
BEGIN
    ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_visit_type_lookup_id] FOREIGN KEY ([visit_type_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
    CREATE NONCLUSTERED INDEX [IX_svc_service_call_visit_type_lookup_id] ON [svc].[service_call] ([visit_type_lookup_id]);
    EXEC sys.sp_addextendedproperty N'MS_Description', N'Type of visit: MSI, M/W, G/W, ASC, Paid...', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'visit_type_lookup_id';
END
GO
