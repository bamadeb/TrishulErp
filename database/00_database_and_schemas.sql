/* =====================================================================
   TRISHUL Integrated System - database and schemas
   Run once as a login with CREATE DATABASE rights.
   ===================================================================== */
IF DB_ID(N'TrishulDev') IS NULL
BEGIN
    CREATE DATABASE [TrishulDev];
END
GO
ALTER DATABASE [TrishulDev] SET READ_COMMITTED_SNAPSHOT ON WITH ROLLBACK IMMEDIATE;
GO
USE [TrishulDev];
GO
IF SCHEMA_ID(N'core') IS NULL EXEC(N'CREATE SCHEMA [core] AUTHORIZATION [dbo]');
GO
IF SCHEMA_ID(N'svc') IS NULL EXEC(N'CREATE SCHEMA [svc] AUTHORIZATION [dbo]');
GO
IF SCHEMA_ID(N'inv') IS NULL EXEC(N'CREATE SCHEMA [inv] AUTHORIZATION [dbo]');
GO
IF SCHEMA_ID(N'pur') IS NULL EXEC(N'CREATE SCHEMA [pur] AUTHORIZATION [dbo]');
GO
IF SCHEMA_ID(N'sal') IS NULL EXEC(N'CREATE SCHEMA [sal] AUTHORIZATION [dbo]');
GO
IF SCHEMA_ID(N'pre') IS NULL EXEC(N'CREATE SCHEMA [pre] AUTHORIZATION [dbo]');
GO
IF SCHEMA_ID(N'hr') IS NULL EXEC(N'CREATE SCHEMA [hr] AUTHORIZATION [dbo]');
GO
IF SCHEMA_ID(N'acc') IS NULL EXEC(N'CREATE SCHEMA [acc] AUTHORIZATION [dbo]');
GO
IF SCHEMA_ID(N'int') IS NULL EXEC(N'CREATE SCHEMA [int] AUTHORIZATION [dbo]');
GO
IF SCHEMA_ID(N'rls') IS NULL EXEC(N'CREATE SCHEMA [rls] AUTHORIZATION [dbo]');
GO
