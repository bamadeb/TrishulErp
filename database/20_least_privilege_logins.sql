/* =====================================================================
   TRISHUL ERP - least-privilege SQL Server logins
   ---------------------------------------------------------------------
   Replaces the RDS master user ("admin") for day-to-day use:
     * trishul_app       - the API login: data rights only, subject to
                           row-level security.
     * trishul_migrator  - the migration login: DDL rights, used only by
                           `alembic upgrade head`.

   HOW TO USE
     1. Run this as a sysadmin / the RDS master user, once per environment.
     2. Replace <APP_PASSWORD> and <MIGRATION_PASSWORD> below with strong
        passwords (do NOT commit them).
     3. Put the SAME password in the matching Secrets Manager secret, in the
        RDS JSON format (see docs/Trishul_Secrets_Manager.md §3):
            trishul_app       -> trishul/<env>/db-app        (username "trishul_app")
            trishul_migrator  -> trishul/<env>/db-migration  (username "trishul_migrator")
     4. Point the app at the app secret (TRISHUL_DB_SECRET_ID) and, for
        migrations, TRISHUL_MIGRATION_DB_SECRET_ID.

   Change USE [TrishulDev] to the environment's database name before running.
   Re-runnable: it creates only what is missing and (re)applies the grants.
   ===================================================================== */

USE [master];
GO

IF SUSER_ID(N'trishul_app') IS NULL
    CREATE LOGIN [trishul_app] WITH PASSWORD = N'<APP_PASSWORD>', CHECK_POLICY = ON;
GO
IF SUSER_ID(N'trishul_migrator') IS NULL
    CREATE LOGIN [trishul_migrator] WITH PASSWORD = N'<MIGRATION_PASSWORD>', CHECK_POLICY = ON;
GO

USE [TrishulDev];
GO

/* ---------------------------------------------------------------------
   Application login: read/write data only.
   NOT a member of db_owner/sysadmin, so the row-level security policy
   (rls.brand_branch_policy) applies to it once enabled.
   --------------------------------------------------------------------- */
IF USER_ID(N'trishul_app') IS NULL
    CREATE USER [trishul_app] FOR LOGIN [trishul_app];
GO

ALTER ROLE [db_datareader] ADD MEMBER [trishul_app];
ALTER ROLE [db_datawriter] ADD MEMBER [trishul_app];
GO

-- EXECUTE on the application schemas (stored procedures / functions used in queries).
-- The rls schema is intentionally excluded: its predicate function is invoked by the
-- security policy itself and needs no grant to the login.
GRANT EXECUTE ON SCHEMA::[core] TO [trishul_app];
GRANT EXECUTE ON SCHEMA::[svc]  TO [trishul_app];
GRANT EXECUTE ON SCHEMA::[inv]  TO [trishul_app];
GRANT EXECUTE ON SCHEMA::[pur]  TO [trishul_app];
GRANT EXECUTE ON SCHEMA::[sal]  TO [trishul_app];
GRANT EXECUTE ON SCHEMA::[pre]  TO [trishul_app];
GRANT EXECUTE ON SCHEMA::[hr]   TO [trishul_app];
GRANT EXECUTE ON SCHEMA::[acc]  TO [trishul_app];
GRANT EXECUTE ON SCHEMA::[int]  TO [trishul_app];
GRANT EXECUTE ON SCHEMA::[rpt]  TO [trishul_app];
GO

-- The API tags every connection with the signed-in user for RLS:
--   EXEC sys.sp_set_session_context @key = N'app_user_id', @value = <id>, @read_only = 1;
-- sp_set_session_context and sp_reset_connection are executable by public, so no extra grant.

/* ---------------------------------------------------------------------
   Migration login: DDL rights for `alembic upgrade head`.
   --------------------------------------------------------------------- */
IF USER_ID(N'trishul_migrator') IS NULL
    CREATE USER [trishul_migrator] FOR LOGIN [trishul_migrator];
GO

ALTER ROLE [db_ddladmin]   ADD MEMBER [trishul_migrator];  -- CREATE/ALTER/DROP objects, CREATE SCHEMA
ALTER ROLE [db_datareader] ADD MEMBER [trishul_migrator];
ALTER ROLE [db_datawriter] ADD MEMBER [trishul_migrator];  -- seed/reference data in migrations
GO

-- Needed to toggle the row-level security policy from a migration
-- (ALTER SECURITY POLICY [rls].[brand_branch_policy] WITH (STATE = ON|OFF)).
GRANT ALTER ANY SECURITY POLICY TO [trishul_migrator];
GO

-- If future migrations must grant permissions or manage database roles, add:
--   ALTER ROLE [db_securityadmin] ADD MEMBER [trishul_migrator];
-- Prefer this to db_owner, which is broader than migrations need.

/* ---------------------------------------------------------------------
   Verify (optional)
   --------------------------------------------------------------------- */
-- SELECT dp.name AS principal, r.name AS role
-- FROM sys.database_role_members rm
-- JOIN sys.database_principals dp ON dp.principal_id = rm.member_principal_id
-- JOIN sys.database_principals r  ON r.principal_id  = rm.role_principal_id
-- WHERE dp.name IN (N'trishul_app', N'trishul_migrator')
-- ORDER BY dp.name, r.name;
GO
