/* =====================================================================
   16_sample_machine_model_update.sql
   Loads the machine model catalogue and maps machine serials to models
   from the "Machine Sl. No. / M/C MODEL" sample sheet.
   - Sheet is a call log (same machine many times); de-duplicated here.
   - Where one serial had different models on different rows, the model
     on most rows wins (e.g. SP20-68256 -> EX-200 PRIME, 3 of 4 rows).
   - Obvious serial typos are folded into the correct serial:
       THHB200R-10782 / THHB2000R10782 -> THHB2000R-10782
       THHB200R-10783                  -> THHB2000R-10783
       DMCB 1000-657                   -> DMCB1000-657
       THEDJLL0P0050726                -> THEDJLL0P00050726
       THEDGNL0A00000078               -> THEDGML0A0000078
       THEDOLL0H00050395               -> THEDJLL0H00050395
       THEDJL0K00004024                -> THEDHJL0K00004024
   - Model names normalised: TH76 -> TH-76, TH86 -> TH-86,
     SHINRAI -PRIME -> SHINRAI PRIME, SHINRAI -> SHINRAI BX-80.
   - Serials with no model on any row stay on placeholder 'UNMAPPED'.
   - Re-runnable.
   ===================================================================== */
USE [TrishulDev];
GO
SET NOCOUNT ON;

DECLARE @principal_id BIGINT = (SELECT [id] FROM [core].[principal] WHERE [code] = N'TATA_HITACHI');

-- 1. Model catalogue -------------------------------------------------------
INSERT INTO [core].[machine_model] ([model_code], [model_name], [product_line], [principal_id])
SELECT v.[model_code], v.[model_code], v.[product_line], @principal_id
FROM (VALUES
    (N'EX-70',          N'Excavator'),
    (N'EX-70 PRIME',    N'Excavator'),
    (N'EX-70 SUPER',    N'Excavator'),
    (N'EX-70 SUPER+',   N'Excavator'),
    (N'EX-110 SUPER',   N'Excavator'),
    (N'EX-130 SUPER+',  N'Excavator'),
    (N'EX-200 INFRA',   N'Excavator'),
    (N'EX-200 PRIME',   N'Excavator'),
    (N'EX-200 SUPER+',  N'Excavator'),
    (N'EX-210 INFRA',   N'Excavator'),
    (N'EX-210 PRIME',   N'Excavator'),
    (N'EX-210 SUPER',   N'Excavator'),
    (N'EX-210 SUPER+',  N'Excavator'),
    (N'EX-350 PRIME',   N'Excavator'),
    (N'ZX-80',          N'Excavator'),
    (N'ZX-120',         N'Excavator'),
    (N'ZX-140',         N'Excavator'),
    (N'ZX-140 M',       N'Excavator'),
    (N'ZX-140 U',       N'Excavator'),
    (N'ZX-220 M',       N'Excavator'),
    (N'ZX-370',         N'Excavator'),
    (N'NX-80',          N'Excavator'),
    (N'SHINRAI PRIME',  N'Backhoe loader'),
    (N'SHINRAI BX-80',  N'Backhoe loader'),
    (N'TH-76',          N'Backhoe loader'),
    (N'TH-86',          N'Backhoe loader'),
    (N'TMX-20 SUPER',   N'Backhoe loader'),
    (N'ZW-225',         N'Wheel loader'),
    (N'TL-340H',        N'Wheel loader'),
    (N'TATA 315 V',     N'Other'),
    (N'CLAMSHELL',      N'Other')
) AS v([model_code], [product_line])
WHERE NOT EXISTS (SELECT 1 FROM [core].[machine_model] m WHERE m.[model_code] = v.[model_code] AND m.[principal_id] = @principal_id);
PRINT CONCAT(@@ROWCOUNT, N' model(s) added.');

