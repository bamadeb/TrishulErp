/* =====================================================================
   14_sample_machine_import.sql
   Imports the sample machine serial numbers into core.machine_unit.
   - Model is not known yet, so machines go under the placeholder model
     'UNMAPPED' (Tata Hitachi). Re-point model_id once models are loaded.
   - Duplicates in the source list are ignored; script is re-runnable.
   ===================================================================== */
USE [TrishulDev];
GO
SET NOCOUNT ON;

DECLARE @principal_id BIGINT = (SELECT [id] FROM [core].[principal] WHERE [code] = N'TATA_HITACHI');

IF NOT EXISTS (SELECT 1 FROM [core].[machine_model] WHERE [model_code] = N'UNMAPPED' AND [principal_id] = @principal_id)
    INSERT INTO [core].[machine_model] ([model_code], [model_name], [product_line], [principal_id])
    VALUES (N'UNMAPPED', N'Model not yet identified', N'Other', @principal_id);

DECLARE @model_id BIGINT = (SELECT [id] FROM [core].[machine_model] WHERE [model_code] = N'UNMAPPED' AND [principal_id] = @principal_id);

INSERT INTO [core].[machine_unit] ([serial_number], [model_id], [principal_id], [status])
SELECT DISTINCT s.[serial_number], @model_id, @principal_id, N'Sold'
FROM (VALUES
    (N'S070-16140'), (N'THEDD1L0L00002289'), (N'THEDD1L0V00002290'), (N'SP20-65515'),
    (N'THEDJLL0J00068338'), (N'DMCB1000-657'), (N'THEWAED0HS0000263'), (N'THEWAED0ES0000474'),
    (N'THEWAED0ES0000328'), (N'THEWAED0LS0000424'), (N'THEDJLL0H00050395'), (N'SP20-65666'),
    (N'THEDJLL0V00050540'), (N'P070-21741'), (N'SP20-68256'), (N'B145-2726'),
    (N'THEDJLL0C00068639'), (N'THEDJLL0V00050442'), (N'THEDJLL0C00068446'), (N'TH86-10217'),
    (N'THEDJLL0A00050684'), (N'THEWAED0ES0000474'), (N'THEDE0L0A00000015'), (N'P070-21042'),
    (N'S110-12174'), (N'SP20-68064'), (N'S110-12174'), (N'THEDGML0J00000075'),
    (N'THEWACD0ER0003471')
) AS s([serial_number])
WHERE NOT EXISTS (SELECT 1 FROM [core].[machine_unit] m WHERE m.[serial_number] = s.[serial_number]);

PRINT CONCAT(@@ROWCOUNT, N' machine(s) imported.');
GO
