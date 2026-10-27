/* =====================================================================
   15_sample_customer_import.sql
   Imports the sample customer list into core.customer + core.contact.
   - Source sheet repeats customers per call; de-duplicated to 49 customers.
   - The most-used number becomes customer.primary_phone; every distinct
     number is also stored as a core.contact row (is_primary = 1 for main).
   - SURENDRA PARIDA and PRATAP KUMAR BISWAL had no number in the sheet:
     primary_phone is left blank and no contact row is created.
   - customer_type is inferred from the name (PVT LTD = Company,
     firm names = Contractor, person names = Individual).
   - Re-runnable: existing customers (by name) and contacts are skipped.
   ===================================================================== */
USE [TrishulDev];
GO
SET NOCOUNT ON;

-- Group companies. Sample customers belong to Trishul.
INSERT INTO [core].[company] ([code], [legal_name])
SELECT v.[code], v.[legal_name]
FROM (VALUES (N'TRISHUL', N'Trishul'), (N'KASHI', N'Kashi Sales')) AS v([code], [legal_name])
WHERE NOT EXISTS (SELECT 1 FROM [core].[company] c WHERE c.[code] = v.[code]);

DECLARE @company_id BIGINT = (SELECT [id] FROM [core].[company] WHERE [code] = N'TRISHUL');

