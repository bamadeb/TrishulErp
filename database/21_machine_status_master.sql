/* =====================================================================
   21_machine_status_master.sql
   "Present Status of M/C" from the sample call sheet: RUNNING, B/D.
   - Reuses the existing MACHINE_CONDITION lookup (seeded in 09, used by
     svc.service_report) instead of creating a duplicate list. Labels are
     aligned to back-office terms; codes are unchanged:
       WORKING            -> Running
       WORKING_WITH_ISSUE -> Running with issue
       BREAKDOWN          -> Breakdown (B/D)
   - Adds core.machine_unit.current_condition_lookup_id so each machine
     carries its latest status (set from the last service report).
   - Re-runnable.
   ===================================================================== */
USE [TrishulDev];
GO
SET NOCOUNT ON;

UPDATE v
SET v.[label] = m.[label], v.[updated_at] = SYSUTCDATETIME()
FROM [core].[lookup_value] v
JOIN [core].[lookup_type] t ON t.[id] = v.[lookup_type_id] AND t.[code] = N'MACHINE_CONDITION'
JOIN (VALUES
    (N'WORKING',            N'Running'),
    (N'WORKING_WITH_ISSUE', N'Running with issue'),
    (N'BREAKDOWN',          N'Breakdown (B/D)')
) AS m([code], [label]) ON m.[code] = v.[code]
WHERE v.[label] <> m.[label];
PRINT CONCAT(@@ROWCOUNT, N' machine status label(s) updated.');
GO

IF COL_LENGTH(N'core.machine_unit', N'current_condition_lookup_id') IS NULL
    ALTER TABLE [core].[machine_unit] ADD [current_condition_lookup_id] BIGINT NULL;
GO
IF OBJECT_ID(N'[core].[FK_core_machine_unit_current_condition_lookup_id]', N'F') IS NULL
BEGIN
    ALTER TABLE [core].[machine_unit] ADD CONSTRAINT [FK_core_machine_unit_current_condition_lookup_id] FOREIGN KEY ([current_condition_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
    CREATE NONCLUSTERED INDEX [IX_core_machine_unit_current_condition_lookup_id] ON [core].[machine_unit] ([current_condition_lookup_id]);
    EXEC sys.sp_addextendedproperty N'MS_Description', N'Present status of machine: Running / Breakdown (B/D)', N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'current_condition_lookup_id';
END
GO