-- 2. Serial -> model (NULL = model not given in sheet) ---------------------
DECLARE @src TABLE ([serial_number] NVARCHAR(40) PRIMARY KEY, [model_code] NVARCHAR(20) NULL);
INSERT INTO @src VALUES
    -- machines already loaded by script 14
    (N'B145-2726', NULL),                 (N'DMCB1000-657', N'CLAMSHELL'),
    (N'P070-21042', NULL),                (N'P070-21741', N'EX-70 PRIME'),
    (N'S070-16140', NULL),                (N'S110-12174', NULL),
    (N'SP20-65515', NULL),                (N'SP20-65666', N'EX-200 SUPER+'),
    (N'SP20-68064', N'EX-200 SUPER+'),    (N'SP20-68256', N'EX-200 PRIME'),
    (N'TH86-10217', N'TH-86'),            (N'THEDD1L0L00002289', N'ZX-370'),
    (N'THEDD1L0V00002290', N'ZX-370'),    (N'THEDE0L0A00000015', N'NX-80'),
    (N'THEDGML0J00000075', N'EX-350 PRIME'), (N'THEDJLL0A00050684', N'EX-200 SUPER+'),
    (N'THEDJLL0C00068446', N'EX-210 PRIME'), (N'THEDJLL0C00068639', N'EX-210 PRIME'),
    (N'THEDJLL0H00050395', N'EX-210 PRIME'), (N'THEDJLL0J00068338', N'ZX-370'),
    (N'THEDJLL0V00050442', N'EX-210 PRIME'), (N'THEDJLL0V00050540', N'EX-200 PRIME'),
    (N'THEWACD0ER0003471', NULL),         (N'THEWAED0ES0000328', N'SHINRAI PRIME'),
    (N'THEWAED0ES0000474', N'SHINRAI PRIME'), (N'THEWAED0HS0000263', N'SHINRAI PRIME'),
    (N'THEWAED0LS0000424', N'SHINRAI PRIME'),
    -- new serials, model not given
    (N'THEWBHK0HL0000377', NULL),         (N'TH86-10632', NULL),
    (N'SP13-14094', NULL),                (N'SP21-85175', NULL),
    (N'THEWACD0JP0002437', NULL),         (N'SP07-18732', NULL),
    (N'THEWABD0TK0000489', NULL),         (N'P070-21328', NULL),
    (N'THEDJLL0C00068320', NULL),         (N'01S1-051885', NULL),
    (N'SP07-18972', NULL),                (N'SP21-63156', NULL),
    (N'SP21-62796', NULL),                (N'SP07-19146', NULL),
    (N'SP07-19154', NULL),
    -- new serials with model
    (N'P070-20062', N'EX-70 PRIME'),      (N'P070-21144', N'EX-70 PRIME'),
    (N'0703-4982', N'EX-70'),             (N'S070-15275', N'EX-70 SUPER'),
    (N'S070-15334', N'EX-70 SUPER'),      (N'S070-16406', N'EX-70 SUPER'),
    (N'S070-17205', N'EX-70 SUPER'),      (N'SP07-18560', N'EX-70 SUPER+'),
    (N'SP07-18946', N'EX-70 SUPER+'),     (N'SP07-18985', N'EX-70 SUPER+'),
    (N'SP07-19156', N'EX-70 SUPER+'),     (N'S110-12241', N'EX-110 SUPER'),
    (N'SP13-14994', N'EX-130 SUPER+'),    (N'SP20-68271', N'EX-200 INFRA'),
    (N'THEDJLL0H00050672', N'EX-200 PRIME'), (N'SP21-85142', N'EX-210 PRIME'),
    (N'SP21-85218', N'EX-210 PRIME'),     (N'THEDJLL0C00050660', N'EX-210 PRIME'),
    (N'THEDJLL0C00068630', N'EX-210 PRIME'), (N'THEDJLL0P00050726', N'EX-210 PRIME'),
    (N'S210-56090', N'EX-210 SUPER+'),    (N'S210-56215', N'EX-210 SUPER+'),
    (N'SP21-46605', N'EX-210 SUPER+'),    (N'SP21-46619', N'EX-210 SUPER+'),
    (N'SP21-60576', N'EX-210 SUPER+'),    (N'SP21-61088', N'EX-210 SUPER+'),
    (N'SP21-61107', N'EX-210 SUPER+'),    (N'SP21-63444', N'EX-210 SUPER+'),
    (N'SP21-63446', N'EX-210 SUPER+'),    (N'SP21-63457', N'EX-210 SUPER+'),
    (N'THEDGML0A0000078', N'EX-350 PRIME'), (N'THEDGML0L00000034', N'EX-350 PRIME'),
    (N'THEDGML0V00000077', N'EX-350 PRIME'), (N'THEDEKL0E00000239', N'ZX-80'),
    (N'01S1-053306', N'ZX-120'),          (N'01S1-053600', N'ZX-120'),
    (N'THEDA0L0V00002521', N'ZX-140 M'),  (N'THEDHJL0K00004024', N'ZX-140 U'),
    (N'THEDC0L0V00000570', N'ZX-220 M'),  (N'THEDD1L0J00002254', N'ZX-370'),
    (N'THEDD1L0J00002271', N'ZX-370'),    (N'THEZFLZH00002246', N'ZX-370'),
    (N'THEWAED0ES0000326', N'SHINRAI PRIME'), (N'THEWACD0CM000466', N'SHINRAI PRIME'),
    (N'THEWACD0CR0003690', N'SHINRAI PRIME'), (N'THEWABD0TL0001689', N'SHINRAI BX-80'),
    (N'TH76-10731', N'TH-76'),            (N'TH76-10830', N'TH-76'),
    (N'TH76-10832', N'TH-76'),            (N'SP02-5576', N'TMX-20 SUPER'),
    (N'THENUDL0PS0000025', N'ZW-225'),    (N'THEWBHK0EL0000381', N'TL-340H'),
    (N'315 V 8345', N'TATA 315 V'),       (N'THHB2000R-10781', N'CLAMSHELL'),
    (N'THHB2000R-10782', N'CLAMSHELL'),   (N'THHB2000R-10783', N'CLAMSHELL');

DECLARE @unmapped_id BIGINT = (SELECT [id] FROM [core].[machine_model] WHERE [model_code] = N'UNMAPPED' AND [principal_id] = @principal_id);

-- 3. Update model on machines already present -----------------------------
UPDATE u
SET u.[model_id] = m.[id], u.[updated_at] = SYSUTCDATETIME()
FROM [core].[machine_unit] u
JOIN @src s ON s.[serial_number] = u.[serial_number]
JOIN [core].[machine_model] m ON m.[model_code] = s.[model_code] AND m.[principal_id] = @principal_id
WHERE u.[model_id] <> m.[id];
PRINT CONCAT(@@ROWCOUNT, N' existing machine(s) updated with model.');

-- 4. Insert new machines ---------------------------------------------------
INSERT INTO [core].[machine_unit] ([serial_number], [model_id], [principal_id], [status])
SELECT s.[serial_number], ISNULL(m.[id], @unmapped_id), @principal_id, N'Sold'
FROM @src s
LEFT JOIN [core].[machine_model] m ON m.[model_code] = s.[model_code] AND m.[principal_id] = @principal_id
WHERE NOT EXISTS (SELECT 1 FROM [core].[machine_unit] u WHERE u.[serial_number] = s.[serial_number]);
PRINT CONCAT(@@ROWCOUNT, N' new machine(s) added.');
GO