DECLARE @src TABLE ([code] NVARCHAR(20), [name] NVARCHAR(200), [customer_type] NVARCHAR(30), [phone] NVARCHAR(15), [is_primary] BIT);
INSERT INTO @src VALUES
    (N'CUST0001', N'SAMBIT KUMAR JENA',             N'Individual', N'6370169434', 1),
    (N'CUST0002', N'SAMAL BROTHERS',                N'Contractor', N'7381398288', 1),
    (N'CUST0003', N'SBB CONSTRUCTION PVT LTD',      N'Company',    N'9583552857', 1),
    (N'CUST0003', N'SBB CONSTRUCTION PVT LTD',      N'Company',    N'7847059127', 0),
    (N'CUST0003', N'SBB CONSTRUCTION PVT LTD',      N'Company',    N'8455957437', 0),
    (N'CUST0003', N'SBB CONSTRUCTION PVT LTD',      N'Company',    N'6372478737', 0),
    (N'CUST0003', N'SBB CONSTRUCTION PVT LTD',      N'Company',    N'9124377377', 0),
    (N'CUST0003', N'SBB CONSTRUCTION PVT LTD',      N'Company',    N'6371774843', 0),
    (N'CUST0003', N'SBB CONSTRUCTION PVT LTD',      N'Company',    N'6370523066', 0),
    (N'CUST0003', N'SBB CONSTRUCTION PVT LTD',      N'Company',    N'9124367377', 0),
    (N'CUST0003', N'SBB CONSTRUCTION PVT LTD',      N'Company',    N'6371535011', 0),
    (N'CUST0003', N'SBB CONSTRUCTION PVT LTD',      N'Company',    N'9337744865', 0),
    (N'CUST0003', N'SBB CONSTRUCTION PVT LTD',      N'Company',    N'9937957549', 0),
    (N'CUST0003', N'SBB CONSTRUCTION PVT LTD',      N'Company',    N'9853278537', 0),
    (N'CUST0004', N'RABINDRA KUMAR SAHOO',          N'Individual', N'6371201106', 1),
    (N'CUST0004', N'RABINDRA KUMAR SAHOO',          N'Individual', N'9178888555', 0),
    (N'CUST0005', N'BIPLAB KUMAR PANDA',            N'Individual', N'9938103531', 1),
    (N'CUST0006', N'LAXMAN MISHRA',                 N'Individual', N'7008848102', 1),
    (N'CUST0007', N'NOVEL HOTMIX PLANT PVT LTD',    N'Company',    N'8984015141', 1),
    (N'CUST0007', N'NOVEL HOTMIX PLANT PVT LTD',    N'Company',    N'9668717222', 0),
    (N'CUST0008', N'SHRADDHA EARTH MOVERS',         N'Contractor', N'8260800608', 1),
    (N'CUST0009', N'SARAT KUMAR SAMAL',             N'Individual', N'9373713587', 1),
    (N'CUST0009', N'SARAT KUMAR SAMAL',             N'Individual', N'9827916841', 0),
    (N'CUST0010', N'BISWAJIT ROUT',                 N'Individual', N'7077105654', 1),
    (N'CUST0011', N'MEGMA ENTERPRISES',             N'Contractor', N'8658337947', 1),
    (N'CUST0012', N'GOURAV CONSTRUCTION',           N'Contractor', N'9937503808', 1),
    (N'CUST0013', N'SIDHESWAR JANA',                N'Individual', N'9937448939', 1),
    (N'CUST0013', N'SIDHESWAR JANA',                N'Individual', N'8328855397', 0),
    (N'CUST0014', N'NIRMAL CHANDRA ROUT',           N'Individual', N'6370862627', 1),
    (N'CUST0014', N'NIRMAL CHANDRA ROUT',           N'Individual', N'6370783437', 0),
    (N'CUST0015', N'ARYAN CONSTRUCTION & COMMERCE', N'Contractor', N'7281000007', 1),
    (N'CUST0015', N'ARYAN CONSTRUCTION & COMMERCE', N'Contractor', N'8144032536', 0),
    (N'CUST0016', N'NAROTTAM MAHIMA JENA',          N'Individual', N'9556977341', 1),
    (N'CUST0017', N'ABHIJIT SWAIN',                 N'Individual', N'9348902129', 1),
    (N'CUST0018', N'RCB ENTERPRISES',               N'Contractor', N'9853278537', 1),
    (N'CUST0019', N'SHUBHENDU BHUSAN BEHERA',       N'Individual', N'8847843059', 1),
    (N'CUST0019', N'SHUBHENDU BHUSAN BEHERA',       N'Individual', N'9583164164', 0),
    (N'CUST0019', N'SHUBHENDU BHUSAN BEHERA',       N'Individual', N'6371774843', 0),
    (N'CUST0020', N'MAA MANASHA ASSOCIATES',        N'Contractor', N'9937311236', 1),
    (N'CUST0021', N'KAMALAKANTA LENKA',             N'Individual', N'7978714920', 1),
    (N'CUST0022', N'TAPAN KUMAR PADHI',             N'Individual', N'8328829349', 1),
    (N'CUST0023', N'SHASADHAR BISWAL',              N'Individual', N'9439621405', 1),
    (N'CUST0023', N'SHASADHAR BISWAL',              N'Individual', N'8329031428', 0),
    (N'CUST0024', N'MAHESWAR DAS',                  N'Individual', N'6370428032', 1),
    (N'CUST0025', N'PRANAB KUMAR DAS',              N'Individual', N'6370051425', 1),
    (N'CUST0026', N'SHANTILATA ROUT',               N'Individual', N'8457926691', 1),
    (N'CUST0027', N'SUCHARITA DAS',                 N'Individual', N'8260792968', 1),
    (N'CUST0028', N'SUDHAKAR NAYAK',                N'Individual', N'9437884128', 1),
    (N'CUST0029', N'SARBESWAR BARIK',               N'Individual', N'8456824446', 1),
    (N'CUST0030', N'PRATAP CHANDRA MOHAPATRA',      N'Individual', N'7608905631', 1),
    (N'CUST0031', N'BIBEKANANDA ROUT',              N'Individual', N'7077105654', 1),
    (N'CUST0032', N'LAXMINARAYAN CONSTRUCTION',     N'Contractor', N'9556079064', 1),
    (N'CUST0033', N'SHREE STEVEDORES PVT LTD',      N'Company',    N'7008608110', 1),
    (N'CUST0034', N'PRAKASH KUMAR MOHAPATRA',       N'Individual', N'6370401464', 1),
    (N'CUST0035', N'RABINDRA SAMAL',                N'Individual', N'9078032008', 1),
    (N'CUST0036', N'NARAYAN PRASAD JENA',           N'Individual', N'9938480796', 1),
    (N'CUST0036', N'NARAYAN PRASAD JENA',           N'Individual', N'7608023585', 0),
    (N'CUST0037', N'NITYANANDA PAHI',               N'Individual', N'9439882178', 1),
    (N'CUST0038', N'SURENDRA PARIDA',               N'Individual', NULL,          1),
    (N'CUST0039', N'RAJESH KUMAR SUTAR',            N'Individual', N'9438759277', 1),
    (N'CUST0040', N'NARENDRANATH DHAR',             N'Individual', N'9777864951', 1),
    (N'CUST0041', N'RAMA KRISHNA INFRA',            N'Contractor', N'9414625059', 1),
    (N'CUST0041', N'RAMA KRISHNA INFRA',            N'Contractor', N'9829185880', 0),
    (N'CUST0042', N'UMESH MAHUNTA',                 N'Individual', N'6370619498', 1),
    (N'CUST0043', N'HARIHAR LENKA',                 N'Individual', N'8658999996', 1),
    (N'CUST0044', N'JAGA BALIA STONE CRUSHER',      N'Contractor', N'9556977341', 1),
    (N'CUST0045', N'BANAMALI BEHERA',               N'Individual', N'7855821196', 1),
    (N'CUST0046', N'PRATAP KUMAR BISWAL',           N'Individual', NULL,          1),
    (N'CUST0047', N'RAJESH KUMAR MOHAPATRA',        N'Individual', N'6372796113', 1),
    (N'CUST0048', N'SMC INFRASTRUCTURE',            N'Contractor', N'8159922164', 1),
    (N'CUST0049', N'HARAPARBATI CONSTRUCTION',      N'Contractor', N'7894449241', 1);

INSERT INTO [core].[customer] ([company_id], [code], [name], [customer_type], [primary_phone])
SELECT @company_id, s.[code], s.[name], s.[customer_type], ISNULL(s.[phone], N'')
FROM @src s
WHERE s.[is_primary] = 1
  AND NOT EXISTS (SELECT 1 FROM [core].[customer] c WHERE c.[name] = s.[name] OR c.[code] = s.[code]);
PRINT CONCAT(@@ROWCOUNT, N' customer(s) imported.');

INSERT INTO [core].[contact] ([customer_id], [name], [phone], [is_primary])
SELECT c.[id], s.[name], s.[phone], s.[is_primary]
FROM @src s
JOIN [core].[customer] c ON c.[code] = s.[code]
WHERE s.[phone] IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM [core].[contact] x WHERE x.[customer_id] = c.[id] AND x.[phone] = s.[phone]);
PRINT CONCAT(@@ROWCOUNT, N' contact number(s) imported.');
GO
