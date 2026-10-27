/* =====================================================================
   17_odisha_districts_localities.sql
   - Adds state Odisha (GST code 21) and its 30 districts.
   - Adds core.locality: village / town where a machine works and where
     back office sends a service engineer. (core.location is warehouse
     stock locations, so it is not used for this.)
   - Loads the sample machine locations, all in Bhadrak district.
     KRNDUAPADA in the sheet is a typo of KENDUAPADA.
   - Re-runnable.
   ===================================================================== */
USE [TrishulDev];
GO
SET NOCOUNT ON;

-- 1. Locality table --------------------------------------------------------
IF OBJECT_ID(N'[core].[locality]', N'U') IS NULL
BEGIN
    -- Village / town where machines work; used to route service engineers.
    CREATE TABLE [core].[locality] (
        [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_locality] PRIMARY KEY,
        [district_id] BIGINT NOT NULL,
        [name] NVARCHAR(120) NOT NULL,
        [pincode_id] BIGINT NULL,
        [latitude] DECIMAL(9,6) NULL,
        [longitude] DECIMAL(9,6) NULL,
        [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_locality_created_at] DEFAULT (SYSUTCDATETIME()),
        [created_by_user_id] BIGINT NULL,
        [updated_at] DATETIME2(0) NULL,
        [updated_by_user_id] BIGINT NULL,
        [is_active] BIT NOT NULL CONSTRAINT [DF_core_locality_is_active] DEFAULT (1),
        [row_version] ROWVERSION NOT NULL
    );
    CREATE UNIQUE NONCLUSTERED INDEX [UX_core_locality_k1] ON [core].[locality] ([district_id], [name]);
    CREATE NONCLUSTERED INDEX [IX_core_locality_pincode_id] ON [core].[locality] ([pincode_id]);
    ALTER TABLE [core].[locality] ADD CONSTRAINT [FK_core_locality_district_id] FOREIGN KEY ([district_id]) REFERENCES [core].[district] ([id]) ON DELETE NO ACTION;
    ALTER TABLE [core].[locality] ADD CONSTRAINT [FK_core_locality_pincode_id] FOREIGN KEY ([pincode_id]) REFERENCES [core].[pincode] ([id]) ON DELETE NO ACTION;
    ALTER TABLE [core].[locality] ADD CONSTRAINT [FK_core_locality_created_by_user_id] FOREIGN KEY ([created_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
    ALTER TABLE [core].[locality] ADD CONSTRAINT [FK_core_locality_updated_by_user_id] FOREIGN KEY ([updated_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
    EXEC sys.sp_addextendedproperty N'MS_Description', N'Village / town where machines work; used to route service engineers.', N'SCHEMA', N'core', N'TABLE', N'locality';
END
GO

-- Machine site -> locality link.
IF COL_LENGTH(N'core.customer_site', N'locality_id') IS NULL
    ALTER TABLE [core].[customer_site] ADD [locality_id] BIGINT NULL;
GO
IF OBJECT_ID(N'[core].[FK_core_customer_site_locality_id]', N'F') IS NULL
BEGIN
    ALTER TABLE [core].[customer_site] ADD CONSTRAINT [FK_core_customer_site_locality_id] FOREIGN KEY ([locality_id]) REFERENCES [core].[locality] ([id]) ON DELETE NO ACTION;
    CREATE NONCLUSTERED INDEX [IX_core_customer_site_locality_id] ON [core].[customer_site] ([locality_id]);
END
GO

-- 2. State + districts -----------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM [core].[state] WHERE [gst_state_code] = N'21')
    INSERT INTO [core].[state] ([gst_state_code], [name]) VALUES (N'21', N'Odisha');

DECLARE @state_id BIGINT = (SELECT [id] FROM [core].[state] WHERE [gst_state_code] = N'21');

INSERT INTO [core].[district] ([state_id], [name])
SELECT @state_id, v.[name]
FROM (VALUES
    (N'Angul'), (N'Balangir'), (N'Balasore'), (N'Bargarh'), (N'Bhadrak'),
    (N'Boudh'), (N'Cuttack'), (N'Deogarh'), (N'Dhenkanal'), (N'Gajapati'),
    (N'Ganjam'), (N'Jagatsinghpur'), (N'Jajpur'), (N'Jharsuguda'), (N'Kalahandi'),
    (N'Kandhamal'), (N'Kendrapara'), (N'Keonjhar'), (N'Khordha'), (N'Koraput'),
    (N'Malkangiri'), (N'Mayurbhanj'), (N'Nabarangpur'), (N'Nayagarh'), (N'Nuapada'),
    (N'Puri'), (N'Rayagada'), (N'Sambalpur'), (N'Subarnapur'), (N'Sundargarh')
) AS v([name])
WHERE NOT EXISTS (SELECT 1 FROM [core].[district] d WHERE d.[state_id] = @state_id AND d.[name] = v.[name]);
PRINT CONCAT(@@ROWCOUNT, N' district(s) added.');

-- 3. Bhadrak localities ----------------------------------------------------
DECLARE @district_id BIGINT = (SELECT [id] FROM [core].[district] WHERE [state_id] = @state_id AND [name] = N'Bhadrak');

INSERT INTO [core].[locality] ([district_id], [name])
SELECT @district_id, v.[name]
FROM (VALUES
    (N'ADA'), (N'AGARPADA'), (N'AKHUAPADA'), (N'AMBO'), (N'ANANDAPUR'),
    (N'ARADI'), (N'BAGORE'), (N'BAGUDI'), (N'BAINCHA'), (N'BALIKHANDA'),
    (N'BALIMUNDA'), (N'BANSADA'), (N'BANTHA'), (N'BARAPADA'), (N'BASUDEVPUR'),
    (N'BAULA'), (N'BHANDARIPOKHARI'), (N'BIDEIPUR'), (N'CHANDABALI'), (N'DEOGAWN'),
    (N'DHAMARA'), (N'DHENKA'), (N'GHANTESWAR'), (N'HARICHANDANPUR'), (N'JAMUJHADI'),
    (N'JARAKA'), (N'KAJUPAL'), (N'KALAMGADIA'), (N'KAYANGOLA'), (N'KENDUAPADA'),
    (N'KODOPADA'), (N'KUPARI'), (N'MAHUMUHAN'), (N'RANITAL'), (N'SALABANI')
) AS v([name])
WHERE NOT EXISTS (SELECT 1 FROM [core].[locality] l WHERE l.[district_id] = @district_id AND l.[name] = v.[name]);
PRINT CONCAT(@@ROWCOUNT, N' locality(ies) added.');
GO
