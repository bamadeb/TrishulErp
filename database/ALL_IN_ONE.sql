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

/* =====================================================================
   TRISHUL Integrated System - SQL Server DDL (dictionary v2)
   Core Setup
   Generated from the TRISHUL Database Dictionary. Do not edit by hand:
   change the dictionary and regenerate.
   Target: SQL Server 2019+ / Amazon RDS for SQL Server
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
/* ---------- 1. Tables (58) ---------- */

/* ===== core: Core Masters & Platform ===== */
-- Legal entity (e.g. TRISHUL). One row per company.
CREATE TABLE [core].[company] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_company] PRIMARY KEY,
    [code] NVARCHAR(10) NOT NULL,
    [legal_name] NVARCHAR(200) NOT NULL,
    [trade_name] NVARCHAR(200) NULL,
    [pan] NVARCHAR(10) NULL,
    [cin] NVARCHAR(21) NULL,
    [address] NVARCHAR(500) NULL,
    [state_id] BIGINT NULL,
    [logo_url] NVARCHAR(500) NULL,
    [fiscal_year_start_month] TINYINT NOT NULL CONSTRAINT [DF_core_company_fiscal_year_start_month] DEFAULT (4),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_company_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_company_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- OEM brands the master company sells and services (Tata Hitachi, Kaashi, ...). Every brand-specific master and document points here.
CREATE TABLE [core].[principal] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_principal] PRIMARY KEY,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(120) NOT NULL,
    [supplier_id] BIGINT NULL,
    [handles_sales] BIT NOT NULL CONSTRAINT [DF_core_principal_handles_sales] DEFAULT (1),
    [handles_service] BIT NOT NULL CONSTRAINT [DF_core_principal_handles_service] DEFAULT (1),
    [handles_parts] BIT NOT NULL CONSTRAINT [DF_core_principal_handles_parts] DEFAULT (1),
    [oem_portal_name] NVARCHAR(60) NULL,
    [logo_url] NVARCHAR(500) NULL,
    [website] NVARCHAR(200) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_principal_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_principal_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Indian states and UTs with GST state code.
CREATE TABLE [core].[state] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_state] PRIMARY KEY,
    [gst_state_code] NVARCHAR(2) NOT NULL,
    [name] NVARCHAR(60) NOT NULL,
    [is_union_territory] BIT NOT NULL CONSTRAINT [DF_core_state_is_union_territory] DEFAULT (0),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_state_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_state_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Districts within a state.
CREATE TABLE [core].[district] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_district] PRIMARY KEY,
    [state_id] BIGINT NOT NULL,
    [name] NVARCHAR(80) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_district_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_district_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- PIN codes with centroid coordinates for distance and nearby logic.
CREATE TABLE [core].[pincode] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_pincode] PRIMARY KEY,
    [pincode] NVARCHAR(6) NOT NULL,
    [district_id] BIGINT NOT NULL,
    [area_name] NVARCHAR(120) NULL,
    [latitude] DECIMAL(9,6) NULL,
    [longitude] DECIMAL(9,6) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_pincode_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_pincode_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Head office, warehouse or branch. Branches point to the warehouse that supplies them.
CREATE TABLE [core].[branch] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_branch] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [code] NVARCHAR(10) NOT NULL,
    [name] NVARCHAR(120) NOT NULL,
    [branch_type] NVARCHAR(30) NOT NULL,
    [parent_warehouse_id] BIGINT NULL,
    [address] NVARCHAR(500) NULL,
    [state_id] BIGINT NOT NULL,
    [district_id] BIGINT NULL,
    [pincode_id] BIGINT NULL,
    [gstin_registration_id] BIGINT NULL,
    [phone] NVARCHAR(20) NULL,
    [email] NVARCHAR(120) NULL,
    [latitude] DECIMAL(9,6) NULL,
    [longitude] DECIMAL(9,6) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_branch_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_branch_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_core_branch_branch_type] CHECK ([branch_type] IN (N'Head office', N'Warehouse', N'Branch', N'Service point'))
);
GO
-- Stock location inside a warehouse. Branches hold no stock; all stock is in the 3-4 warehouses.
CREATE TABLE [core].[location] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_location] PRIMARY KEY,
    [branch_id] BIGINT NOT NULL,
    [code] NVARCHAR(10) NOT NULL,
    [name] NVARCHAR(120) NOT NULL,
    [location_type] NVARCHAR(30) NOT NULL,
    [address] NVARCHAR(500) NULL,
    [is_stock_location] BIT NOT NULL CONSTRAINT [DF_core_location_is_stock_location] DEFAULT (1),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_location_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_location_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_core_location_location_type] CHECK ([location_type] IN (N'Main store', N'Transit', N'Quarantine', N'Scrap'))
);
GO
-- Sales area grouping for reports.
CREATE TABLE [core].[area] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_area] PRIMARY KEY,
    [code] NVARCHAR(10) NOT NULL,
    [name] NVARCHAR(80) NOT NULL,
    [branch_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_area_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_area_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Service/sales territory covered by a team.
CREATE TABLE [core].[territory] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_territory] PRIMARY KEY,
    [branch_id] BIGINT NOT NULL,
    [code] NVARCHAR(10) NOT NULL,
    [name] NVARCHAR(80) NOT NULL,
    [description] NVARCHAR(300) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_territory_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_territory_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- PIN codes that fall inside a territory.
CREATE TABLE [core].[territory_pincode] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_territory_pincode] PRIMARY KEY,
    [territory_id] BIGINT NOT NULL,
    [pincode_id] BIGINT NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_territory_pincode_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_territory_pincode_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Service or sales team led by a Team Lead.
CREATE TABLE [core].[team] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_team] PRIMARY KEY,
    [branch_id] BIGINT NOT NULL,
    [name] NVARCHAR(80) NOT NULL,
    [team_type] NVARCHAR(30) NOT NULL,
    [team_lead_employee_id] BIGINT NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_team_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_team_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_core_team_team_type] CHECK ([team_type] IN (N'Service', N'Sales', N'Back office'))
);
GO
-- Engineers or salespeople in a team, with their territory.
CREATE TABLE [core].[team_member] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_team_member] PRIMARY KEY,
    [team_id] BIGINT NOT NULL,
    [employee_id] BIGINT NOT NULL,
    [territory_id] BIGINT NULL,
    [from_date] DATE NOT NULL,
    [to_date] DATE NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_team_member_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_team_member_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Brands each warehouse/branch deals in, with the OEM dealer code for that outlet.
CREATE TABLE [core].[branch_principal] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_branch_principal] PRIMARY KEY,
    [branch_id] BIGINT NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [oem_dealer_code] NVARCHAR(30) NULL,
    [is_sales_authorised] BIT NOT NULL CONSTRAINT [DF_core_branch_principal_is_sales_authorised] DEFAULT (1),
    [is_service_authorised] BIT NOT NULL CONSTRAINT [DF_core_branch_principal_is_service_authorised] DEFAULT (1),
    [is_parts_authorised] BIT NOT NULL CONSTRAINT [DF_core_branch_principal_is_parts_authorised] DEFAULT (1),
    [valid_from] DATE NULL,
    [valid_to] DATE NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_branch_principal_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_branch_principal_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Currencies (INR default).
CREATE TABLE [core].[currency] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_currency] PRIMARY KEY,
    [code] CHAR(3) NOT NULL,
    [name] NVARCHAR(40) NOT NULL,
    [symbol] NVARCHAR(5) NULL,
    [decimals] TINYINT NOT NULL CONSTRAINT [DF_core_currency_decimals] DEFAULT (2),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_currency_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_currency_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Credit terms for customers and suppliers.
CREATE TABLE [core].[payment_terms] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_payment_terms] PRIMARY KEY,
    [code] NVARCHAR(10) NOT NULL,
    [description] NVARCHAR(100) NOT NULL,
    [days_before_due] SMALLINT NULL,
    [day_in_following_month] SMALLINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_payment_terms_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_payment_terms_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Customer (billing party).
CREATE TABLE [core].[customer] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_customer] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(200) NOT NULL,
    [customer_type] NVARCHAR(30) NOT NULL,
    [pan] NVARCHAR(10) NULL,
    [gstin] NVARCHAR(15) NULL,
    [gst_registration_type] NVARCHAR(30) NOT NULL CONSTRAINT [DF_core_customer_gst_registration_type] DEFAULT (N'Unregistered'),
    [billing_address] NVARCHAR(500) NULL,
    [billing_state_id] BIGINT NULL,
    [billing_pincode_id] BIGINT NULL,
    [primary_phone] NVARCHAR(15) NOT NULL,
    [alternate_phone] NVARCHAR(15) NULL,
    [email] NVARCHAR(120) NULL,
    [area_id] BIGINT NULL,
    [salesman_employee_id] BIGINT NULL,
    [payment_terms_id] BIGINT NULL,
    [credit_limit] DECIMAL(18,2) NULL,
    [credit_status_id] BIGINT NULL,
    [is_asc_customer] BIT NOT NULL CONSTRAINT [DF_core_customer_is_asc_customer] DEFAULT (0),
    [priority_tier] NVARCHAR(30) NULL CONSTRAINT [DF_core_customer_priority_tier] DEFAULT (N'Normal'),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_customer_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_customer_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_core_customer_customer_type] CHECK ([customer_type] IN (N'Individual', N'Contractor', N'Company', N'Government', N'Rental', N'Dealer')),
    CONSTRAINT [CK_core_customer_gst_registration_type] CHECK ([gst_registration_type] IN (N'Regular', N'Composition', N'Unregistered', N'SEZ')),
    CONSTRAINT [CK_core_customer_priority_tier] CHECK ([priority_tier] IN (N'Key', N'Normal', N'Low'))
);
GO
-- Customer's code in each OEM system (replaces byd_customer_id). One customer can buy several brands.
CREATE TABLE [core].[customer_principal] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_customer_principal] PRIMARY KEY,
    [customer_id] BIGINT NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [oem_customer_code] NVARCHAR(40) NULL,
    [account_owner_employee_id] BIGINT NULL,
    [first_purchase_date] DATE NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_customer_principal_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_customer_principal_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Work sites where the customer's machines operate.
CREATE TABLE [core].[customer_site] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_customer_site] PRIMARY KEY,
    [customer_id] BIGINT NOT NULL,
    [site_name] NVARCHAR(120) NOT NULL,
    [address] NVARCHAR(500) NOT NULL,
    [pincode_id] BIGINT NULL,
    [district_id] BIGINT NULL,
    [state_id] BIGINT NULL,
    [latitude] DECIMAL(9,6) NULL,
    [longitude] DECIMAL(9,6) NULL,
    [site_contact_name] NVARCHAR(100) NULL,
    [site_contact_phone] NVARCHAR(15) NULL,
    [is_default] BIT NOT NULL CONSTRAINT [DF_core_customer_site_is_default] DEFAULT (0),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_customer_site_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_customer_site_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- People at a customer or supplier.
CREATE TABLE [core].[contact] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_contact] PRIMARY KEY,
    [customer_id] BIGINT NULL,
    [supplier_id] BIGINT NULL,
    [name] NVARCHAR(100) NOT NULL,
    [designation] NVARCHAR(60) NULL,
    [phone] NVARCHAR(15) NOT NULL,
    [alternate_phone] NVARCHAR(15) NULL,
    [whatsapp_number] NVARCHAR(15) NULL,
    [email] NVARCHAR(120) NULL,
    [preferred_language] NVARCHAR(30) NULL CONSTRAINT [DF_core_contact_preferred_language] DEFAULT (N'English'),
    [is_primary] BIT NOT NULL CONSTRAINT [DF_core_contact_is_primary] DEFAULT (0),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_contact_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_contact_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_core_contact_preferred_language] CHECK ([preferred_language] IN (N'English', N'Odia', N'Hindi'))
);
GO
-- Supplier / vendor, including TATA HITACHI as OEM.
CREATE TABLE [core].[supplier] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_supplier] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(200) NOT NULL,
    [supplier_type] NVARCHAR(30) NOT NULL,
    [pan] NVARCHAR(10) NULL,
    [gstin] NVARCHAR(15) NULL,
    [gst_registration_type] NVARCHAR(30) NULL,
    [address] NVARCHAR(500) NULL,
    [state_id] BIGINT NULL,
    [pincode_id] BIGINT NULL,
    [phone] NVARCHAR(15) NULL,
    [email] NVARCHAR(120) NULL,
    [payment_terms_id] BIGINT NULL,
    [credit_limit] DECIMAL(18,2) NULL,
    [bank_name] NVARCHAR(100) NULL,
    [bank_account_no] NVARCHAR(30) NULL,
    [ifsc] NVARCHAR(11) NULL,
    [tds_section_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_supplier_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_supplier_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_core_supplier_supplier_type] CHECK ([supplier_type] IN (N'OEM', N'Parts', N'Lubricants', N'Services', N'Transporter', N'Other')),
    CONSTRAINT [CK_core_supplier_gst_registration_type] CHECK ([gst_registration_type] IN (N'Regular', N'Composition', N'Unregistered', N'SEZ', N'Overseas'))
);
GO
-- Units of measure.
CREATE TABLE [core].[uom] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_uom] PRIMARY KEY,
    [code] NVARCHAR(10) NOT NULL,
    [name] NVARCHAR(40) NOT NULL,
    [decimals] TINYINT NOT NULL CONSTRAINT [DF_core_uom_decimals] DEFAULT (0),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_uom_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_uom_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- HSN (goods) and SAC (services) codes with GST rate.
CREATE TABLE [core].[hsn_sac] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_hsn_sac] PRIMARY KEY,
    [code] NVARCHAR(8) NOT NULL,
    [code_type] NVARCHAR(30) NOT NULL,
    [description] NVARCHAR(300) NULL,
    [gst_rate_id] BIGINT NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_hsn_sac_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_hsn_sac_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_core_hsn_sac_code_type] CHECK ([code_type] IN (N'HSN', N'SAC'))
);
GO
-- Item categories (hierarchical).
CREATE TABLE [core].[item_category] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_item_category] PRIMARY KEY,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(100) NOT NULL,
    [parent_category_id] BIGINT NULL,
    [item_nature] NVARCHAR(30) NOT NULL,
    [default_uom_id] BIGINT NULL,
    [default_hsn_sac_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_item_category_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_item_category_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_core_item_category_item_nature] CHECK ([item_nature] IN (N'Machine', N'Spare part', N'Lubricant', N'Attachment', N'Service', N'Consumable'))
);
GO
-- Item master: machines, spare parts, lubricants, services. Brand items carry principal_id.
CREATE TABLE [core].[item] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_item] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [item_code] NVARCHAR(40) NOT NULL,
    [principal_id] BIGINT NULL,
    [oem_part_number] NVARCHAR(40) NULL,
    [description] NVARCHAR(200) NOT NULL,
    [long_description] NVARCHAR(1000) NULL,
    [category_id] BIGINT NOT NULL,
    [uom_id] BIGINT NOT NULL,
    [hsn_sac_id] BIGINT NULL,
    [item_type] NVARCHAR(30) NOT NULL,
    [is_serialized] BIT NOT NULL CONSTRAINT [DF_core_item_is_serialized] DEFAULT (0),
    [is_batch_tracked] BIT NOT NULL CONSTRAINT [DF_core_item_is_batch_tracked] DEFAULT (0),
    [machine_model_id] BIGINT NULL,
    [standard_cost] DECIMAL(18,4) NULL,
    [last_purchase_cost] DECIMAL(18,4) NULL,
    [mrp] DECIMAL(18,2) NULL,
    [reorder_level] DECIMAL(18,3) NULL,
    [reorder_qty] DECIMAL(18,3) NULL,
    [lead_time_days] SMALLINT NULL,
    [movement_class_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_item_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_item_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_core_item_item_type] CHECK ([item_type] IN (N'Stock', N'Non stock', N'Service'))
);
GO
-- Machine models of every brand.
CREATE TABLE [core].[machine_model] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_machine_model] PRIMARY KEY,
    [model_code] NVARCHAR(20) NOT NULL,
    [model_name] NVARCHAR(100) NOT NULL,
    [product_line] NVARCHAR(30) NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [operating_weight_kg] DECIMAL(10,2) NULL,
    [engine_model] NVARCHAR(40) NULL,
    [default_warranty_months] SMALLINT NULL,
    [default_warranty_hours] INT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_machine_model_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_machine_model_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_core_machine_model_product_line] CHECK ([product_line] IN (N'Excavator', N'Backhoe loader', N'Wheel loader', N'Mini excavator', N'Other'))
);
GO
-- One physical machine, identified by serial/chassis number. Shared by Service, Sales and Pre-Sales.
CREATE TABLE [core].[machine_unit] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_machine_unit] PRIMARY KEY,
    [serial_number] NVARCHAR(40) NOT NULL,
    [engine_number] NVARCHAR(40) NULL,
    [model_id] BIGINT NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [item_id] BIGINT NULL,
    [customer_id] BIGINT NULL,
    [customer_site_id] BIGINT NULL,
    [sold_by_branch_id] BIGINT NULL,
    [sale_invoice_id] BIGINT NULL,
    [sale_date] DATE NULL,
    [commissioning_date] DATE NULL,
    [warranty_start_date] DATE NULL,
    [warranty_end_date] DATE NULL,
    [warranty_hours_limit] INT NULL,
    [current_hmr] DECIMAL(10,1) NULL,
    [hmr_updated_at] DATETIME2(0) NULL,
    [year_of_manufacture] SMALLINT NULL,
    [registration_number] NVARCHAR(20) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [oem_registered_product_id] NVARCHAR(40) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_machine_unit_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_machine_unit_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_core_machine_unit_status] CHECK ([status] IN (N'In stock', N'Sold', N'Transferred', N'Scrapped'))
);
GO
-- Ownership history, for resold machines (old customers).
CREATE TABLE [core].[machine_ownership] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_machine_ownership] PRIMARY KEY,
    [machine_unit_id] BIGINT NOT NULL,
    [customer_id] BIGINT NOT NULL,
    [from_date] DATE NOT NULL,
    [to_date] DATE NULL,
    [transfer_reason] NVARCHAR(200) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_machine_ownership_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_machine_ownership_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Every hour-meter (HMR) reading. Drives scheduled services and warranty checks.
CREATE TABLE [core].[machine_meter_reading] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_machine_meter_reading] PRIMARY KEY,
    [machine_unit_id] BIGINT NOT NULL,
    [reading_hmr] DECIMAL(10,1) NOT NULL,
    [reading_at] DATETIME2(0) NOT NULL,
    [source] NVARCHAR(30) NOT NULL,
    [service_call_id] BIGINT NULL,
    [recorded_by_user_id] BIGINT NULL,
    [photo_attachment_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_machine_meter_reading_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_machine_meter_reading_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_core_machine_meter_reading_source] CHECK ([source] IN (N'Service report', N'Customer', N'Import', N'Telematics'))
);
GO
-- Employee shell used by all modules. Full HR profile in hr.employee_profile.
CREATE TABLE [core].[employee] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_employee] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [employee_code] NVARCHAR(20) NOT NULL,
    [first_name] NVARCHAR(60) NOT NULL,
    [last_name] NVARCHAR(60) NULL,
    [mobile] NVARCHAR(15) NOT NULL,
    [email] NVARCHAR(120) NULL,
    [branch_id] BIGINT NOT NULL,
    [department_id] BIGINT NULL,
    [designation_id] BIGINT NULL,
    [reporting_manager_id] BIGINT NULL,
    [employee_type] NVARCHAR(30) NOT NULL,
    [date_of_joining] DATE NULL,
    [date_of_exit] DATE NULL,
    [status] NVARCHAR(30) NOT NULL CONSTRAINT [DF_core_employee_status] DEFAULT (N'Active'),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_employee_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_employee_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_core_employee_employee_type] CHECK ([employee_type] IN (N'Permanent', N'Contract', N'Trainee', N'Consultant')),
    CONSTRAINT [CK_core_employee_status] CHECK ([status] IN (N'Active', N'Notice', N'Exited'))
);
GO
-- Brands an engineer or salesperson is authorised or certified for. Used for assignment and targets.
CREATE TABLE [core].[employee_principal] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_employee_principal] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [role_type] NVARCHAR(30) NOT NULL,
    [certification_level] NVARCHAR(40) NULL,
    [certified_on] DATE NULL,
    [valid_until] DATE NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_employee_principal_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_employee_principal_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_core_employee_principal_role_type] CHECK ([role_type] IN (N'Service', N'Sales', N'Parts'))
);
GO
-- Login account. Sign-in handled by AWS Cognito; no passwords here.
CREATE TABLE [core].[app_user] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_app_user] PRIMARY KEY,
    [employee_id] BIGINT NULL,
    [cognito_sub] NVARCHAR(64) NOT NULL,
    [username] NVARCHAR(100) NOT NULL,
    [email] NVARCHAR(120) NULL,
    [mobile] NVARCHAR(15) NULL,
    [default_branch_id] BIGINT NULL,
    [last_login_at] DATETIME2(0) NULL,
    [is_locked] BIT NOT NULL CONSTRAINT [DF_core_app_user_is_locked] DEFAULT (0),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_app_user_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_app_user_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Roles: Admin, Back office, Team Lead, Service engineer, etc.
CREATE TABLE [core].[role] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_role] PRIMARY KEY,
    [code] NVARCHAR(40) NOT NULL,
    [name] NVARCHAR(80) NOT NULL,
    [description] NVARCHAR(300) NULL,
    [is_system] BIT NOT NULL CONSTRAINT [DF_core_role_is_system] DEFAULT (0),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_role_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_role_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Individual permission, e.g. svc.call.assign.
CREATE TABLE [core].[permission] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_permission] PRIMARY KEY,
    [code] NVARCHAR(80) NOT NULL,
    [module] NVARCHAR(20) NOT NULL,
    [description] NVARCHAR(300) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_permission_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_permission_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Permissions granted to a role.
CREATE TABLE [core].[role_permission] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_role_permission] PRIMARY KEY,
    [role_id] BIGINT NOT NULL,
    [permission_id] BIGINT NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_role_permission_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_role_permission_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Roles given to a user, optionally limited to a branch.
CREATE TABLE [core].[user_role] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_user_role] PRIMARY KEY,
    [app_user_id] BIGINT NOT NULL,
    [role_id] BIGINT NOT NULL,
    [branch_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_user_role_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_user_role_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Brands a user may see. With branch scope, drives row-level security on every screen and report.
CREATE TABLE [core].[user_principal_access] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_user_principal_access] PRIMARY KEY,
    [app_user_id] BIGINT NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_user_principal_access_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_user_principal_access_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Mobile devices for push notifications and offline sync.
CREATE TABLE [core].[user_device] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_user_device] PRIMARY KEY,
    [app_user_id] BIGINT NOT NULL,
    [device_id] NVARCHAR(100) NOT NULL,
    [platform] NVARCHAR(30) NOT NULL,
    [app_version] NVARCHAR(20) NULL,
    [push_token] NVARCHAR(500) NULL,
    [last_seen_at] DATETIME2(0) NULL,
    [last_sync_at] DATETIME2(0) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_user_device_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_user_device_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_core_user_device_platform] CHECK ([platform] IN (N'Android', N'iOS', N'Web'))
);
GO
-- Types of dropdown lists (see Lookup Lists sheet).
CREATE TABLE [core].[lookup_type] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_lookup_type] PRIMARY KEY,
    [code] NVARCHAR(40) NOT NULL,
    [name] NVARCHAR(80) NOT NULL,
    [module] NVARCHAR(20) NULL,
    [is_editable] BIT NOT NULL CONSTRAINT [DF_core_lookup_type_is_editable] DEFAULT (1),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_lookup_type_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_lookup_type_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Values in a dropdown list.
CREATE TABLE [core].[lookup_value] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_lookup_value] PRIMARY KEY,
    [lookup_type_id] BIGINT NOT NULL,
    [code] NVARCHAR(40) NOT NULL,
    [label] NVARCHAR(120) NOT NULL,
    [sort_order] SMALLINT NOT NULL CONSTRAINT [DF_core_lookup_value_sort_order] DEFAULT (0),
    [parent_value_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_lookup_value_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_lookup_value_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Document numbering per branch and fiscal year.
CREATE TABLE [core].[number_series] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_number_series] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [branch_id] BIGINT NULL,
    [document_type] NVARCHAR(40) NOT NULL,
    [principal_id] BIGINT NULL,
    [fiscal_year_id] BIGINT NULL,
    [prefix] NVARCHAR(20) NULL,
    [next_number] INT NOT NULL CONSTRAINT [DF_core_number_series_next_number] DEFAULT (1),
    [padding] TINYINT NOT NULL CONSTRAINT [DF_core_number_series_padding] DEFAULT (5),
    [suffix] NVARCHAR(20) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_number_series_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_number_series_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Files stored in Amazon S3, linked to any record.
CREATE TABLE [core].[attachment] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_attachment] PRIMARY KEY,
    [entity_type] NVARCHAR(50) NOT NULL,
    [entity_id] BIGINT NOT NULL,
    [category] NVARCHAR(30) NOT NULL,
    [file_name] NVARCHAR(200) NOT NULL,
    [content_type] NVARCHAR(100) NULL,
    [file_size_bytes] BIGINT NULL,
    [s3_key] NVARCHAR(500) NOT NULL,
    [captured_latitude] DECIMAL(9,6) NULL,
    [captured_longitude] DECIMAL(9,6) NULL,
    [captured_at] DATETIME2(0) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_attachment_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_attachment_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_core_attachment_category] CHECK ([category] IN (N'Photo', N'Signature', N'Report PDF', N'Document', N'Invoice', N'Other'))
);
GO
-- Field-level change history for sensitive tables.
CREATE TABLE [core].[audit_log] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_audit_log] PRIMARY KEY,
    [entity_type] NVARCHAR(50) NOT NULL,
    [entity_id] BIGINT NOT NULL,
    [action] NVARCHAR(30) NOT NULL,
    [old_values] NVARCHAR(MAX) NULL,
    [new_values] NVARCHAR(MAX) NULL,
    [changed_by_user_id] BIGINT NULL,
    [changed_at] DATETIME2(0) NOT NULL,
    [source] NVARCHAR(30) NOT NULL,
    [ip_address] NVARCHAR(45) NULL,
    CONSTRAINT [CK_core_audit_log_action] CHECK ([action] IN (N'Insert', N'Update', N'Delete')),
    CONSTRAINT [CK_core_audit_log_source] CHECK ([source] IN (N'Web', N'Android', N'iOS', N'API', N'Sync', N'System'))
);
GO
-- Generic status change log for documents other than service calls.
CREATE TABLE [core].[status_history] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_status_history] PRIMARY KEY,
    [entity_type] NVARCHAR(50) NOT NULL,
    [entity_id] BIGINT NOT NULL,
    [from_status] NVARCHAR(30) NULL,
    [to_status] NVARCHAR(30) NOT NULL,
    [changed_by_user_id] BIGINT NULL,
    [changed_at] DATETIME2(0) NOT NULL,
    [reason_lookup_id] BIGINT NULL,
    [remarks] NVARCHAR(500) NULL
);
GO
-- Who must approve which documents, by value band.
CREATE TABLE [core].[approval_rule] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_approval_rule] PRIMARY KEY,
    [document_type] NVARCHAR(40) NOT NULL,
    [branch_id] BIGINT NULL,
    [min_value] DECIMAL(18,2) NULL,
    [max_value] DECIMAL(18,2) NULL,
    [approval_level] TINYINT NOT NULL CONSTRAINT [DF_core_approval_rule_approval_level] DEFAULT (1),
    [approver_role_id] BIGINT NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_approval_rule_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_approval_rule_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Approval requests raised by documents.
CREATE TABLE [core].[approval_request] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_approval_request] PRIMARY KEY,
    [approval_rule_id] BIGINT NULL,
    [document_type] NVARCHAR(40) NOT NULL,
    [document_id] BIGINT NOT NULL,
    [approval_level] TINYINT NOT NULL,
    [requested_by_user_id] BIGINT NOT NULL,
    [requested_at] DATETIME2(0) NOT NULL,
    [approver_user_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [acted_at] DATETIME2(0) NULL,
    [remarks] NVARCHAR(500) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_approval_request_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_approval_request_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_core_approval_request_status] CHECK ([status] IN (N'Pending', N'Approved', N'Rejected', N'Cancelled'))
);
GO
-- Message templates for push, WhatsApp, email, SMS.
CREATE TABLE [core].[notification_template] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_notification_template] PRIMARY KEY,
    [code] NVARCHAR(40) NOT NULL,
    [channel] NVARCHAR(30) NOT NULL,
    [language] NVARCHAR(30) NOT NULL CONSTRAINT [DF_core_notification_template_language] DEFAULT (N'English'),
    [subject] NVARCHAR(200) NULL,
    [body] NVARCHAR(2000) NOT NULL,
    [whatsapp_template_name] NVARCHAR(100) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_notification_template_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_notification_template_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_core_notification_template_channel] CHECK ([channel] IN (N'Push', N'WhatsApp', N'Email', N'SMS')),
    CONSTRAINT [CK_core_notification_template_language] CHECK ([language] IN (N'English', N'Odia', N'Hindi'))
);
GO
-- Every message sent, with delivery status.
CREATE TABLE [core].[notification] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_notification] PRIMARY KEY,
    [template_id] BIGINT NULL,
    [channel] NVARCHAR(30) NOT NULL,
    [recipient_user_id] BIGINT NULL,
    [recipient_address] NVARCHAR(150) NULL,
    [entity_type] NVARCHAR(50) NULL,
    [entity_id] BIGINT NULL,
    [payload] NVARCHAR(MAX) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [provider_message_id] NVARCHAR(100) NULL,
    [sent_at] DATETIME2(0) NULL,
    [error_message] NVARCHAR(500) NULL,
    CONSTRAINT [CK_core_notification_channel] CHECK ([channel] IN (N'Push', N'WhatsApp', N'Email', N'SMS')),
    CONSTRAINT [CK_core_notification_status] CHECK ([status] IN (N'Queued', N'Sent', N'Delivered', N'Read', N'Failed'))
);
GO
-- Configurable settings per company.
CREATE TABLE [core].[system_setting] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_core_system_setting] PRIMARY KEY,
    [company_id] BIGINT NULL,
    [setting_key] NVARCHAR(80) NOT NULL,
    [setting_value] NVARCHAR(1000) NULL,
    [data_type] NVARCHAR(30) NOT NULL,
    [description] NVARCHAR(300) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_core_system_setting_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_core_system_setting_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_core_system_setting_data_type] CHECK ([data_type] IN (N'Text', N'Number', N'Boolean', N'JSON'))
);
GO

/* ===== acc: Accounting & GST ===== */
-- Financial years (April-March).
CREATE TABLE [acc].[fiscal_year] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_fiscal_year] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [code] NVARCHAR(10) NOT NULL,
    [start_date] DATE NOT NULL,
    [end_date] DATE NOT NULL,
    [is_closed] BIT NOT NULL CONSTRAINT [DF_acc_fiscal_year_is_closed] DEFAULT (0),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_fiscal_year_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_fiscal_year_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Monthly periods; locking stops back-dated postings.
CREATE TABLE [acc].[accounting_period] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_accounting_period] PRIMARY KEY,
    [fiscal_year_id] BIGINT NOT NULL,
    [period_month] DATE NOT NULL,
    [is_locked] BIT NOT NULL CONSTRAINT [DF_acc_accounting_period_is_locked] DEFAULT (0),
    [locked_by_user_id] BIGINT NULL,
    [locked_at] DATETIME2(0) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_accounting_period_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_accounting_period_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Company GST registrations (one per state).
CREATE TABLE [acc].[gstin_registration] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_gstin_registration] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [gstin] NVARCHAR(15) NOT NULL,
    [state_id] BIGINT NOT NULL,
    [legal_name] NVARCHAR(200) NOT NULL,
    [trade_name] NVARCHAR(200) NULL,
    [address] NVARCHAR(500) NULL,
    [is_e_invoice_enabled] BIT NOT NULL CONSTRAINT [DF_acc_gstin_registration_is_e_invoice_enabled] DEFAULT (0),
    [credential_secret_name] NVARCHAR(100) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_gstin_registration_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_gstin_registration_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- GST rate slabs with CGST/SGST/IGST split and ledger accounts.
CREATE TABLE [acc].[gst_rate] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_gst_rate] PRIMARY KEY,
    [code] NVARCHAR(10) NOT NULL,
    [description] NVARCHAR(60) NULL,
    [total_rate] DECIMAL(5,2) NOT NULL,
    [cgst_rate] DECIMAL(5,2) NOT NULL,
    [sgst_rate] DECIMAL(5,2) NOT NULL,
    [igst_rate] DECIMAL(5,2) NOT NULL,
    [cess_rate] DECIMAL(5,2) NOT NULL CONSTRAINT [DF_acc_gst_rate_cess_rate] DEFAULT (0),
    [effective_from] DATE NOT NULL,
    [effective_to] DATE NULL,
    [output_gl_account_id] BIGINT NULL,
    [input_gl_account_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_gst_rate_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_gst_rate_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Tax treatment: intra-state, inter-state, exempt, export, RCM.
CREATE TABLE [acc].[tax_group] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_tax_group] PRIMARY KEY,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(60) NOT NULL,
    [description] NVARCHAR(200) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_tax_group_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_tax_group_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- TDS sections and rates.
CREATE TABLE [acc].[tds_section] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_tds_section] PRIMARY KEY,
    [section_code] NVARCHAR(10) NOT NULL,
    [description] NVARCHAR(200) NULL,
    [rate_individual] DECIMAL(5,2) NULL,
    [rate_company] DECIMAL(5,2) NULL,
    [threshold_single] DECIMAL(18,2) NULL,
    [threshold_annual] DECIMAL(18,2) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_tds_section_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_tds_section_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Top-level classes.
CREATE TABLE [acc].[account_class] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_account_class] PRIMARY KEY,
    [code] NVARCHAR(3) NOT NULL,
    [name] NVARCHAR(60) NOT NULL,
    [class_type] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_account_class_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_account_class_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_acc_account_class_class_type] CHECK ([class_type] IN (N'Asset', N'Liability', N'Equity', N'Income', N'Expense'))
);
GO
-- Account groups (Tally-style).
CREATE TABLE [acc].[account_group] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_account_group] PRIMARY KEY,
    [code] NVARCHAR(10) NOT NULL,
    [name] NVARCHAR(100) NOT NULL,
    [account_class_id] BIGINT NOT NULL,
    [parent_group_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_account_group_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_account_group_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Chart of accounts (ledgers).
CREATE TABLE [acc].[gl_account] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_gl_account] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [account_code] NVARCHAR(20) NOT NULL,
    [account_name] NVARCHAR(150) NOT NULL,
    [account_group_id] BIGINT NOT NULL,
    [account_type] NVARCHAR(30) NOT NULL,
    [is_control_account] BIT NOT NULL CONSTRAINT [DF_acc_gl_account_is_control_account] DEFAULT (0),
    [allow_manual_entry] BIT NOT NULL CONSTRAINT [DF_acc_gl_account_allow_manual_entry] DEFAULT (1),
    [tally_ledger_name] NVARCHAR(150) NULL,
    [sap_gl_code] NVARCHAR(20) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_gl_account_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_gl_account_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_acc_gl_account_account_type] CHECK ([account_type] IN (N'Bank', N'Cash', N'Receivable', N'Payable', N'Tax', N'Stock', N'Income', N'Expense', N'General'))
);
GO
-- Cost centres by branch and business line.
CREATE TABLE [acc].[cost_centre] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_cost_centre] PRIMARY KEY,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(100) NOT NULL,
    [branch_id] BIGINT NULL,
    [principal_id] BIGINT NULL,
    [cost_centre_type] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_cost_centre_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_cost_centre_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_acc_cost_centre_cost_centre_type] CHECK ([cost_centre_type] IN (N'Branch', N'Warehouse', N'Machines', N'Parts', N'Service', N'Admin'))
);
GO

/* ---------- 2. Unique keys (50) ---------- */
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_company_code] ON [core].[company] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_principal_code] ON [core].[principal] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_state_gst_state_code] ON [core].[state] ([gst_state_code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_district_k1] ON [core].[district] ([state_id], [name]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_pincode_pincode] ON [core].[pincode] ([pincode]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_branch_code] ON [core].[branch] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_location_code] ON [core].[location] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_area_code] ON [core].[area] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_territory_code] ON [core].[territory] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_territory_pincode_k1] ON [core].[territory_pincode] ([territory_id], [pincode_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_branch_principal_k1] ON [core].[branch_principal] ([branch_id], [principal_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_currency_code] ON [core].[currency] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_payment_terms_code] ON [core].[payment_terms] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_customer_code] ON [core].[customer] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_customer_principal_k1] ON [core].[customer_principal] ([customer_id], [principal_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_customer_site_k1] ON [core].[customer_site] ([customer_id], [site_name]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_supplier_code] ON [core].[supplier] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_uom_code] ON [core].[uom] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_hsn_sac_code] ON [core].[hsn_sac] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_item_category_code] ON [core].[item_category] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_item_item_code] ON [core].[item] ([item_code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_machine_model_model_code] ON [core].[machine_model] ([model_code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_machine_unit_serial_number] ON [core].[machine_unit] ([serial_number]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_employee_employee_code] ON [core].[employee] ([employee_code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_employee_mobile] ON [core].[employee] ([mobile]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_employee_principal_k1] ON [core].[employee_principal] ([employee_id], [principal_id], [role_type]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_app_user_employee_id] ON [core].[app_user] ([employee_id]) WHERE [employee_id] IS NOT NULL;
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_app_user_cognito_sub] ON [core].[app_user] ([cognito_sub]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_app_user_username] ON [core].[app_user] ([username]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_role_code] ON [core].[role] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_permission_code] ON [core].[permission] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_role_permission_k1] ON [core].[role_permission] ([role_id], [permission_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_user_role_k1] ON [core].[user_role] ([app_user_id], [role_id], [branch_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_user_principal_access_k1] ON [core].[user_principal_access] ([app_user_id], [principal_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_user_device_k1] ON [core].[user_device] ([app_user_id], [device_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_lookup_type_code] ON [core].[lookup_type] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_lookup_value_k1] ON [core].[lookup_value] ([lookup_type_id], [code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_number_series_k1] ON [core].[number_series] ([branch_id], [document_type], [principal_id], [fiscal_year_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_notification_template_k1] ON [core].[notification_template] ([code], [channel], [language]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_core_system_setting_k1] ON [core].[system_setting] ([company_id], [setting_key]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_acc_fiscal_year_k1] ON [acc].[fiscal_year] ([company_id], [code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_acc_accounting_period_k1] ON [acc].[accounting_period] ([fiscal_year_id], [period_month]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_acc_gstin_registration_gstin] ON [acc].[gstin_registration] ([gstin]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_acc_gst_rate_code] ON [acc].[gst_rate] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_acc_tax_group_code] ON [acc].[tax_group] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_acc_tds_section_section_code] ON [acc].[tds_section] ([section_code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_acc_account_class_code] ON [acc].[account_class] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_acc_account_group_code] ON [acc].[account_group] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_acc_gl_account_k1] ON [acc].[gl_account] ([company_id], [account_code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_acc_cost_centre_code] ON [acc].[cost_centre] ([code]);
GO

/* ---------- 3. Foreign keys (109) ----------
   Includes links from earlier-phase columns to tables created in this phase. */
ALTER TABLE [core].[company] ADD CONSTRAINT [FK_core_company_state_id] FOREIGN KEY ([state_id]) REFERENCES [core].[state] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[principal] ADD CONSTRAINT [FK_core_principal_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[district] ADD CONSTRAINT [FK_core_district_state_id] FOREIGN KEY ([state_id]) REFERENCES [core].[state] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[pincode] ADD CONSTRAINT [FK_core_pincode_district_id] FOREIGN KEY ([district_id]) REFERENCES [core].[district] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[branch] ADD CONSTRAINT [FK_core_branch_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[branch] ADD CONSTRAINT [FK_core_branch_parent_warehouse_id] FOREIGN KEY ([parent_warehouse_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[branch] ADD CONSTRAINT [FK_core_branch_state_id] FOREIGN KEY ([state_id]) REFERENCES [core].[state] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[branch] ADD CONSTRAINT [FK_core_branch_district_id] FOREIGN KEY ([district_id]) REFERENCES [core].[district] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[branch] ADD CONSTRAINT [FK_core_branch_pincode_id] FOREIGN KEY ([pincode_id]) REFERENCES [core].[pincode] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[branch] ADD CONSTRAINT [FK_core_branch_gstin_registration_id] FOREIGN KEY ([gstin_registration_id]) REFERENCES [acc].[gstin_registration] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[location] ADD CONSTRAINT [FK_core_location_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[area] ADD CONSTRAINT [FK_core_area_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[territory] ADD CONSTRAINT [FK_core_territory_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[territory_pincode] ADD CONSTRAINT [FK_core_territory_pincode_territory_id] FOREIGN KEY ([territory_id]) REFERENCES [core].[territory] ([id]) ON DELETE CASCADE;
ALTER TABLE [core].[territory_pincode] ADD CONSTRAINT [FK_core_territory_pincode_pincode_id] FOREIGN KEY ([pincode_id]) REFERENCES [core].[pincode] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[team] ADD CONSTRAINT [FK_core_team_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[team] ADD CONSTRAINT [FK_core_team_team_lead_employee_id] FOREIGN KEY ([team_lead_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[team_member] ADD CONSTRAINT [FK_core_team_member_team_id] FOREIGN KEY ([team_id]) REFERENCES [core].[team] ([id]) ON DELETE CASCADE;
ALTER TABLE [core].[team_member] ADD CONSTRAINT [FK_core_team_member_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[team_member] ADD CONSTRAINT [FK_core_team_member_territory_id] FOREIGN KEY ([territory_id]) REFERENCES [core].[territory] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[branch_principal] ADD CONSTRAINT [FK_core_branch_principal_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE CASCADE;
ALTER TABLE [core].[branch_principal] ADD CONSTRAINT [FK_core_branch_principal_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[customer] ADD CONSTRAINT [FK_core_customer_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[customer] ADD CONSTRAINT [FK_core_customer_billing_state_id] FOREIGN KEY ([billing_state_id]) REFERENCES [core].[state] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[customer] ADD CONSTRAINT [FK_core_customer_billing_pincode_id] FOREIGN KEY ([billing_pincode_id]) REFERENCES [core].[pincode] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[customer] ADD CONSTRAINT [FK_core_customer_area_id] FOREIGN KEY ([area_id]) REFERENCES [core].[area] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[customer] ADD CONSTRAINT [FK_core_customer_salesman_employee_id] FOREIGN KEY ([salesman_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[customer] ADD CONSTRAINT [FK_core_customer_payment_terms_id] FOREIGN KEY ([payment_terms_id]) REFERENCES [core].[payment_terms] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[customer_principal] ADD CONSTRAINT [FK_core_customer_principal_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE CASCADE;
ALTER TABLE [core].[customer_principal] ADD CONSTRAINT [FK_core_customer_principal_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[customer_principal] ADD CONSTRAINT [FK_core_customer_principal_account_owner_employee_id] FOREIGN KEY ([account_owner_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[customer_site] ADD CONSTRAINT [FK_core_customer_site_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE CASCADE;
ALTER TABLE [core].[customer_site] ADD CONSTRAINT [FK_core_customer_site_pincode_id] FOREIGN KEY ([pincode_id]) REFERENCES [core].[pincode] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[customer_site] ADD CONSTRAINT [FK_core_customer_site_district_id] FOREIGN KEY ([district_id]) REFERENCES [core].[district] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[customer_site] ADD CONSTRAINT [FK_core_customer_site_state_id] FOREIGN KEY ([state_id]) REFERENCES [core].[state] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[contact] ADD CONSTRAINT [FK_core_contact_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[contact] ADD CONSTRAINT [FK_core_contact_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[supplier] ADD CONSTRAINT [FK_core_supplier_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[supplier] ADD CONSTRAINT [FK_core_supplier_state_id] FOREIGN KEY ([state_id]) REFERENCES [core].[state] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[supplier] ADD CONSTRAINT [FK_core_supplier_pincode_id] FOREIGN KEY ([pincode_id]) REFERENCES [core].[pincode] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[supplier] ADD CONSTRAINT [FK_core_supplier_payment_terms_id] FOREIGN KEY ([payment_terms_id]) REFERENCES [core].[payment_terms] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[supplier] ADD CONSTRAINT [FK_core_supplier_tds_section_id] FOREIGN KEY ([tds_section_id]) REFERENCES [acc].[tds_section] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[hsn_sac] ADD CONSTRAINT [FK_core_hsn_sac_gst_rate_id] FOREIGN KEY ([gst_rate_id]) REFERENCES [acc].[gst_rate] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[item_category] ADD CONSTRAINT [FK_core_item_category_parent_category_id] FOREIGN KEY ([parent_category_id]) REFERENCES [core].[item_category] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[item_category] ADD CONSTRAINT [FK_core_item_category_default_uom_id] FOREIGN KEY ([default_uom_id]) REFERENCES [core].[uom] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[item_category] ADD CONSTRAINT [FK_core_item_category_default_hsn_sac_id] FOREIGN KEY ([default_hsn_sac_id]) REFERENCES [core].[hsn_sac] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[item] ADD CONSTRAINT [FK_core_item_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[item] ADD CONSTRAINT [FK_core_item_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[item] ADD CONSTRAINT [FK_core_item_category_id] FOREIGN KEY ([category_id]) REFERENCES [core].[item_category] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[item] ADD CONSTRAINT [FK_core_item_uom_id] FOREIGN KEY ([uom_id]) REFERENCES [core].[uom] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[item] ADD CONSTRAINT [FK_core_item_hsn_sac_id] FOREIGN KEY ([hsn_sac_id]) REFERENCES [core].[hsn_sac] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[item] ADD CONSTRAINT [FK_core_item_machine_model_id] FOREIGN KEY ([machine_model_id]) REFERENCES [core].[machine_model] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[machine_model] ADD CONSTRAINT [FK_core_machine_model_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[machine_unit] ADD CONSTRAINT [FK_core_machine_unit_model_id] FOREIGN KEY ([model_id]) REFERENCES [core].[machine_model] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[machine_unit] ADD CONSTRAINT [FK_core_machine_unit_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[machine_unit] ADD CONSTRAINT [FK_core_machine_unit_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[machine_unit] ADD CONSTRAINT [FK_core_machine_unit_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[machine_unit] ADD CONSTRAINT [FK_core_machine_unit_customer_site_id] FOREIGN KEY ([customer_site_id]) REFERENCES [core].[customer_site] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[machine_unit] ADD CONSTRAINT [FK_core_machine_unit_sold_by_branch_id] FOREIGN KEY ([sold_by_branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[machine_ownership] ADD CONSTRAINT [FK_core_machine_ownership_machine_unit_id] FOREIGN KEY ([machine_unit_id]) REFERENCES [core].[machine_unit] ([id]) ON DELETE CASCADE;
ALTER TABLE [core].[machine_ownership] ADD CONSTRAINT [FK_core_machine_ownership_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[machine_meter_reading] ADD CONSTRAINT [FK_core_machine_meter_reading_machine_unit_id] FOREIGN KEY ([machine_unit_id]) REFERENCES [core].[machine_unit] ([id]) ON DELETE CASCADE;
ALTER TABLE [core].[machine_meter_reading] ADD CONSTRAINT [FK_core_machine_meter_reading_recorded_by_user_id] FOREIGN KEY ([recorded_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[machine_meter_reading] ADD CONSTRAINT [FK_core_machine_meter_reading_photo_attachment_id] FOREIGN KEY ([photo_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[employee] ADD CONSTRAINT [FK_core_employee_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[employee] ADD CONSTRAINT [FK_core_employee_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[employee] ADD CONSTRAINT [FK_core_employee_reporting_manager_id] FOREIGN KEY ([reporting_manager_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[employee_principal] ADD CONSTRAINT [FK_core_employee_principal_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE CASCADE;
ALTER TABLE [core].[employee_principal] ADD CONSTRAINT [FK_core_employee_principal_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[app_user] ADD CONSTRAINT [FK_core_app_user_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[app_user] ADD CONSTRAINT [FK_core_app_user_default_branch_id] FOREIGN KEY ([default_branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[role_permission] ADD CONSTRAINT [FK_core_role_permission_role_id] FOREIGN KEY ([role_id]) REFERENCES [core].[role] ([id]) ON DELETE CASCADE;
ALTER TABLE [core].[role_permission] ADD CONSTRAINT [FK_core_role_permission_permission_id] FOREIGN KEY ([permission_id]) REFERENCES [core].[permission] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[user_role] ADD CONSTRAINT [FK_core_user_role_app_user_id] FOREIGN KEY ([app_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE CASCADE;
ALTER TABLE [core].[user_role] ADD CONSTRAINT [FK_core_user_role_role_id] FOREIGN KEY ([role_id]) REFERENCES [core].[role] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[user_role] ADD CONSTRAINT [FK_core_user_role_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[user_principal_access] ADD CONSTRAINT [FK_core_user_principal_access_app_user_id] FOREIGN KEY ([app_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE CASCADE;
ALTER TABLE [core].[user_principal_access] ADD CONSTRAINT [FK_core_user_principal_access_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[user_device] ADD CONSTRAINT [FK_core_user_device_app_user_id] FOREIGN KEY ([app_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE CASCADE;
ALTER TABLE [core].[lookup_value] ADD CONSTRAINT [FK_core_lookup_value_lookup_type_id] FOREIGN KEY ([lookup_type_id]) REFERENCES [core].[lookup_type] ([id]) ON DELETE CASCADE;
ALTER TABLE [core].[lookup_value] ADD CONSTRAINT [FK_core_lookup_value_parent_value_id] FOREIGN KEY ([parent_value_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[number_series] ADD CONSTRAINT [FK_core_number_series_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[number_series] ADD CONSTRAINT [FK_core_number_series_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[number_series] ADD CONSTRAINT [FK_core_number_series_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[number_series] ADD CONSTRAINT [FK_core_number_series_fiscal_year_id] FOREIGN KEY ([fiscal_year_id]) REFERENCES [acc].[fiscal_year] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[audit_log] ADD CONSTRAINT [FK_core_audit_log_changed_by_user_id] FOREIGN KEY ([changed_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[status_history] ADD CONSTRAINT [FK_core_status_history_changed_by_user_id] FOREIGN KEY ([changed_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[status_history] ADD CONSTRAINT [FK_core_status_history_reason_lookup_id] FOREIGN KEY ([reason_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[approval_rule] ADD CONSTRAINT [FK_core_approval_rule_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[approval_rule] ADD CONSTRAINT [FK_core_approval_rule_approver_role_id] FOREIGN KEY ([approver_role_id]) REFERENCES [core].[role] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[approval_request] ADD CONSTRAINT [FK_core_approval_request_approval_rule_id] FOREIGN KEY ([approval_rule_id]) REFERENCES [core].[approval_rule] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[approval_request] ADD CONSTRAINT [FK_core_approval_request_requested_by_user_id] FOREIGN KEY ([requested_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[approval_request] ADD CONSTRAINT [FK_core_approval_request_approver_user_id] FOREIGN KEY ([approver_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[notification] ADD CONSTRAINT [FK_core_notification_template_id] FOREIGN KEY ([template_id]) REFERENCES [core].[notification_template] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[notification] ADD CONSTRAINT [FK_core_notification_recipient_user_id] FOREIGN KEY ([recipient_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[system_setting] ADD CONSTRAINT [FK_core_system_setting_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[fiscal_year] ADD CONSTRAINT [FK_acc_fiscal_year_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[accounting_period] ADD CONSTRAINT [FK_acc_accounting_period_fiscal_year_id] FOREIGN KEY ([fiscal_year_id]) REFERENCES [acc].[fiscal_year] ([id]) ON DELETE CASCADE;
ALTER TABLE [acc].[accounting_period] ADD CONSTRAINT [FK_acc_accounting_period_locked_by_user_id] FOREIGN KEY ([locked_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[gstin_registration] ADD CONSTRAINT [FK_acc_gstin_registration_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[gstin_registration] ADD CONSTRAINT [FK_acc_gstin_registration_state_id] FOREIGN KEY ([state_id]) REFERENCES [core].[state] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[gst_rate] ADD CONSTRAINT [FK_acc_gst_rate_output_gl_account_id] FOREIGN KEY ([output_gl_account_id]) REFERENCES [acc].[gl_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[gst_rate] ADD CONSTRAINT [FK_acc_gst_rate_input_gl_account_id] FOREIGN KEY ([input_gl_account_id]) REFERENCES [acc].[gl_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[account_group] ADD CONSTRAINT [FK_acc_account_group_account_class_id] FOREIGN KEY ([account_class_id]) REFERENCES [acc].[account_class] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[account_group] ADD CONSTRAINT [FK_acc_account_group_parent_group_id] FOREIGN KEY ([parent_group_id]) REFERENCES [acc].[account_group] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[gl_account] ADD CONSTRAINT [FK_acc_gl_account_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[gl_account] ADD CONSTRAINT [FK_acc_gl_account_account_group_id] FOREIGN KEY ([account_group_id]) REFERENCES [acc].[account_group] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[cost_centre] ADD CONSTRAINT [FK_acc_cost_centre_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[cost_centre] ADD CONSTRAINT [FK_acc_cost_centre_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
GO

/* ---------- 4. Foreign-key indexes (108) ---------- */
CREATE NONCLUSTERED INDEX [IX_core_company_state_id] ON [core].[company] ([state_id]);
CREATE NONCLUSTERED INDEX [IX_core_principal_supplier_id] ON [core].[principal] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_core_district_state_id] ON [core].[district] ([state_id]);
CREATE NONCLUSTERED INDEX [IX_core_pincode_district_id] ON [core].[pincode] ([district_id]);
CREATE NONCLUSTERED INDEX [IX_core_branch_company_id] ON [core].[branch] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_core_branch_parent_warehouse_id] ON [core].[branch] ([parent_warehouse_id]);
CREATE NONCLUSTERED INDEX [IX_core_branch_state_id] ON [core].[branch] ([state_id]);
CREATE NONCLUSTERED INDEX [IX_core_branch_district_id] ON [core].[branch] ([district_id]);
CREATE NONCLUSTERED INDEX [IX_core_branch_pincode_id] ON [core].[branch] ([pincode_id]);
CREATE NONCLUSTERED INDEX [IX_core_branch_gstin_registration_id] ON [core].[branch] ([gstin_registration_id]);
CREATE NONCLUSTERED INDEX [IX_core_location_branch_id] ON [core].[location] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_core_area_branch_id] ON [core].[area] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_core_territory_branch_id] ON [core].[territory] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_core_territory_pincode_territory_id] ON [core].[territory_pincode] ([territory_id]);
CREATE NONCLUSTERED INDEX [IX_core_territory_pincode_pincode_id] ON [core].[territory_pincode] ([pincode_id]);
CREATE NONCLUSTERED INDEX [IX_core_team_branch_id] ON [core].[team] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_core_team_team_lead_employee_id] ON [core].[team] ([team_lead_employee_id]);
CREATE NONCLUSTERED INDEX [IX_core_team_member_team_id] ON [core].[team_member] ([team_id]);
CREATE NONCLUSTERED INDEX [IX_core_team_member_employee_id] ON [core].[team_member] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_core_team_member_territory_id] ON [core].[team_member] ([territory_id]);
CREATE NONCLUSTERED INDEX [IX_core_branch_principal_branch_id] ON [core].[branch_principal] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_core_branch_principal_principal_id] ON [core].[branch_principal] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_core_customer_company_id] ON [core].[customer] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_core_customer_billing_state_id] ON [core].[customer] ([billing_state_id]);
CREATE NONCLUSTERED INDEX [IX_core_customer_billing_pincode_id] ON [core].[customer] ([billing_pincode_id]);
CREATE NONCLUSTERED INDEX [IX_core_customer_area_id] ON [core].[customer] ([area_id]);
CREATE NONCLUSTERED INDEX [IX_core_customer_salesman_employee_id] ON [core].[customer] ([salesman_employee_id]);
CREATE NONCLUSTERED INDEX [IX_core_customer_payment_terms_id] ON [core].[customer] ([payment_terms_id]);
CREATE NONCLUSTERED INDEX [IX_core_customer_principal_customer_id] ON [core].[customer_principal] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_core_customer_principal_principal_id] ON [core].[customer_principal] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_core_customer_principal_account_owner_employee_id] ON [core].[customer_principal] ([account_owner_employee_id]);
CREATE NONCLUSTERED INDEX [IX_core_customer_site_customer_id] ON [core].[customer_site] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_core_customer_site_pincode_id] ON [core].[customer_site] ([pincode_id]);
CREATE NONCLUSTERED INDEX [IX_core_customer_site_district_id] ON [core].[customer_site] ([district_id]);
CREATE NONCLUSTERED INDEX [IX_core_customer_site_state_id] ON [core].[customer_site] ([state_id]);
CREATE NONCLUSTERED INDEX [IX_core_contact_customer_id] ON [core].[contact] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_core_contact_supplier_id] ON [core].[contact] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_core_supplier_company_id] ON [core].[supplier] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_core_supplier_state_id] ON [core].[supplier] ([state_id]);
CREATE NONCLUSTERED INDEX [IX_core_supplier_pincode_id] ON [core].[supplier] ([pincode_id]);
CREATE NONCLUSTERED INDEX [IX_core_supplier_payment_terms_id] ON [core].[supplier] ([payment_terms_id]);
CREATE NONCLUSTERED INDEX [IX_core_supplier_tds_section_id] ON [core].[supplier] ([tds_section_id]);
CREATE NONCLUSTERED INDEX [IX_core_hsn_sac_gst_rate_id] ON [core].[hsn_sac] ([gst_rate_id]);
CREATE NONCLUSTERED INDEX [IX_core_item_category_parent_category_id] ON [core].[item_category] ([parent_category_id]);
CREATE NONCLUSTERED INDEX [IX_core_item_category_default_uom_id] ON [core].[item_category] ([default_uom_id]);
CREATE NONCLUSTERED INDEX [IX_core_item_category_default_hsn_sac_id] ON [core].[item_category] ([default_hsn_sac_id]);
CREATE NONCLUSTERED INDEX [IX_core_item_company_id] ON [core].[item] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_core_item_principal_id] ON [core].[item] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_core_item_category_id] ON [core].[item] ([category_id]);
CREATE NONCLUSTERED INDEX [IX_core_item_uom_id] ON [core].[item] ([uom_id]);
CREATE NONCLUSTERED INDEX [IX_core_item_hsn_sac_id] ON [core].[item] ([hsn_sac_id]);
CREATE NONCLUSTERED INDEX [IX_core_item_machine_model_id] ON [core].[item] ([machine_model_id]);
CREATE NONCLUSTERED INDEX [IX_core_machine_model_principal_id] ON [core].[machine_model] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_core_machine_unit_model_id] ON [core].[machine_unit] ([model_id]);
CREATE NONCLUSTERED INDEX [IX_core_machine_unit_principal_id] ON [core].[machine_unit] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_core_machine_unit_item_id] ON [core].[machine_unit] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_core_machine_unit_customer_id] ON [core].[machine_unit] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_core_machine_unit_customer_site_id] ON [core].[machine_unit] ([customer_site_id]);
CREATE NONCLUSTERED INDEX [IX_core_machine_unit_sold_by_branch_id] ON [core].[machine_unit] ([sold_by_branch_id]);
CREATE NONCLUSTERED INDEX [IX_core_machine_ownership_machine_unit_id] ON [core].[machine_ownership] ([machine_unit_id]);
CREATE NONCLUSTERED INDEX [IX_core_machine_ownership_customer_id] ON [core].[machine_ownership] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_core_machine_meter_reading_machine_unit_id] ON [core].[machine_meter_reading] ([machine_unit_id]);
CREATE NONCLUSTERED INDEX [IX_core_machine_meter_reading_recorded_by_user_id] ON [core].[machine_meter_reading] ([recorded_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_core_machine_meter_reading_photo_attachment_id] ON [core].[machine_meter_reading] ([photo_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_core_employee_company_id] ON [core].[employee] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_core_employee_branch_id] ON [core].[employee] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_core_employee_reporting_manager_id] ON [core].[employee] ([reporting_manager_id]);
CREATE NONCLUSTERED INDEX [IX_core_employee_principal_employee_id] ON [core].[employee_principal] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_core_employee_principal_principal_id] ON [core].[employee_principal] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_core_app_user_default_branch_id] ON [core].[app_user] ([default_branch_id]);
CREATE NONCLUSTERED INDEX [IX_core_role_permission_role_id] ON [core].[role_permission] ([role_id]);
CREATE NONCLUSTERED INDEX [IX_core_role_permission_permission_id] ON [core].[role_permission] ([permission_id]);
CREATE NONCLUSTERED INDEX [IX_core_user_role_app_user_id] ON [core].[user_role] ([app_user_id]);
CREATE NONCLUSTERED INDEX [IX_core_user_role_role_id] ON [core].[user_role] ([role_id]);
CREATE NONCLUSTERED INDEX [IX_core_user_role_branch_id] ON [core].[user_role] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_core_user_principal_access_app_user_id] ON [core].[user_principal_access] ([app_user_id]);
CREATE NONCLUSTERED INDEX [IX_core_user_principal_access_principal_id] ON [core].[user_principal_access] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_core_user_device_app_user_id] ON [core].[user_device] ([app_user_id]);
CREATE NONCLUSTERED INDEX [IX_core_lookup_value_lookup_type_id] ON [core].[lookup_value] ([lookup_type_id]);
CREATE NONCLUSTERED INDEX [IX_core_lookup_value_parent_value_id] ON [core].[lookup_value] ([parent_value_id]);
CREATE NONCLUSTERED INDEX [IX_core_number_series_company_id] ON [core].[number_series] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_core_number_series_branch_id] ON [core].[number_series] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_core_number_series_principal_id] ON [core].[number_series] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_core_number_series_fiscal_year_id] ON [core].[number_series] ([fiscal_year_id]);
CREATE NONCLUSTERED INDEX [IX_core_audit_log_changed_by_user_id] ON [core].[audit_log] ([changed_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_core_status_history_changed_by_user_id] ON [core].[status_history] ([changed_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_core_status_history_reason_lookup_id] ON [core].[status_history] ([reason_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_core_approval_rule_branch_id] ON [core].[approval_rule] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_core_approval_rule_approver_role_id] ON [core].[approval_rule] ([approver_role_id]);
CREATE NONCLUSTERED INDEX [IX_core_approval_request_approval_rule_id] ON [core].[approval_request] ([approval_rule_id]);
CREATE NONCLUSTERED INDEX [IX_core_approval_request_requested_by_user_id] ON [core].[approval_request] ([requested_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_core_approval_request_approver_user_id] ON [core].[approval_request] ([approver_user_id]);
CREATE NONCLUSTERED INDEX [IX_core_notification_template_id] ON [core].[notification] ([template_id]);
CREATE NONCLUSTERED INDEX [IX_core_notification_recipient_user_id] ON [core].[notification] ([recipient_user_id]);
CREATE NONCLUSTERED INDEX [IX_core_system_setting_company_id] ON [core].[system_setting] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_acc_fiscal_year_company_id] ON [acc].[fiscal_year] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_acc_accounting_period_fiscal_year_id] ON [acc].[accounting_period] ([fiscal_year_id]);
CREATE NONCLUSTERED INDEX [IX_acc_accounting_period_locked_by_user_id] ON [acc].[accounting_period] ([locked_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gstin_registration_company_id] ON [acc].[gstin_registration] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gstin_registration_state_id] ON [acc].[gstin_registration] ([state_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gst_rate_output_gl_account_id] ON [acc].[gst_rate] ([output_gl_account_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gst_rate_input_gl_account_id] ON [acc].[gst_rate] ([input_gl_account_id]);
CREATE NONCLUSTERED INDEX [IX_acc_account_group_account_class_id] ON [acc].[account_group] ([account_class_id]);
CREATE NONCLUSTERED INDEX [IX_acc_account_group_parent_group_id] ON [acc].[account_group] ([parent_group_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gl_account_company_id] ON [acc].[gl_account] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gl_account_account_group_id] ON [acc].[gl_account] ([account_group_id]);
CREATE NONCLUSTERED INDEX [IX_acc_cost_centre_branch_id] ON [acc].[cost_centre] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_acc_cost_centre_principal_id] ON [acc].[cost_centre] ([principal_id]);
GO

/* =====================================================================
   TRISHUL Integrated System - SQL Server DDL (dictionary v2)
   Phase 1 - Call & Service
   Generated from the TRISHUL Database Dictionary. Do not edit by hand:
   change the dictionary and regenerate.
   Target: SQL Server 2019+ / Amazon RDS for SQL Server
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
/* ---------- 1. Tables (26) ---------- */

/* ===== svc: Call & Service ===== */
-- ASC / AMC / extended warranty / free-service contracts.
CREATE TABLE [svc].[service_contract] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_service_contract] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [contract_no] NVARCHAR(30) NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [customer_id] BIGINT NOT NULL,
    [contract_type] NVARCHAR(30) NOT NULL,
    [start_date] DATE NOT NULL,
    [end_date] DATE NOT NULL,
    [hours_limit] INT NULL,
    [visits_included] SMALLINT NULL,
    [visits_used] SMALLINT NOT NULL CONSTRAINT [DF_svc_service_contract_visits_used] DEFAULT (0),
    [contract_value] DECIMAL(18,2) NULL,
    [sales_invoice_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [terms] NVARCHAR(2000) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_service_contract_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_service_contract_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_service_contract_contract_type] CHECK ([contract_type] IN (N'ASC', N'AMC', N'Extended warranty', N'Free service')),
    CONSTRAINT [CK_svc_service_contract_status] CHECK ([status] IN (N'Draft', N'Active', N'Expired', N'Cancelled'))
);
GO
-- Machines covered by a contract and what is covered.
CREATE TABLE [svc].[contract_coverage] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_contract_coverage] PRIMARY KEY,
    [service_contract_id] BIGINT NOT NULL,
    [machine_unit_id] BIGINT NOT NULL,
    [covers_labour] BIT NOT NULL CONSTRAINT [DF_svc_contract_coverage_covers_labour] DEFAULT (1),
    [covers_parts] BIT NOT NULL CONSTRAINT [DF_svc_contract_coverage_covers_parts] DEFAULT (0),
    [covers_travel] BIT NOT NULL CONSTRAINT [DF_svc_contract_coverage_covers_travel] DEFAULT (1),
    [parts_discount_pct] DECIMAL(5,2) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_contract_coverage_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_contract_coverage_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Inspection checklist by model and call type.
CREATE TABLE [svc].[checklist_template] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_checklist_template] PRIMARY KEY,
    [name] NVARCHAR(120) NOT NULL,
    [principal_id] BIGINT NULL,
    [machine_model_id] BIGINT NULL,
    [call_type_lookup_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_checklist_template_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_checklist_template_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Questions in a checklist.
CREATE TABLE [svc].[checklist_template_item] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_checklist_template_item] PRIMARY KEY,
    [checklist_template_id] BIGINT NOT NULL,
    [sequence] SMALLINT NOT NULL,
    [item_text] NVARCHAR(300) NOT NULL,
    [response_type] NVARCHAR(30) NOT NULL,
    [is_mandatory] BIT NOT NULL CONSTRAINT [DF_svc_checklist_template_item_is_mandatory] DEFAULT (1),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_checklist_template_item_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_checklist_template_item_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_checklist_template_item_response_type] CHECK ([response_type] IN (N'OK Not OK', N'Number', N'Text', N'Photo'))
);
GO
-- Periodic service plan per model, e.g. 50 / 250 / 500 hours.
CREATE TABLE [svc].[service_schedule_template] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_service_schedule_template] PRIMARY KEY,
    [machine_model_id] BIGINT NOT NULL,
    [service_name] NVARCHAR(80) NOT NULL,
    [due_at_hmr] INT NULL,
    [due_after_days] SMALLINT NULL,
    [tolerance_hmr] SMALLINT NULL,
    [is_free] BIT NOT NULL CONSTRAINT [DF_svc_service_schedule_template_is_free] DEFAULT (0),
    [checklist_template_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_service_schedule_template_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_service_schedule_template_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Scheduled service due for a specific machine.
CREATE TABLE [svc].[planned_service] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_planned_service] PRIMARY KEY,
    [machine_unit_id] BIGINT NOT NULL,
    [schedule_template_id] BIGINT NOT NULL,
    [due_hmr] INT NULL,
    [due_date] DATE NULL,
    [status] NVARCHAR(30) NOT NULL,
    [service_call_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_planned_service_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_planned_service_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_planned_service_status] CHECK ([status] IN (N'Upcoming', N'Due', N'Overdue', N'Call raised', N'Done', N'Skipped'))
);
GO
-- Service call (complaint / request). Replaces the register copy and Excel sheet.
CREATE TABLE [svc].[service_call] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_service_call] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [call_no] NVARCHAR(30) NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [client_uuid] UNIQUEIDENTIFIER NULL,
    [call_source_lookup_id] BIGINT NOT NULL,
    [call_type_lookup_id] BIGINT NOT NULL,
    [complaint_category_lookup_id] BIGINT NULL,
    [complaint_description] NVARCHAR(2000) NOT NULL,
    [customer_id] BIGINT NOT NULL,
    [customer_site_id] BIGINT NULL,
    [contact_id] BIGINT NULL,
    [caller_name] NVARCHAR(100) NULL,
    [caller_phone] NVARCHAR(15) NOT NULL,
    [machine_unit_id] BIGINT NULL,
    [reported_hmr] DECIMAL(10,1) NULL,
    [is_machine_down] BIT NOT NULL CONSTRAINT [DF_svc_service_call_is_machine_down] DEFAULT (0),
    [coverage_type] NVARCHAR(30) NULL,
    [service_contract_id] BIGINT NULL,
    [planned_service_id] BIGINT NULL,
    [priority] NVARCHAR(30) NOT NULL CONSTRAINT [DF_svc_service_call_priority] DEFAULT (N'Normal'),
    [is_asc_priority] BIT NOT NULL CONSTRAINT [DF_svc_service_call_is_asc_priority] DEFAULT (0),
    [received_at] DATETIME2(0) NOT NULL,
    [received_by_user_id] BIGINT NULL,
    [source_reference] NVARCHAR(150) NULL,
    [current_status] NVARCHAR(30) NOT NULL,
    [team_id] BIGINT NULL,
    [assigned_engineer_id] BIGINT NULL,
    [oem_call_id] NVARCHAR(40) NULL,
    [sla_due_at] DATETIME2(0) NULL,
    [first_response_at] DATETIME2(0) NULL,
    [closed_at] DATETIME2(0) NULL,
    [closed_by_user_id] BIGINT NULL,
    [closure_type] NVARCHAR(30) NULL,
    [duplicate_of_call_id] BIGINT NULL,
    [customer_rating] TINYINT NULL,
    [customer_feedback] NVARCHAR(500) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_service_call_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_service_call_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_service_call_coverage_type] CHECK ([coverage_type] IN (N'Warranty', N'Contract', N'Chargeable', N'Goodwill')),
    CONSTRAINT [CK_svc_service_call_priority] CHECK ([priority] IN (N'Critical', N'High', N'Normal', N'Low')),
    CONSTRAINT [CK_svc_service_call_current_status] CHECK ([current_status] IN (N'Logged', N'Assigned', N'Call ID linked', N'Customer contacted', N'Trip started', N'Reached site', N'In progress', N'Report submitted', N'Closed', N'Cancelled')),
    CONSTRAINT [CK_svc_service_call_closure_type] CHECK ([closure_type] IN (N'Resolved', N'Cancelled', N'Duplicate', N'Not reachable'))
);
GO
-- Every status change on a call (drives the 24-hour rule and reports).
CREATE TABLE [svc].[call_status_log] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_call_status_log] PRIMARY KEY,
    [service_call_id] BIGINT NOT NULL,
    [from_status] NVARCHAR(30) NULL,
    [to_status] NVARCHAR(30) NOT NULL,
    [changed_at] DATETIME2(0) NOT NULL,
    [changed_by_user_id] BIGINT NULL,
    [reason_lookup_id] BIGINT NULL,
    [remarks] NVARCHAR(500) NULL,
    [latitude] DECIMAL(9,6) NULL,
    [longitude] DECIMAL(9,6) NULL,
    [client_uuid] UNIQUEIDENTIFIER NULL
);
GO
-- Engineer assignments and reassignments by the Team Lead.
CREATE TABLE [svc].[call_assignment] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_call_assignment] PRIMARY KEY,
    [service_call_id] BIGINT NOT NULL,
    [engineer_employee_id] BIGINT NOT NULL,
    [assignment_type] NVARCHAR(30) NOT NULL CONSTRAINT [DF_svc_call_assignment_assignment_type] DEFAULT (N'Primary'),
    [assigned_by_user_id] BIGINT NOT NULL,
    [assigned_at] DATETIME2(0) NOT NULL,
    [reason_lookup_id] BIGINT NULL,
    [distance_km_at_assignment] DECIMAL(8,2) NULL,
    [unassigned_at] DATETIME2(0) NULL,
    [is_current] BIT NOT NULL CONSTRAINT [DF_svc_call_assignment_is_current] DEFAULT (1),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_call_assignment_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_call_assignment_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_call_assignment_assignment_type] CHECK ([assignment_type] IN (N'Primary', N'Support'))
);
GO
-- Link to the call in the brand's OEM portal (E-DOST / SAP ByD for Tata Hitachi; other portals for other brands).
CREATE TABLE [svc].[oem_call_reference] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_oem_call_reference] PRIMARY KEY,
    [service_call_id] BIGINT NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [external_system_id] BIGINT NULL,
    [oem_call_id] NVARCHAR(40) NOT NULL,
    [oem_ticket_uuid] NVARCHAR(40) NULL,
    [created_in_oem_by] NVARCHAR(30) NOT NULL,
    [entered_by_user_id] BIGINT NULL,
    [entered_at] DATETIME2(0) NULL,
    [verified_by_user_id] BIGINT NULL,
    [verified_at] DATETIME2(0) NULL,
    [sync_status] NVARCHAR(30) NOT NULL CONSTRAINT [DF_svc_oem_call_reference_sync_status] DEFAULT (N'Manual'),
    [last_sync_log_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_oem_call_reference_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_oem_call_reference_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_oem_call_reference_created_in_oem_by] CHECK ([created_in_oem_by] IN (N'Back office', N'Engineer', N'API')),
    CONSTRAINT [CK_svc_oem_call_reference_sync_status] CHECK ([sync_status] IN (N'Manual', N'Pending', N'Synced', N'Failed'))
);
GO
-- Each visit to site for a call (inspection, repair, parts fitment...).
CREATE TABLE [svc].[service_visit] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_service_visit] PRIMARY KEY,
    [service_call_id] BIGINT NOT NULL,
    [visit_no] TINYINT NOT NULL,
    [client_uuid] UNIQUEIDENTIFIER NULL,
    [visit_purpose] NVARCHAR(30) NOT NULL,
    [engineer_employee_id] BIGINT NOT NULL,
    [planned_date] DATE NULL,
    [customer_contacted_at] DATETIME2(0) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [service_started_at] DATETIME2(0) NULL,
    [service_ended_at] DATETIME2(0) NULL,
    [site_latitude] DECIMAL(9,6) NULL,
    [site_longitude] DECIMAL(9,6) NULL,
    [next_action] NVARCHAR(30) NULL,
    [remarks] NVARCHAR(1000) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_service_visit_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_service_visit_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_service_visit_visit_purpose] CHECK ([visit_purpose] IN (N'Inspection', N'Repair', N'Parts fitment', N'Periodic service', N'Follow up', N'Installation')),
    CONSTRAINT [CK_svc_service_visit_status] CHECK ([status] IN (N'Planned', N'On the way', N'On site', N'Completed', N'Cancelled')),
    CONSTRAINT [CK_svc_service_visit_next_action] CHECK ([next_action] IN (N'None', N'Parts required', N'Revisit', N'Escalate'))
);
GO
-- Engineer's trip for a visit: start, end, route, km, time.
CREATE TABLE [svc].[trip] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_trip] PRIMARY KEY,
    [service_visit_id] BIGINT NOT NULL,
    [engineer_employee_id] BIGINT NOT NULL,
    [client_uuid] UNIQUEIDENTIFIER NULL,
    [trip_type] NVARCHAR(30) NOT NULL,
    [start_at] DATETIME2(0) NOT NULL,
    [start_latitude] DECIMAL(9,6) NOT NULL,
    [start_longitude] DECIMAL(9,6) NOT NULL,
    [end_at] DATETIME2(0) NULL,
    [end_latitude] DECIMAL(9,6) NULL,
    [end_longitude] DECIMAL(9,6) NULL,
    [gps_distance_km] DECIMAL(8,2) NULL,
    [map_distance_km] DECIMAL(8,2) NULL,
    [duration_minutes] INT NULL,
    [vehicle_type] NVARCHAR(30) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [route_polyline] NVARCHAR(MAX) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_trip_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_trip_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_trip_trip_type] CHECK ([trip_type] IN (N'To site', N'Return', N'Site to site')),
    CONSTRAINT [CK_svc_trip_vehicle_type] CHECK ([vehicle_type] IN (N'Own bike', N'Own car', N'Company vehicle', N'Public transport')),
    CONSTRAINT [CK_svc_trip_status] CHECK ([status] IN (N'In progress', N'Completed', N'Auto closed'))
);
GO
-- GPS points during a trip. Very high volume: partition by month.
CREATE TABLE [svc].[trip_gps_point] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_trip_gps_point] PRIMARY KEY,
    [trip_id] BIGINT NOT NULL,
    [recorded_at] DATETIME2(0) NOT NULL,
    [latitude] DECIMAL(9,6) NOT NULL,
    [longitude] DECIMAL(9,6) NOT NULL,
    [accuracy_m] DECIMAL(6,1) NULL,
    [speed_kmph] DECIMAL(5,1) NULL,
    [battery_pct] TINYINT NULL,
    [is_mock_location] BIT NOT NULL CONSTRAINT [DF_svc_trip_gps_point_is_mock_location] DEFAULT (0)
);
GO
-- Daily duty on / off for engineers (GPS runs only on duty).
CREATE TABLE [svc].[engineer_duty_log] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_engineer_duty_log] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [duty_date] DATE NOT NULL,
    [client_uuid] UNIQUEIDENTIFIER NULL,
    [duty_on_at] DATETIME2(0) NULL,
    [duty_on_latitude] DECIMAL(9,6) NULL,
    [duty_on_longitude] DECIMAL(9,6) NULL,
    [duty_off_at] DATETIME2(0) NULL,
    [duty_off_latitude] DECIMAL(9,6) NULL,
    [duty_off_longitude] DECIMAL(9,6) NULL,
    [total_km] DECIMAL(8,2) NULL,
    [calls_attended] SMALLINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_engineer_duty_log_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_engineer_duty_log_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Service report submitted at the end of a visit.
CREATE TABLE [svc].[service_report] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_service_report] PRIMARY KEY,
    [service_visit_id] BIGINT NOT NULL,
    [report_no] NVARCHAR(30) NOT NULL,
    [client_uuid] UNIQUEIDENTIFIER NULL,
    [hmr_reading] DECIMAL(10,1) NULL,
    [machine_condition_lookup_id] BIGINT NULL,
    [complaint_observed] NVARCHAR(1000) NULL,
    [findings] NVARCHAR(2000) NULL,
    [failure_code_lookup_id] BIGINT NULL,
    [action_taken] NVARCHAR(2000) NULL,
    [is_parts_required] BIT NOT NULL CONSTRAINT [DF_svc_service_report_is_parts_required] DEFAULT (0),
    [labour_hours] DECIMAL(6,2) NULL,
    [recommendations] NVARCHAR(1000) NULL,
    [customer_signed_name] NVARCHAR(100) NULL,
    [customer_signed_mobile] NVARCHAR(15) NULL,
    [customer_signature_attachment_id] BIGINT NULL,
    [is_closure_otp_verified] BIT NOT NULL CONSTRAINT [DF_svc_service_report_is_closure_otp_verified] DEFAULT (0),
    [engineer_signature_attachment_id] BIGINT NULL,
    [pdf_attachment_id] BIGINT NULL,
    [submitted_at] DATETIME2(0) NULL,
    [is_offline_submitted] BIT NOT NULL CONSTRAINT [DF_svc_service_report_is_offline_submitted] DEFAULT (0),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_service_report_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_service_report_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Checklist answers in a service report.
CREATE TABLE [svc].[report_checklist_item] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_report_checklist_item] PRIMARY KEY,
    [service_report_id] BIGINT NOT NULL,
    [checklist_template_item_id] BIGINT NULL,
    [item_text] NVARCHAR(300) NOT NULL,
    [response_value] NVARCHAR(200) NULL,
    [is_ok] BIT NULL,
    [remarks] NVARCHAR(300) NULL,
    [photo_attachment_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_report_checklist_item_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_report_checklist_item_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Parts needed for a call. Captured in Phase 1; issued from stock in Phase 2.
CREATE TABLE [svc].[service_part_request] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_service_part_request] PRIMARY KEY,
    [service_call_id] BIGINT NOT NULL,
    [service_visit_id] BIGINT NULL,
    [item_id] BIGINT NULL,
    [part_description] NVARCHAR(200) NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [uom_id] BIGINT NULL,
    [is_chargeable] BIT NOT NULL CONSTRAINT [DF_svc_service_part_request_is_chargeable] DEFAULT (1),
    [status] NVARCHAR(30) NOT NULL,
    [requested_by_employee_id] BIGINT NULL,
    [required_by_date] DATE NULL,
    [stock_reservation_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_service_part_request_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_service_part_request_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_service_part_request_status] CHECK ([status] IN (N'Requested', N'Approved', N'Reserved', N'Issued', N'Fitted', N'Returned', N'Cancelled'))
);
GO
-- Chargeable items on a call, billed in Phase 4.
CREATE TABLE [svc].[service_charge] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_service_charge] PRIMARY KEY,
    [service_call_id] BIGINT NOT NULL,
    [charge_type] NVARCHAR(30) NOT NULL,
    [description] NVARCHAR(200) NOT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [rate] DECIMAL(18,4) NOT NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [is_billable] BIT NOT NULL CONSTRAINT [DF_svc_service_charge_is_billable] DEFAULT (1),
    [sales_invoice_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_service_charge_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_service_charge_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_service_charge_charge_type] CHECK ([charge_type] IN (N'Labour', N'Travel', N'Parts', N'Other'))
);
GO
-- Response and closure targets per brand (default 24 hours).
CREATE TABLE [svc].[sla_rule] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_sla_rule] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [principal_id] BIGINT NULL,
    [call_type_lookup_id] BIGINT NULL,
    [priority] NVARCHAR(30) NULL,
    [response_hours] DECIMAL(5,1) NULL,
    [resolution_hours] DECIMAL(5,1) NOT NULL CONSTRAINT [DF_svc_sla_rule_resolution_hours] DEFAULT (24),
    [clock_type] NVARCHAR(30) NOT NULL CONSTRAINT [DF_svc_sla_rule_clock_type] DEFAULT (N'Calendar'),
    [alert_before_minutes] INT NULL,
    [escalate_to_role_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_sla_rule_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_sla_rule_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_sla_rule_priority] CHECK ([priority] IN (N'Critical', N'High', N'Normal', N'Low')),
    CONSTRAINT [CK_svc_sla_rule_clock_type] CHECK ([clock_type] IN (N'Calendar', N'Working hours'))
);
GO
-- Warnings, breaches and escalations raised on calls.
CREATE TABLE [svc].[sla_event] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_sla_event] PRIMARY KEY,
    [service_call_id] BIGINT NOT NULL,
    [sla_rule_id] BIGINT NULL,
    [event_type] NVARCHAR(30) NOT NULL,
    [event_at] DATETIME2(0) NOT NULL,
    [notified_user_id] BIGINT NULL,
    CONSTRAINT [CK_svc_sla_event_event_type] CHECK ([event_type] IN (N'Warning', N'Breached', N'Escalated'))
);
GO

/* ===== int: Integration ===== */
-- Connected systems. Credentials stay in AWS Secrets Manager.
CREATE TABLE [int].[external_system] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_int_external_system] PRIMARY KEY,
    [code] NVARCHAR(20) NOT NULL,
    [principal_id] BIGINT NULL,
    [name] NVARCHAR(100) NOT NULL,
    [base_url] NVARCHAR(300) NULL,
    [auth_type] NVARCHAR(30) NOT NULL,
    [credential_secret_name] NVARCHAR(100) NULL,
    [is_enabled] BIT NOT NULL CONSTRAINT [DF_int_external_system_is_enabled] DEFAULT (0),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_int_external_system_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_int_external_system_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_int_external_system_auth_type] CHECK ([auth_type] IN (N'Basic', N'OAuth2', N'API key', N'Certificate', N'None'))
);
GO
-- Our ID to external ID mapping (replaces the byd_* columns; works for every OEM portal).
CREATE TABLE [int].[sync_mapping] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_int_sync_mapping] PRIMARY KEY,
    [external_system_id] BIGINT NOT NULL,
    [entity_type] NVARCHAR(50) NOT NULL,
    [internal_id] BIGINT NOT NULL,
    [external_id] NVARCHAR(100) NOT NULL,
    [external_uuid] NVARCHAR(64) NULL,
    [last_synced_at] DATETIME2(0) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_int_sync_mapping_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_int_sync_mapping_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Every API call to or from an external system, with retry state.
CREATE TABLE [int].[sync_log] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_int_sync_log] PRIMARY KEY,
    [external_system_id] BIGINT NOT NULL,
    [entity_type] NVARCHAR(50) NULL,
    [entity_id] BIGINT NULL,
    [direction] NVARCHAR(30) NOT NULL,
    [operation] NVARCHAR(30) NOT NULL,
    [request_payload] NVARCHAR(MAX) NULL,
    [response_payload] NVARCHAR(MAX) NULL,
    [http_status] SMALLINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [attempt_count] TINYINT NOT NULL CONSTRAINT [DF_int_sync_log_attempt_count] DEFAULT (1),
    [next_retry_at] DATETIME2(0) NULL,
    [error_message] NVARCHAR(1000) NULL,
    [started_at] DATETIME2(0) NOT NULL,
    [finished_at] DATETIME2(0) NULL,
    CONSTRAINT [CK_int_sync_log_direction] CHECK ([direction] IN (N'Outbound', N'Inbound')),
    CONSTRAINT [CK_int_sync_log_operation] CHECK ([operation] IN (N'Create', N'Update', N'Read', N'Delete')),
    CONSTRAINT [CK_int_sync_log_status] CHECK ([status] IN (N'Success', N'Failed', N'Retrying'))
);
GO
-- Excel/CSV imports (masters, ByD exports, bank statements).
CREATE TABLE [int].[file_import] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_int_file_import] PRIMARY KEY,
    [external_system_id] BIGINT NULL,
    [import_type] NVARCHAR(30) NOT NULL,
    [file_name] NVARCHAR(200) NOT NULL,
    [s3_key] NVARCHAR(500) NOT NULL,
    [uploaded_by_user_id] BIGINT NOT NULL,
    [uploaded_at] DATETIME2(0) NOT NULL,
    [total_rows] INT NULL,
    [success_rows] INT NULL,
    [error_rows] INT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [error_report_attachment_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_int_file_import_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_int_file_import_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_int_file_import_import_type] CHECK ([import_type] IN (N'Customers', N'Machines', N'Items', N'Open calls', N'Registered products', N'Service tickets', N'Bank statement', N'Opening balances')),
    CONSTRAINT [CK_int_file_import_status] CHECK ([status] IN (N'Uploaded', N'Validating', N'Imported', N'Failed'))
);
GO
-- Row-level import errors.
CREATE TABLE [int].[file_import_error] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_int_file_import_error] PRIMARY KEY,
    [file_import_id] BIGINT NOT NULL,
    [row_number] INT NOT NULL,
    [column_name] NVARCHAR(60) NULL,
    [error_message] NVARCHAR(500) NOT NULL,
    [raw_row_json] NVARCHAR(MAX) NULL
);
GO
-- Inbound events (WhatsApp replies, ByD notifications).
CREATE TABLE [int].[webhook_event] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_int_webhook_event] PRIMARY KEY,
    [external_system_id] BIGINT NOT NULL,
    [event_type] NVARCHAR(60) NOT NULL,
    [payload] NVARCHAR(MAX) NOT NULL,
    [received_at] DATETIME2(0) NOT NULL,
    [processed_at] DATETIME2(0) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [error_message] NVARCHAR(500) NULL,
    CONSTRAINT [CK_int_webhook_event_status] CHECK ([status] IN (N'Received', N'Processed', N'Failed', N'Ignored'))
);
GO

/* ---------- 2. Unique keys (16) ---------- */
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_service_contract_contract_no] ON [svc].[service_contract] ([contract_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_contract_coverage_k1] ON [svc].[contract_coverage] ([service_contract_id], [machine_unit_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_service_call_call_no] ON [svc].[service_call] ([call_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_service_call_client_uuid] ON [svc].[service_call] ([client_uuid]) WHERE [client_uuid] IS NOT NULL;
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_call_status_log_client_uuid] ON [svc].[call_status_log] ([client_uuid]) WHERE [client_uuid] IS NOT NULL;
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_oem_call_reference_service_call_id] ON [svc].[oem_call_reference] ([service_call_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_service_visit_client_uuid] ON [svc].[service_visit] ([client_uuid]) WHERE [client_uuid] IS NOT NULL;
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_service_visit_k1] ON [svc].[service_visit] ([service_call_id], [visit_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_trip_client_uuid] ON [svc].[trip] ([client_uuid]) WHERE [client_uuid] IS NOT NULL;
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_engineer_duty_log_client_uuid] ON [svc].[engineer_duty_log] ([client_uuid]) WHERE [client_uuid] IS NOT NULL;
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_engineer_duty_log_k1] ON [svc].[engineer_duty_log] ([employee_id], [duty_date]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_service_report_service_visit_id] ON [svc].[service_report] ([service_visit_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_service_report_report_no] ON [svc].[service_report] ([report_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_service_report_client_uuid] ON [svc].[service_report] ([client_uuid]) WHERE [client_uuid] IS NOT NULL;
CREATE UNIQUE NONCLUSTERED INDEX [UX_int_external_system_code] ON [int].[external_system] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_int_sync_mapping_k1] ON [int].[sync_mapping] ([external_system_id], [entity_type], [internal_id]);
GO

/* ---------- 3. Foreign keys (81) ----------
   Includes links from earlier-phase columns to tables created in this phase. */
ALTER TABLE [core].[machine_meter_reading] ADD CONSTRAINT [FK_core_machine_meter_reading_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_contract] ADD CONSTRAINT [FK_svc_service_contract_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_contract] ADD CONSTRAINT [FK_svc_service_contract_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_contract] ADD CONSTRAINT [FK_svc_service_contract_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[contract_coverage] ADD CONSTRAINT [FK_svc_contract_coverage_service_contract_id] FOREIGN KEY ([service_contract_id]) REFERENCES [svc].[service_contract] ([id]) ON DELETE CASCADE;
ALTER TABLE [svc].[contract_coverage] ADD CONSTRAINT [FK_svc_contract_coverage_machine_unit_id] FOREIGN KEY ([machine_unit_id]) REFERENCES [core].[machine_unit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[checklist_template] ADD CONSTRAINT [FK_svc_checklist_template_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[checklist_template] ADD CONSTRAINT [FK_svc_checklist_template_machine_model_id] FOREIGN KEY ([machine_model_id]) REFERENCES [core].[machine_model] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[checklist_template] ADD CONSTRAINT [FK_svc_checklist_template_call_type_lookup_id] FOREIGN KEY ([call_type_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[checklist_template_item] ADD CONSTRAINT [FK_svc_checklist_template_item_checklist_template_id] FOREIGN KEY ([checklist_template_id]) REFERENCES [svc].[checklist_template] ([id]) ON DELETE CASCADE;
ALTER TABLE [svc].[service_schedule_template] ADD CONSTRAINT [FK_svc_service_schedule_template_machine_model_id] FOREIGN KEY ([machine_model_id]) REFERENCES [core].[machine_model] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_schedule_template] ADD CONSTRAINT [FK_svc_service_schedule_template_checklist_template_id] FOREIGN KEY ([checklist_template_id]) REFERENCES [svc].[checklist_template] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[planned_service] ADD CONSTRAINT [FK_svc_planned_service_machine_unit_id] FOREIGN KEY ([machine_unit_id]) REFERENCES [core].[machine_unit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[planned_service] ADD CONSTRAINT [FK_svc_planned_service_schedule_template_id] FOREIGN KEY ([schedule_template_id]) REFERENCES [svc].[service_schedule_template] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[planned_service] ADD CONSTRAINT [FK_svc_planned_service_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_call_source_lookup_id] FOREIGN KEY ([call_source_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_call_type_lookup_id] FOREIGN KEY ([call_type_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_complaint_category_lookup_id] FOREIGN KEY ([complaint_category_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_customer_site_id] FOREIGN KEY ([customer_site_id]) REFERENCES [core].[customer_site] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_contact_id] FOREIGN KEY ([contact_id]) REFERENCES [core].[contact] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_machine_unit_id] FOREIGN KEY ([machine_unit_id]) REFERENCES [core].[machine_unit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_service_contract_id] FOREIGN KEY ([service_contract_id]) REFERENCES [svc].[service_contract] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_planned_service_id] FOREIGN KEY ([planned_service_id]) REFERENCES [svc].[planned_service] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_received_by_user_id] FOREIGN KEY ([received_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_team_id] FOREIGN KEY ([team_id]) REFERENCES [core].[team] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_assigned_engineer_id] FOREIGN KEY ([assigned_engineer_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_closed_by_user_id] FOREIGN KEY ([closed_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_call] ADD CONSTRAINT [FK_svc_service_call_duplicate_of_call_id] FOREIGN KEY ([duplicate_of_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[call_status_log] ADD CONSTRAINT [FK_svc_call_status_log_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE CASCADE;
ALTER TABLE [svc].[call_status_log] ADD CONSTRAINT [FK_svc_call_status_log_changed_by_user_id] FOREIGN KEY ([changed_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[call_status_log] ADD CONSTRAINT [FK_svc_call_status_log_reason_lookup_id] FOREIGN KEY ([reason_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[call_assignment] ADD CONSTRAINT [FK_svc_call_assignment_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE CASCADE;
ALTER TABLE [svc].[call_assignment] ADD CONSTRAINT [FK_svc_call_assignment_engineer_employee_id] FOREIGN KEY ([engineer_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[call_assignment] ADD CONSTRAINT [FK_svc_call_assignment_assigned_by_user_id] FOREIGN KEY ([assigned_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[call_assignment] ADD CONSTRAINT [FK_svc_call_assignment_reason_lookup_id] FOREIGN KEY ([reason_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[oem_call_reference] ADD CONSTRAINT [FK_svc_oem_call_reference_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[oem_call_reference] ADD CONSTRAINT [FK_svc_oem_call_reference_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[oem_call_reference] ADD CONSTRAINT [FK_svc_oem_call_reference_external_system_id] FOREIGN KEY ([external_system_id]) REFERENCES [int].[external_system] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[oem_call_reference] ADD CONSTRAINT [FK_svc_oem_call_reference_entered_by_user_id] FOREIGN KEY ([entered_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[oem_call_reference] ADD CONSTRAINT [FK_svc_oem_call_reference_verified_by_user_id] FOREIGN KEY ([verified_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[oem_call_reference] ADD CONSTRAINT [FK_svc_oem_call_reference_last_sync_log_id] FOREIGN KEY ([last_sync_log_id]) REFERENCES [int].[sync_log] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_visit] ADD CONSTRAINT [FK_svc_service_visit_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE CASCADE;
ALTER TABLE [svc].[service_visit] ADD CONSTRAINT [FK_svc_service_visit_engineer_employee_id] FOREIGN KEY ([engineer_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[trip] ADD CONSTRAINT [FK_svc_trip_service_visit_id] FOREIGN KEY ([service_visit_id]) REFERENCES [svc].[service_visit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[trip] ADD CONSTRAINT [FK_svc_trip_engineer_employee_id] FOREIGN KEY ([engineer_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[trip_gps_point] ADD CONSTRAINT [FK_svc_trip_gps_point_trip_id] FOREIGN KEY ([trip_id]) REFERENCES [svc].[trip] ([id]) ON DELETE CASCADE;
ALTER TABLE [svc].[engineer_duty_log] ADD CONSTRAINT [FK_svc_engineer_duty_log_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_report] ADD CONSTRAINT [FK_svc_service_report_service_visit_id] FOREIGN KEY ([service_visit_id]) REFERENCES [svc].[service_visit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_report] ADD CONSTRAINT [FK_svc_service_report_machine_condition_lookup_id] FOREIGN KEY ([machine_condition_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_report] ADD CONSTRAINT [FK_svc_service_report_failure_code_lookup_id] FOREIGN KEY ([failure_code_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_report] ADD CONSTRAINT [FK_svc_service_report_customer_signature_attachment_id] FOREIGN KEY ([customer_signature_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_report] ADD CONSTRAINT [FK_svc_service_report_engineer_signature_attachment_id] FOREIGN KEY ([engineer_signature_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_report] ADD CONSTRAINT [FK_svc_service_report_pdf_attachment_id] FOREIGN KEY ([pdf_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[report_checklist_item] ADD CONSTRAINT [FK_svc_report_checklist_item_service_report_id] FOREIGN KEY ([service_report_id]) REFERENCES [svc].[service_report] ([id]) ON DELETE CASCADE;
ALTER TABLE [svc].[report_checklist_item] ADD CONSTRAINT [FK_svc_report_checklist_item_checklist_template_item_id] FOREIGN KEY ([checklist_template_item_id]) REFERENCES [svc].[checklist_template_item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[report_checklist_item] ADD CONSTRAINT [FK_svc_report_checklist_item_photo_attachment_id] FOREIGN KEY ([photo_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_part_request] ADD CONSTRAINT [FK_svc_service_part_request_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_part_request] ADD CONSTRAINT [FK_svc_service_part_request_service_visit_id] FOREIGN KEY ([service_visit_id]) REFERENCES [svc].[service_visit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_part_request] ADD CONSTRAINT [FK_svc_service_part_request_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_part_request] ADD CONSTRAINT [FK_svc_service_part_request_uom_id] FOREIGN KEY ([uom_id]) REFERENCES [core].[uom] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_part_request] ADD CONSTRAINT [FK_svc_service_part_request_requested_by_employee_id] FOREIGN KEY ([requested_by_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_charge] ADD CONSTRAINT [FK_svc_service_charge_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[sla_rule] ADD CONSTRAINT [FK_svc_sla_rule_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[sla_rule] ADD CONSTRAINT [FK_svc_sla_rule_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[sla_rule] ADD CONSTRAINT [FK_svc_sla_rule_call_type_lookup_id] FOREIGN KEY ([call_type_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[sla_rule] ADD CONSTRAINT [FK_svc_sla_rule_escalate_to_role_id] FOREIGN KEY ([escalate_to_role_id]) REFERENCES [core].[role] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[sla_event] ADD CONSTRAINT [FK_svc_sla_event_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE CASCADE;
ALTER TABLE [svc].[sla_event] ADD CONSTRAINT [FK_svc_sla_event_sla_rule_id] FOREIGN KEY ([sla_rule_id]) REFERENCES [svc].[sla_rule] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[sla_event] ADD CONSTRAINT [FK_svc_sla_event_notified_user_id] FOREIGN KEY ([notified_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [int].[external_system] ADD CONSTRAINT [FK_int_external_system_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [int].[sync_mapping] ADD CONSTRAINT [FK_int_sync_mapping_external_system_id] FOREIGN KEY ([external_system_id]) REFERENCES [int].[external_system] ([id]) ON DELETE NO ACTION;
ALTER TABLE [int].[sync_log] ADD CONSTRAINT [FK_int_sync_log_external_system_id] FOREIGN KEY ([external_system_id]) REFERENCES [int].[external_system] ([id]) ON DELETE NO ACTION;
ALTER TABLE [int].[file_import] ADD CONSTRAINT [FK_int_file_import_external_system_id] FOREIGN KEY ([external_system_id]) REFERENCES [int].[external_system] ([id]) ON DELETE NO ACTION;
ALTER TABLE [int].[file_import] ADD CONSTRAINT [FK_int_file_import_uploaded_by_user_id] FOREIGN KEY ([uploaded_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [int].[file_import] ADD CONSTRAINT [FK_int_file_import_error_report_attachment_id] FOREIGN KEY ([error_report_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [int].[file_import_error] ADD CONSTRAINT [FK_int_file_import_error_file_import_id] FOREIGN KEY ([file_import_id]) REFERENCES [int].[file_import] ([id]) ON DELETE CASCADE;
ALTER TABLE [int].[webhook_event] ADD CONSTRAINT [FK_int_webhook_event_external_system_id] FOREIGN KEY ([external_system_id]) REFERENCES [int].[external_system] ([id]) ON DELETE NO ACTION;
GO

/* ---------- 4. Foreign-key indexes (79) ---------- */
CREATE NONCLUSTERED INDEX [IX_core_machine_meter_reading_service_call_id] ON [core].[machine_meter_reading] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_contract_company_id] ON [svc].[service_contract] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_contract_principal_id] ON [svc].[service_contract] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_contract_customer_id] ON [svc].[service_contract] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_svc_contract_coverage_service_contract_id] ON [svc].[contract_coverage] ([service_contract_id]);
CREATE NONCLUSTERED INDEX [IX_svc_contract_coverage_machine_unit_id] ON [svc].[contract_coverage] ([machine_unit_id]);
CREATE NONCLUSTERED INDEX [IX_svc_checklist_template_principal_id] ON [svc].[checklist_template] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_svc_checklist_template_machine_model_id] ON [svc].[checklist_template] ([machine_model_id]);
CREATE NONCLUSTERED INDEX [IX_svc_checklist_template_call_type_lookup_id] ON [svc].[checklist_template] ([call_type_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_svc_checklist_template_item_checklist_template_id] ON [svc].[checklist_template_item] ([checklist_template_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_schedule_template_machine_model_id] ON [svc].[service_schedule_template] ([machine_model_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_schedule_template_checklist_template_id] ON [svc].[service_schedule_template] ([checklist_template_id]);
CREATE NONCLUSTERED INDEX [IX_svc_planned_service_machine_unit_id] ON [svc].[planned_service] ([machine_unit_id]);
CREATE NONCLUSTERED INDEX [IX_svc_planned_service_schedule_template_id] ON [svc].[planned_service] ([schedule_template_id]);
CREATE NONCLUSTERED INDEX [IX_svc_planned_service_service_call_id] ON [svc].[planned_service] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_company_id] ON [svc].[service_call] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_branch_id] ON [svc].[service_call] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_principal_id] ON [svc].[service_call] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_call_source_lookup_id] ON [svc].[service_call] ([call_source_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_call_type_lookup_id] ON [svc].[service_call] ([call_type_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_complaint_category_lookup_id] ON [svc].[service_call] ([complaint_category_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_customer_id] ON [svc].[service_call] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_customer_site_id] ON [svc].[service_call] ([customer_site_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_contact_id] ON [svc].[service_call] ([contact_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_machine_unit_id] ON [svc].[service_call] ([machine_unit_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_service_contract_id] ON [svc].[service_call] ([service_contract_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_planned_service_id] ON [svc].[service_call] ([planned_service_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_received_by_user_id] ON [svc].[service_call] ([received_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_team_id] ON [svc].[service_call] ([team_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_assigned_engineer_id] ON [svc].[service_call] ([assigned_engineer_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_closed_by_user_id] ON [svc].[service_call] ([closed_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_call_duplicate_of_call_id] ON [svc].[service_call] ([duplicate_of_call_id]);
CREATE NONCLUSTERED INDEX [IX_svc_call_status_log_service_call_id] ON [svc].[call_status_log] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_svc_call_status_log_changed_by_user_id] ON [svc].[call_status_log] ([changed_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_svc_call_status_log_reason_lookup_id] ON [svc].[call_status_log] ([reason_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_svc_call_assignment_service_call_id] ON [svc].[call_assignment] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_svc_call_assignment_engineer_employee_id] ON [svc].[call_assignment] ([engineer_employee_id]);
CREATE NONCLUSTERED INDEX [IX_svc_call_assignment_assigned_by_user_id] ON [svc].[call_assignment] ([assigned_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_svc_call_assignment_reason_lookup_id] ON [svc].[call_assignment] ([reason_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_svc_oem_call_reference_principal_id] ON [svc].[oem_call_reference] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_svc_oem_call_reference_external_system_id] ON [svc].[oem_call_reference] ([external_system_id]);
CREATE NONCLUSTERED INDEX [IX_svc_oem_call_reference_entered_by_user_id] ON [svc].[oem_call_reference] ([entered_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_svc_oem_call_reference_verified_by_user_id] ON [svc].[oem_call_reference] ([verified_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_svc_oem_call_reference_last_sync_log_id] ON [svc].[oem_call_reference] ([last_sync_log_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_visit_service_call_id] ON [svc].[service_visit] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_visit_engineer_employee_id] ON [svc].[service_visit] ([engineer_employee_id]);
CREATE NONCLUSTERED INDEX [IX_svc_trip_service_visit_id] ON [svc].[trip] ([service_visit_id]);
CREATE NONCLUSTERED INDEX [IX_svc_trip_engineer_employee_id] ON [svc].[trip] ([engineer_employee_id]);
CREATE NONCLUSTERED INDEX [IX_svc_trip_gps_point_trip_id] ON [svc].[trip_gps_point] ([trip_id]);
CREATE NONCLUSTERED INDEX [IX_svc_engineer_duty_log_employee_id] ON [svc].[engineer_duty_log] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_report_machine_condition_lookup_id] ON [svc].[service_report] ([machine_condition_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_report_failure_code_lookup_id] ON [svc].[service_report] ([failure_code_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_report_customer_signature_attachment_id] ON [svc].[service_report] ([customer_signature_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_report_engineer_signature_attachment_id] ON [svc].[service_report] ([engineer_signature_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_report_pdf_attachment_id] ON [svc].[service_report] ([pdf_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_svc_report_checklist_item_service_report_id] ON [svc].[report_checklist_item] ([service_report_id]);
CREATE NONCLUSTERED INDEX [IX_svc_report_checklist_item_checklist_template_item_id] ON [svc].[report_checklist_item] ([checklist_template_item_id]);
CREATE NONCLUSTERED INDEX [IX_svc_report_checklist_item_photo_attachment_id] ON [svc].[report_checklist_item] ([photo_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_part_request_service_call_id] ON [svc].[service_part_request] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_part_request_service_visit_id] ON [svc].[service_part_request] ([service_visit_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_part_request_item_id] ON [svc].[service_part_request] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_part_request_uom_id] ON [svc].[service_part_request] ([uom_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_part_request_requested_by_employee_id] ON [svc].[service_part_request] ([requested_by_employee_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_charge_service_call_id] ON [svc].[service_charge] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_svc_sla_rule_company_id] ON [svc].[sla_rule] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_svc_sla_rule_principal_id] ON [svc].[sla_rule] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_svc_sla_rule_call_type_lookup_id] ON [svc].[sla_rule] ([call_type_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_svc_sla_rule_escalate_to_role_id] ON [svc].[sla_rule] ([escalate_to_role_id]);
CREATE NONCLUSTERED INDEX [IX_svc_sla_event_service_call_id] ON [svc].[sla_event] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_svc_sla_event_sla_rule_id] ON [svc].[sla_event] ([sla_rule_id]);
CREATE NONCLUSTERED INDEX [IX_svc_sla_event_notified_user_id] ON [svc].[sla_event] ([notified_user_id]);
CREATE NONCLUSTERED INDEX [IX_int_external_system_principal_id] ON [int].[external_system] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_int_sync_mapping_external_system_id] ON [int].[sync_mapping] ([external_system_id]);
CREATE NONCLUSTERED INDEX [IX_int_sync_log_external_system_id] ON [int].[sync_log] ([external_system_id]);
CREATE NONCLUSTERED INDEX [IX_int_file_import_external_system_id] ON [int].[file_import] ([external_system_id]);
CREATE NONCLUSTERED INDEX [IX_int_file_import_uploaded_by_user_id] ON [int].[file_import] ([uploaded_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_int_file_import_error_report_attachment_id] ON [int].[file_import] ([error_report_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_int_file_import_error_file_import_id] ON [int].[file_import_error] ([file_import_id]);
CREATE NONCLUSTERED INDEX [IX_int_webhook_event_external_system_id] ON [int].[webhook_event] ([external_system_id]);
GO

/* =====================================================================
   TRISHUL Integrated System - SQL Server DDL (dictionary v2)
   Phase 2 - Inventory
   Generated from the TRISHUL Database Dictionary. Do not edit by hand:
   change the dictionary and regenerate.
   Target: SQL Server 2019+ / Amazon RDS for SQL Server
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
/* ---------- 1. Tables (27) ---------- */

/* ===== inv: Inventory ===== */
-- Movement classes: Fast / Slow / Non-moving (FSN) or ABC.
CREATE TABLE [inv].[movement_class] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_movement_class] PRIMARY KEY,
    [code] NVARCHAR(5) NOT NULL,
    [name] NVARCHAR(40) NOT NULL,
    [criteria] NVARCHAR(300) NULL,
    [min_issues_per_year] INT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_movement_class_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_movement_class_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Rack/shelf position inside a location.
CREATE TABLE [inv].[bin] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_bin] PRIMARY KEY,
    [location_id] BIGINT NOT NULL,
    [code] NVARCHAR(20) NOT NULL,
    [rack] NVARCHAR(10) NULL,
    [shelf] NVARCHAR(10) NULL,
    [description] NVARCHAR(100) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_bin_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_bin_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Types of stock movement.
CREATE TABLE [inv].[movement_type] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_movement_type] PRIMARY KEY,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(60) NOT NULL,
    [direction] NVARCHAR(30) NOT NULL,
    [affects_cost] BIT NOT NULL CONSTRAINT [DF_inv_movement_type_affects_cost] DEFAULT (1),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_movement_type_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_movement_type_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_inv_movement_type_direction] CHECK ([direction] IN (N'In', N'Out'))
);
GO
-- Current quantity per item, location and bin.
CREATE TABLE [inv].[stock_balance] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_balance] PRIMARY KEY,
    [item_id] BIGINT NOT NULL,
    [location_id] BIGINT NOT NULL,
    [bin_id] BIGINT NULL,
    [qty_on_hand] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_inv_stock_balance_qty_on_hand] DEFAULT (0),
    [qty_reserved] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_inv_stock_balance_qty_reserved] DEFAULT (0),
    [qty_in_transit] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_inv_stock_balance_qty_in_transit] DEFAULT (0),
    [avg_cost] DECIMAL(18,4) NULL,
    [last_movement_at] DATETIME2(0) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_stock_balance_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_stock_balance_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Serial or batch number of a stock item.
CREATE TABLE [inv].[serial_batch] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_serial_batch] PRIMARY KEY,
    [item_id] BIGINT NOT NULL,
    [serial_or_batch_no] NVARCHAR(60) NOT NULL,
    [tracking_type] NVARCHAR(30) NOT NULL,
    [manufacture_date] DATE NULL,
    [expiry_date] DATE NULL,
    [current_location_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [grn_line_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_serial_batch_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_serial_batch_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_inv_serial_batch_tracking_type] CHECK ([tracking_type] IN (N'Serial', N'Batch')),
    CONSTRAINT [CK_inv_serial_batch_status] CHECK ([status] IN (N'In stock', N'Reserved', N'Issued', N'Sold', N'Returned', N'Scrapped'))
);
GO
-- Stock ledger: every quantity change. Insert only.
CREATE TABLE [inv].[stock_move] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_move] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [move_at] DATETIME2(0) NOT NULL,
    [movement_type_id] BIGINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [location_id] BIGINT NOT NULL,
    [bin_id] BIGINT NULL,
    [serial_batch_id] BIGINT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [unit_cost] DECIMAL(18,4) NULL,
    [value] DECIMAL(18,2) NULL,
    [source_document_type] NVARCHAR(40) NOT NULL,
    [source_document_id] BIGINT NOT NULL,
    [source_line_id] BIGINT NULL,
    [reference] NVARCHAR(60) NULL,
    [performed_by_user_id] BIGINT NULL
);
GO
-- Receipt layers for FIFO valuation (if FIFO is chosen).
CREATE TABLE [inv].[cost_layer] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_cost_layer] PRIMARY KEY,
    [item_id] BIGINT NOT NULL,
    [location_id] BIGINT NOT NULL,
    [stock_move_id] BIGINT NOT NULL,
    [received_at] DATETIME2(0) NOT NULL,
    [qty_received] DECIMAL(18,3) NOT NULL,
    [qty_remaining] DECIMAL(18,3) NOT NULL,
    [unit_cost] DECIMAL(18,4) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_cost_layer_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_cost_layer_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Barcodes for an item, incl. pack barcodes.
CREATE TABLE [inv].[item_barcode] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_item_barcode] PRIMARY KEY,
    [item_id] BIGINT NOT NULL,
    [barcode] NVARCHAR(60) NOT NULL,
    [barcode_type] NVARCHAR(30) NOT NULL,
    [pack_qty] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_inv_item_barcode_pack_qty] DEFAULT (1),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_item_barcode_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_item_barcode_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_inv_item_barcode_barcode_type] CHECK ([barcode_type] IN (N'EAN13', N'Code128', N'QR'))
);
GO
-- Stock held for a service call or sales order.
CREATE TABLE [inv].[stock_reservation] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_reservation] PRIMARY KEY,
    [item_id] BIGINT NOT NULL,
    [location_id] BIGINT NOT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [reserved_for_type] NVARCHAR(30) NOT NULL,
    [service_call_id] BIGINT NULL,
    [sales_order_id] BIGINT NULL,
    [reserved_by_user_id] BIGINT NULL,
    [reserved_until] DATETIME2(0) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_stock_reservation_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_stock_reservation_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_inv_stock_reservation_reserved_for_type] CHECK ([reserved_for_type] IN (N'Service call', N'Sales order')),
    CONSTRAINT [CK_inv_stock_reservation_status] CHECK ([status] IN (N'Active', N'Consumed', N'Released'))
);
GO
-- Parts issued from a warehouse to a service call or engineer (branches hold no stock).
CREATE TABLE [inv].[stock_issue] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_issue] PRIMARY KEY,
    [issue_no] NVARCHAR(30) NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [issue_date] DATE NOT NULL,
    [issue_type] NVARCHAR(30) NOT NULL,
    [principal_id] BIGINT NULL,
    [service_call_id] BIGINT NULL,
    [issued_to_employee_id] BIGINT NULL,
    [from_location_id] BIGINT NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_stock_issue_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_stock_issue_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_inv_stock_issue_issue_type] CHECK ([issue_type] IN (N'Service', N'Internal', N'Sample')),
    CONSTRAINT [CK_inv_stock_issue_status] CHECK ([status] IN (N'Draft', N'Issued', N'Cancelled'))
);
GO
-- Parts in an issue.
CREATE TABLE [inv].[stock_issue_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_issue_line] PRIMARY KEY,
    [stock_issue_id] BIGINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [serial_batch_id] BIGINT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [unit_cost] DECIMAL(18,4) NULL,
    [service_part_request_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_stock_issue_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_stock_issue_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Defective parts returned from the field.
CREATE TABLE [inv].[defective_return] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_defective_return] PRIMARY KEY,
    [return_no] NVARCHAR(30) NOT NULL,
    [service_call_id] BIGINT NULL,
    [warranty_claim_id] BIGINT NULL,
    [item_id] BIGINT NOT NULL,
    [serial_batch_id] BIGINT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [received_location_id] BIGINT NOT NULL,
    [received_at] DATETIME2(0) NOT NULL,
    [disposition] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_defective_return_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_defective_return_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_inv_defective_return_disposition] CHECK ([disposition] IN (N'Return to OEM', N'Scrap', N'Repair', N'Pending'))
);
GO
-- Transfer between warehouses (same GSTIN, so delivery challan + e-way bill).
CREATE TABLE [inv].[stock_transfer] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_transfer] PRIMARY KEY,
    [transfer_no] NVARCHAR(30) NOT NULL,
    [from_location_id] BIGINT NOT NULL,
    [to_location_id] BIGINT NOT NULL,
    [transfer_date] DATE NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [dispatched_at] DATETIME2(0) NULL,
    [received_at] DATETIME2(0) NULL,
    [e_way_bill_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_stock_transfer_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_stock_transfer_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_inv_stock_transfer_status] CHECK ([status] IN (N'Draft', N'Dispatched', N'Received', N'Cancelled'))
);
GO
-- Items in a transfer.
CREATE TABLE [inv].[stock_transfer_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_transfer_line] PRIMARY KEY,
    [stock_transfer_id] BIGINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [serial_batch_id] BIGINT NULL,
    [qty_sent] DECIMAL(18,3) NOT NULL,
    [qty_received] DECIMAL(18,3) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_stock_transfer_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_stock_transfer_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Stock corrections with approval.
CREATE TABLE [inv].[stock_adjustment] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_adjustment] PRIMARY KEY,
    [adjustment_no] NVARCHAR(30) NOT NULL,
    [location_id] BIGINT NOT NULL,
    [adjustment_date] DATE NOT NULL,
    [reason_lookup_id] BIGINT NOT NULL,
    [stock_count_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_stock_adjustment_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_stock_adjustment_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_inv_stock_adjustment_status] CHECK ([status] IN (N'Draft', N'Pending approval', N'Posted', N'Rejected'))
);
GO
-- Lines of an adjustment.
CREATE TABLE [inv].[stock_adjustment_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_adjustment_line] PRIMARY KEY,
    [stock_adjustment_id] BIGINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [bin_id] BIGINT NULL,
    [serial_batch_id] BIGINT NULL,
    [qty_change] DECIMAL(18,3) NOT NULL,
    [unit_cost] DECIMAL(18,4) NULL,
    [remarks] NVARCHAR(200) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_stock_adjustment_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_stock_adjustment_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Physical stock count (full or cycle).
CREATE TABLE [inv].[stock_count] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_count] PRIMARY KEY,
    [count_no] NVARCHAR(30) NOT NULL,
    [location_id] BIGINT NOT NULL,
    [count_date] DATE NOT NULL,
    [count_type] NVARCHAR(30) NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_stock_count_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_stock_count_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_inv_stock_count_count_type] CHECK ([count_type] IN (N'Full', N'Cycle')),
    CONSTRAINT [CK_inv_stock_count_status] CHECK ([status] IN (N'Open', N'Counted', N'Adjusted', N'Cancelled'))
);
GO
-- Counted quantities.
CREATE TABLE [inv].[stock_count_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_inv_stock_count_line] PRIMARY KEY,
    [stock_count_id] BIGINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [bin_id] BIGINT NULL,
    [system_qty] DECIMAL(18,3) NOT NULL,
    [counted_qty] DECIMAL(18,3) NULL,
    [counted_by_user_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_inv_stock_count_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_inv_stock_count_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO

/* ===== acc: Accounting & GST ===== */
-- Journal header: one per posting document.
CREATE TABLE [acc].[journal] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_journal] PRIMARY KEY,
    [journal_no] NVARCHAR(30) NOT NULL,
    [company_id] BIGINT NOT NULL,
    [branch_id] BIGINT NULL,
    [journal_date] DATE NOT NULL,
    [fiscal_year_id] BIGINT NOT NULL,
    [journal_type] NVARCHAR(30) NOT NULL,
    [source_document_type] NVARCHAR(40) NULL,
    [source_document_id] BIGINT NULL,
    [narration] NVARCHAR(500) NULL,
    [total_debit] DECIMAL(18,2) NOT NULL,
    [total_credit] DECIMAL(18,2) NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [reversed_journal_id] BIGINT NULL,
    [posted_by_user_id] BIGINT NULL,
    [posted_at] DATETIME2(0) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_journal_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_journal_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_acc_journal_journal_type] CHECK ([journal_type] IN (N'Sales', N'Purchase', N'Receipt', N'Payment', N'Payroll', N'Stock', N'Manual', N'Opening', N'Contra')),
    CONSTRAINT [CK_acc_journal_status] CHECK ([status] IN (N'Draft', N'Posted', N'Reversed'))
);
GO
-- Ledger lines (double entry).
CREATE TABLE [acc].[gl_entry] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_gl_entry] PRIMARY KEY,
    [journal_id] BIGINT NOT NULL,
    [line_no] SMALLINT NOT NULL,
    [entry_date] DATE NOT NULL,
    [gl_account_id] BIGINT NOT NULL,
    [debit] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_acc_gl_entry_debit] DEFAULT (0),
    [credit] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_acc_gl_entry_credit] DEFAULT (0),
    [cost_centre_id] BIGINT NULL,
    [principal_id] BIGINT NULL,
    [branch_id] BIGINT NULL,
    [party_type] NVARCHAR(30) NULL,
    [customer_id] BIGINT NULL,
    [supplier_id] BIGINT NULL,
    [employee_id] BIGINT NULL,
    [narration] NVARCHAR(300) NULL,
    CONSTRAINT [CK_acc_gl_entry_party_type] CHECK ([party_type] IN (N'Customer', N'Supplier', N'Employee'))
);
GO
-- Opening balances by account and party at go-live.
CREATE TABLE [acc].[opening_balance] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_opening_balance] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [fiscal_year_id] BIGINT NOT NULL,
    [gl_account_id] BIGINT NOT NULL,
    [party_type] NVARCHAR(30) NULL,
    [customer_id] BIGINT NULL,
    [supplier_id] BIGINT NULL,
    [reference_document_no] NVARCHAR(40) NULL,
    [document_date] DATE NULL,
    [due_date] DATE NULL,
    [debit] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_acc_opening_balance_debit] DEFAULT (0),
    [credit] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_acc_opening_balance_credit] DEFAULT (0),
    [journal_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_opening_balance_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_opening_balance_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_acc_opening_balance_party_type] CHECK ([party_type] IN (N'Customer', N'Supplier', N'Employee'))
);
GO
-- Company bank and cash accounts.
CREATE TABLE [acc].[bank_account] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_bank_account] PRIMARY KEY,
    [gl_account_id] BIGINT NOT NULL,
    [bank_name] NVARCHAR(100) NOT NULL,
    [account_name] NVARCHAR(150) NULL,
    [account_number] NVARCHAR(30) NULL,
    [ifsc] NVARCHAR(11) NULL,
    [branch_name] NVARCHAR(100) NULL,
    [account_type] NVARCHAR(30) NOT NULL,
    [currency_id] BIGINT NOT NULL,
    [last_reconciled_date] DATE NULL,
    [reconciled_balance] DECIMAL(18,2) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_bank_account_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_bank_account_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_acc_bank_account_account_type] CHECK ([account_type] IN (N'Current', N'Cash credit', N'Overdraft', N'Savings', N'Cash'))
);
GO
-- Imported bank statement lines for reconciliation.
CREATE TABLE [acc].[bank_statement_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_bank_statement_line] PRIMARY KEY,
    [bank_account_id] BIGINT NOT NULL,
    [statement_date] DATE NOT NULL,
    [description] NVARCHAR(300) NULL,
    [reference] NVARCHAR(60) NULL,
    [debit] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_acc_bank_statement_line_debit] DEFAULT (0),
    [credit] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_acc_bank_statement_line_credit] DEFAULT (0),
    [balance] DECIMAL(18,2) NULL,
    [file_import_id] BIGINT NULL
);
GO
-- Bank / cash book entries.
CREATE TABLE [acc].[bank_txn] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_bank_txn] PRIMARY KEY,
    [bank_account_id] BIGINT NOT NULL,
    [txn_date] DATE NOT NULL,
    [value_date] DATE NULL,
    [txn_type] NVARCHAR(30) NOT NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [reference_no] NVARCHAR(60) NULL,
    [journal_id] BIGINT NULL,
    [source_document_type] NVARCHAR(40) NULL,
    [source_document_id] BIGINT NULL,
    [is_reconciled] BIT NOT NULL CONSTRAINT [DF_acc_bank_txn_is_reconciled] DEFAULT (0),
    [reconciled_on] DATE NULL,
    [bank_statement_line_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_bank_txn_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_bank_txn_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_acc_bank_txn_txn_type] CHECK ([txn_type] IN (N'Receipt', N'Payment', N'Transfer', N'Charges', N'Interest'))
);
GO
-- Monthly budget per account and cost centre.
CREATE TABLE [acc].[budget] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_budget] PRIMARY KEY,
    [fiscal_year_id] BIGINT NOT NULL,
    [gl_account_id] BIGINT NOT NULL,
    [cost_centre_id] BIGINT NULL,
    [period_month] DATE NOT NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_budget_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_budget_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- GST split per document line (for GSTR reports).
CREATE TABLE [acc].[doc_tax_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_doc_tax_line] PRIMARY KEY,
    [document_type] NVARCHAR(40) NOT NULL,
    [document_id] BIGINT NOT NULL,
    [document_line_id] BIGINT NULL,
    [gst_rate_id] BIGINT NOT NULL,
    [tax_component] NVARCHAR(30) NOT NULL,
    [taxable_value] DECIMAL(18,2) NOT NULL,
    [rate] DECIMAL(5,2) NOT NULL,
    [tax_amount] DECIMAL(18,2) NOT NULL,
    [is_itc_eligible] BIT NULL,
    [gl_account_id] BIGINT NULL,
    CONSTRAINT [CK_acc_doc_tax_line_tax_component] CHECK ([tax_component] IN (N'CGST', N'SGST', N'IGST', N'Cess'))
);
GO
-- TDS deducted by us or deducted from us.
CREATE TABLE [acc].[tds_entry] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_tds_entry] PRIMARY KEY,
    [tds_section_id] BIGINT NOT NULL,
    [direction] NVARCHAR(30) NOT NULL,
    [supplier_id] BIGINT NULL,
    [customer_id] BIGINT NULL,
    [employee_id] BIGINT NULL,
    [document_type] NVARCHAR(40) NULL,
    [document_id] BIGINT NULL,
    [base_amount] DECIMAL(18,2) NOT NULL,
    [tds_rate] DECIMAL(5,2) NOT NULL,
    [tds_amount] DECIMAL(18,2) NOT NULL,
    [deduction_date] DATE NOT NULL,
    [challan_no] NVARCHAR(20) NULL,
    [challan_date] DATE NULL,
    [quarter] NVARCHAR(7) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_tds_entry_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_tds_entry_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_acc_tds_entry_direction] CHECK ([direction] IN (N'Deducted by us', N'Deducted from us'))
);
GO

/* ---------- 2. Unique keys (13) ---------- */
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_movement_class_code] ON [inv].[movement_class] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_bin_k1] ON [inv].[bin] ([location_id], [code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_movement_type_code] ON [inv].[movement_type] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_stock_balance_k1] ON [inv].[stock_balance] ([item_id], [location_id], [bin_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_serial_batch_k1] ON [inv].[serial_batch] ([item_id], [serial_or_batch_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_item_barcode_barcode] ON [inv].[item_barcode] ([barcode]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_stock_issue_issue_no] ON [inv].[stock_issue] ([issue_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_defective_return_return_no] ON [inv].[defective_return] ([return_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_stock_transfer_transfer_no] ON [inv].[stock_transfer] ([transfer_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_stock_adjustment_adjustment_no] ON [inv].[stock_adjustment] ([adjustment_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_inv_stock_count_count_no] ON [inv].[stock_count] ([count_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_acc_journal_journal_no] ON [acc].[journal] ([journal_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_acc_bank_account_gl_account_id] ON [acc].[bank_account] ([gl_account_id]);
GO

/* ---------- 3. Foreign keys (88) ----------
   Includes links from earlier-phase columns to tables created in this phase. */
ALTER TABLE [core].[item] ADD CONSTRAINT [FK_core_item_movement_class_id] FOREIGN KEY ([movement_class_id]) REFERENCES [inv].[movement_class] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_part_request] ADD CONSTRAINT [FK_svc_service_part_request_stock_reservation_id] FOREIGN KEY ([stock_reservation_id]) REFERENCES [inv].[stock_reservation] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[bin] ADD CONSTRAINT [FK_inv_bin_location_id] FOREIGN KEY ([location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_balance] ADD CONSTRAINT [FK_inv_stock_balance_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_balance] ADD CONSTRAINT [FK_inv_stock_balance_location_id] FOREIGN KEY ([location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_balance] ADD CONSTRAINT [FK_inv_stock_balance_bin_id] FOREIGN KEY ([bin_id]) REFERENCES [inv].[bin] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[serial_batch] ADD CONSTRAINT [FK_inv_serial_batch_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[serial_batch] ADD CONSTRAINT [FK_inv_serial_batch_current_location_id] FOREIGN KEY ([current_location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_move] ADD CONSTRAINT [FK_inv_stock_move_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_move] ADD CONSTRAINT [FK_inv_stock_move_movement_type_id] FOREIGN KEY ([movement_type_id]) REFERENCES [inv].[movement_type] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_move] ADD CONSTRAINT [FK_inv_stock_move_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_move] ADD CONSTRAINT [FK_inv_stock_move_location_id] FOREIGN KEY ([location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_move] ADD CONSTRAINT [FK_inv_stock_move_bin_id] FOREIGN KEY ([bin_id]) REFERENCES [inv].[bin] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_move] ADD CONSTRAINT [FK_inv_stock_move_serial_batch_id] FOREIGN KEY ([serial_batch_id]) REFERENCES [inv].[serial_batch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_move] ADD CONSTRAINT [FK_inv_stock_move_performed_by_user_id] FOREIGN KEY ([performed_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[cost_layer] ADD CONSTRAINT [FK_inv_cost_layer_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[cost_layer] ADD CONSTRAINT [FK_inv_cost_layer_location_id] FOREIGN KEY ([location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[cost_layer] ADD CONSTRAINT [FK_inv_cost_layer_stock_move_id] FOREIGN KEY ([stock_move_id]) REFERENCES [inv].[stock_move] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[item_barcode] ADD CONSTRAINT [FK_inv_item_barcode_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_reservation] ADD CONSTRAINT [FK_inv_stock_reservation_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_reservation] ADD CONSTRAINT [FK_inv_stock_reservation_location_id] FOREIGN KEY ([location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_reservation] ADD CONSTRAINT [FK_inv_stock_reservation_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_reservation] ADD CONSTRAINT [FK_inv_stock_reservation_reserved_by_user_id] FOREIGN KEY ([reserved_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_issue] ADD CONSTRAINT [FK_inv_stock_issue_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_issue] ADD CONSTRAINT [FK_inv_stock_issue_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_issue] ADD CONSTRAINT [FK_inv_stock_issue_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_issue] ADD CONSTRAINT [FK_inv_stock_issue_issued_to_employee_id] FOREIGN KEY ([issued_to_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_issue] ADD CONSTRAINT [FK_inv_stock_issue_from_location_id] FOREIGN KEY ([from_location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_issue_line] ADD CONSTRAINT [FK_inv_stock_issue_line_stock_issue_id] FOREIGN KEY ([stock_issue_id]) REFERENCES [inv].[stock_issue] ([id]) ON DELETE CASCADE;
ALTER TABLE [inv].[stock_issue_line] ADD CONSTRAINT [FK_inv_stock_issue_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_issue_line] ADD CONSTRAINT [FK_inv_stock_issue_line_serial_batch_id] FOREIGN KEY ([serial_batch_id]) REFERENCES [inv].[serial_batch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_issue_line] ADD CONSTRAINT [FK_inv_stock_issue_line_service_part_request_id] FOREIGN KEY ([service_part_request_id]) REFERENCES [svc].[service_part_request] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[defective_return] ADD CONSTRAINT [FK_inv_defective_return_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[defective_return] ADD CONSTRAINT [FK_inv_defective_return_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[defective_return] ADD CONSTRAINT [FK_inv_defective_return_serial_batch_id] FOREIGN KEY ([serial_batch_id]) REFERENCES [inv].[serial_batch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[defective_return] ADD CONSTRAINT [FK_inv_defective_return_received_location_id] FOREIGN KEY ([received_location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_transfer] ADD CONSTRAINT [FK_inv_stock_transfer_from_location_id] FOREIGN KEY ([from_location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_transfer] ADD CONSTRAINT [FK_inv_stock_transfer_to_location_id] FOREIGN KEY ([to_location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_transfer_line] ADD CONSTRAINT [FK_inv_stock_transfer_line_stock_transfer_id] FOREIGN KEY ([stock_transfer_id]) REFERENCES [inv].[stock_transfer] ([id]) ON DELETE CASCADE;
ALTER TABLE [inv].[stock_transfer_line] ADD CONSTRAINT [FK_inv_stock_transfer_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_transfer_line] ADD CONSTRAINT [FK_inv_stock_transfer_line_serial_batch_id] FOREIGN KEY ([serial_batch_id]) REFERENCES [inv].[serial_batch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_adjustment] ADD CONSTRAINT [FK_inv_stock_adjustment_location_id] FOREIGN KEY ([location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_adjustment] ADD CONSTRAINT [FK_inv_stock_adjustment_reason_lookup_id] FOREIGN KEY ([reason_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_adjustment] ADD CONSTRAINT [FK_inv_stock_adjustment_stock_count_id] FOREIGN KEY ([stock_count_id]) REFERENCES [inv].[stock_count] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_adjustment_line] ADD CONSTRAINT [FK_inv_stock_adjustment_line_stock_adjustment_id] FOREIGN KEY ([stock_adjustment_id]) REFERENCES [inv].[stock_adjustment] ([id]) ON DELETE CASCADE;
ALTER TABLE [inv].[stock_adjustment_line] ADD CONSTRAINT [FK_inv_stock_adjustment_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_adjustment_line] ADD CONSTRAINT [FK_inv_stock_adjustment_line_bin_id] FOREIGN KEY ([bin_id]) REFERENCES [inv].[bin] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_adjustment_line] ADD CONSTRAINT [FK_inv_stock_adjustment_line_serial_batch_id] FOREIGN KEY ([serial_batch_id]) REFERENCES [inv].[serial_batch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_count] ADD CONSTRAINT [FK_inv_stock_count_location_id] FOREIGN KEY ([location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_count_line] ADD CONSTRAINT [FK_inv_stock_count_line_stock_count_id] FOREIGN KEY ([stock_count_id]) REFERENCES [inv].[stock_count] ([id]) ON DELETE CASCADE;
ALTER TABLE [inv].[stock_count_line] ADD CONSTRAINT [FK_inv_stock_count_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_count_line] ADD CONSTRAINT [FK_inv_stock_count_line_bin_id] FOREIGN KEY ([bin_id]) REFERENCES [inv].[bin] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_count_line] ADD CONSTRAINT [FK_inv_stock_count_line_counted_by_user_id] FOREIGN KEY ([counted_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[journal] ADD CONSTRAINT [FK_acc_journal_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[journal] ADD CONSTRAINT [FK_acc_journal_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[journal] ADD CONSTRAINT [FK_acc_journal_fiscal_year_id] FOREIGN KEY ([fiscal_year_id]) REFERENCES [acc].[fiscal_year] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[journal] ADD CONSTRAINT [FK_acc_journal_reversed_journal_id] FOREIGN KEY ([reversed_journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[journal] ADD CONSTRAINT [FK_acc_journal_posted_by_user_id] FOREIGN KEY ([posted_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[gl_entry] ADD CONSTRAINT [FK_acc_gl_entry_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE CASCADE;
ALTER TABLE [acc].[gl_entry] ADD CONSTRAINT [FK_acc_gl_entry_gl_account_id] FOREIGN KEY ([gl_account_id]) REFERENCES [acc].[gl_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[gl_entry] ADD CONSTRAINT [FK_acc_gl_entry_cost_centre_id] FOREIGN KEY ([cost_centre_id]) REFERENCES [acc].[cost_centre] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[gl_entry] ADD CONSTRAINT [FK_acc_gl_entry_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[gl_entry] ADD CONSTRAINT [FK_acc_gl_entry_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[gl_entry] ADD CONSTRAINT [FK_acc_gl_entry_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[gl_entry] ADD CONSTRAINT [FK_acc_gl_entry_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[gl_entry] ADD CONSTRAINT [FK_acc_gl_entry_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[opening_balance] ADD CONSTRAINT [FK_acc_opening_balance_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[opening_balance] ADD CONSTRAINT [FK_acc_opening_balance_fiscal_year_id] FOREIGN KEY ([fiscal_year_id]) REFERENCES [acc].[fiscal_year] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[opening_balance] ADD CONSTRAINT [FK_acc_opening_balance_gl_account_id] FOREIGN KEY ([gl_account_id]) REFERENCES [acc].[gl_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[opening_balance] ADD CONSTRAINT [FK_acc_opening_balance_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[opening_balance] ADD CONSTRAINT [FK_acc_opening_balance_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[opening_balance] ADD CONSTRAINT [FK_acc_opening_balance_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[bank_account] ADD CONSTRAINT [FK_acc_bank_account_gl_account_id] FOREIGN KEY ([gl_account_id]) REFERENCES [acc].[gl_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[bank_account] ADD CONSTRAINT [FK_acc_bank_account_currency_id] FOREIGN KEY ([currency_id]) REFERENCES [core].[currency] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[bank_statement_line] ADD CONSTRAINT [FK_acc_bank_statement_line_bank_account_id] FOREIGN KEY ([bank_account_id]) REFERENCES [acc].[bank_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[bank_statement_line] ADD CONSTRAINT [FK_acc_bank_statement_line_file_import_id] FOREIGN KEY ([file_import_id]) REFERENCES [int].[file_import] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[bank_txn] ADD CONSTRAINT [FK_acc_bank_txn_bank_account_id] FOREIGN KEY ([bank_account_id]) REFERENCES [acc].[bank_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[bank_txn] ADD CONSTRAINT [FK_acc_bank_txn_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[bank_txn] ADD CONSTRAINT [FK_acc_bank_txn_bank_statement_line_id] FOREIGN KEY ([bank_statement_line_id]) REFERENCES [acc].[bank_statement_line] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[budget] ADD CONSTRAINT [FK_acc_budget_fiscal_year_id] FOREIGN KEY ([fiscal_year_id]) REFERENCES [acc].[fiscal_year] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[budget] ADD CONSTRAINT [FK_acc_budget_gl_account_id] FOREIGN KEY ([gl_account_id]) REFERENCES [acc].[gl_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[budget] ADD CONSTRAINT [FK_acc_budget_cost_centre_id] FOREIGN KEY ([cost_centre_id]) REFERENCES [acc].[cost_centre] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[doc_tax_line] ADD CONSTRAINT [FK_acc_doc_tax_line_gst_rate_id] FOREIGN KEY ([gst_rate_id]) REFERENCES [acc].[gst_rate] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[doc_tax_line] ADD CONSTRAINT [FK_acc_doc_tax_line_gl_account_id] FOREIGN KEY ([gl_account_id]) REFERENCES [acc].[gl_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[tds_entry] ADD CONSTRAINT [FK_acc_tds_entry_tds_section_id] FOREIGN KEY ([tds_section_id]) REFERENCES [acc].[tds_section] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[tds_entry] ADD CONSTRAINT [FK_acc_tds_entry_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[tds_entry] ADD CONSTRAINT [FK_acc_tds_entry_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[tds_entry] ADD CONSTRAINT [FK_acc_tds_entry_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
GO

/* ---------- 4. Foreign-key indexes (87) ---------- */
CREATE NONCLUSTERED INDEX [IX_core_item_movement_class_id] ON [core].[item] ([movement_class_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_part_request_stock_reservation_id] ON [svc].[service_part_request] ([stock_reservation_id]);
CREATE NONCLUSTERED INDEX [IX_inv_bin_location_id] ON [inv].[bin] ([location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_balance_item_id] ON [inv].[stock_balance] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_balance_location_id] ON [inv].[stock_balance] ([location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_balance_bin_id] ON [inv].[stock_balance] ([bin_id]);
CREATE NONCLUSTERED INDEX [IX_inv_serial_batch_item_id] ON [inv].[serial_batch] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_serial_batch_current_location_id] ON [inv].[serial_batch] ([current_location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_move_company_id] ON [inv].[stock_move] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_move_movement_type_id] ON [inv].[stock_move] ([movement_type_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_move_item_id] ON [inv].[stock_move] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_move_location_id] ON [inv].[stock_move] ([location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_move_bin_id] ON [inv].[stock_move] ([bin_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_move_serial_batch_id] ON [inv].[stock_move] ([serial_batch_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_move_performed_by_user_id] ON [inv].[stock_move] ([performed_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_inv_cost_layer_item_id] ON [inv].[cost_layer] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_cost_layer_location_id] ON [inv].[cost_layer] ([location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_cost_layer_stock_move_id] ON [inv].[cost_layer] ([stock_move_id]);
CREATE NONCLUSTERED INDEX [IX_inv_item_barcode_item_id] ON [inv].[item_barcode] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_reservation_item_id] ON [inv].[stock_reservation] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_reservation_location_id] ON [inv].[stock_reservation] ([location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_reservation_service_call_id] ON [inv].[stock_reservation] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_reservation_reserved_by_user_id] ON [inv].[stock_reservation] ([reserved_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_issue_branch_id] ON [inv].[stock_issue] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_issue_principal_id] ON [inv].[stock_issue] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_issue_service_call_id] ON [inv].[stock_issue] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_issue_issued_to_employee_id] ON [inv].[stock_issue] ([issued_to_employee_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_issue_from_location_id] ON [inv].[stock_issue] ([from_location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_issue_line_stock_issue_id] ON [inv].[stock_issue_line] ([stock_issue_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_issue_line_item_id] ON [inv].[stock_issue_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_issue_line_serial_batch_id] ON [inv].[stock_issue_line] ([serial_batch_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_issue_line_service_part_request_id] ON [inv].[stock_issue_line] ([service_part_request_id]);
CREATE NONCLUSTERED INDEX [IX_inv_defective_return_service_call_id] ON [inv].[defective_return] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_inv_defective_return_item_id] ON [inv].[defective_return] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_defective_return_serial_batch_id] ON [inv].[defective_return] ([serial_batch_id]);
CREATE NONCLUSTERED INDEX [IX_inv_defective_return_received_location_id] ON [inv].[defective_return] ([received_location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_transfer_from_location_id] ON [inv].[stock_transfer] ([from_location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_transfer_to_location_id] ON [inv].[stock_transfer] ([to_location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_transfer_line_stock_transfer_id] ON [inv].[stock_transfer_line] ([stock_transfer_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_transfer_line_item_id] ON [inv].[stock_transfer_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_transfer_line_serial_batch_id] ON [inv].[stock_transfer_line] ([serial_batch_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_adjustment_location_id] ON [inv].[stock_adjustment] ([location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_adjustment_reason_lookup_id] ON [inv].[stock_adjustment] ([reason_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_adjustment_stock_count_id] ON [inv].[stock_adjustment] ([stock_count_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_adjustment_line_stock_adjustment_id] ON [inv].[stock_adjustment_line] ([stock_adjustment_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_adjustment_line_item_id] ON [inv].[stock_adjustment_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_adjustment_line_bin_id] ON [inv].[stock_adjustment_line] ([bin_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_adjustment_line_serial_batch_id] ON [inv].[stock_adjustment_line] ([serial_batch_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_count_location_id] ON [inv].[stock_count] ([location_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_count_line_stock_count_id] ON [inv].[stock_count_line] ([stock_count_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_count_line_item_id] ON [inv].[stock_count_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_count_line_bin_id] ON [inv].[stock_count_line] ([bin_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_count_line_counted_by_user_id] ON [inv].[stock_count_line] ([counted_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_acc_journal_company_id] ON [acc].[journal] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_acc_journal_branch_id] ON [acc].[journal] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_acc_journal_fiscal_year_id] ON [acc].[journal] ([fiscal_year_id]);
CREATE NONCLUSTERED INDEX [IX_acc_journal_reversed_journal_id] ON [acc].[journal] ([reversed_journal_id]);
CREATE NONCLUSTERED INDEX [IX_acc_journal_posted_by_user_id] ON [acc].[journal] ([posted_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gl_entry_journal_id] ON [acc].[gl_entry] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gl_entry_gl_account_id] ON [acc].[gl_entry] ([gl_account_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gl_entry_cost_centre_id] ON [acc].[gl_entry] ([cost_centre_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gl_entry_principal_id] ON [acc].[gl_entry] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gl_entry_branch_id] ON [acc].[gl_entry] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gl_entry_customer_id] ON [acc].[gl_entry] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gl_entry_supplier_id] ON [acc].[gl_entry] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_acc_gl_entry_employee_id] ON [acc].[gl_entry] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_acc_opening_balance_company_id] ON [acc].[opening_balance] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_acc_opening_balance_fiscal_year_id] ON [acc].[opening_balance] ([fiscal_year_id]);
CREATE NONCLUSTERED INDEX [IX_acc_opening_balance_gl_account_id] ON [acc].[opening_balance] ([gl_account_id]);
CREATE NONCLUSTERED INDEX [IX_acc_opening_balance_customer_id] ON [acc].[opening_balance] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_acc_opening_balance_supplier_id] ON [acc].[opening_balance] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_acc_opening_balance_journal_id] ON [acc].[opening_balance] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_acc_bank_account_currency_id] ON [acc].[bank_account] ([currency_id]);
CREATE NONCLUSTERED INDEX [IX_acc_bank_statement_line_bank_account_id] ON [acc].[bank_statement_line] ([bank_account_id]);
CREATE NONCLUSTERED INDEX [IX_acc_bank_statement_line_file_import_id] ON [acc].[bank_statement_line] ([file_import_id]);
CREATE NONCLUSTERED INDEX [IX_acc_bank_txn_bank_account_id] ON [acc].[bank_txn] ([bank_account_id]);
CREATE NONCLUSTERED INDEX [IX_acc_bank_txn_journal_id] ON [acc].[bank_txn] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_acc_bank_txn_bank_statement_line_id] ON [acc].[bank_txn] ([bank_statement_line_id]);
CREATE NONCLUSTERED INDEX [IX_acc_budget_fiscal_year_id] ON [acc].[budget] ([fiscal_year_id]);
CREATE NONCLUSTERED INDEX [IX_acc_budget_gl_account_id] ON [acc].[budget] ([gl_account_id]);
CREATE NONCLUSTERED INDEX [IX_acc_budget_cost_centre_id] ON [acc].[budget] ([cost_centre_id]);
CREATE NONCLUSTERED INDEX [IX_acc_doc_tax_line_gst_rate_id] ON [acc].[doc_tax_line] ([gst_rate_id]);
CREATE NONCLUSTERED INDEX [IX_acc_doc_tax_line_gl_account_id] ON [acc].[doc_tax_line] ([gl_account_id]);
CREATE NONCLUSTERED INDEX [IX_acc_tds_entry_tds_section_id] ON [acc].[tds_entry] ([tds_section_id]);
CREATE NONCLUSTERED INDEX [IX_acc_tds_entry_supplier_id] ON [acc].[tds_entry] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_acc_tds_entry_customer_id] ON [acc].[tds_entry] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_acc_tds_entry_employee_id] ON [acc].[tds_entry] ([employee_id]);
GO

/* =====================================================================
   TRISHUL Integrated System - SQL Server DDL (dictionary v2)
   Phase 3 - Purchase + HR
   Generated from the TRISHUL Database Dictionary. Do not edit by hand:
   change the dictionary and regenerate.
   Target: SQL Server 2019+ / Amazon RDS for SQL Server
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
/* ---------- 1. Tables (46) ---------- */

/* ===== svc: Call & Service ===== */
-- Warranty claim to the OEM for a failed part.
CREATE TABLE [svc].[warranty_claim] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_warranty_claim] PRIMARY KEY,
    [claim_no] NVARCHAR(30) NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [service_call_id] BIGINT NOT NULL,
    [machine_unit_id] BIGINT NOT NULL,
    [failure_code_lookup_id] BIGINT NULL,
    [claim_date] DATE NOT NULL,
    [claimed_amount] DECIMAL(18,2) NULL,
    [approved_amount] DECIMAL(18,2) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [oem_claim_ref] NVARCHAR(40) NULL,
    [credit_note_ref] NVARCHAR(40) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_warranty_claim_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_warranty_claim_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_svc_warranty_claim_status] CHECK ([status] IN (N'Draft', N'Submitted', N'Approved', N'Rejected', N'Settled'))
);
GO
-- Parts in a warranty claim.
CREATE TABLE [svc].[warranty_claim_part] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_svc_warranty_claim_part] PRIMARY KEY,
    [warranty_claim_id] BIGINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [failed_part_serial] NVARCHAR(60) NULL,
    [is_returned_to_oem] BIT NOT NULL CONSTRAINT [DF_svc_warranty_claim_part_is_returned_to_oem] DEFAULT (0),
    [return_docket_no] NVARCHAR(40) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_svc_warranty_claim_part_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_svc_warranty_claim_part_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO

/* ===== pur: Purchase ===== */
-- Supplier prices and part numbers for items.
CREATE TABLE [pur].[supplier_item_price] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_supplier_item_price] PRIMARY KEY,
    [supplier_id] BIGINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [supplier_part_no] NVARCHAR(40) NULL,
    [supplier_uom] NVARCHAR(10) NULL,
    [conversion_factor] DECIMAL(12,4) NOT NULL CONSTRAINT [DF_pur_supplier_item_price_conversion_factor] DEFAULT (1),
    [price] DECIMAL(18,4) NOT NULL,
    [currency_id] BIGINT NOT NULL,
    [valid_from] DATE NULL,
    [valid_to] DATE NULL,
    [lead_time_days] SMALLINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_supplier_item_price_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_supplier_item_price_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Internal request to buy (reorder, service need, manual).
CREATE TABLE [pur].[purchase_request] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_purchase_request] PRIMARY KEY,
    [pr_no] NVARCHAR(30) NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [principal_id] BIGINT NULL,
    [requested_by_employee_id] BIGINT NOT NULL,
    [request_date] DATE NOT NULL,
    [required_by] DATE NULL,
    [source_type] NVARCHAR(30) NOT NULL,
    [service_call_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_purchase_request_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_purchase_request_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pur_purchase_request_source_type] CHECK ([source_type] IN (N'Reorder', N'Service call', N'Manual')),
    CONSTRAINT [CK_pur_purchase_request_status] CHECK ([status] IN (N'Draft', N'Pending approval', N'Approved', N'Ordered', N'Rejected'))
);
GO
-- Items requested.
CREATE TABLE [pur].[purchase_request_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_purchase_request_line] PRIMARY KEY,
    [purchase_request_id] BIGINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [remarks] NVARCHAR(200) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_purchase_request_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_purchase_request_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Purchase order to a supplier.
CREATE TABLE [pur].[purchase_order] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_purchase_order] PRIMARY KEY,
    [po_no] NVARCHAR(30) NOT NULL,
    [company_id] BIGINT NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [supplier_id] BIGINT NOT NULL,
    [principal_id] BIGINT NULL,
    [po_date] DATE NOT NULL,
    [expected_date] DATE NULL,
    [delivery_location_id] BIGINT NOT NULL,
    [payment_terms_id] BIGINT NULL,
    [place_of_supply_state_id] BIGINT NOT NULL,
    [currency_id] BIGINT NOT NULL,
    [subtotal] DECIMAL(18,2) NOT NULL,
    [tax_total] DECIMAL(18,2) NOT NULL,
    [total] DECIMAL(18,2) NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [oem_po_ref] NVARCHAR(40) NULL,
    [remarks] NVARCHAR(500) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_purchase_order_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_purchase_order_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pur_purchase_order_status] CHECK ([status] IN (N'Draft', N'Pending approval', N'Approved', N'Sent', N'Part received', N'Closed', N'Cancelled'))
);
GO
-- PO lines.
CREATE TABLE [pur].[purchase_order_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_purchase_order_line] PRIMARY KEY,
    [purchase_order_id] BIGINT NOT NULL,
    [line_no] SMALLINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [description] NVARCHAR(200) NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [uom_id] BIGINT NOT NULL,
    [unit_price] DECIMAL(18,4) NOT NULL,
    [discount_pct] DECIMAL(5,2) NULL,
    [hsn_sac_id] BIGINT NULL,
    [gst_rate_id] BIGINT NULL,
    [taxable_value] DECIMAL(18,2) NOT NULL,
    [tax_amount] DECIMAL(18,2) NOT NULL,
    [line_total] DECIMAL(18,2) NOT NULL,
    [qty_received] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_pur_purchase_order_line_qty_received] DEFAULT (0),
    [qty_invoiced] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_pur_purchase_order_line_qty_invoiced] DEFAULT (0),
    [purchase_request_line_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_purchase_order_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_purchase_order_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Goods receipt note.
CREATE TABLE [pur].[grn] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_grn] PRIMARY KEY,
    [grn_no] NVARCHAR(30) NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [supplier_id] BIGINT NOT NULL,
    [purchase_order_id] BIGINT NULL,
    [principal_id] BIGINT NULL,
    [grn_date] DATE NOT NULL,
    [location_id] BIGINT NOT NULL,
    [supplier_invoice_no] NVARCHAR(40) NULL,
    [supplier_invoice_date] DATE NULL,
    [vehicle_no] NVARCHAR(20) NULL,
    [lr_no] NVARCHAR(40) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_grn_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_grn_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pur_grn_status] CHECK ([status] IN (N'Draft', N'Posted', N'Cancelled'))
);
GO
-- Items received.
CREATE TABLE [pur].[grn_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_grn_line] PRIMARY KEY,
    [grn_id] BIGINT NOT NULL,
    [purchase_order_line_id] BIGINT NULL,
    [item_id] BIGINT NOT NULL,
    [qty_received] DECIMAL(18,3) NOT NULL,
    [qty_accepted] DECIMAL(18,3) NOT NULL,
    [qty_rejected] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_pur_grn_line_qty_rejected] DEFAULT (0),
    [bin_id] BIGINT NULL,
    [unit_cost] DECIMAL(18,4) NOT NULL,
    [rejection_reason] NVARCHAR(200) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_grn_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_grn_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Supplier bill (accounts payable).
CREATE TABLE [pur].[supplier_invoice] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_supplier_invoice] PRIMARY KEY,
    [invoice_no] NVARCHAR(30) NOT NULL,
    [supplier_invoice_no] NVARCHAR(40) NOT NULL,
    [supplier_invoice_date] DATE NOT NULL,
    [supplier_id] BIGINT NOT NULL,
    [principal_id] BIGINT NULL,
    [branch_id] BIGINT NOT NULL,
    [purchase_order_id] BIGINT NULL,
    [grn_id] BIGINT NULL,
    [place_of_supply_state_id] BIGINT NOT NULL,
    [is_reverse_charge] BIT NOT NULL CONSTRAINT [DF_pur_supplier_invoice_is_reverse_charge] DEFAULT (0),
    [taxable_value] DECIMAL(18,2) NOT NULL,
    [cgst] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_pur_supplier_invoice_cgst] DEFAULT (0),
    [sgst] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_pur_supplier_invoice_sgst] DEFAULT (0),
    [igst] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_pur_supplier_invoice_igst] DEFAULT (0),
    [cess] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_pur_supplier_invoice_cess] DEFAULT (0),
    [tds_amount] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_pur_supplier_invoice_tds_amount] DEFAULT (0),
    [round_off] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_pur_supplier_invoice_round_off] DEFAULT (0),
    [total] DECIMAL(18,2) NOT NULL,
    [due_date] DATE NULL,
    [amount_paid] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_pur_supplier_invoice_amount_paid] DEFAULT (0),
    [status] NVARCHAR(30) NOT NULL,
    [journal_id] BIGINT NULL,
    [oem_invoice_ref] NVARCHAR(40) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_supplier_invoice_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_supplier_invoice_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pur_supplier_invoice_status] CHECK ([status] IN (N'Draft', N'Posted', N'Part paid', N'Paid', N'Cancelled'))
);
GO
-- Supplier bill lines.
CREATE TABLE [pur].[supplier_invoice_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_supplier_invoice_line] PRIMARY KEY,
    [supplier_invoice_id] BIGINT NOT NULL,
    [grn_line_id] BIGINT NULL,
    [purchase_order_line_id] BIGINT NULL,
    [item_id] BIGINT NULL,
    [gl_account_id] BIGINT NULL,
    [description] NVARCHAR(200) NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [unit_price] DECIMAL(18,4) NOT NULL,
    [hsn_sac_id] BIGINT NULL,
    [gst_rate_id] BIGINT NULL,
    [taxable_value] DECIMAL(18,2) NOT NULL,
    [tax_amount] DECIMAL(18,2) NOT NULL,
    [line_total] DECIMAL(18,2) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_supplier_invoice_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_supplier_invoice_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Payment made to a supplier.
CREATE TABLE [pur].[supplier_payment] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_supplier_payment] PRIMARY KEY,
    [payment_no] NVARCHAR(30) NOT NULL,
    [supplier_id] BIGINT NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [payment_date] DATE NOT NULL,
    [payment_mode] NVARCHAR(30) NOT NULL,
    [bank_account_id] BIGINT NULL,
    [cheque_id] BIGINT NULL,
    [reference_no] NVARCHAR(40) NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [tds_deducted] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_pur_supplier_payment_tds_deducted] DEFAULT (0),
    [status] NVARCHAR(30) NOT NULL,
    [journal_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_supplier_payment_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_supplier_payment_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pur_supplier_payment_payment_mode] CHECK ([payment_mode] IN (N'NEFT', N'RTGS', N'Cheque', N'Cash', N'UPI')),
    CONSTRAINT [CK_pur_supplier_payment_status] CHECK ([status] IN (N'Draft', N'Posted', N'Cancelled'))
);
GO
-- Purchase return / debit note to supplier.
CREATE TABLE [pur].[debit_note] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_debit_note] PRIMARY KEY,
    [debit_note_no] NVARCHAR(30) NOT NULL,
    [supplier_id] BIGINT NOT NULL,
    [supplier_invoice_id] BIGINT NULL,
    [grn_id] BIGINT NULL,
    [note_date] DATE NOT NULL,
    [reason_lookup_id] BIGINT NULL,
    [taxable_value] DECIMAL(18,2) NOT NULL,
    [tax_amount] DECIMAL(18,2) NOT NULL,
    [total] DECIMAL(18,2) NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [journal_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_debit_note_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_debit_note_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pur_debit_note_status] CHECK ([status] IN (N'Draft', N'Posted', N'Cancelled'))
);
GO
-- Returned items.
CREATE TABLE [pur].[debit_note_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_debit_note_line] PRIMARY KEY,
    [debit_note_id] BIGINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [serial_batch_id] BIGINT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [unit_price] DECIMAL(18,4) NOT NULL,
    [gst_rate_id] BIGINT NULL,
    [tax_amount] DECIMAL(18,2) NOT NULL,
    [line_total] DECIMAL(18,2) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_debit_note_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_debit_note_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Matches payments and debit notes to supplier bills.
CREATE TABLE [pur].[supplier_allocation] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pur_supplier_allocation] PRIMARY KEY,
    [supplier_invoice_id] BIGINT NOT NULL,
    [supplier_payment_id] BIGINT NULL,
    [debit_note_id] BIGINT NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [allocated_on] DATE NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pur_supplier_allocation_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pur_supplier_allocation_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO

/* ===== hr: HR & Payroll ===== */
-- Departments.
CREATE TABLE [hr].[department] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_department] PRIMARY KEY,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(80) NOT NULL,
    [parent_department_id] BIGINT NULL,
    [head_employee_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_department_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_department_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Designations and grades.
CREATE TABLE [hr].[designation] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_designation] PRIMARY KEY,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(80) NOT NULL,
    [grade] NVARCHAR(10) NULL,
    [department_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_designation_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_designation_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Personal, statutory and bank details (1:1 with employee).
CREATE TABLE [hr].[employee_profile] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_employee_profile] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [date_of_birth] DATE NULL,
    [gender] NVARCHAR(30) NULL,
    [personal_email] NVARCHAR(120) NULL,
    [current_address] NVARCHAR(500) NULL,
    [permanent_address] NVARCHAR(500) NULL,
    [emergency_contact_name] NVARCHAR(100) NULL,
    [emergency_contact_phone] NVARCHAR(15) NULL,
    [pan] NVARCHAR(10) NULL,
    [aadhaar_masked] NVARCHAR(14) NULL,
    [uan] NVARCHAR(12) NULL,
    [esic_no] NVARCHAR(17) NULL,
    [bank_name] NVARCHAR(100) NULL,
    [bank_account_no] NVARCHAR(30) NULL,
    [ifsc] NVARCHAR(11) NULL,
    [is_pf_applicable] BIT NOT NULL CONSTRAINT [DF_hr_employee_profile_is_pf_applicable] DEFAULT (1),
    [is_esi_applicable] BIT NOT NULL CONSTRAINT [DF_hr_employee_profile_is_esi_applicable] DEFAULT (0),
    [pt_state_id] BIGINT NULL,
    [tax_regime] NVARCHAR(30) NOT NULL CONSTRAINT [DF_hr_employee_profile_tax_regime] DEFAULT (N'New'),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_employee_profile_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_employee_profile_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_employee_profile_gender] CHECK ([gender] IN (N'Male', N'Female', N'Other')),
    CONSTRAINT [CK_hr_employee_profile_tax_regime] CHECK ([tax_regime] IN (N'Old', N'New'))
);
GO
-- Joining, confirmation, transfer, promotion, exit.
CREATE TABLE [hr].[employment_history] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_employment_history] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [event_type] NVARCHAR(30) NOT NULL,
    [effective_date] DATE NOT NULL,
    [from_branch_id] BIGINT NULL,
    [to_branch_id] BIGINT NULL,
    [from_designation_id] BIGINT NULL,
    [to_designation_id] BIGINT NULL,
    [remarks] NVARCHAR(500) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_employment_history_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_employment_history_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_employment_history_event_type] CHECK ([event_type] IN (N'Joined', N'Confirmed', N'Transferred', N'Promoted', N'Resigned', N'Terminated', N'Retired'))
);
GO
-- Employee documents (offer letter, ID proof, licence).
CREATE TABLE [hr].[employee_document] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_employee_document] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [document_type_lookup_id] BIGINT NOT NULL,
    [document_number_masked] NVARCHAR(30) NULL,
    [attachment_id] BIGINT NOT NULL,
    [valid_until] DATE NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_employee_document_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_employee_document_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Onboarding and offboarding checklist.
CREATE TABLE [hr].[onboarding_task] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_onboarding_task] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [task_type] NVARCHAR(30) NOT NULL,
    [task_name] NVARCHAR(200) NOT NULL,
    [owner_employee_id] BIGINT NULL,
    [due_date] DATE NULL,
    [completed_at] DATETIME2(0) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_onboarding_task_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_onboarding_task_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_onboarding_task_task_type] CHECK ([task_type] IN (N'Onboarding', N'Offboarding')),
    CONSTRAINT [CK_hr_onboarding_task_status] CHECK ([status] IN (N'Pending', N'Done', N'Not applicable'))
);
GO
-- Work shifts.
CREATE TABLE [hr].[shift] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_shift] PRIMARY KEY,
    [code] NVARCHAR(10) NOT NULL,
    [name] NVARCHAR(60) NOT NULL,
    [start_time] TIME(0) NOT NULL,
    [end_time] TIME(0) NOT NULL,
    [grace_minutes] SMALLINT NOT NULL CONSTRAINT [DF_hr_shift_grace_minutes] DEFAULT (10),
    [half_day_hours] DECIMAL(4,2) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_shift_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_shift_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Shift and weekly off per employee.
CREATE TABLE [hr].[employee_shift] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_employee_shift] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [shift_id] BIGINT NOT NULL,
    [weekly_off_days] NVARCHAR(20) NULL,
    [from_date] DATE NOT NULL,
    [to_date] DATE NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_employee_shift_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_employee_shift_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Holiday calendar.
CREATE TABLE [hr].[holiday] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_holiday] PRIMARY KEY,
    [branch_id] BIGINT NULL,
    [holiday_date] DATE NOT NULL,
    [name] NVARCHAR(80) NOT NULL,
    [holiday_type] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_holiday_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_holiday_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_holiday_holiday_type] CHECK ([holiday_type] IN (N'National', N'Festival', N'Optional'))
);
GO
-- Daily attendance (app, biometric, or engineer duty log).
CREATE TABLE [hr].[attendance] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_attendance] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [attendance_date] DATE NOT NULL,
    [shift_id] BIGINT NULL,
    [check_in_at] DATETIME2(0) NULL,
    [check_in_latitude] DECIMAL(9,6) NULL,
    [check_in_longitude] DECIMAL(9,6) NULL,
    [check_out_at] DATETIME2(0) NULL,
    [check_out_latitude] DECIMAL(9,6) NULL,
    [check_out_longitude] DECIMAL(9,6) NULL,
    [source] NVARCHAR(30) NOT NULL,
    [duty_log_id] BIGINT NULL,
    [worked_hours] DECIMAL(4,2) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [is_regularized] BIT NOT NULL CONSTRAINT [DF_hr_attendance_is_regularized] DEFAULT (0),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_attendance_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_attendance_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_attendance_source] CHECK ([source] IN (N'App', N'Biometric', N'Duty log', N'Manual')),
    CONSTRAINT [CK_hr_attendance_status] CHECK ([status] IN (N'Present', N'Absent', N'Half day', N'Leave', N'Holiday', N'Week off', N'On duty'))
);
GO
-- Requests to correct attendance.
CREATE TABLE [hr].[attendance_regularization] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_attendance_regularization] PRIMARY KEY,
    [attendance_id] BIGINT NOT NULL,
    [employee_id] BIGINT NOT NULL,
    [requested_status] NVARCHAR(20) NOT NULL,
    [reason] NVARCHAR(300) NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [approver_user_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_attendance_regularization_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_attendance_regularization_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_attendance_regularization_status] CHECK ([status] IN (N'Pending', N'Approved', N'Rejected'))
);
GO
-- Leave types.
CREATE TABLE [hr].[leave_type] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_leave_type] PRIMARY KEY,
    [code] NVARCHAR(10) NOT NULL,
    [name] NVARCHAR(60) NOT NULL,
    [annual_quota] DECIMAL(5,1) NULL,
    [carry_forward_max] DECIMAL(5,1) NULL,
    [is_paid] BIT NOT NULL CONSTRAINT [DF_hr_leave_type_is_paid] DEFAULT (1),
    [is_encashable] BIT NOT NULL CONSTRAINT [DF_hr_leave_type_is_encashable] DEFAULT (0),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_leave_type_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_leave_type_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Leave balance per employee per year.
CREATE TABLE [hr].[leave_balance] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_leave_balance] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [leave_type_id] BIGINT NOT NULL,
    [leave_year] SMALLINT NOT NULL,
    [opening] DECIMAL(5,1) NOT NULL CONSTRAINT [DF_hr_leave_balance_opening] DEFAULT (0),
    [accrued] DECIMAL(5,1) NOT NULL CONSTRAINT [DF_hr_leave_balance_accrued] DEFAULT (0),
    [availed] DECIMAL(5,1) NOT NULL CONSTRAINT [DF_hr_leave_balance_availed] DEFAULT (0),
    [encashed] DECIMAL(5,1) NOT NULL CONSTRAINT [DF_hr_leave_balance_encashed] DEFAULT (0),
    [closing] DECIMAL(5,1) NOT NULL CONSTRAINT [DF_hr_leave_balance_closing] DEFAULT (0),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_leave_balance_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_leave_balance_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Leave applications.
CREATE TABLE [hr].[leave_request] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_leave_request] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [leave_type_id] BIGINT NOT NULL,
    [from_date] DATE NOT NULL,
    [to_date] DATE NOT NULL,
    [is_half_day] BIT NOT NULL CONSTRAINT [DF_hr_leave_request_is_half_day] DEFAULT (0),
    [days] DECIMAL(4,1) NOT NULL,
    [reason] NVARCHAR(300) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [approver_user_id] BIGINT NULL,
    [acted_at] DATETIME2(0) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_leave_request_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_leave_request_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_leave_request_status] CHECK ([status] IN (N'Pending', N'Approved', N'Rejected', N'Cancelled'))
);
GO
-- Earnings, deductions and employer contributions.
CREATE TABLE [hr].[salary_component] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_salary_component] PRIMARY KEY,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(80) NOT NULL,
    [component_type] NVARCHAR(30) NOT NULL,
    [calculation_type] NVARCHAR(30) NOT NULL,
    [is_taxable] BIT NOT NULL CONSTRAINT [DF_hr_salary_component_is_taxable] DEFAULT (1),
    [is_pf_wage] BIT NOT NULL CONSTRAINT [DF_hr_salary_component_is_pf_wage] DEFAULT (0),
    [is_esi_wage] BIT NOT NULL CONSTRAINT [DF_hr_salary_component_is_esi_wage] DEFAULT (0),
    [gl_account_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_salary_component_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_salary_component_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_salary_component_component_type] CHECK ([component_type] IN (N'Earning', N'Deduction', N'Employer contribution')),
    CONSTRAINT [CK_hr_salary_component_calculation_type] CHECK ([calculation_type] IN (N'Fixed', N'Percent of basic', N'Formula', N'Statutory'))
);
GO
-- Employee salary structure with effective dates.
CREATE TABLE [hr].[salary_structure] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_salary_structure] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [effective_from] DATE NOT NULL,
    [effective_to] DATE NULL,
    [annual_ctc] DECIMAL(18,2) NOT NULL,
    [monthly_gross] DECIMAL(18,2) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_salary_structure_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_salary_structure_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Components in a structure.
CREATE TABLE [hr].[salary_structure_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_salary_structure_line] PRIMARY KEY,
    [salary_structure_id] BIGINT NOT NULL,
    [salary_component_id] BIGINT NOT NULL,
    [monthly_amount] DECIMAL(18,2) NULL,
    [percentage] DECIMAL(5,2) NULL,
    [formula] NVARCHAR(300) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_salary_structure_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_salary_structure_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- PF, ESI, PT, LWF, TDS rates and ceilings.
CREATE TABLE [hr].[statutory_config] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_statutory_config] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [config_type] NVARCHAR(30) NOT NULL,
    [state_id] BIGINT NULL,
    [effective_from] DATE NOT NULL,
    [employee_rate] DECIMAL(5,2) NULL,
    [employer_rate] DECIMAL(5,2) NULL,
    [wage_ceiling] DECIMAL(18,2) NULL,
    [slab_json] NVARCHAR(MAX) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_statutory_config_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_statutory_config_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_statutory_config_config_type] CHECK ([config_type] IN (N'PF', N'ESI', N'PT', N'LWF', N'TDS'))
);
GO
-- Monthly payroll run.
CREATE TABLE [hr].[payroll_run] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_payroll_run] PRIMARY KEY,
    [company_id] BIGINT NOT NULL,
    [branch_id] BIGINT NULL,
    [period_month] DATE NOT NULL,
    [run_date] DATE NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [total_gross] DECIMAL(18,2) NULL,
    [total_deductions] DECIMAL(18,2) NULL,
    [total_net] DECIMAL(18,2) NULL,
    [journal_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_payroll_run_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_payroll_run_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_payroll_run_status] CHECK ([status] IN (N'Draft', N'Processed', N'Approved', N'Paid', N'Locked'))
);
GO
-- Payslip per employee per run.
CREATE TABLE [hr].[payslip] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_payslip] PRIMARY KEY,
    [payroll_run_id] BIGINT NOT NULL,
    [employee_id] BIGINT NOT NULL,
    [paid_days] DECIMAL(4,1) NOT NULL,
    [lop_days] DECIMAL(4,1) NOT NULL CONSTRAINT [DF_hr_payslip_lop_days] DEFAULT (0),
    [gross] DECIMAL(18,2) NOT NULL,
    [total_deductions] DECIMAL(18,2) NOT NULL,
    [net_pay] DECIMAL(18,2) NOT NULL,
    [pdf_attachment_id] BIGINT NULL,
    [payment_reference] NVARCHAR(40) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_payslip_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_payslip_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Component amounts in a payslip.
CREATE TABLE [hr].[payslip_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_payslip_line] PRIMARY KEY,
    [payslip_id] BIGINT NOT NULL,
    [salary_component_id] BIGINT NOT NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_payslip_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_payslip_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Loans and salary advances.
CREATE TABLE [hr].[employee_loan] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_employee_loan] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [loan_type] NVARCHAR(30) NOT NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [sanctioned_on] DATE NOT NULL,
    [emi_amount] DECIMAL(18,2) NOT NULL,
    [installments] SMALLINT NOT NULL,
    [balance] DECIMAL(18,2) NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_employee_loan_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_employee_loan_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_employee_loan_loan_type] CHECK ([loan_type] IN (N'Loan', N'Salary advance')),
    CONSTRAINT [CK_hr_employee_loan_status] CHECK ([status] IN (N'Active', N'Closed'))
);
GO
-- Expense claims (travel km from trips, food, lodging).
CREATE TABLE [hr].[expense_claim] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_expense_claim] PRIMARY KEY,
    [claim_no] NVARCHAR(30) NOT NULL,
    [employee_id] BIGINT NOT NULL,
    [claim_date] DATE NOT NULL,
    [period_from] DATE NULL,
    [period_to] DATE NULL,
    [total_amount] DECIMAL(18,2) NOT NULL,
    [approved_amount] DECIMAL(18,2) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [paid_via] NVARCHAR(30) NULL,
    [payroll_run_id] BIGINT NULL,
    [journal_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_expense_claim_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_expense_claim_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_expense_claim_status] CHECK ([status] IN (N'Draft', N'Submitted', N'Approved', N'Rejected', N'Paid')),
    CONSTRAINT [CK_hr_expense_claim_paid_via] CHECK ([paid_via] IN (N'Payroll', N'Direct'))
);
GO
-- Claim lines; travel lines link to trips.
CREATE TABLE [hr].[expense_claim_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_expense_claim_line] PRIMARY KEY,
    [expense_claim_id] BIGINT NOT NULL,
    [expense_type_lookup_id] BIGINT NOT NULL,
    [expense_date] DATE NOT NULL,
    [trip_id] BIGINT NULL,
    [km] DECIMAL(8,2) NULL,
    [rate_per_km] DECIMAL(6,2) NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [receipt_attachment_id] BIGINT NULL,
    [remarks] NVARCHAR(300) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_expense_claim_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_expense_claim_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Company assets given to employees (phone, laptop, tool kit, SIM).
CREATE TABLE [hr].[asset] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_asset] PRIMARY KEY,
    [asset_tag] NVARCHAR(30) NOT NULL,
    [asset_type_lookup_id] BIGINT NOT NULL,
    [description] NVARCHAR(200) NULL,
    [serial_no] NVARCHAR(60) NULL,
    [purchase_date] DATE NULL,
    [purchase_value] DECIMAL(18,2) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_asset_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_asset_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_asset_status] CHECK ([status] IN (N'In store', N'Assigned', N'Repair', N'Retired'))
);
GO
-- Who holds which asset.
CREATE TABLE [hr].[asset_assignment] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_asset_assignment] PRIMARY KEY,
    [asset_id] BIGINT NOT NULL,
    [employee_id] BIGINT NOT NULL,
    [assigned_on] DATE NOT NULL,
    [returned_on] DATE NULL,
    [condition_on_return] NVARCHAR(200) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_asset_assignment_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_asset_assignment_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Periodic performance reviews.
CREATE TABLE [hr].[performance_review] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_performance_review] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [review_period] NVARCHAR(20) NOT NULL,
    [reviewer_employee_id] BIGINT NULL,
    [rating] DECIMAL(3,1) NULL,
    [goals_json] NVARCHAR(MAX) NULL,
    [comments] NVARCHAR(2000) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_performance_review_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_performance_review_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_performance_review_status] CHECK ([status] IN (N'Draft', N'Self review', N'Manager review', N'Closed'))
);
GO
-- Open positions.
CREATE TABLE [hr].[job_opening] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_job_opening] PRIMARY KEY,
    [title] NVARCHAR(120) NOT NULL,
    [designation_id] BIGINT NULL,
    [branch_id] BIGINT NULL,
    [openings] SMALLINT NOT NULL CONSTRAINT [DF_hr_job_opening_openings] DEFAULT (1),
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_job_opening_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_job_opening_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_job_opening_status] CHECK ([status] IN (N'Open', N'On hold', N'Closed'))
);
GO
-- Applicants for an opening.
CREATE TABLE [hr].[candidate] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_candidate] PRIMARY KEY,
    [job_opening_id] BIGINT NOT NULL,
    [name] NVARCHAR(120) NOT NULL,
    [phone] NVARCHAR(15) NOT NULL,
    [email] NVARCHAR(120) NULL,
    [resume_attachment_id] BIGINT NULL,
    [stage] NVARCHAR(30) NOT NULL,
    [joined_employee_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_candidate_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_candidate_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_candidate_stage] CHECK ([stage] IN (N'Applied', N'Screening', N'Interview', N'Offered', N'Joined', N'Rejected'))
);
GO
-- Exit settlement.
CREATE TABLE [hr].[full_final_settlement] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_full_final_settlement] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [last_working_day] DATE NOT NULL,
    [leave_encashment] DECIMAL(18,2) NULL,
    [gratuity] DECIMAL(18,2) NULL,
    [notice_recovery] DECIMAL(18,2) NULL,
    [loan_recovery] DECIMAL(18,2) NULL,
    [net_payable] DECIMAL(18,2) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [paid_on] DATE NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_full_final_settlement_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_full_final_settlement_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_full_final_settlement_status] CHECK ([status] IN (N'Draft', N'Approved', N'Paid'))
);
GO
-- Employee queries to HR / admin.
CREATE TABLE [hr].[helpdesk_ticket] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_hr_helpdesk_ticket] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [category_lookup_id] BIGINT NULL,
    [subject] NVARCHAR(200) NOT NULL,
    [description] NVARCHAR(2000) NULL,
    [assigned_to_employee_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [resolved_at] DATETIME2(0) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_hr_helpdesk_ticket_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_hr_helpdesk_ticket_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_hr_helpdesk_ticket_status] CHECK ([status] IN (N'Open', N'In progress', N'Resolved', N'Closed'))
);
GO

/* ---------- 2. Unique keys (21) ---------- */
CREATE UNIQUE NONCLUSTERED INDEX [UX_svc_warranty_claim_claim_no] ON [svc].[warranty_claim] ([claim_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pur_supplier_item_price_k1] ON [pur].[supplier_item_price] ([supplier_id], [item_id], [valid_from]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pur_purchase_request_pr_no] ON [pur].[purchase_request] ([pr_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pur_purchase_order_po_no] ON [pur].[purchase_order] ([po_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pur_grn_grn_no] ON [pur].[grn] ([grn_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pur_supplier_invoice_invoice_no] ON [pur].[supplier_invoice] ([invoice_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pur_supplier_invoice_k1] ON [pur].[supplier_invoice] ([supplier_id], [supplier_invoice_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pur_supplier_payment_payment_no] ON [pur].[supplier_payment] ([payment_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pur_debit_note_debit_note_no] ON [pur].[debit_note] ([debit_note_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_department_code] ON [hr].[department] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_designation_code] ON [hr].[designation] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_employee_profile_employee_id] ON [hr].[employee_profile] ([employee_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_shift_code] ON [hr].[shift] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_attendance_k1] ON [hr].[attendance] ([employee_id], [attendance_date]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_leave_type_code] ON [hr].[leave_type] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_leave_balance_k1] ON [hr].[leave_balance] ([employee_id], [leave_type_id], [leave_year]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_salary_component_code] ON [hr].[salary_component] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_payslip_k1] ON [hr].[payslip] ([payroll_run_id], [employee_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_expense_claim_claim_no] ON [hr].[expense_claim] ([claim_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_asset_asset_tag] ON [hr].[asset] ([asset_tag]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_hr_full_final_settlement_employee_id] ON [hr].[full_final_settlement] ([employee_id]);
GO

/* ---------- 3. Foreign keys (137) ----------
   Includes links from earlier-phase columns to tables created in this phase. */
ALTER TABLE [core].[employee] ADD CONSTRAINT [FK_core_employee_department_id] FOREIGN KEY ([department_id]) REFERENCES [hr].[department] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[employee] ADD CONSTRAINT [FK_core_employee_designation_id] FOREIGN KEY ([designation_id]) REFERENCES [hr].[designation] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[warranty_claim] ADD CONSTRAINT [FK_svc_warranty_claim_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[warranty_claim] ADD CONSTRAINT [FK_svc_warranty_claim_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[warranty_claim] ADD CONSTRAINT [FK_svc_warranty_claim_machine_unit_id] FOREIGN KEY ([machine_unit_id]) REFERENCES [core].[machine_unit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[warranty_claim] ADD CONSTRAINT [FK_svc_warranty_claim_failure_code_lookup_id] FOREIGN KEY ([failure_code_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[warranty_claim_part] ADD CONSTRAINT [FK_svc_warranty_claim_part_warranty_claim_id] FOREIGN KEY ([warranty_claim_id]) REFERENCES [svc].[warranty_claim] ([id]) ON DELETE CASCADE;
ALTER TABLE [svc].[warranty_claim_part] ADD CONSTRAINT [FK_svc_warranty_claim_part_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[serial_batch] ADD CONSTRAINT [FK_inv_serial_batch_grn_line_id] FOREIGN KEY ([grn_line_id]) REFERENCES [pur].[grn_line] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[defective_return] ADD CONSTRAINT [FK_inv_defective_return_warranty_claim_id] FOREIGN KEY ([warranty_claim_id]) REFERENCES [svc].[warranty_claim] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_item_price] ADD CONSTRAINT [FK_pur_supplier_item_price_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_item_price] ADD CONSTRAINT [FK_pur_supplier_item_price_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_item_price] ADD CONSTRAINT [FK_pur_supplier_item_price_currency_id] FOREIGN KEY ([currency_id]) REFERENCES [core].[currency] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_request] ADD CONSTRAINT [FK_pur_purchase_request_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_request] ADD CONSTRAINT [FK_pur_purchase_request_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_request] ADD CONSTRAINT [FK_pur_purchase_request_requested_by_employee_id] FOREIGN KEY ([requested_by_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_request] ADD CONSTRAINT [FK_pur_purchase_request_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_request_line] ADD CONSTRAINT [FK_pur_purchase_request_line_purchase_request_id] FOREIGN KEY ([purchase_request_id]) REFERENCES [pur].[purchase_request] ([id]) ON DELETE CASCADE;
ALTER TABLE [pur].[purchase_request_line] ADD CONSTRAINT [FK_pur_purchase_request_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order] ADD CONSTRAINT [FK_pur_purchase_order_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order] ADD CONSTRAINT [FK_pur_purchase_order_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order] ADD CONSTRAINT [FK_pur_purchase_order_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order] ADD CONSTRAINT [FK_pur_purchase_order_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order] ADD CONSTRAINT [FK_pur_purchase_order_delivery_location_id] FOREIGN KEY ([delivery_location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order] ADD CONSTRAINT [FK_pur_purchase_order_payment_terms_id] FOREIGN KEY ([payment_terms_id]) REFERENCES [core].[payment_terms] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order] ADD CONSTRAINT [FK_pur_purchase_order_place_of_supply_state_id] FOREIGN KEY ([place_of_supply_state_id]) REFERENCES [core].[state] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order] ADD CONSTRAINT [FK_pur_purchase_order_currency_id] FOREIGN KEY ([currency_id]) REFERENCES [core].[currency] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order_line] ADD CONSTRAINT [FK_pur_purchase_order_line_purchase_order_id] FOREIGN KEY ([purchase_order_id]) REFERENCES [pur].[purchase_order] ([id]) ON DELETE CASCADE;
ALTER TABLE [pur].[purchase_order_line] ADD CONSTRAINT [FK_pur_purchase_order_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order_line] ADD CONSTRAINT [FK_pur_purchase_order_line_uom_id] FOREIGN KEY ([uom_id]) REFERENCES [core].[uom] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order_line] ADD CONSTRAINT [FK_pur_purchase_order_line_hsn_sac_id] FOREIGN KEY ([hsn_sac_id]) REFERENCES [core].[hsn_sac] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order_line] ADD CONSTRAINT [FK_pur_purchase_order_line_gst_rate_id] FOREIGN KEY ([gst_rate_id]) REFERENCES [acc].[gst_rate] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[purchase_order_line] ADD CONSTRAINT [FK_pur_purchase_order_line_purchase_request_line_id] FOREIGN KEY ([purchase_request_line_id]) REFERENCES [pur].[purchase_request_line] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[grn] ADD CONSTRAINT [FK_pur_grn_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[grn] ADD CONSTRAINT [FK_pur_grn_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[grn] ADD CONSTRAINT [FK_pur_grn_purchase_order_id] FOREIGN KEY ([purchase_order_id]) REFERENCES [pur].[purchase_order] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[grn] ADD CONSTRAINT [FK_pur_grn_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[grn] ADD CONSTRAINT [FK_pur_grn_location_id] FOREIGN KEY ([location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[grn_line] ADD CONSTRAINT [FK_pur_grn_line_grn_id] FOREIGN KEY ([grn_id]) REFERENCES [pur].[grn] ([id]) ON DELETE CASCADE;
ALTER TABLE [pur].[grn_line] ADD CONSTRAINT [FK_pur_grn_line_purchase_order_line_id] FOREIGN KEY ([purchase_order_line_id]) REFERENCES [pur].[purchase_order_line] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[grn_line] ADD CONSTRAINT [FK_pur_grn_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[grn_line] ADD CONSTRAINT [FK_pur_grn_line_bin_id] FOREIGN KEY ([bin_id]) REFERENCES [inv].[bin] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice] ADD CONSTRAINT [FK_pur_supplier_invoice_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice] ADD CONSTRAINT [FK_pur_supplier_invoice_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice] ADD CONSTRAINT [FK_pur_supplier_invoice_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice] ADD CONSTRAINT [FK_pur_supplier_invoice_purchase_order_id] FOREIGN KEY ([purchase_order_id]) REFERENCES [pur].[purchase_order] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice] ADD CONSTRAINT [FK_pur_supplier_invoice_grn_id] FOREIGN KEY ([grn_id]) REFERENCES [pur].[grn] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice] ADD CONSTRAINT [FK_pur_supplier_invoice_place_of_supply_state_id] FOREIGN KEY ([place_of_supply_state_id]) REFERENCES [core].[state] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice] ADD CONSTRAINT [FK_pur_supplier_invoice_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice_line] ADD CONSTRAINT [FK_pur_supplier_invoice_line_supplier_invoice_id] FOREIGN KEY ([supplier_invoice_id]) REFERENCES [pur].[supplier_invoice] ([id]) ON DELETE CASCADE;
ALTER TABLE [pur].[supplier_invoice_line] ADD CONSTRAINT [FK_pur_supplier_invoice_line_grn_line_id] FOREIGN KEY ([grn_line_id]) REFERENCES [pur].[grn_line] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice_line] ADD CONSTRAINT [FK_pur_supplier_invoice_line_purchase_order_line_id] FOREIGN KEY ([purchase_order_line_id]) REFERENCES [pur].[purchase_order_line] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice_line] ADD CONSTRAINT [FK_pur_supplier_invoice_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice_line] ADD CONSTRAINT [FK_pur_supplier_invoice_line_gl_account_id] FOREIGN KEY ([gl_account_id]) REFERENCES [acc].[gl_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice_line] ADD CONSTRAINT [FK_pur_supplier_invoice_line_hsn_sac_id] FOREIGN KEY ([hsn_sac_id]) REFERENCES [core].[hsn_sac] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_invoice_line] ADD CONSTRAINT [FK_pur_supplier_invoice_line_gst_rate_id] FOREIGN KEY ([gst_rate_id]) REFERENCES [acc].[gst_rate] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_payment] ADD CONSTRAINT [FK_pur_supplier_payment_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_payment] ADD CONSTRAINT [FK_pur_supplier_payment_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_payment] ADD CONSTRAINT [FK_pur_supplier_payment_bank_account_id] FOREIGN KEY ([bank_account_id]) REFERENCES [acc].[bank_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_payment] ADD CONSTRAINT [FK_pur_supplier_payment_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[debit_note] ADD CONSTRAINT [FK_pur_debit_note_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[debit_note] ADD CONSTRAINT [FK_pur_debit_note_supplier_invoice_id] FOREIGN KEY ([supplier_invoice_id]) REFERENCES [pur].[supplier_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[debit_note] ADD CONSTRAINT [FK_pur_debit_note_grn_id] FOREIGN KEY ([grn_id]) REFERENCES [pur].[grn] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[debit_note] ADD CONSTRAINT [FK_pur_debit_note_reason_lookup_id] FOREIGN KEY ([reason_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[debit_note] ADD CONSTRAINT [FK_pur_debit_note_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[debit_note_line] ADD CONSTRAINT [FK_pur_debit_note_line_debit_note_id] FOREIGN KEY ([debit_note_id]) REFERENCES [pur].[debit_note] ([id]) ON DELETE CASCADE;
ALTER TABLE [pur].[debit_note_line] ADD CONSTRAINT [FK_pur_debit_note_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[debit_note_line] ADD CONSTRAINT [FK_pur_debit_note_line_serial_batch_id] FOREIGN KEY ([serial_batch_id]) REFERENCES [inv].[serial_batch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[debit_note_line] ADD CONSTRAINT [FK_pur_debit_note_line_gst_rate_id] FOREIGN KEY ([gst_rate_id]) REFERENCES [acc].[gst_rate] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_allocation] ADD CONSTRAINT [FK_pur_supplier_allocation_supplier_invoice_id] FOREIGN KEY ([supplier_invoice_id]) REFERENCES [pur].[supplier_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_allocation] ADD CONSTRAINT [FK_pur_supplier_allocation_supplier_payment_id] FOREIGN KEY ([supplier_payment_id]) REFERENCES [pur].[supplier_payment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_allocation] ADD CONSTRAINT [FK_pur_supplier_allocation_debit_note_id] FOREIGN KEY ([debit_note_id]) REFERENCES [pur].[debit_note] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[department] ADD CONSTRAINT [FK_hr_department_parent_department_id] FOREIGN KEY ([parent_department_id]) REFERENCES [hr].[department] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[department] ADD CONSTRAINT [FK_hr_department_head_employee_id] FOREIGN KEY ([head_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[designation] ADD CONSTRAINT [FK_hr_designation_department_id] FOREIGN KEY ([department_id]) REFERENCES [hr].[department] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employee_profile] ADD CONSTRAINT [FK_hr_employee_profile_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employee_profile] ADD CONSTRAINT [FK_hr_employee_profile_pt_state_id] FOREIGN KEY ([pt_state_id]) REFERENCES [core].[state] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employment_history] ADD CONSTRAINT [FK_hr_employment_history_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employment_history] ADD CONSTRAINT [FK_hr_employment_history_from_branch_id] FOREIGN KEY ([from_branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employment_history] ADD CONSTRAINT [FK_hr_employment_history_to_branch_id] FOREIGN KEY ([to_branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employment_history] ADD CONSTRAINT [FK_hr_employment_history_from_designation_id] FOREIGN KEY ([from_designation_id]) REFERENCES [hr].[designation] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employment_history] ADD CONSTRAINT [FK_hr_employment_history_to_designation_id] FOREIGN KEY ([to_designation_id]) REFERENCES [hr].[designation] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employee_document] ADD CONSTRAINT [FK_hr_employee_document_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employee_document] ADD CONSTRAINT [FK_hr_employee_document_document_type_lookup_id] FOREIGN KEY ([document_type_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employee_document] ADD CONSTRAINT [FK_hr_employee_document_attachment_id] FOREIGN KEY ([attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[onboarding_task] ADD CONSTRAINT [FK_hr_onboarding_task_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[onboarding_task] ADD CONSTRAINT [FK_hr_onboarding_task_owner_employee_id] FOREIGN KEY ([owner_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employee_shift] ADD CONSTRAINT [FK_hr_employee_shift_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employee_shift] ADD CONSTRAINT [FK_hr_employee_shift_shift_id] FOREIGN KEY ([shift_id]) REFERENCES [hr].[shift] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[holiday] ADD CONSTRAINT [FK_hr_holiday_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[attendance] ADD CONSTRAINT [FK_hr_attendance_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[attendance] ADD CONSTRAINT [FK_hr_attendance_shift_id] FOREIGN KEY ([shift_id]) REFERENCES [hr].[shift] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[attendance] ADD CONSTRAINT [FK_hr_attendance_duty_log_id] FOREIGN KEY ([duty_log_id]) REFERENCES [svc].[engineer_duty_log] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[attendance_regularization] ADD CONSTRAINT [FK_hr_attendance_regularization_attendance_id] FOREIGN KEY ([attendance_id]) REFERENCES [hr].[attendance] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[attendance_regularization] ADD CONSTRAINT [FK_hr_attendance_regularization_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[attendance_regularization] ADD CONSTRAINT [FK_hr_attendance_regularization_approver_user_id] FOREIGN KEY ([approver_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[leave_balance] ADD CONSTRAINT [FK_hr_leave_balance_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[leave_balance] ADD CONSTRAINT [FK_hr_leave_balance_leave_type_id] FOREIGN KEY ([leave_type_id]) REFERENCES [hr].[leave_type] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[leave_request] ADD CONSTRAINT [FK_hr_leave_request_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[leave_request] ADD CONSTRAINT [FK_hr_leave_request_leave_type_id] FOREIGN KEY ([leave_type_id]) REFERENCES [hr].[leave_type] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[leave_request] ADD CONSTRAINT [FK_hr_leave_request_approver_user_id] FOREIGN KEY ([approver_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[salary_component] ADD CONSTRAINT [FK_hr_salary_component_gl_account_id] FOREIGN KEY ([gl_account_id]) REFERENCES [acc].[gl_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[salary_structure] ADD CONSTRAINT [FK_hr_salary_structure_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[salary_structure_line] ADD CONSTRAINT [FK_hr_salary_structure_line_salary_structure_id] FOREIGN KEY ([salary_structure_id]) REFERENCES [hr].[salary_structure] ([id]) ON DELETE CASCADE;
ALTER TABLE [hr].[salary_structure_line] ADD CONSTRAINT [FK_hr_salary_structure_line_salary_component_id] FOREIGN KEY ([salary_component_id]) REFERENCES [hr].[salary_component] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[statutory_config] ADD CONSTRAINT [FK_hr_statutory_config_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[statutory_config] ADD CONSTRAINT [FK_hr_statutory_config_state_id] FOREIGN KEY ([state_id]) REFERENCES [core].[state] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[payroll_run] ADD CONSTRAINT [FK_hr_payroll_run_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[payroll_run] ADD CONSTRAINT [FK_hr_payroll_run_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[payroll_run] ADD CONSTRAINT [FK_hr_payroll_run_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[payslip] ADD CONSTRAINT [FK_hr_payslip_payroll_run_id] FOREIGN KEY ([payroll_run_id]) REFERENCES [hr].[payroll_run] ([id]) ON DELETE CASCADE;
ALTER TABLE [hr].[payslip] ADD CONSTRAINT [FK_hr_payslip_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[payslip] ADD CONSTRAINT [FK_hr_payslip_pdf_attachment_id] FOREIGN KEY ([pdf_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[payslip_line] ADD CONSTRAINT [FK_hr_payslip_line_payslip_id] FOREIGN KEY ([payslip_id]) REFERENCES [hr].[payslip] ([id]) ON DELETE CASCADE;
ALTER TABLE [hr].[payslip_line] ADD CONSTRAINT [FK_hr_payslip_line_salary_component_id] FOREIGN KEY ([salary_component_id]) REFERENCES [hr].[salary_component] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[employee_loan] ADD CONSTRAINT [FK_hr_employee_loan_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[expense_claim] ADD CONSTRAINT [FK_hr_expense_claim_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[expense_claim] ADD CONSTRAINT [FK_hr_expense_claim_payroll_run_id] FOREIGN KEY ([payroll_run_id]) REFERENCES [hr].[payroll_run] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[expense_claim] ADD CONSTRAINT [FK_hr_expense_claim_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[expense_claim_line] ADD CONSTRAINT [FK_hr_expense_claim_line_expense_claim_id] FOREIGN KEY ([expense_claim_id]) REFERENCES [hr].[expense_claim] ([id]) ON DELETE CASCADE;
ALTER TABLE [hr].[expense_claim_line] ADD CONSTRAINT [FK_hr_expense_claim_line_expense_type_lookup_id] FOREIGN KEY ([expense_type_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[expense_claim_line] ADD CONSTRAINT [FK_hr_expense_claim_line_trip_id] FOREIGN KEY ([trip_id]) REFERENCES [svc].[trip] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[expense_claim_line] ADD CONSTRAINT [FK_hr_expense_claim_line_receipt_attachment_id] FOREIGN KEY ([receipt_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[asset] ADD CONSTRAINT [FK_hr_asset_asset_type_lookup_id] FOREIGN KEY ([asset_type_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[asset_assignment] ADD CONSTRAINT [FK_hr_asset_assignment_asset_id] FOREIGN KEY ([asset_id]) REFERENCES [hr].[asset] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[asset_assignment] ADD CONSTRAINT [FK_hr_asset_assignment_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[performance_review] ADD CONSTRAINT [FK_hr_performance_review_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[performance_review] ADD CONSTRAINT [FK_hr_performance_review_reviewer_employee_id] FOREIGN KEY ([reviewer_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[job_opening] ADD CONSTRAINT [FK_hr_job_opening_designation_id] FOREIGN KEY ([designation_id]) REFERENCES [hr].[designation] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[job_opening] ADD CONSTRAINT [FK_hr_job_opening_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[candidate] ADD CONSTRAINT [FK_hr_candidate_job_opening_id] FOREIGN KEY ([job_opening_id]) REFERENCES [hr].[job_opening] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[candidate] ADD CONSTRAINT [FK_hr_candidate_resume_attachment_id] FOREIGN KEY ([resume_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[candidate] ADD CONSTRAINT [FK_hr_candidate_joined_employee_id] FOREIGN KEY ([joined_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[full_final_settlement] ADD CONSTRAINT [FK_hr_full_final_settlement_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[helpdesk_ticket] ADD CONSTRAINT [FK_hr_helpdesk_ticket_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[helpdesk_ticket] ADD CONSTRAINT [FK_hr_helpdesk_ticket_category_lookup_id] FOREIGN KEY ([category_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [hr].[helpdesk_ticket] ADD CONSTRAINT [FK_hr_helpdesk_ticket_assigned_to_employee_id] FOREIGN KEY ([assigned_to_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
GO

/* ---------- 4. Foreign-key indexes (135) ---------- */
CREATE NONCLUSTERED INDEX [IX_core_employee_department_id] ON [core].[employee] ([department_id]);
CREATE NONCLUSTERED INDEX [IX_core_employee_designation_id] ON [core].[employee] ([designation_id]);
CREATE NONCLUSTERED INDEX [IX_svc_warranty_claim_principal_id] ON [svc].[warranty_claim] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_svc_warranty_claim_service_call_id] ON [svc].[warranty_claim] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_svc_warranty_claim_machine_unit_id] ON [svc].[warranty_claim] ([machine_unit_id]);
CREATE NONCLUSTERED INDEX [IX_svc_warranty_claim_failure_code_lookup_id] ON [svc].[warranty_claim] ([failure_code_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_svc_warranty_claim_part_warranty_claim_id] ON [svc].[warranty_claim_part] ([warranty_claim_id]);
CREATE NONCLUSTERED INDEX [IX_svc_warranty_claim_part_item_id] ON [svc].[warranty_claim_part] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_inv_serial_batch_grn_line_id] ON [inv].[serial_batch] ([grn_line_id]);
CREATE NONCLUSTERED INDEX [IX_inv_defective_return_warranty_claim_id] ON [inv].[defective_return] ([warranty_claim_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_item_price_supplier_id] ON [pur].[supplier_item_price] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_item_price_item_id] ON [pur].[supplier_item_price] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_item_price_currency_id] ON [pur].[supplier_item_price] ([currency_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_request_branch_id] ON [pur].[purchase_request] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_request_principal_id] ON [pur].[purchase_request] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_request_requested_by_employee_id] ON [pur].[purchase_request] ([requested_by_employee_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_request_service_call_id] ON [pur].[purchase_request] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_request_line_purchase_request_id] ON [pur].[purchase_request_line] ([purchase_request_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_request_line_item_id] ON [pur].[purchase_request_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_company_id] ON [pur].[purchase_order] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_branch_id] ON [pur].[purchase_order] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_supplier_id] ON [pur].[purchase_order] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_principal_id] ON [pur].[purchase_order] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_delivery_location_id] ON [pur].[purchase_order] ([delivery_location_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_payment_terms_id] ON [pur].[purchase_order] ([payment_terms_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_place_of_supply_state_id] ON [pur].[purchase_order] ([place_of_supply_state_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_currency_id] ON [pur].[purchase_order] ([currency_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_line_purchase_order_id] ON [pur].[purchase_order_line] ([purchase_order_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_line_item_id] ON [pur].[purchase_order_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_line_uom_id] ON [pur].[purchase_order_line] ([uom_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_line_hsn_sac_id] ON [pur].[purchase_order_line] ([hsn_sac_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_line_gst_rate_id] ON [pur].[purchase_order_line] ([gst_rate_id]);
CREATE NONCLUSTERED INDEX [IX_pur_purchase_order_line_purchase_request_line_id] ON [pur].[purchase_order_line] ([purchase_request_line_id]);
CREATE NONCLUSTERED INDEX [IX_pur_grn_branch_id] ON [pur].[grn] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_pur_grn_supplier_id] ON [pur].[grn] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_pur_grn_purchase_order_id] ON [pur].[grn] ([purchase_order_id]);
CREATE NONCLUSTERED INDEX [IX_pur_grn_principal_id] ON [pur].[grn] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_pur_grn_location_id] ON [pur].[grn] ([location_id]);
CREATE NONCLUSTERED INDEX [IX_pur_grn_line_grn_id] ON [pur].[grn_line] ([grn_id]);
CREATE NONCLUSTERED INDEX [IX_pur_grn_line_purchase_order_line_id] ON [pur].[grn_line] ([purchase_order_line_id]);
CREATE NONCLUSTERED INDEX [IX_pur_grn_line_item_id] ON [pur].[grn_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_pur_grn_line_bin_id] ON [pur].[grn_line] ([bin_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_supplier_id] ON [pur].[supplier_invoice] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_principal_id] ON [pur].[supplier_invoice] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_branch_id] ON [pur].[supplier_invoice] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_purchase_order_id] ON [pur].[supplier_invoice] ([purchase_order_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_grn_id] ON [pur].[supplier_invoice] ([grn_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_place_of_supply_state_id] ON [pur].[supplier_invoice] ([place_of_supply_state_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_journal_id] ON [pur].[supplier_invoice] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_line_supplier_invoice_id] ON [pur].[supplier_invoice_line] ([supplier_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_line_grn_line_id] ON [pur].[supplier_invoice_line] ([grn_line_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_line_purchase_order_line_id] ON [pur].[supplier_invoice_line] ([purchase_order_line_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_line_item_id] ON [pur].[supplier_invoice_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_line_gl_account_id] ON [pur].[supplier_invoice_line] ([gl_account_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_line_hsn_sac_id] ON [pur].[supplier_invoice_line] ([hsn_sac_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_invoice_line_gst_rate_id] ON [pur].[supplier_invoice_line] ([gst_rate_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_payment_supplier_id] ON [pur].[supplier_payment] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_payment_branch_id] ON [pur].[supplier_payment] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_payment_bank_account_id] ON [pur].[supplier_payment] ([bank_account_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_payment_journal_id] ON [pur].[supplier_payment] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_pur_debit_note_supplier_id] ON [pur].[debit_note] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_pur_debit_note_supplier_invoice_id] ON [pur].[debit_note] ([supplier_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_pur_debit_note_grn_id] ON [pur].[debit_note] ([grn_id]);
CREATE NONCLUSTERED INDEX [IX_pur_debit_note_reason_lookup_id] ON [pur].[debit_note] ([reason_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_pur_debit_note_journal_id] ON [pur].[debit_note] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_pur_debit_note_line_debit_note_id] ON [pur].[debit_note_line] ([debit_note_id]);
CREATE NONCLUSTERED INDEX [IX_pur_debit_note_line_item_id] ON [pur].[debit_note_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_pur_debit_note_line_serial_batch_id] ON [pur].[debit_note_line] ([serial_batch_id]);
CREATE NONCLUSTERED INDEX [IX_pur_debit_note_line_gst_rate_id] ON [pur].[debit_note_line] ([gst_rate_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_allocation_supplier_invoice_id] ON [pur].[supplier_allocation] ([supplier_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_allocation_supplier_payment_id] ON [pur].[supplier_allocation] ([supplier_payment_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_allocation_debit_note_id] ON [pur].[supplier_allocation] ([debit_note_id]);
CREATE NONCLUSTERED INDEX [IX_hr_department_parent_department_id] ON [hr].[department] ([parent_department_id]);
CREATE NONCLUSTERED INDEX [IX_hr_department_head_employee_id] ON [hr].[department] ([head_employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_designation_department_id] ON [hr].[designation] ([department_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employee_profile_pt_state_id] ON [hr].[employee_profile] ([pt_state_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employment_history_employee_id] ON [hr].[employment_history] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employment_history_from_branch_id] ON [hr].[employment_history] ([from_branch_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employment_history_to_branch_id] ON [hr].[employment_history] ([to_branch_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employment_history_from_designation_id] ON [hr].[employment_history] ([from_designation_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employment_history_to_designation_id] ON [hr].[employment_history] ([to_designation_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employee_document_employee_id] ON [hr].[employee_document] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employee_document_document_type_lookup_id] ON [hr].[employee_document] ([document_type_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employee_document_attachment_id] ON [hr].[employee_document] ([attachment_id]);
CREATE NONCLUSTERED INDEX [IX_hr_onboarding_task_employee_id] ON [hr].[onboarding_task] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_onboarding_task_owner_employee_id] ON [hr].[onboarding_task] ([owner_employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employee_shift_employee_id] ON [hr].[employee_shift] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employee_shift_shift_id] ON [hr].[employee_shift] ([shift_id]);
CREATE NONCLUSTERED INDEX [IX_hr_holiday_branch_id] ON [hr].[holiday] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_hr_attendance_employee_id] ON [hr].[attendance] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_attendance_shift_id] ON [hr].[attendance] ([shift_id]);
CREATE NONCLUSTERED INDEX [IX_hr_attendance_duty_log_id] ON [hr].[attendance] ([duty_log_id]);
CREATE NONCLUSTERED INDEX [IX_hr_attendance_regularization_attendance_id] ON [hr].[attendance_regularization] ([attendance_id]);
CREATE NONCLUSTERED INDEX [IX_hr_attendance_regularization_employee_id] ON [hr].[attendance_regularization] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_attendance_regularization_approver_user_id] ON [hr].[attendance_regularization] ([approver_user_id]);
CREATE NONCLUSTERED INDEX [IX_hr_leave_balance_employee_id] ON [hr].[leave_balance] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_leave_balance_leave_type_id] ON [hr].[leave_balance] ([leave_type_id]);
CREATE NONCLUSTERED INDEX [IX_hr_leave_request_employee_id] ON [hr].[leave_request] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_leave_request_leave_type_id] ON [hr].[leave_request] ([leave_type_id]);
CREATE NONCLUSTERED INDEX [IX_hr_leave_request_approver_user_id] ON [hr].[leave_request] ([approver_user_id]);
CREATE NONCLUSTERED INDEX [IX_hr_salary_component_gl_account_id] ON [hr].[salary_component] ([gl_account_id]);
CREATE NONCLUSTERED INDEX [IX_hr_salary_structure_employee_id] ON [hr].[salary_structure] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_salary_structure_line_salary_structure_id] ON [hr].[salary_structure_line] ([salary_structure_id]);
CREATE NONCLUSTERED INDEX [IX_hr_salary_structure_line_salary_component_id] ON [hr].[salary_structure_line] ([salary_component_id]);
CREATE NONCLUSTERED INDEX [IX_hr_statutory_config_company_id] ON [hr].[statutory_config] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_hr_statutory_config_state_id] ON [hr].[statutory_config] ([state_id]);
CREATE NONCLUSTERED INDEX [IX_hr_payroll_run_company_id] ON [hr].[payroll_run] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_hr_payroll_run_branch_id] ON [hr].[payroll_run] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_hr_payroll_run_journal_id] ON [hr].[payroll_run] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_hr_payslip_payroll_run_id] ON [hr].[payslip] ([payroll_run_id]);
CREATE NONCLUSTERED INDEX [IX_hr_payslip_employee_id] ON [hr].[payslip] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_payslip_pdf_attachment_id] ON [hr].[payslip] ([pdf_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_hr_payslip_line_payslip_id] ON [hr].[payslip_line] ([payslip_id]);
CREATE NONCLUSTERED INDEX [IX_hr_payslip_line_salary_component_id] ON [hr].[payslip_line] ([salary_component_id]);
CREATE NONCLUSTERED INDEX [IX_hr_employee_loan_employee_id] ON [hr].[employee_loan] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_expense_claim_employee_id] ON [hr].[expense_claim] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_expense_claim_payroll_run_id] ON [hr].[expense_claim] ([payroll_run_id]);
CREATE NONCLUSTERED INDEX [IX_hr_expense_claim_journal_id] ON [hr].[expense_claim] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_hr_expense_claim_line_expense_claim_id] ON [hr].[expense_claim_line] ([expense_claim_id]);
CREATE NONCLUSTERED INDEX [IX_hr_expense_claim_line_expense_type_lookup_id] ON [hr].[expense_claim_line] ([expense_type_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_hr_expense_claim_line_trip_id] ON [hr].[expense_claim_line] ([trip_id]);
CREATE NONCLUSTERED INDEX [IX_hr_expense_claim_line_receipt_attachment_id] ON [hr].[expense_claim_line] ([receipt_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_hr_asset_asset_type_lookup_id] ON [hr].[asset] ([asset_type_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_hr_asset_assignment_asset_id] ON [hr].[asset_assignment] ([asset_id]);
CREATE NONCLUSTERED INDEX [IX_hr_asset_assignment_employee_id] ON [hr].[asset_assignment] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_performance_review_employee_id] ON [hr].[performance_review] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_performance_review_reviewer_employee_id] ON [hr].[performance_review] ([reviewer_employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_job_opening_designation_id] ON [hr].[job_opening] ([designation_id]);
CREATE NONCLUSTERED INDEX [IX_hr_job_opening_branch_id] ON [hr].[job_opening] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_hr_candidate_job_opening_id] ON [hr].[candidate] ([job_opening_id]);
CREATE NONCLUSTERED INDEX [IX_hr_candidate_resume_attachment_id] ON [hr].[candidate] ([resume_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_hr_candidate_joined_employee_id] ON [hr].[candidate] ([joined_employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_helpdesk_ticket_employee_id] ON [hr].[helpdesk_ticket] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_hr_helpdesk_ticket_category_lookup_id] ON [hr].[helpdesk_ticket] ([category_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_hr_helpdesk_ticket_assigned_to_employee_id] ON [hr].[helpdesk_ticket] ([assigned_to_employee_id]);
GO

/* =====================================================================
   TRISHUL Integrated System - SQL Server DDL (dictionary v2)
   Phase 4 - Sales
   Generated from the TRISHUL Database Dictionary. Do not edit by hand:
   change the dictionary and regenerate.
   Target: SQL Server 2019+ / Amazon RDS for SQL Server
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
/* ---------- 1. Tables (23) ---------- */

/* ===== sal: Sales ===== */
-- Customer credit status.
CREATE TABLE [sal].[credit_status] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_credit_status] PRIMARY KEY,
    [code] NVARCHAR(10) NOT NULL,
    [description] NVARCHAR(100) NOT NULL,
    [disallow_invoicing] BIT NOT NULL CONSTRAINT [DF_sal_credit_status_disallow_invoicing] DEFAULT (0),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_credit_status_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_credit_status_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Price lists (retail, dealer, government, service labour).
CREATE TABLE [sal].[price_list] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_price_list] PRIMARY KEY,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(80) NOT NULL,
    [principal_id] BIGINT NULL,
    [price_list_type] NVARCHAR(30) NOT NULL,
    [currency_id] BIGINT NOT NULL,
    [includes_tax] BIT NOT NULL CONSTRAINT [DF_sal_price_list_includes_tax] DEFAULT (0),
    [valid_from] DATE NULL,
    [valid_to] DATE NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_price_list_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_price_list_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_price_list_price_list_type] CHECK ([price_list_type] IN (N'Retail', N'Dealer', N'Government', N'Service labour'))
);
GO
-- Item price in a price list.
CREATE TABLE [sal].[price_list_item] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_price_list_item] PRIMARY KEY,
    [price_list_id] BIGINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [unit_price] DECIMAL(18,4) NOT NULL,
    [min_qty] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_sal_price_list_item_min_qty] DEFAULT (1),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_price_list_item_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_price_list_item_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Quotation for machines, parts or service.
CREATE TABLE [sal].[quotation] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_quotation] PRIMARY KEY,
    [quotation_no] NVARCHAR(30) NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [customer_id] BIGINT NOT NULL,
    [contact_id] BIGINT NULL,
    [opportunity_id] BIGINT NULL,
    [service_call_id] BIGINT NULL,
    [quotation_type] NVARCHAR(30) NOT NULL,
    [quotation_date] DATE NOT NULL,
    [valid_until] DATE NULL,
    [salesperson_employee_id] BIGINT NULL,
    [price_list_id] BIGINT NULL,
    [place_of_supply_state_id] BIGINT NOT NULL,
    [subtotal] DECIMAL(18,2) NOT NULL,
    [discount_total] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_quotation_discount_total] DEFAULT (0),
    [tax_total] DECIMAL(18,2) NOT NULL,
    [total] DECIMAL(18,2) NOT NULL,
    [current_version] SMALLINT NOT NULL CONSTRAINT [DF_sal_quotation_current_version] DEFAULT (1),
    [status] NVARCHAR(30) NOT NULL,
    [terms] NVARCHAR(2000) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_quotation_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_quotation_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_quotation_quotation_type] CHECK ([quotation_type] IN (N'Machine', N'Parts', N'Service')),
    CONSTRAINT [CK_sal_quotation_status] CHECK ([status] IN (N'Draft', N'Pending approval', N'Sent', N'Accepted', N'Rejected', N'Expired'))
);
GO
-- Each revision sent to the customer.
CREATE TABLE [sal].[quotation_version] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_quotation_version] PRIMARY KEY,
    [quotation_id] BIGINT NOT NULL,
    [version_no] SMALLINT NOT NULL,
    [total] DECIMAL(18,2) NOT NULL,
    [change_note] NVARCHAR(500) NULL,
    [pdf_attachment_id] BIGINT NULL,
    [sent_at] DATETIME2(0) NULL,
    [sent_via] NVARCHAR(30) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_quotation_version_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_quotation_version_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_quotation_version_sent_via] CHECK ([sent_via] IN (N'Email', N'WhatsApp', N'Print'))
);
GO
-- Quotation lines (per version).
CREATE TABLE [sal].[quotation_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_quotation_line] PRIMARY KEY,
    [quotation_id] BIGINT NOT NULL,
    [version_no] SMALLINT NOT NULL,
    [line_no] SMALLINT NOT NULL,
    [item_id] BIGINT NULL,
    [machine_model_id] BIGINT NULL,
    [description] NVARCHAR(300) NOT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [uom_id] BIGINT NULL,
    [unit_price] DECIMAL(18,4) NOT NULL,
    [discount_pct] DECIMAL(5,2) NULL,
    [discount_amount] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_quotation_line_discount_amount] DEFAULT (0),
    [hsn_sac_id] BIGINT NULL,
    [gst_rate_id] BIGINT NULL,
    [taxable_value] DECIMAL(18,2) NOT NULL,
    [tax_amount] DECIMAL(18,2) NOT NULL,
    [line_total] DECIMAL(18,2) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_quotation_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_quotation_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Confirmed customer order.
CREATE TABLE [sal].[sales_order] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_sales_order] PRIMARY KEY,
    [order_no] NVARCHAR(30) NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [customer_id] BIGINT NOT NULL,
    [quotation_id] BIGINT NULL,
    [order_date] DATE NOT NULL,
    [customer_po_no] NVARCHAR(40) NULL,
    [customer_po_date] DATE NULL,
    [salesperson_employee_id] BIGINT NULL,
    [delivery_site_id] BIGINT NULL,
    [expected_delivery_date] DATE NULL,
    [payment_terms_id] BIGINT NULL,
    [finance_mode] NVARCHAR(30) NOT NULL CONSTRAINT [DF_sal_sales_order_finance_mode] DEFAULT (N'Cash'),
    [finance_application_id] BIGINT NULL,
    [subtotal] DECIMAL(18,2) NOT NULL,
    [tax_total] DECIMAL(18,2) NOT NULL,
    [total] DECIMAL(18,2) NOT NULL,
    [advance_received] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_order_advance_received] DEFAULT (0),
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_sales_order_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_sales_order_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_sales_order_finance_mode] CHECK ([finance_mode] IN (N'Cash', N'Financed')),
    CONSTRAINT [CK_sal_sales_order_status] CHECK ([status] IN (N'Draft', N'Confirmed', N'Part delivered', N'Delivered', N'Invoiced', N'Cancelled'))
);
GO
-- Order lines.
CREATE TABLE [sal].[sales_order_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_sales_order_line] PRIMARY KEY,
    [sales_order_id] BIGINT NOT NULL,
    [line_no] SMALLINT NOT NULL,
    [item_id] BIGINT NOT NULL,
    [description] NVARCHAR(300) NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [unit_price] DECIMAL(18,4) NOT NULL,
    [discount_amount] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_order_line_discount_amount] DEFAULT (0),
    [hsn_sac_id] BIGINT NULL,
    [gst_rate_id] BIGINT NULL,
    [taxable_value] DECIMAL(18,2) NOT NULL,
    [tax_amount] DECIMAL(18,2) NOT NULL,
    [line_total] DECIMAL(18,2) NOT NULL,
    [qty_delivered] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_sal_sales_order_line_qty_delivered] DEFAULT (0),
    [qty_invoiced] DECIMAL(18,3) NOT NULL CONSTRAINT [DF_sal_sales_order_line_qty_invoiced] DEFAULT (0),
    [allocated_machine_unit_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_sales_order_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_sales_order_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Old machine taken in exchange.
CREATE TABLE [sal].[exchange_machine] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_exchange_machine] PRIMARY KEY,
    [sales_order_id] BIGINT NOT NULL,
    [customer_id] BIGINT NOT NULL,
    [make] NVARCHAR(40) NOT NULL,
    [model] NVARCHAR(60) NULL,
    [serial_number] NVARCHAR(40) NULL,
    [year_of_manufacture] SMALLINT NULL,
    [hmr] DECIMAL(10,1) NULL,
    [evaluated_value] DECIMAL(18,2) NULL,
    [agreed_value] DECIMAL(18,2) NULL,
    [evaluated_by_employee_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_exchange_machine_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_exchange_machine_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_exchange_machine_status] CHECK ([status] IN (N'Evaluated', N'Agreed', N'Received', N'Cancelled'))
);
GO
-- Delivery of goods / machine.
CREATE TABLE [sal].[delivery_note] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_delivery_note] PRIMARY KEY,
    [delivery_no] NVARCHAR(30) NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [sales_order_id] BIGINT NULL,
    [customer_id] BIGINT NOT NULL,
    [delivery_date] DATE NOT NULL,
    [from_location_id] BIGINT NOT NULL,
    [delivery_site_id] BIGINT NULL,
    [vehicle_no] NVARCHAR(20) NULL,
    [transporter] NVARCHAR(100) NULL,
    [e_way_bill_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_delivery_note_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_delivery_note_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_delivery_note_status] CHECK ([status] IN (N'Draft', N'Dispatched', N'Delivered', N'Cancelled'))
);
GO
-- Delivered items.
CREATE TABLE [sal].[delivery_note_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_delivery_note_line] PRIMARY KEY,
    [delivery_note_id] BIGINT NOT NULL,
    [sales_order_line_id] BIGINT NULL,
    [item_id] BIGINT NOT NULL,
    [serial_batch_id] BIGINT NULL,
    [machine_unit_id] BIGINT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_delivery_note_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_delivery_note_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Pre-delivery inspection, installation and commissioning.
CREATE TABLE [sal].[pdi_installation] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_pdi_installation] PRIMARY KEY,
    [machine_unit_id] BIGINT NOT NULL,
    [delivery_note_id] BIGINT NULL,
    [service_call_id] BIGINT NULL,
    [record_type] NVARCHAR(30) NOT NULL,
    [done_by_employee_id] BIGINT NOT NULL,
    [done_at] DATETIME2(0) NOT NULL,
    [hmr] DECIMAL(10,1) NULL,
    [report_attachment_id] BIGINT NULL,
    [customer_signature_attachment_id] BIGINT NULL,
    [remarks] NVARCHAR(1000) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_pdi_installation_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_pdi_installation_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_pdi_installation_record_type] CHECK ([record_type] IN (N'PDI', N'Installation', N'Commissioning'))
);
GO
-- GST tax invoice to customer.
CREATE TABLE [sal].[sales_invoice] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_sales_invoice] PRIMARY KEY,
    [invoice_no] NVARCHAR(16) NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [company_id] BIGINT NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [gstin_registration_id] BIGINT NOT NULL,
    [customer_id] BIGINT NOT NULL,
    [bill_to_address] NVARCHAR(500) NULL,
    [ship_to_site_id] BIGINT NULL,
    [place_of_supply_state_id] BIGINT NOT NULL,
    [invoice_type] NVARCHAR(30) NOT NULL,
    [source_type] NVARCHAR(30) NOT NULL,
    [sales_order_id] BIGINT NULL,
    [service_call_id] BIGINT NULL,
    [delivery_note_id] BIGINT NULL,
    [invoice_date] DATE NOT NULL,
    [due_date] DATE NULL,
    [is_reverse_charge] BIT NOT NULL CONSTRAINT [DF_sal_sales_invoice_is_reverse_charge] DEFAULT (0),
    [taxable_value] DECIMAL(18,2) NOT NULL,
    [cgst] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_invoice_cgst] DEFAULT (0),
    [sgst] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_invoice_sgst] DEFAULT (0),
    [igst] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_invoice_igst] DEFAULT (0),
    [cess] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_invoice_cess] DEFAULT (0),
    [round_off] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_invoice_round_off] DEFAULT (0),
    [total] DECIMAL(18,2) NOT NULL,
    [amount_received] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_invoice_amount_received] DEFAULT (0),
    [status] NVARCHAR(30) NOT NULL,
    [e_invoice_id] BIGINT NULL,
    [journal_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_sales_invoice_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_sales_invoice_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_sales_invoice_invoice_type] CHECK ([invoice_type] IN (N'Tax invoice', N'Bill of supply', N'Export')),
    CONSTRAINT [CK_sal_sales_invoice_source_type] CHECK ([source_type] IN (N'Sales order', N'Service call', N'Counter sale', N'Contract')),
    CONSTRAINT [CK_sal_sales_invoice_status] CHECK ([status] IN (N'Draft', N'Posted', N'Part paid', N'Paid', N'Cancelled'))
);
GO
-- Invoice lines.
CREATE TABLE [sal].[sales_invoice_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_sales_invoice_line] PRIMARY KEY,
    [sales_invoice_id] BIGINT NOT NULL,
    [line_no] SMALLINT NOT NULL,
    [item_id] BIGINT NULL,
    [machine_unit_id] BIGINT NULL,
    [serial_batch_id] BIGINT NULL,
    [sales_order_line_id] BIGINT NULL,
    [service_charge_id] BIGINT NULL,
    [description] NVARCHAR(300) NOT NULL,
    [hsn_sac_id] BIGINT NOT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [uom_id] BIGINT NULL,
    [unit_price] DECIMAL(18,4) NOT NULL,
    [discount_amount] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_invoice_line_discount_amount] DEFAULT (0),
    [taxable_value] DECIMAL(18,2) NOT NULL,
    [gst_rate_id] BIGINT NOT NULL,
    [cgst_amount] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_invoice_line_cgst_amount] DEFAULT (0),
    [sgst_amount] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_invoice_line_sgst_amount] DEFAULT (0),
    [igst_amount] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_sales_invoice_line_igst_amount] DEFAULT (0),
    [line_total] DECIMAL(18,2) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_sales_invoice_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_sales_invoice_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Money received from customer, incl. advances and finance disbursement. Brand-neutral: split by brand through allocations to invoices.
CREATE TABLE [sal].[receipt] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_receipt] PRIMARY KEY,
    [receipt_no] NVARCHAR(30) NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [customer_id] BIGINT NOT NULL,
    [receipt_date] DATE NOT NULL,
    [receipt_type] NVARCHAR(30) NOT NULL,
    [payment_mode] NVARCHAR(30) NOT NULL,
    [bank_account_id] BIGINT NULL,
    [cheque_id] BIGINT NULL,
    [financer_id] BIGINT NULL,
    [reference_no] NVARCHAR(40) NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [tds_deducted] DECIMAL(18,2) NOT NULL CONSTRAINT [DF_sal_receipt_tds_deducted] DEFAULT (0),
    [status] NVARCHAR(30) NOT NULL,
    [journal_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_receipt_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_receipt_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_receipt_receipt_type] CHECK ([receipt_type] IN (N'Against invoice', N'Advance', N'Order advance')),
    CONSTRAINT [CK_sal_receipt_payment_mode] CHECK ([payment_mode] IN (N'Cash', N'Cheque', N'NEFT', N'RTGS', N'UPI', N'Finance disbursement')),
    CONSTRAINT [CK_sal_receipt_status] CHECK ([status] IN (N'Draft', N'Posted', N'Bounced', N'Cancelled'))
);
GO
-- Sales return / price adjustment.
CREATE TABLE [sal].[credit_note] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_credit_note] PRIMARY KEY,
    [credit_note_no] NVARCHAR(16) NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [customer_id] BIGINT NOT NULL,
    [sales_invoice_id] BIGINT NULL,
    [note_date] DATE NOT NULL,
    [note_type] NVARCHAR(30) NOT NULL,
    [reason_lookup_id] BIGINT NULL,
    [taxable_value] DECIMAL(18,2) NOT NULL,
    [tax_amount] DECIMAL(18,2) NOT NULL,
    [total] DECIMAL(18,2) NOT NULL,
    [e_invoice_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [journal_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_credit_note_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_credit_note_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_credit_note_note_type] CHECK ([note_type] IN (N'Sales return', N'Price adjustment', N'Discount')),
    CONSTRAINT [CK_sal_credit_note_status] CHECK ([status] IN (N'Draft', N'Posted', N'Cancelled'))
);
GO
-- Credit note lines.
CREATE TABLE [sal].[credit_note_line] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_credit_note_line] PRIMARY KEY,
    [credit_note_id] BIGINT NOT NULL,
    [sales_invoice_line_id] BIGINT NULL,
    [item_id] BIGINT NULL,
    [serial_batch_id] BIGINT NULL,
    [quantity] DECIMAL(18,3) NOT NULL,
    [unit_price] DECIMAL(18,4) NOT NULL,
    [tax_amount] DECIMAL(18,2) NOT NULL,
    [line_total] DECIMAL(18,2) NOT NULL,
    [return_location_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_credit_note_line_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_credit_note_line_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Matches receipts and credit notes to invoices.
CREATE TABLE [sal].[customer_allocation] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_customer_allocation] PRIMARY KEY,
    [sales_invoice_id] BIGINT NOT NULL,
    [receipt_id] BIGINT NULL,
    [credit_note_id] BIGINT NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [allocated_on] DATE NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_customer_allocation_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_customer_allocation_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Credit holds when limit or overdue is exceeded.
CREATE TABLE [sal].[credit_hold] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_credit_hold] PRIMARY KEY,
    [customer_id] BIGINT NOT NULL,
    [hold_at] DATETIME2(0) NOT NULL,
    [reason] NVARCHAR(30) NOT NULL,
    [outstanding_amount] DECIMAL(18,2) NULL,
    [credit_limit] DECIMAL(18,2) NULL,
    [released_by_user_id] BIGINT NULL,
    [released_at] DATETIME2(0) NULL,
    [release_remarks] NVARCHAR(300) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_credit_hold_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_credit_hold_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_credit_hold_reason] CHECK ([reason] IN (N'Over limit', N'Overdue', N'Manual'))
);
GO
-- Salesperson incentive per invoice, paid via payroll.
CREATE TABLE [sal].[sales_incentive] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_sal_sales_incentive] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [period_month] DATE NOT NULL,
    [sales_invoice_id] BIGINT NOT NULL,
    [basis_amount] DECIMAL(18,2) NOT NULL,
    [incentive_pct] DECIMAL(5,2) NULL,
    [incentive_amount] DECIMAL(18,2) NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [payroll_run_id] BIGINT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_sal_sales_incentive_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_sal_sales_incentive_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_sal_sales_incentive_status] CHECK ([status] IN (N'Calculated', N'Approved', N'Paid'))
);
GO

/* ===== acc: Accounting & GST ===== */
-- Cheques and post-dated cheques received or issued.
CREATE TABLE [acc].[cheque] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_cheque] PRIMARY KEY,
    [cheque_no] NVARCHAR(10) NOT NULL,
    [bank_name] NVARCHAR(100) NULL,
    [cheque_date] DATE NOT NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [direction] NVARCHAR(30) NOT NULL,
    [customer_id] BIGINT NULL,
    [supplier_id] BIGINT NULL,
    [bank_account_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [deposit_date] DATE NULL,
    [clearing_date] DATE NULL,
    [bounce_reason] NVARCHAR(200) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_cheque_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_cheque_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_acc_cheque_direction] CHECK ([direction] IN (N'Received', N'Issued')),
    CONSTRAINT [CK_acc_cheque_status] CHECK ([status] IN (N'PDC', N'In hand', N'Deposited', N'Cleared', N'Bounced', N'Cancelled'))
);
GO
-- IRN and QR from the GST e-invoice portal.
CREATE TABLE [acc].[e_invoice] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_e_invoice] PRIMARY KEY,
    [sales_invoice_id] BIGINT NULL,
    [credit_note_id] BIGINT NULL,
    [irn] NVARCHAR(64) NOT NULL,
    [ack_no] NVARCHAR(20) NULL,
    [ack_date] DATETIME2(0) NULL,
    [signed_qr_code] NVARCHAR(MAX) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [cancel_reason] NVARCHAR(200) NULL,
    [cancelled_at] DATETIME2(0) NULL,
    [request_json] NVARCHAR(MAX) NULL,
    [response_json] NVARCHAR(MAX) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_e_invoice_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_e_invoice_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_acc_e_invoice_status] CHECK ([status] IN (N'Generated', N'Cancelled', N'Failed'))
);
GO
-- E-way bills for invoices, deliveries and transfers.
CREATE TABLE [acc].[e_way_bill] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_acc_e_way_bill] PRIMARY KEY,
    [ewb_no] NVARCHAR(12) NOT NULL,
    [ewb_date] DATETIME2(0) NOT NULL,
    [valid_until] DATETIME2(0) NULL,
    [document_type] NVARCHAR(30) NOT NULL,
    [sales_invoice_id] BIGINT NULL,
    [delivery_note_id] BIGINT NULL,
    [stock_transfer_id] BIGINT NULL,
    [from_pincode] NVARCHAR(6) NULL,
    [to_pincode] NVARCHAR(6) NULL,
    [distance_km] SMALLINT NULL,
    [vehicle_no] NVARCHAR(20) NULL,
    [transporter_gstin] NVARCHAR(15) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_acc_e_way_bill_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_acc_e_way_bill_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_acc_e_way_bill_document_type] CHECK ([document_type] IN (N'Invoice', N'Delivery challan', N'Stock transfer')),
    CONSTRAINT [CK_acc_e_way_bill_status] CHECK ([status] IN (N'Active', N'Cancelled', N'Expired'))
);
GO

/* ---------- 2. Unique keys (12) ---------- */
CREATE UNIQUE NONCLUSTERED INDEX [UX_sal_credit_status_code] ON [sal].[credit_status] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_sal_price_list_code] ON [sal].[price_list] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_sal_price_list_item_k1] ON [sal].[price_list_item] ([price_list_id], [item_id], [min_qty]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_sal_quotation_quotation_no] ON [sal].[quotation] ([quotation_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_sal_quotation_version_k1] ON [sal].[quotation_version] ([quotation_id], [version_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_sal_sales_order_order_no] ON [sal].[sales_order] ([order_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_sal_delivery_note_delivery_no] ON [sal].[delivery_note] ([delivery_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_sal_sales_invoice_invoice_no] ON [sal].[sales_invoice] ([invoice_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_sal_receipt_receipt_no] ON [sal].[receipt] ([receipt_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_sal_credit_note_credit_note_no] ON [sal].[credit_note] ([credit_note_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_acc_e_invoice_irn] ON [acc].[e_invoice] ([irn]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_acc_e_way_bill_ewb_no] ON [acc].[e_way_bill] ([ewb_no]);
GO

/* ---------- 3. Foreign keys (113) ----------
   Includes links from earlier-phase columns to tables created in this phase. */
ALTER TABLE [core].[customer] ADD CONSTRAINT [FK_core_customer_credit_status_id] FOREIGN KEY ([credit_status_id]) REFERENCES [sal].[credit_status] ([id]) ON DELETE NO ACTION;
ALTER TABLE [core].[machine_unit] ADD CONSTRAINT [FK_core_machine_unit_sale_invoice_id] FOREIGN KEY ([sale_invoice_id]) REFERENCES [sal].[sales_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_contract] ADD CONSTRAINT [FK_svc_service_contract_sales_invoice_id] FOREIGN KEY ([sales_invoice_id]) REFERENCES [sal].[sales_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [svc].[service_charge] ADD CONSTRAINT [FK_svc_service_charge_sales_invoice_id] FOREIGN KEY ([sales_invoice_id]) REFERENCES [sal].[sales_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_reservation] ADD CONSTRAINT [FK_inv_stock_reservation_sales_order_id] FOREIGN KEY ([sales_order_id]) REFERENCES [sal].[sales_order] ([id]) ON DELETE NO ACTION;
ALTER TABLE [inv].[stock_transfer] ADD CONSTRAINT [FK_inv_stock_transfer_e_way_bill_id] FOREIGN KEY ([e_way_bill_id]) REFERENCES [acc].[e_way_bill] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pur].[supplier_payment] ADD CONSTRAINT [FK_pur_supplier_payment_cheque_id] FOREIGN KEY ([cheque_id]) REFERENCES [acc].[cheque] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[price_list] ADD CONSTRAINT [FK_sal_price_list_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[price_list] ADD CONSTRAINT [FK_sal_price_list_currency_id] FOREIGN KEY ([currency_id]) REFERENCES [core].[currency] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[price_list_item] ADD CONSTRAINT [FK_sal_price_list_item_price_list_id] FOREIGN KEY ([price_list_id]) REFERENCES [sal].[price_list] ([id]) ON DELETE CASCADE;
ALTER TABLE [sal].[price_list_item] ADD CONSTRAINT [FK_sal_price_list_item_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_contact_id] FOREIGN KEY ([contact_id]) REFERENCES [core].[contact] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_salesperson_employee_id] FOREIGN KEY ([salesperson_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_price_list_id] FOREIGN KEY ([price_list_id]) REFERENCES [sal].[price_list] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_place_of_supply_state_id] FOREIGN KEY ([place_of_supply_state_id]) REFERENCES [core].[state] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation_version] ADD CONSTRAINT [FK_sal_quotation_version_quotation_id] FOREIGN KEY ([quotation_id]) REFERENCES [sal].[quotation] ([id]) ON DELETE CASCADE;
ALTER TABLE [sal].[quotation_version] ADD CONSTRAINT [FK_sal_quotation_version_pdf_attachment_id] FOREIGN KEY ([pdf_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation_line] ADD CONSTRAINT [FK_sal_quotation_line_quotation_id] FOREIGN KEY ([quotation_id]) REFERENCES [sal].[quotation] ([id]) ON DELETE CASCADE;
ALTER TABLE [sal].[quotation_line] ADD CONSTRAINT [FK_sal_quotation_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation_line] ADD CONSTRAINT [FK_sal_quotation_line_machine_model_id] FOREIGN KEY ([machine_model_id]) REFERENCES [core].[machine_model] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation_line] ADD CONSTRAINT [FK_sal_quotation_line_uom_id] FOREIGN KEY ([uom_id]) REFERENCES [core].[uom] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation_line] ADD CONSTRAINT [FK_sal_quotation_line_hsn_sac_id] FOREIGN KEY ([hsn_sac_id]) REFERENCES [core].[hsn_sac] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[quotation_line] ADD CONSTRAINT [FK_sal_quotation_line_gst_rate_id] FOREIGN KEY ([gst_rate_id]) REFERENCES [acc].[gst_rate] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_quotation_id] FOREIGN KEY ([quotation_id]) REFERENCES [sal].[quotation] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_salesperson_employee_id] FOREIGN KEY ([salesperson_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_delivery_site_id] FOREIGN KEY ([delivery_site_id]) REFERENCES [core].[customer_site] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_payment_terms_id] FOREIGN KEY ([payment_terms_id]) REFERENCES [core].[payment_terms] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order_line] ADD CONSTRAINT [FK_sal_sales_order_line_sales_order_id] FOREIGN KEY ([sales_order_id]) REFERENCES [sal].[sales_order] ([id]) ON DELETE CASCADE;
ALTER TABLE [sal].[sales_order_line] ADD CONSTRAINT [FK_sal_sales_order_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order_line] ADD CONSTRAINT [FK_sal_sales_order_line_hsn_sac_id] FOREIGN KEY ([hsn_sac_id]) REFERENCES [core].[hsn_sac] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order_line] ADD CONSTRAINT [FK_sal_sales_order_line_gst_rate_id] FOREIGN KEY ([gst_rate_id]) REFERENCES [acc].[gst_rate] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_order_line] ADD CONSTRAINT [FK_sal_sales_order_line_allocated_machine_unit_id] FOREIGN KEY ([allocated_machine_unit_id]) REFERENCES [core].[machine_unit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[exchange_machine] ADD CONSTRAINT [FK_sal_exchange_machine_sales_order_id] FOREIGN KEY ([sales_order_id]) REFERENCES [sal].[sales_order] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[exchange_machine] ADD CONSTRAINT [FK_sal_exchange_machine_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[exchange_machine] ADD CONSTRAINT [FK_sal_exchange_machine_evaluated_by_employee_id] FOREIGN KEY ([evaluated_by_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note] ADD CONSTRAINT [FK_sal_delivery_note_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note] ADD CONSTRAINT [FK_sal_delivery_note_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note] ADD CONSTRAINT [FK_sal_delivery_note_sales_order_id] FOREIGN KEY ([sales_order_id]) REFERENCES [sal].[sales_order] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note] ADD CONSTRAINT [FK_sal_delivery_note_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note] ADD CONSTRAINT [FK_sal_delivery_note_from_location_id] FOREIGN KEY ([from_location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note] ADD CONSTRAINT [FK_sal_delivery_note_delivery_site_id] FOREIGN KEY ([delivery_site_id]) REFERENCES [core].[customer_site] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note] ADD CONSTRAINT [FK_sal_delivery_note_e_way_bill_id] FOREIGN KEY ([e_way_bill_id]) REFERENCES [acc].[e_way_bill] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note_line] ADD CONSTRAINT [FK_sal_delivery_note_line_delivery_note_id] FOREIGN KEY ([delivery_note_id]) REFERENCES [sal].[delivery_note] ([id]) ON DELETE CASCADE;
ALTER TABLE [sal].[delivery_note_line] ADD CONSTRAINT [FK_sal_delivery_note_line_sales_order_line_id] FOREIGN KEY ([sales_order_line_id]) REFERENCES [sal].[sales_order_line] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note_line] ADD CONSTRAINT [FK_sal_delivery_note_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note_line] ADD CONSTRAINT [FK_sal_delivery_note_line_serial_batch_id] FOREIGN KEY ([serial_batch_id]) REFERENCES [inv].[serial_batch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[delivery_note_line] ADD CONSTRAINT [FK_sal_delivery_note_line_machine_unit_id] FOREIGN KEY ([machine_unit_id]) REFERENCES [core].[machine_unit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[pdi_installation] ADD CONSTRAINT [FK_sal_pdi_installation_machine_unit_id] FOREIGN KEY ([machine_unit_id]) REFERENCES [core].[machine_unit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[pdi_installation] ADD CONSTRAINT [FK_sal_pdi_installation_delivery_note_id] FOREIGN KEY ([delivery_note_id]) REFERENCES [sal].[delivery_note] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[pdi_installation] ADD CONSTRAINT [FK_sal_pdi_installation_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[pdi_installation] ADD CONSTRAINT [FK_sal_pdi_installation_done_by_employee_id] FOREIGN KEY ([done_by_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[pdi_installation] ADD CONSTRAINT [FK_sal_pdi_installation_report_attachment_id] FOREIGN KEY ([report_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[pdi_installation] ADD CONSTRAINT [FK_sal_pdi_installation_customer_signature_attachment_id] FOREIGN KEY ([customer_signature_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_company_id] FOREIGN KEY ([company_id]) REFERENCES [core].[company] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_gstin_registration_id] FOREIGN KEY ([gstin_registration_id]) REFERENCES [acc].[gstin_registration] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_ship_to_site_id] FOREIGN KEY ([ship_to_site_id]) REFERENCES [core].[customer_site] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_place_of_supply_state_id] FOREIGN KEY ([place_of_supply_state_id]) REFERENCES [core].[state] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_sales_order_id] FOREIGN KEY ([sales_order_id]) REFERENCES [sal].[sales_order] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_service_call_id] FOREIGN KEY ([service_call_id]) REFERENCES [svc].[service_call] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_delivery_note_id] FOREIGN KEY ([delivery_note_id]) REFERENCES [sal].[delivery_note] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_e_invoice_id] FOREIGN KEY ([e_invoice_id]) REFERENCES [acc].[e_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice] ADD CONSTRAINT [FK_sal_sales_invoice_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice_line] ADD CONSTRAINT [FK_sal_sales_invoice_line_sales_invoice_id] FOREIGN KEY ([sales_invoice_id]) REFERENCES [sal].[sales_invoice] ([id]) ON DELETE CASCADE;
ALTER TABLE [sal].[sales_invoice_line] ADD CONSTRAINT [FK_sal_sales_invoice_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice_line] ADD CONSTRAINT [FK_sal_sales_invoice_line_machine_unit_id] FOREIGN KEY ([machine_unit_id]) REFERENCES [core].[machine_unit] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice_line] ADD CONSTRAINT [FK_sal_sales_invoice_line_serial_batch_id] FOREIGN KEY ([serial_batch_id]) REFERENCES [inv].[serial_batch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice_line] ADD CONSTRAINT [FK_sal_sales_invoice_line_sales_order_line_id] FOREIGN KEY ([sales_order_line_id]) REFERENCES [sal].[sales_order_line] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice_line] ADD CONSTRAINT [FK_sal_sales_invoice_line_service_charge_id] FOREIGN KEY ([service_charge_id]) REFERENCES [svc].[service_charge] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice_line] ADD CONSTRAINT [FK_sal_sales_invoice_line_hsn_sac_id] FOREIGN KEY ([hsn_sac_id]) REFERENCES [core].[hsn_sac] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice_line] ADD CONSTRAINT [FK_sal_sales_invoice_line_uom_id] FOREIGN KEY ([uom_id]) REFERENCES [core].[uom] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_invoice_line] ADD CONSTRAINT [FK_sal_sales_invoice_line_gst_rate_id] FOREIGN KEY ([gst_rate_id]) REFERENCES [acc].[gst_rate] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[receipt] ADD CONSTRAINT [FK_sal_receipt_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[receipt] ADD CONSTRAINT [FK_sal_receipt_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[receipt] ADD CONSTRAINT [FK_sal_receipt_bank_account_id] FOREIGN KEY ([bank_account_id]) REFERENCES [acc].[bank_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[receipt] ADD CONSTRAINT [FK_sal_receipt_cheque_id] FOREIGN KEY ([cheque_id]) REFERENCES [acc].[cheque] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[receipt] ADD CONSTRAINT [FK_sal_receipt_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_note] ADD CONSTRAINT [FK_sal_credit_note_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_note] ADD CONSTRAINT [FK_sal_credit_note_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_note] ADD CONSTRAINT [FK_sal_credit_note_sales_invoice_id] FOREIGN KEY ([sales_invoice_id]) REFERENCES [sal].[sales_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_note] ADD CONSTRAINT [FK_sal_credit_note_reason_lookup_id] FOREIGN KEY ([reason_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_note] ADD CONSTRAINT [FK_sal_credit_note_e_invoice_id] FOREIGN KEY ([e_invoice_id]) REFERENCES [acc].[e_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_note] ADD CONSTRAINT [FK_sal_credit_note_journal_id] FOREIGN KEY ([journal_id]) REFERENCES [acc].[journal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_note_line] ADD CONSTRAINT [FK_sal_credit_note_line_credit_note_id] FOREIGN KEY ([credit_note_id]) REFERENCES [sal].[credit_note] ([id]) ON DELETE CASCADE;
ALTER TABLE [sal].[credit_note_line] ADD CONSTRAINT [FK_sal_credit_note_line_sales_invoice_line_id] FOREIGN KEY ([sales_invoice_line_id]) REFERENCES [sal].[sales_invoice_line] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_note_line] ADD CONSTRAINT [FK_sal_credit_note_line_item_id] FOREIGN KEY ([item_id]) REFERENCES [core].[item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_note_line] ADD CONSTRAINT [FK_sal_credit_note_line_serial_batch_id] FOREIGN KEY ([serial_batch_id]) REFERENCES [inv].[serial_batch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_note_line] ADD CONSTRAINT [FK_sal_credit_note_line_return_location_id] FOREIGN KEY ([return_location_id]) REFERENCES [core].[location] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[customer_allocation] ADD CONSTRAINT [FK_sal_customer_allocation_sales_invoice_id] FOREIGN KEY ([sales_invoice_id]) REFERENCES [sal].[sales_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[customer_allocation] ADD CONSTRAINT [FK_sal_customer_allocation_receipt_id] FOREIGN KEY ([receipt_id]) REFERENCES [sal].[receipt] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[customer_allocation] ADD CONSTRAINT [FK_sal_customer_allocation_credit_note_id] FOREIGN KEY ([credit_note_id]) REFERENCES [sal].[credit_note] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_hold] ADD CONSTRAINT [FK_sal_credit_hold_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[credit_hold] ADD CONSTRAINT [FK_sal_credit_hold_released_by_user_id] FOREIGN KEY ([released_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_incentive] ADD CONSTRAINT [FK_sal_sales_incentive_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_incentive] ADD CONSTRAINT [FK_sal_sales_incentive_sales_invoice_id] FOREIGN KEY ([sales_invoice_id]) REFERENCES [sal].[sales_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[sales_incentive] ADD CONSTRAINT [FK_sal_sales_incentive_payroll_run_id] FOREIGN KEY ([payroll_run_id]) REFERENCES [hr].[payroll_run] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[cheque] ADD CONSTRAINT [FK_acc_cheque_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[cheque] ADD CONSTRAINT [FK_acc_cheque_supplier_id] FOREIGN KEY ([supplier_id]) REFERENCES [core].[supplier] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[cheque] ADD CONSTRAINT [FK_acc_cheque_bank_account_id] FOREIGN KEY ([bank_account_id]) REFERENCES [acc].[bank_account] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[e_invoice] ADD CONSTRAINT [FK_acc_e_invoice_sales_invoice_id] FOREIGN KEY ([sales_invoice_id]) REFERENCES [sal].[sales_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[e_invoice] ADD CONSTRAINT [FK_acc_e_invoice_credit_note_id] FOREIGN KEY ([credit_note_id]) REFERENCES [sal].[credit_note] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[e_way_bill] ADD CONSTRAINT [FK_acc_e_way_bill_sales_invoice_id] FOREIGN KEY ([sales_invoice_id]) REFERENCES [sal].[sales_invoice] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[e_way_bill] ADD CONSTRAINT [FK_acc_e_way_bill_delivery_note_id] FOREIGN KEY ([delivery_note_id]) REFERENCES [sal].[delivery_note] ([id]) ON DELETE NO ACTION;
ALTER TABLE [acc].[e_way_bill] ADD CONSTRAINT [FK_acc_e_way_bill_stock_transfer_id] FOREIGN KEY ([stock_transfer_id]) REFERENCES [inv].[stock_transfer] ([id]) ON DELETE NO ACTION;
GO

/* ---------- 4. Foreign-key indexes (113) ---------- */
CREATE NONCLUSTERED INDEX [IX_core_customer_credit_status_id] ON [core].[customer] ([credit_status_id]);
CREATE NONCLUSTERED INDEX [IX_core_machine_unit_sale_invoice_id] ON [core].[machine_unit] ([sale_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_contract_sales_invoice_id] ON [svc].[service_contract] ([sales_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_svc_service_charge_sales_invoice_id] ON [svc].[service_charge] ([sales_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_reservation_sales_order_id] ON [inv].[stock_reservation] ([sales_order_id]);
CREATE NONCLUSTERED INDEX [IX_inv_stock_transfer_e_way_bill_id] ON [inv].[stock_transfer] ([e_way_bill_id]);
CREATE NONCLUSTERED INDEX [IX_pur_supplier_payment_cheque_id] ON [pur].[supplier_payment] ([cheque_id]);
CREATE NONCLUSTERED INDEX [IX_sal_price_list_principal_id] ON [sal].[price_list] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_sal_price_list_currency_id] ON [sal].[price_list] ([currency_id]);
CREATE NONCLUSTERED INDEX [IX_sal_price_list_item_price_list_id] ON [sal].[price_list_item] ([price_list_id]);
CREATE NONCLUSTERED INDEX [IX_sal_price_list_item_item_id] ON [sal].[price_list_item] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_principal_id] ON [sal].[quotation] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_branch_id] ON [sal].[quotation] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_customer_id] ON [sal].[quotation] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_contact_id] ON [sal].[quotation] ([contact_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_service_call_id] ON [sal].[quotation] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_salesperson_employee_id] ON [sal].[quotation] ([salesperson_employee_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_price_list_id] ON [sal].[quotation] ([price_list_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_place_of_supply_state_id] ON [sal].[quotation] ([place_of_supply_state_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_version_quotation_id] ON [sal].[quotation_version] ([quotation_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_version_pdf_attachment_id] ON [sal].[quotation_version] ([pdf_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_line_quotation_id] ON [sal].[quotation_line] ([quotation_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_line_item_id] ON [sal].[quotation_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_line_machine_model_id] ON [sal].[quotation_line] ([machine_model_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_line_uom_id] ON [sal].[quotation_line] ([uom_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_line_hsn_sac_id] ON [sal].[quotation_line] ([hsn_sac_id]);
CREATE NONCLUSTERED INDEX [IX_sal_quotation_line_gst_rate_id] ON [sal].[quotation_line] ([gst_rate_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_principal_id] ON [sal].[sales_order] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_branch_id] ON [sal].[sales_order] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_customer_id] ON [sal].[sales_order] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_quotation_id] ON [sal].[sales_order] ([quotation_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_salesperson_employee_id] ON [sal].[sales_order] ([salesperson_employee_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_delivery_site_id] ON [sal].[sales_order] ([delivery_site_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_payment_terms_id] ON [sal].[sales_order] ([payment_terms_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_line_sales_order_id] ON [sal].[sales_order_line] ([sales_order_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_line_item_id] ON [sal].[sales_order_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_line_hsn_sac_id] ON [sal].[sales_order_line] ([hsn_sac_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_line_gst_rate_id] ON [sal].[sales_order_line] ([gst_rate_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_line_allocated_machine_unit_id] ON [sal].[sales_order_line] ([allocated_machine_unit_id]);
CREATE NONCLUSTERED INDEX [IX_sal_exchange_machine_sales_order_id] ON [sal].[exchange_machine] ([sales_order_id]);
CREATE NONCLUSTERED INDEX [IX_sal_exchange_machine_customer_id] ON [sal].[exchange_machine] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_sal_exchange_machine_evaluated_by_employee_id] ON [sal].[exchange_machine] ([evaluated_by_employee_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_principal_id] ON [sal].[delivery_note] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_branch_id] ON [sal].[delivery_note] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_sales_order_id] ON [sal].[delivery_note] ([sales_order_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_customer_id] ON [sal].[delivery_note] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_from_location_id] ON [sal].[delivery_note] ([from_location_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_delivery_site_id] ON [sal].[delivery_note] ([delivery_site_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_e_way_bill_id] ON [sal].[delivery_note] ([e_way_bill_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_line_delivery_note_id] ON [sal].[delivery_note_line] ([delivery_note_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_line_sales_order_line_id] ON [sal].[delivery_note_line] ([sales_order_line_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_line_item_id] ON [sal].[delivery_note_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_line_serial_batch_id] ON [sal].[delivery_note_line] ([serial_batch_id]);
CREATE NONCLUSTERED INDEX [IX_sal_delivery_note_line_machine_unit_id] ON [sal].[delivery_note_line] ([machine_unit_id]);
CREATE NONCLUSTERED INDEX [IX_sal_pdi_installation_machine_unit_id] ON [sal].[pdi_installation] ([machine_unit_id]);
CREATE NONCLUSTERED INDEX [IX_sal_pdi_installation_delivery_note_id] ON [sal].[pdi_installation] ([delivery_note_id]);
CREATE NONCLUSTERED INDEX [IX_sal_pdi_installation_service_call_id] ON [sal].[pdi_installation] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_sal_pdi_installation_done_by_employee_id] ON [sal].[pdi_installation] ([done_by_employee_id]);
CREATE NONCLUSTERED INDEX [IX_sal_pdi_installation_report_attachment_id] ON [sal].[pdi_installation] ([report_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_sal_pdi_installation_customer_signature_attachment_id] ON [sal].[pdi_installation] ([customer_signature_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_principal_id] ON [sal].[sales_invoice] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_company_id] ON [sal].[sales_invoice] ([company_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_branch_id] ON [sal].[sales_invoice] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_gstin_registration_id] ON [sal].[sales_invoice] ([gstin_registration_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_customer_id] ON [sal].[sales_invoice] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_ship_to_site_id] ON [sal].[sales_invoice] ([ship_to_site_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_place_of_supply_state_id] ON [sal].[sales_invoice] ([place_of_supply_state_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_sales_order_id] ON [sal].[sales_invoice] ([sales_order_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_service_call_id] ON [sal].[sales_invoice] ([service_call_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_delivery_note_id] ON [sal].[sales_invoice] ([delivery_note_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_e_invoice_id] ON [sal].[sales_invoice] ([e_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_journal_id] ON [sal].[sales_invoice] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_line_sales_invoice_id] ON [sal].[sales_invoice_line] ([sales_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_line_item_id] ON [sal].[sales_invoice_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_line_machine_unit_id] ON [sal].[sales_invoice_line] ([machine_unit_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_line_serial_batch_id] ON [sal].[sales_invoice_line] ([serial_batch_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_line_sales_order_line_id] ON [sal].[sales_invoice_line] ([sales_order_line_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_line_service_charge_id] ON [sal].[sales_invoice_line] ([service_charge_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_line_hsn_sac_id] ON [sal].[sales_invoice_line] ([hsn_sac_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_line_uom_id] ON [sal].[sales_invoice_line] ([uom_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_line_gst_rate_id] ON [sal].[sales_invoice_line] ([gst_rate_id]);
CREATE NONCLUSTERED INDEX [IX_sal_receipt_branch_id] ON [sal].[receipt] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_sal_receipt_customer_id] ON [sal].[receipt] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_sal_receipt_bank_account_id] ON [sal].[receipt] ([bank_account_id]);
CREATE NONCLUSTERED INDEX [IX_sal_receipt_cheque_id] ON [sal].[receipt] ([cheque_id]);
CREATE NONCLUSTERED INDEX [IX_sal_receipt_journal_id] ON [sal].[receipt] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_principal_id] ON [sal].[credit_note] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_customer_id] ON [sal].[credit_note] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_sales_invoice_id] ON [sal].[credit_note] ([sales_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_reason_lookup_id] ON [sal].[credit_note] ([reason_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_e_invoice_id] ON [sal].[credit_note] ([e_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_journal_id] ON [sal].[credit_note] ([journal_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_line_credit_note_id] ON [sal].[credit_note_line] ([credit_note_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_line_sales_invoice_line_id] ON [sal].[credit_note_line] ([sales_invoice_line_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_line_item_id] ON [sal].[credit_note_line] ([item_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_line_serial_batch_id] ON [sal].[credit_note_line] ([serial_batch_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_note_line_return_location_id] ON [sal].[credit_note_line] ([return_location_id]);
CREATE NONCLUSTERED INDEX [IX_sal_customer_allocation_sales_invoice_id] ON [sal].[customer_allocation] ([sales_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_sal_customer_allocation_receipt_id] ON [sal].[customer_allocation] ([receipt_id]);
CREATE NONCLUSTERED INDEX [IX_sal_customer_allocation_credit_note_id] ON [sal].[customer_allocation] ([credit_note_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_hold_customer_id] ON [sal].[credit_hold] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_sal_credit_hold_released_by_user_id] ON [sal].[credit_hold] ([released_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_incentive_employee_id] ON [sal].[sales_incentive] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_incentive_sales_invoice_id] ON [sal].[sales_incentive] ([sales_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_sal_sales_incentive_payroll_run_id] ON [sal].[sales_incentive] ([payroll_run_id]);
CREATE NONCLUSTERED INDEX [IX_acc_cheque_customer_id] ON [acc].[cheque] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_acc_cheque_supplier_id] ON [acc].[cheque] ([supplier_id]);
CREATE NONCLUSTERED INDEX [IX_acc_cheque_bank_account_id] ON [acc].[cheque] ([bank_account_id]);
CREATE NONCLUSTERED INDEX [IX_acc_e_invoice_sales_invoice_id] ON [acc].[e_invoice] ([sales_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_acc_e_invoice_credit_note_id] ON [acc].[e_invoice] ([credit_note_id]);
CREATE NONCLUSTERED INDEX [IX_acc_e_way_bill_sales_invoice_id] ON [acc].[e_way_bill] ([sales_invoice_id]);
CREATE NONCLUSTERED INDEX [IX_acc_e_way_bill_delivery_note_id] ON [acc].[e_way_bill] ([delivery_note_id]);
CREATE NONCLUSTERED INDEX [IX_acc_e_way_bill_stock_transfer_id] ON [acc].[e_way_bill] ([stock_transfer_id]);
GO

/* =====================================================================
   TRISHUL Integrated System - SQL Server DDL (dictionary v2)
   Phase 5 - Pre-Sales core
   Generated from the TRISHUL Database Dictionary. Do not edit by hand:
   change the dictionary and regenerate.
   Target: SQL Server 2019+ / Amazon RDS for SQL Server
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
/* ---------- 1. Tables (9) ---------- */

/* ===== pre: Pre-Sales ===== */
-- Where leads come from.
CREATE TABLE [pre].[lead_source] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_lead_source] PRIMARY KEY,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(80) NOT NULL,
    [source_type] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_lead_source_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_lead_source_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pre_lead_source_source_type] CHECK ([source_type] IN (N'Referral', N'Walk in', N'Campaign', N'Service engineer', N'TATA HITACHI', N'Website', N'Old customer', N'Other'))
);
GO
-- Expos, demos, melas, digital campaigns.
CREATE TABLE [pre].[campaign] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_campaign] PRIMARY KEY,
    [name] NVARCHAR(120) NOT NULL,
    [campaign_type] NVARCHAR(30) NOT NULL,
    [branch_id] BIGINT NULL,
    [start_date] DATE NULL,
    [end_date] DATE NULL,
    [budget] DECIMAL(18,2) NULL,
    [notes] NVARCHAR(500) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_campaign_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_campaign_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pre_campaign_campaign_type] CHECK ([campaign_type] IN (N'Expo', N'Demo', N'Mela', N'Digital', N'Other'))
);
GO
-- Competitor brands.
CREATE TABLE [pre].[competitor] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_competitor] PRIMARY KEY,
    [name] NVARCHAR(80) NOT NULL,
    [notes] NVARCHAR(300) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_competitor_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_competitor_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Enquiry / referral before qualification.
CREATE TABLE [pre].[lead] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_lead] PRIMARY KEY,
    [lead_no] NVARCHAR(30) NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [client_uuid] UNIQUEIDENTIFIER NULL,
    [principal_id] BIGINT NULL,
    [lead_source_id] BIGINT NOT NULL,
    [campaign_id] BIGINT NULL,
    [referred_by_customer_id] BIGINT NULL,
    [referred_by_employee_id] BIGINT NULL,
    [prospect_name] NVARCHAR(120) NOT NULL,
    [company_name] NVARCHAR(200) NULL,
    [phone] NVARCHAR(15) NOT NULL,
    [alternate_phone] NVARCHAR(15) NULL,
    [email] NVARCHAR(120) NULL,
    [district_id] BIGINT NULL,
    [pincode_id] BIGINT NULL,
    [interested_model_id] BIGINT NULL,
    [quantity] SMALLINT NULL,
    [application_lookup_id] BIGINT NULL,
    [expected_purchase_month] DATE NULL,
    [assigned_to_employee_id] BIGINT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [lost_reason_lookup_id] BIGINT NULL,
    [converted_customer_id] BIGINT NULL,
    [captured_latitude] DECIMAL(9,6) NULL,
    [captured_longitude] DECIMAL(9,6) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_lead_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_lead_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pre_lead_status] CHECK ([status] IN (N'New', N'Contacted', N'Qualified', N'Converted', N'Lost'))
);
GO
-- Qualified deal moving through the SOP stages.
CREATE TABLE [pre].[opportunity] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_opportunity] PRIMARY KEY,
    [opportunity_no] NVARCHAR(30) NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [lead_id] BIGINT NULL,
    [customer_id] BIGINT NOT NULL,
    [contact_id] BIGINT NULL,
    [machine_model_id] BIGINT NULL,
    [quantity] SMALLINT NOT NULL CONSTRAINT [DF_pre_opportunity_quantity] DEFAULT (1),
    [estimated_value] DECIMAL(18,2) NULL,
    [probability_pct] DECIMAL(5,2) NULL,
    [expected_close_date] DATE NULL,
    [salesperson_employee_id] BIGINT NOT NULL,
    [current_sop_stage_id] BIGINT NULL,
    [stage_entered_at] DATETIME2(0) NULL,
    [finance_mode] NVARCHAR(30) NULL,
    [is_exchange_offered] BIT NOT NULL CONSTRAINT [DF_pre_opportunity_is_exchange_offered] DEFAULT (0),
    [competitor_id] BIGINT NULL,
    [competitor_price] DECIMAL(18,2) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [won_sales_order_id] BIGINT NULL,
    [lost_reason_lookup_id] BIGINT NULL,
    [lost_to_competitor_id] BIGINT NULL,
    [closed_at] DATETIME2(0) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_opportunity_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_opportunity_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pre_opportunity_finance_mode] CHECK ([finance_mode] IN (N'Cash', N'Financed')),
    CONSTRAINT [CK_pre_opportunity_status] CHECK ([status] IN (N'Open', N'Won', N'Lost', N'On hold'))
);
GO
-- Stage changes for pipeline ageing.
CREATE TABLE [pre].[opportunity_stage_log] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_opportunity_stage_log] PRIMARY KEY,
    [opportunity_id] BIGINT NOT NULL,
    [from_stage_id] BIGINT NULL,
    [to_stage_id] BIGINT NOT NULL,
    [changed_at] DATETIME2(0) NOT NULL,
    [changed_by_user_id] BIGINT NULL,
    [days_in_previous_stage] SMALLINT NULL,
    [remarks] NVARCHAR(300) NULL
);
GO
-- Calls, visits, demos, meetings by salespeople.
CREATE TABLE [pre].[sales_activity] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_sales_activity] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [client_uuid] UNIQUEIDENTIFIER NULL,
    [lead_id] BIGINT NULL,
    [opportunity_id] BIGINT NULL,
    [customer_id] BIGINT NULL,
    [activity_type] NVARCHAR(30) NOT NULL,
    [planned_at] DATETIME2(0) NULL,
    [started_at] DATETIME2(0) NULL,
    [ended_at] DATETIME2(0) NULL,
    [outcome_lookup_id] BIGINT NULL,
    [notes] NVARCHAR(1000) NULL,
    [next_follow_up_at] DATETIME2(0) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_sales_activity_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_sales_activity_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pre_sales_activity_activity_type] CHECK ([activity_type] IN (N'Call', N'Visit', N'Demo', N'Meeting', N'WhatsApp', N'Email'))
);
GO
-- Live-location check-in/out to verify visits.
CREATE TABLE [pre].[location_check] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_location_check] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [sales_activity_id] BIGINT NULL,
    [check_type] NVARCHAR(30) NOT NULL,
    [captured_at] DATETIME2(0) NOT NULL,
    [latitude] DECIMAL(9,6) NOT NULL,
    [longitude] DECIMAL(9,6) NOT NULL,
    [accuracy_m] DECIMAL(6,1) NULL,
    [target_latitude] DECIMAL(9,6) NULL,
    [target_longitude] DECIMAL(9,6) NULL,
    [distance_from_target_m] INT NULL,
    [is_within_geofence] BIT NULL,
    [is_mock_location] BIT NOT NULL CONSTRAINT [DF_pre_location_check_is_mock_location] DEFAULT (0),
    [photo_attachment_id] BIGINT NULL,
    CONSTRAINT [CK_pre_location_check_check_type] CHECK ([check_type] IN (N'Check in', N'Check out'))
);
GO
-- WhatsApp messages with leads and customers.
CREATE TABLE [pre].[whatsapp_log] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_whatsapp_log] PRIMARY KEY,
    [direction] NVARCHAR(30) NOT NULL,
    [phone] NVARCHAR(15) NOT NULL,
    [customer_id] BIGINT NULL,
    [lead_id] BIGINT NULL,
    [opportunity_id] BIGINT NULL,
    [employee_id] BIGINT NULL,
    [template_name] NVARCHAR(100) NULL,
    [message_text] NVARCHAR(4000) NULL,
    [media_attachment_id] BIGINT NULL,
    [provider_message_id] NVARCHAR(100) NULL,
    [status] NVARCHAR(30) NOT NULL,
    [sent_at] DATETIME2(0) NULL,
    [read_at] DATETIME2(0) NULL,
    CONSTRAINT [CK_pre_whatsapp_log_direction] CHECK ([direction] IN (N'Outbound', N'Inbound')),
    CONSTRAINT [CK_pre_whatsapp_log_status] CHECK ([status] IN (N'Sent', N'Delivered', N'Read', N'Failed', N'Received'))
);
GO

/* ---------- 2. Unique keys (6) ---------- */
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_lead_source_code] ON [pre].[lead_source] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_competitor_name] ON [pre].[competitor] ([name]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_lead_lead_no] ON [pre].[lead] ([lead_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_lead_client_uuid] ON [pre].[lead] ([client_uuid]) WHERE [client_uuid] IS NOT NULL;
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_opportunity_opportunity_no] ON [pre].[opportunity] ([opportunity_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_sales_activity_client_uuid] ON [pre].[sales_activity] ([client_uuid]) WHERE [client_uuid] IS NOT NULL;
GO

/* ---------- 3. Foreign keys (41) ----------
   Includes links from earlier-phase columns to tables created in this phase. */
ALTER TABLE [sal].[quotation] ADD CONSTRAINT [FK_sal_quotation_opportunity_id] FOREIGN KEY ([opportunity_id]) REFERENCES [pre].[opportunity] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[campaign] ADD CONSTRAINT [FK_pre_campaign_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_lead_source_id] FOREIGN KEY ([lead_source_id]) REFERENCES [pre].[lead_source] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_campaign_id] FOREIGN KEY ([campaign_id]) REFERENCES [pre].[campaign] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_referred_by_customer_id] FOREIGN KEY ([referred_by_customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_referred_by_employee_id] FOREIGN KEY ([referred_by_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_district_id] FOREIGN KEY ([district_id]) REFERENCES [core].[district] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_pincode_id] FOREIGN KEY ([pincode_id]) REFERENCES [core].[pincode] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_interested_model_id] FOREIGN KEY ([interested_model_id]) REFERENCES [core].[machine_model] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_application_lookup_id] FOREIGN KEY ([application_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_assigned_to_employee_id] FOREIGN KEY ([assigned_to_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_lost_reason_lookup_id] FOREIGN KEY ([lost_reason_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[lead] ADD CONSTRAINT [FK_pre_lead_converted_customer_id] FOREIGN KEY ([converted_customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_lead_id] FOREIGN KEY ([lead_id]) REFERENCES [pre].[lead] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_contact_id] FOREIGN KEY ([contact_id]) REFERENCES [core].[contact] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_machine_model_id] FOREIGN KEY ([machine_model_id]) REFERENCES [core].[machine_model] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_salesperson_employee_id] FOREIGN KEY ([salesperson_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_competitor_id] FOREIGN KEY ([competitor_id]) REFERENCES [pre].[competitor] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_won_sales_order_id] FOREIGN KEY ([won_sales_order_id]) REFERENCES [sal].[sales_order] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_lost_reason_lookup_id] FOREIGN KEY ([lost_reason_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_lost_to_competitor_id] FOREIGN KEY ([lost_to_competitor_id]) REFERENCES [pre].[competitor] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity_stage_log] ADD CONSTRAINT [FK_pre_opportunity_stage_log_opportunity_id] FOREIGN KEY ([opportunity_id]) REFERENCES [pre].[opportunity] ([id]) ON DELETE CASCADE;
ALTER TABLE [pre].[opportunity_stage_log] ADD CONSTRAINT [FK_pre_opportunity_stage_log_changed_by_user_id] FOREIGN KEY ([changed_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sales_activity] ADD CONSTRAINT [FK_pre_sales_activity_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sales_activity] ADD CONSTRAINT [FK_pre_sales_activity_lead_id] FOREIGN KEY ([lead_id]) REFERENCES [pre].[lead] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sales_activity] ADD CONSTRAINT [FK_pre_sales_activity_opportunity_id] FOREIGN KEY ([opportunity_id]) REFERENCES [pre].[opportunity] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sales_activity] ADD CONSTRAINT [FK_pre_sales_activity_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sales_activity] ADD CONSTRAINT [FK_pre_sales_activity_outcome_lookup_id] FOREIGN KEY ([outcome_lookup_id]) REFERENCES [core].[lookup_value] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[location_check] ADD CONSTRAINT [FK_pre_location_check_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[location_check] ADD CONSTRAINT [FK_pre_location_check_sales_activity_id] FOREIGN KEY ([sales_activity_id]) REFERENCES [pre].[sales_activity] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[location_check] ADD CONSTRAINT [FK_pre_location_check_photo_attachment_id] FOREIGN KEY ([photo_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[whatsapp_log] ADD CONSTRAINT [FK_pre_whatsapp_log_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[whatsapp_log] ADD CONSTRAINT [FK_pre_whatsapp_log_lead_id] FOREIGN KEY ([lead_id]) REFERENCES [pre].[lead] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[whatsapp_log] ADD CONSTRAINT [FK_pre_whatsapp_log_opportunity_id] FOREIGN KEY ([opportunity_id]) REFERENCES [pre].[opportunity] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[whatsapp_log] ADD CONSTRAINT [FK_pre_whatsapp_log_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[whatsapp_log] ADD CONSTRAINT [FK_pre_whatsapp_log_media_attachment_id] FOREIGN KEY ([media_attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
GO

/* ---------- 4. Foreign-key indexes (41) ---------- */
CREATE NONCLUSTERED INDEX [IX_sal_quotation_opportunity_id] ON [sal].[quotation] ([opportunity_id]);
CREATE NONCLUSTERED INDEX [IX_pre_campaign_branch_id] ON [pre].[campaign] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_branch_id] ON [pre].[lead] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_principal_id] ON [pre].[lead] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_lead_source_id] ON [pre].[lead] ([lead_source_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_campaign_id] ON [pre].[lead] ([campaign_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_referred_by_customer_id] ON [pre].[lead] ([referred_by_customer_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_referred_by_employee_id] ON [pre].[lead] ([referred_by_employee_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_district_id] ON [pre].[lead] ([district_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_pincode_id] ON [pre].[lead] ([pincode_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_interested_model_id] ON [pre].[lead] ([interested_model_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_application_lookup_id] ON [pre].[lead] ([application_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_assigned_to_employee_id] ON [pre].[lead] ([assigned_to_employee_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_lost_reason_lookup_id] ON [pre].[lead] ([lost_reason_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_pre_lead_converted_customer_id] ON [pre].[lead] ([converted_customer_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_principal_id] ON [pre].[opportunity] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_branch_id] ON [pre].[opportunity] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_lead_id] ON [pre].[opportunity] ([lead_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_customer_id] ON [pre].[opportunity] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_contact_id] ON [pre].[opportunity] ([contact_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_machine_model_id] ON [pre].[opportunity] ([machine_model_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_salesperson_employee_id] ON [pre].[opportunity] ([salesperson_employee_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_competitor_id] ON [pre].[opportunity] ([competitor_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_won_sales_order_id] ON [pre].[opportunity] ([won_sales_order_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_lost_reason_lookup_id] ON [pre].[opportunity] ([lost_reason_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_lost_to_competitor_id] ON [pre].[opportunity] ([lost_to_competitor_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_stage_log_opportunity_id] ON [pre].[opportunity_stage_log] ([opportunity_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_stage_log_changed_by_user_id] ON [pre].[opportunity_stage_log] ([changed_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sales_activity_employee_id] ON [pre].[sales_activity] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sales_activity_lead_id] ON [pre].[sales_activity] ([lead_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sales_activity_opportunity_id] ON [pre].[sales_activity] ([opportunity_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sales_activity_customer_id] ON [pre].[sales_activity] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sales_activity_outcome_lookup_id] ON [pre].[sales_activity] ([outcome_lookup_id]);
CREATE NONCLUSTERED INDEX [IX_pre_location_check_employee_id] ON [pre].[location_check] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_pre_location_check_sales_activity_id] ON [pre].[location_check] ([sales_activity_id]);
CREATE NONCLUSTERED INDEX [IX_pre_location_check_photo_attachment_id] ON [pre].[location_check] ([photo_attachment_id]);
CREATE NONCLUSTERED INDEX [IX_pre_whatsapp_log_customer_id] ON [pre].[whatsapp_log] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_pre_whatsapp_log_lead_id] ON [pre].[whatsapp_log] ([lead_id]);
CREATE NONCLUSTERED INDEX [IX_pre_whatsapp_log_opportunity_id] ON [pre].[whatsapp_log] ([opportunity_id]);
CREATE NONCLUSTERED INDEX [IX_pre_whatsapp_log_employee_id] ON [pre].[whatsapp_log] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_pre_whatsapp_log_media_attachment_id] ON [pre].[whatsapp_log] ([media_attachment_id]);
GO

/* =====================================================================
   TRISHUL Integrated System - SQL Server DDL (dictionary v2)
   Phase 6 - Pre-Sales completion
   Generated from the TRISHUL Database Dictionary. Do not edit by hand:
   change the dictionary and regenerate.
   Target: SQL Server 2019+ / Amazon RDS for SQL Server
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
/* ---------- 1. Tables (8) ---------- */

/* ===== pre: Pre-Sales ===== */
-- Pre-sale SOP stages up to order advance.
CREATE TABLE [pre].[sop_stage] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_sop_stage] PRIMARY KEY,
    [principal_id] BIGINT NULL,
    [sequence] SMALLINT NOT NULL,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(80) NOT NULL,
    [expected_days] SMALLINT NULL,
    [is_mandatory] BIT NOT NULL CONSTRAINT [DF_pre_sop_stage_is_mandatory] DEFAULT (1),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_sop_stage_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_sop_stage_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Tasks required in each SOP stage.
CREATE TABLE [pre].[sop_checklist_item] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_sop_checklist_item] PRIMARY KEY,
    [sop_stage_id] BIGINT NOT NULL,
    [sequence] SMALLINT NOT NULL,
    [item_text] NVARCHAR(300) NOT NULL,
    [requires_attachment] BIT NOT NULL CONSTRAINT [DF_pre_sop_checklist_item_requires_attachment] DEFAULT (0),
    [is_mandatory] BIT NOT NULL CONSTRAINT [DF_pre_sop_checklist_item_is_mandatory] DEFAULT (1),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_sop_checklist_item_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_sop_checklist_item_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Completion of SOP tasks per opportunity.
CREATE TABLE [pre].[sop_progress] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_sop_progress] PRIMARY KEY,
    [opportunity_id] BIGINT NOT NULL,
    [sop_checklist_item_id] BIGINT NOT NULL,
    [is_done] BIT NOT NULL CONSTRAINT [DF_pre_sop_progress_is_done] DEFAULT (0),
    [done_at] DATETIME2(0) NULL,
    [done_by_user_id] BIGINT NULL,
    [attachment_id] BIGINT NULL,
    [remarks] NVARCHAR(300) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_sop_progress_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_sop_progress_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO
-- Banks / NBFCs financing machines.
CREATE TABLE [pre].[financer] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_financer] PRIMARY KEY,
    [code] NVARCHAR(20) NOT NULL,
    [name] NVARCHAR(120) NOT NULL,
    [financer_type] NVARCHAR(30) NOT NULL,
    [contact_person] NVARCHAR(100) NULL,
    [phone] NVARCHAR(15) NULL,
    [email] NVARCHAR(120) NULL,
    [branch_address] NVARCHAR(500) NULL,
    [is_empanelled] BIT NOT NULL CONSTRAINT [DF_pre_financer_is_empanelled] DEFAULT (1),
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_financer_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_financer_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pre_financer_financer_type] CHECK ([financer_type] IN (N'Bank', N'NBFC', N'OEM captive'))
);
GO
-- Loan application for a deal.
CREATE TABLE [pre].[finance_application] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_finance_application] PRIMARY KEY,
    [application_no] NVARCHAR(30) NOT NULL,
    [opportunity_id] BIGINT NOT NULL,
    [customer_id] BIGINT NOT NULL,
    [financer_id] BIGINT NOT NULL,
    [loan_amount] DECIMAL(18,2) NOT NULL,
    [down_payment] DECIMAL(18,2) NULL,
    [tenure_months] SMALLINT NULL,
    [interest_rate] DECIMAL(5,2) NULL,
    [applied_on] DATE NULL,
    [status] NVARCHAR(30) NOT NULL,
    [sanctioned_amount] DECIMAL(18,2) NULL,
    [sanctioned_on] DATE NULL,
    [disbursed_amount] DECIMAL(18,2) NULL,
    [disbursed_on] DATE NULL,
    [financer_reference] NVARCHAR(60) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_finance_application_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_finance_application_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pre_finance_application_status] CHECK ([status] IN (N'Docs pending', N'Submitted', N'Sanctioned', N'Rejected', N'Disbursed'))
);
GO
-- Booking advance received at the end of the SOP.
CREATE TABLE [pre].[order_advance] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_order_advance] PRIMARY KEY,
    [opportunity_id] BIGINT NOT NULL,
    [customer_id] BIGINT NOT NULL,
    [receipt_id] BIGINT NULL,
    [amount] DECIMAL(18,2) NOT NULL,
    [received_on] DATE NOT NULL,
    [status] NVARCHAR(30) NOT NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_order_advance_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_order_advance_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL,
    CONSTRAINT [CK_pre_order_advance_status] CHECK ([status] IN (N'Received', N'Adjusted', N'Refunded'))
);
GO
-- Daily pipeline totals for trend and ageing reports.
CREATE TABLE [pre].[pipeline_snapshot] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_pipeline_snapshot] PRIMARY KEY,
    [snapshot_date] DATE NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [salesperson_employee_id] BIGINT NULL,
    [sop_stage_id] BIGINT NOT NULL,
    [opportunity_count] INT NOT NULL,
    [pipeline_value] DECIMAL(18,2) NOT NULL,
    [weighted_value] DECIMAL(18,2) NULL,
    [avg_age_days] DECIMAL(6,1) NULL
);
GO
-- Monthly targets per salesperson and model.
CREATE TABLE [pre].[sales_target] (
    [id] BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT [PK_pre_sales_target] PRIMARY KEY,
    [employee_id] BIGINT NOT NULL,
    [principal_id] BIGINT NOT NULL,
    [branch_id] BIGINT NOT NULL,
    [period_month] DATE NOT NULL,
    [machine_model_id] BIGINT NULL,
    [target_units] SMALLINT NULL,
    [target_value] DECIMAL(18,2) NULL,
    [created_at] DATETIME2(0) NOT NULL CONSTRAINT [DF_pre_sales_target_created_at] DEFAULT (SYSUTCDATETIME()),
    [created_by_user_id] BIGINT NULL,
    [updated_at] DATETIME2(0) NULL,
    [updated_by_user_id] BIGINT NULL,
    [is_active] BIT NOT NULL CONSTRAINT [DF_pre_sales_target_is_active] DEFAULT (1),
    [row_version] ROWVERSION NOT NULL
);
GO

/* ---------- 2. Unique keys (6) ---------- */
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_sop_stage_k1] ON [pre].[sop_stage] ([principal_id], [sequence]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_sop_stage_k2] ON [pre].[sop_stage] ([principal_id], [code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_sop_progress_k1] ON [pre].[sop_progress] ([opportunity_id], [sop_checklist_item_id]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_financer_code] ON [pre].[financer] ([code]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_finance_application_application_no] ON [pre].[finance_application] ([application_no]);
CREATE UNIQUE NONCLUSTERED INDEX [UX_pre_sales_target_k1] ON [pre].[sales_target] ([employee_id], [principal_id], [period_month], [machine_model_id]);
GO

/* ---------- 3. Foreign keys (25) ----------
   Includes links from earlier-phase columns to tables created in this phase. */
ALTER TABLE [sal].[sales_order] ADD CONSTRAINT [FK_sal_sales_order_finance_application_id] FOREIGN KEY ([finance_application_id]) REFERENCES [pre].[finance_application] ([id]) ON DELETE NO ACTION;
ALTER TABLE [sal].[receipt] ADD CONSTRAINT [FK_sal_receipt_financer_id] FOREIGN KEY ([financer_id]) REFERENCES [pre].[financer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity] ADD CONSTRAINT [FK_pre_opportunity_current_sop_stage_id] FOREIGN KEY ([current_sop_stage_id]) REFERENCES [pre].[sop_stage] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity_stage_log] ADD CONSTRAINT [FK_pre_opportunity_stage_log_from_stage_id] FOREIGN KEY ([from_stage_id]) REFERENCES [pre].[sop_stage] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[opportunity_stage_log] ADD CONSTRAINT [FK_pre_opportunity_stage_log_to_stage_id] FOREIGN KEY ([to_stage_id]) REFERENCES [pre].[sop_stage] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sop_stage] ADD CONSTRAINT [FK_pre_sop_stage_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sop_checklist_item] ADD CONSTRAINT [FK_pre_sop_checklist_item_sop_stage_id] FOREIGN KEY ([sop_stage_id]) REFERENCES [pre].[sop_stage] ([id]) ON DELETE CASCADE;
ALTER TABLE [pre].[sop_progress] ADD CONSTRAINT [FK_pre_sop_progress_opportunity_id] FOREIGN KEY ([opportunity_id]) REFERENCES [pre].[opportunity] ([id]) ON DELETE CASCADE;
ALTER TABLE [pre].[sop_progress] ADD CONSTRAINT [FK_pre_sop_progress_sop_checklist_item_id] FOREIGN KEY ([sop_checklist_item_id]) REFERENCES [pre].[sop_checklist_item] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sop_progress] ADD CONSTRAINT [FK_pre_sop_progress_done_by_user_id] FOREIGN KEY ([done_by_user_id]) REFERENCES [core].[app_user] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sop_progress] ADD CONSTRAINT [FK_pre_sop_progress_attachment_id] FOREIGN KEY ([attachment_id]) REFERENCES [core].[attachment] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[finance_application] ADD CONSTRAINT [FK_pre_finance_application_opportunity_id] FOREIGN KEY ([opportunity_id]) REFERENCES [pre].[opportunity] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[finance_application] ADD CONSTRAINT [FK_pre_finance_application_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[finance_application] ADD CONSTRAINT [FK_pre_finance_application_financer_id] FOREIGN KEY ([financer_id]) REFERENCES [pre].[financer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[order_advance] ADD CONSTRAINT [FK_pre_order_advance_opportunity_id] FOREIGN KEY ([opportunity_id]) REFERENCES [pre].[opportunity] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[order_advance] ADD CONSTRAINT [FK_pre_order_advance_customer_id] FOREIGN KEY ([customer_id]) REFERENCES [core].[customer] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[order_advance] ADD CONSTRAINT [FK_pre_order_advance_receipt_id] FOREIGN KEY ([receipt_id]) REFERENCES [sal].[receipt] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[pipeline_snapshot] ADD CONSTRAINT [FK_pre_pipeline_snapshot_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[pipeline_snapshot] ADD CONSTRAINT [FK_pre_pipeline_snapshot_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[pipeline_snapshot] ADD CONSTRAINT [FK_pre_pipeline_snapshot_salesperson_employee_id] FOREIGN KEY ([salesperson_employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[pipeline_snapshot] ADD CONSTRAINT [FK_pre_pipeline_snapshot_sop_stage_id] FOREIGN KEY ([sop_stage_id]) REFERENCES [pre].[sop_stage] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sales_target] ADD CONSTRAINT [FK_pre_sales_target_employee_id] FOREIGN KEY ([employee_id]) REFERENCES [core].[employee] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sales_target] ADD CONSTRAINT [FK_pre_sales_target_principal_id] FOREIGN KEY ([principal_id]) REFERENCES [core].[principal] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sales_target] ADD CONSTRAINT [FK_pre_sales_target_branch_id] FOREIGN KEY ([branch_id]) REFERENCES [core].[branch] ([id]) ON DELETE NO ACTION;
ALTER TABLE [pre].[sales_target] ADD CONSTRAINT [FK_pre_sales_target_machine_model_id] FOREIGN KEY ([machine_model_id]) REFERENCES [core].[machine_model] ([id]) ON DELETE NO ACTION;
GO

/* ---------- 4. Foreign-key indexes (25) ---------- */
CREATE NONCLUSTERED INDEX [IX_sal_sales_order_finance_application_id] ON [sal].[sales_order] ([finance_application_id]);
CREATE NONCLUSTERED INDEX [IX_sal_receipt_financer_id] ON [sal].[receipt] ([financer_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_current_sop_stage_id] ON [pre].[opportunity] ([current_sop_stage_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_stage_log_from_stage_id] ON [pre].[opportunity_stage_log] ([from_stage_id]);
CREATE NONCLUSTERED INDEX [IX_pre_opportunity_stage_log_to_stage_id] ON [pre].[opportunity_stage_log] ([to_stage_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sop_stage_principal_id] ON [pre].[sop_stage] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sop_checklist_item_sop_stage_id] ON [pre].[sop_checklist_item] ([sop_stage_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sop_progress_opportunity_id] ON [pre].[sop_progress] ([opportunity_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sop_progress_sop_checklist_item_id] ON [pre].[sop_progress] ([sop_checklist_item_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sop_progress_done_by_user_id] ON [pre].[sop_progress] ([done_by_user_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sop_progress_attachment_id] ON [pre].[sop_progress] ([attachment_id]);
CREATE NONCLUSTERED INDEX [IX_pre_finance_application_opportunity_id] ON [pre].[finance_application] ([opportunity_id]);
CREATE NONCLUSTERED INDEX [IX_pre_finance_application_customer_id] ON [pre].[finance_application] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_pre_finance_application_financer_id] ON [pre].[finance_application] ([financer_id]);
CREATE NONCLUSTERED INDEX [IX_pre_order_advance_opportunity_id] ON [pre].[order_advance] ([opportunity_id]);
CREATE NONCLUSTERED INDEX [IX_pre_order_advance_customer_id] ON [pre].[order_advance] ([customer_id]);
CREATE NONCLUSTERED INDEX [IX_pre_order_advance_receipt_id] ON [pre].[order_advance] ([receipt_id]);
CREATE NONCLUSTERED INDEX [IX_pre_pipeline_snapshot_principal_id] ON [pre].[pipeline_snapshot] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_pre_pipeline_snapshot_branch_id] ON [pre].[pipeline_snapshot] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_pre_pipeline_snapshot_salesperson_employee_id] ON [pre].[pipeline_snapshot] ([salesperson_employee_id]);
CREATE NONCLUSTERED INDEX [IX_pre_pipeline_snapshot_sop_stage_id] ON [pre].[pipeline_snapshot] ([sop_stage_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sales_target_employee_id] ON [pre].[sales_target] ([employee_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sales_target_principal_id] ON [pre].[sales_target] ([principal_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sales_target_branch_id] ON [pre].[sales_target] ([branch_id]);
CREATE NONCLUSTERED INDEX [IX_pre_sales_target_machine_model_id] ON [pre].[sales_target] ([machine_model_id]);
GO

/* =====================================================================
   TRISHUL Integrated System - SQL Server DDL (dictionary v2)
   Extra indexes for common screens and reports
   Generated from the TRISHUL Database Dictionary. Do not edit by hand:
   change the dictionary and regenerate.
   Target: SQL Server 2019+ / Amazon RDS for SQL Server
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

/* Service call board: open calls by branch/brand/status */
CREATE NONCLUSTERED INDEX [IX_svc_service_call_board] ON [svc].[service_call] ([principal_id], [branch_id], [current_status]) INCLUDE ([received_at], [assigned_engineer_id], [sla_due_at]);
/* Engineer's own calls on the mobile app */
CREATE NONCLUSTERED INDEX [IX_svc_service_call_engineer] ON [svc].[service_call] ([assigned_engineer_id], [current_status]);
/* GPS points by trip and time (table should be partitioned by month on recorded_at in production) */
CREATE NONCLUSTERED INDEX [IX_svc_trip_gps_point_time] ON [svc].[trip_gps_point] ([trip_id], [recorded_at]);
/* Stock ledger by item and date */
CREATE NONCLUSTERED INDEX [IX_inv_stock_move_item_date] ON [inv].[stock_move] ([item_id], [location_id], [move_at]);
/* Ledger by account and date */
CREATE NONCLUSTERED INDEX [IX_acc_gl_entry_account_date] ON [acc].[gl_entry] ([gl_account_id], [entry_date]) INCLUDE ([debit], [credit], [principal_id], [branch_id]);
/* Brand-wise sales */
CREATE NONCLUSTERED INDEX [IX_sal_sales_invoice_brand_date] ON [sal].[sales_invoice] ([principal_id], [invoice_date]) INCLUDE ([branch_id], [total], [status]);
GO

/* =====================================================================
   TRISHUL Integrated System - SQL Server DDL (dictionary v2)
   Seed data: lookup lists, roles, movement types
   Generated from the TRISHUL Database Dictionary. Do not edit by hand:
   change the dictionary and regenerate.
   Target: SQL Server 2019+ / Amazon RDS for SQL Server
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
SET XACT_ABORT ON;
BEGIN TRANSACTION;

/* Lookup lists (client to confirm values) */
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'CALL_SOURCE', N'Call Source', N'Service');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'CUSTOMER_PHONE_CALL', N'Customer phone call', 1 FROM [core].[lookup_type] WHERE [code] = N'CALL_SOURCE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'EMAIL', N'Email', 2 FROM [core].[lookup_type] WHERE [code] = N'CALL_SOURCE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'WHATSAPP', N'WhatsApp', 3 FROM [core].[lookup_type] WHERE [code] = N'CALL_SOURCE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'OEM_CUSTOMER_CARE_PER_BRAND', N'OEM Customer Care (per brand)', 4 FROM [core].[lookup_type] WHERE [code] = N'CALL_SOURCE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'SALES_PERSON', N'Sales person', 5 FROM [core].[lookup_type] WHERE [code] = N'CALL_SOURCE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'OLD_CUSTOMER', N'Old customer', 6 FROM [core].[lookup_type] WHERE [code] = N'CALL_SOURCE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'FOLLOW_UP_CALL', N'Follow-up call', 7 FROM [core].[lookup_type] WHERE [code] = N'CALL_SOURCE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'PLANNED_SERVICE', N'Planned service', 8 FROM [core].[lookup_type] WHERE [code] = N'CALL_SOURCE';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'CALL_TYPE', N'Call Type', N'Service');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'BREAKDOWN', N'Breakdown', 1 FROM [core].[lookup_type] WHERE [code] = N'CALL_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'PERIODIC_SERVICE', N'Periodic service', 2 FROM [core].[lookup_type] WHERE [code] = N'CALL_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'INSPECTION', N'Inspection', 3 FROM [core].[lookup_type] WHERE [code] = N'CALL_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'INSTALLATION', N'Installation', 4 FROM [core].[lookup_type] WHERE [code] = N'CALL_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'PDI', N'PDI', 5 FROM [core].[lookup_type] WHERE [code] = N'CALL_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'FOLLOW_UP', N'Follow-up', 6 FROM [core].[lookup_type] WHERE [code] = N'CALL_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'WARRANTY', N'Warranty', 7 FROM [core].[lookup_type] WHERE [code] = N'CALL_TYPE';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'COMPLAINT_CATEGORY', N'Complaint Category', N'Service');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'ENGINE', N'Engine', 1 FROM [core].[lookup_type] WHERE [code] = N'COMPLAINT_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'HYDRAULICS', N'Hydraulics', 2 FROM [core].[lookup_type] WHERE [code] = N'COMPLAINT_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'ELECTRICAL', N'Electrical', 3 FROM [core].[lookup_type] WHERE [code] = N'COMPLAINT_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'UNDERCARRIAGE', N'Undercarriage', 4 FROM [core].[lookup_type] WHERE [code] = N'COMPLAINT_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'TRANSMISSION', N'Transmission', 5 FROM [core].[lookup_type] WHERE [code] = N'COMPLAINT_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'CABIN_AC', N'Cabin/AC', 6 FROM [core].[lookup_type] WHERE [code] = N'COMPLAINT_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'ATTACHMENT', N'Attachment', 7 FROM [core].[lookup_type] WHERE [code] = N'COMPLAINT_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'OTHER', N'Other', 8 FROM [core].[lookup_type] WHERE [code] = N'COMPLAINT_CATEGORY';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'FAILURE_CODE', N'Failure Code', N'Service');
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'MACHINE_CONDITION', N'Machine Condition', N'Service');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'WORKING', N'Working', 1 FROM [core].[lookup_type] WHERE [code] = N'MACHINE_CONDITION';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'WORKING_WITH_ISSUE', N'Working with issue', 2 FROM [core].[lookup_type] WHERE [code] = N'MACHINE_CONDITION';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'BREAKDOWN', N'Breakdown', 3 FROM [core].[lookup_type] WHERE [code] = N'MACHINE_CONDITION';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'REASSIGN_REASON', N'Reassign Reason', N'Service');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'ENGINEER_ON_LEAVE', N'Engineer on leave', 1 FROM [core].[lookup_type] WHERE [code] = N'REASSIGN_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'CLOSER_ENGINEER_AVAILABLE', N'Closer engineer available', 2 FROM [core].[lookup_type] WHERE [code] = N'REASSIGN_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'SKILL_REQUIRED', N'Skill required', 3 FROM [core].[lookup_type] WHERE [code] = N'REASSIGN_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'WORKLOAD', N'Workload', 4 FROM [core].[lookup_type] WHERE [code] = N'REASSIGN_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'CUSTOMER_REQUEST', N'Customer request', 5 FROM [core].[lookup_type] WHERE [code] = N'REASSIGN_REASON';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'CALL_CANCEL_REASON', N'Call Cancel Reason', N'Service');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'DUPLICATE', N'Duplicate', 1 FROM [core].[lookup_type] WHERE [code] = N'CALL_CANCEL_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'CUSTOMER_CANCELLED', N'Customer cancelled', 2 FROM [core].[lookup_type] WHERE [code] = N'CALL_CANCEL_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'NOT_REACHABLE', N'Not reachable', 3 FROM [core].[lookup_type] WHERE [code] = N'CALL_CANCEL_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'RESOLVED_ON_PHONE', N'Resolved on phone', 4 FROM [core].[lookup_type] WHERE [code] = N'CALL_CANCEL_REASON';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'ADJUSTMENT_REASON', N'Adjustment Reason', N'Inventory');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'DAMAGE', N'Damage', 1 FROM [core].[lookup_type] WHERE [code] = N'ADJUSTMENT_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'COUNT_DIFFERENCE', N'Count difference', 2 FROM [core].[lookup_type] WHERE [code] = N'ADJUSTMENT_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'EXPIRY', N'Expiry', 3 FROM [core].[lookup_type] WHERE [code] = N'ADJUSTMENT_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'FOUND', N'Found', 4 FROM [core].[lookup_type] WHERE [code] = N'ADJUSTMENT_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'WRITE_OFF', N'Write-off', 5 FROM [core].[lookup_type] WHERE [code] = N'ADJUSTMENT_REASON';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'RETURN_REASON', N'Return Reason', N'Purchase / Sales');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'DAMAGED', N'Damaged', 1 FROM [core].[lookup_type] WHERE [code] = N'RETURN_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'WRONG_ITEM', N'Wrong item', 2 FROM [core].[lookup_type] WHERE [code] = N'RETURN_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'EXCESS', N'Excess', 3 FROM [core].[lookup_type] WHERE [code] = N'RETURN_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'QUALITY_ISSUE', N'Quality issue', 4 FROM [core].[lookup_type] WHERE [code] = N'RETURN_REASON';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'LEAD_APPLICATION', N'Lead Application', N'Pre-Sales');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'MINING', N'Mining', 1 FROM [core].[lookup_type] WHERE [code] = N'LEAD_APPLICATION';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'ROAD_CONSTRUCTION', N'Road construction', 2 FROM [core].[lookup_type] WHERE [code] = N'LEAD_APPLICATION';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'IRRIGATION', N'Irrigation', 3 FROM [core].[lookup_type] WHERE [code] = N'LEAD_APPLICATION';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'BUILDING', N'Building', 4 FROM [core].[lookup_type] WHERE [code] = N'LEAD_APPLICATION';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'QUARRY', N'Quarry', 5 FROM [core].[lookup_type] WHERE [code] = N'LEAD_APPLICATION';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'RENTAL', N'Rental', 6 FROM [core].[lookup_type] WHERE [code] = N'LEAD_APPLICATION';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'ACTIVITY_OUTCOME', N'Activity Outcome', N'Pre-Sales');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'INTERESTED', N'Interested', 1 FROM [core].[lookup_type] WHERE [code] = N'ACTIVITY_OUTCOME';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'DEMO_REQUESTED', N'Demo requested', 2 FROM [core].[lookup_type] WHERE [code] = N'ACTIVITY_OUTCOME';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'QUOTE_REQUESTED', N'Quote requested', 3 FROM [core].[lookup_type] WHERE [code] = N'ACTIVITY_OUTCOME';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'NOT_INTERESTED', N'Not interested', 4 FROM [core].[lookup_type] WHERE [code] = N'ACTIVITY_OUTCOME';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'CALL_BACK', N'Call back', 5 FROM [core].[lookup_type] WHERE [code] = N'ACTIVITY_OUTCOME';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'LOST_REASON', N'Lost Reason', N'Pre-Sales');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'PRICE', N'Price', 1 FROM [core].[lookup_type] WHERE [code] = N'LOST_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'FINANCE_NOT_APPROVED', N'Finance not approved', 2 FROM [core].[lookup_type] WHERE [code] = N'LOST_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'BOUGHT_COMPETITOR', N'Bought competitor', 3 FROM [core].[lookup_type] WHERE [code] = N'LOST_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'POSTPONED', N'Postponed', 4 FROM [core].[lookup_type] WHERE [code] = N'LOST_REASON';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'NO_BUDGET', N'No budget', 5 FROM [core].[lookup_type] WHERE [code] = N'LOST_REASON';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'EXPENSE_TYPE', N'Expense Type', N'HR');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'TRAVEL_KM', N'Travel (km)', 1 FROM [core].[lookup_type] WHERE [code] = N'EXPENSE_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'FUEL', N'Fuel', 2 FROM [core].[lookup_type] WHERE [code] = N'EXPENSE_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'FOOD', N'Food', 3 FROM [core].[lookup_type] WHERE [code] = N'EXPENSE_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'LODGING', N'Lodging', 4 FROM [core].[lookup_type] WHERE [code] = N'EXPENSE_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'MOBILE', N'Mobile', 5 FROM [core].[lookup_type] WHERE [code] = N'EXPENSE_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'OTHER', N'Other', 6 FROM [core].[lookup_type] WHERE [code] = N'EXPENSE_TYPE';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'EMPLOYEE_DOCUMENT_TYPE', N'Employee Document Type', N'HR');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'OFFER_LETTER', N'Offer letter', 1 FROM [core].[lookup_type] WHERE [code] = N'EMPLOYEE_DOCUMENT_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'ID_PROOF', N'ID proof', 2 FROM [core].[lookup_type] WHERE [code] = N'EMPLOYEE_DOCUMENT_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'ADDRESS_PROOF', N'Address proof', 3 FROM [core].[lookup_type] WHERE [code] = N'EMPLOYEE_DOCUMENT_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'DRIVING_LICENCE', N'Driving licence', 4 FROM [core].[lookup_type] WHERE [code] = N'EMPLOYEE_DOCUMENT_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'EDUCATION', N'Education', 5 FROM [core].[lookup_type] WHERE [code] = N'EMPLOYEE_DOCUMENT_TYPE';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'ASSET_TYPE', N'Asset Type', N'HR');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'MOBILE_PHONE', N'Mobile phone', 1 FROM [core].[lookup_type] WHERE [code] = N'ASSET_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'LAPTOP', N'Laptop', 2 FROM [core].[lookup_type] WHERE [code] = N'ASSET_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'TOOL_KIT', N'Tool kit', 3 FROM [core].[lookup_type] WHERE [code] = N'ASSET_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'SIM_CARD', N'SIM card', 4 FROM [core].[lookup_type] WHERE [code] = N'ASSET_TYPE';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'VEHICLE', N'Vehicle', 5 FROM [core].[lookup_type] WHERE [code] = N'ASSET_TYPE';
INSERT INTO [core].[lookup_type] ([code], [name], [module]) VALUES (N'HELPDESK_CATEGORY', N'Helpdesk Category', N'HR');
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'PAYROLL', N'Payroll', 1 FROM [core].[lookup_type] WHERE [code] = N'HELPDESK_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'LEAVE', N'Leave', 2 FROM [core].[lookup_type] WHERE [code] = N'HELPDESK_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'ATTENDANCE', N'Attendance', 3 FROM [core].[lookup_type] WHERE [code] = N'HELPDESK_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'REIMBURSEMENT', N'Reimbursement', 4 FROM [core].[lookup_type] WHERE [code] = N'HELPDESK_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'IT', N'IT', 5 FROM [core].[lookup_type] WHERE [code] = N'HELPDESK_CATEGORY';
INSERT INTO [core].[lookup_value] ([lookup_type_id], [code], [label], [sort_order]) SELECT [id], N'OTHER', N'Other', 6 FROM [core].[lookup_type] WHERE [code] = N'HELPDESK_CATEGORY';

/* Roles */
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'ADMIN', N'Administrator', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'BACK_OFFICE', N'Back office', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'TEAM_LEAD', N'Service Team Lead', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'SERVICE_ENGINEER', N'Service engineer', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'SALESPERSON', N'Salesperson', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'SALES_MANAGER', N'Sales manager', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'BRAND_MANAGER', N'Brand manager', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'WAREHOUSE', N'Warehouse / stores', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'PURCHASE', N'Purchase', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'ACCOUNTS', N'Accounts', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'HR', N'HR', 1);
INSERT INTO [core].[role] ([code], [name], [is_system]) VALUES (N'MANAGEMENT', N'Management (read only)', 1);

/* Stock movement types (used from Phase 2) */
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'GRN', N'Goods receipt', N'In');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'ISSUE_SERVICE', N'Issue to service call', N'Out');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'ISSUE_INTERNAL', N'Internal issue', N'Out');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'SALE', N'Sales delivery', N'Out');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'SALES_RETURN', N'Sales return', N'In');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'PURCHASE_RETURN', N'Purchase return', N'Out');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'TRANSFER_OUT', N'Transfer out', N'Out');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'TRANSFER_IN', N'Transfer in', N'In');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'ADJUST_IN', N'Adjustment +', N'In');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'ADJUST_OUT', N'Adjustment -', N'Out');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'DEFECTIVE_IN', N'Defective part received', N'In');
INSERT INTO [inv].[movement_type] ([code], [name], [direction]) VALUES (N'OPENING', N'Opening stock', N'In');

/* Currency */
INSERT INTO [core].[currency] ([code], [name], [symbol], [decimals]) VALUES (N'INR', N'Indian Rupee', N'₹', 2);

COMMIT TRANSACTION;
GO

/* =====================================================================
   TRISHUL Integrated System - SQL Server DDL (dictionary v2)
   Row-level security by brand and branch (created OFF; switch ON after testing)
   Generated from the TRISHUL Database Dictionary. Do not edit by hand:
   change the dictionary and regenerate.
   Target: SQL Server 2019+ / Amazon RDS for SQL Server
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
/*
   How it works
   - The API sets the signed-in user on every connection:
       EXEC sys.sp_set_session_context @key = N'app_user_id', @value = <id>, @read_only = 1;
   - A row is visible when the user is allowed its brand (core.user_principal_access)
     AND its branch (core.user_role with branch_id NULL = all branches, a matching branch,
     or the branch's parent warehouse).
   - Rows with no brand (common items) or no branch are visible to everyone.
   - Users holding the ADMIN, MANAGEMENT or ACCOUNTS role see everything.
   - core and int tables are not filtered (masters and integration jobs), except core.machine_unit.
*/
CREATE FUNCTION [rls].[fn_can_see] (@principal_id BIGINT, @branch_id BIGINT)
RETURNS TABLE
WITH SCHEMABINDING
AS
RETURN
    SELECT 1 AS [ok]
    WHERE
        EXISTS (SELECT 1 FROM [core].[user_role] ur JOIN [core].[role] r ON r.[id] = ur.[role_id]
                WHERE ur.[app_user_id] = CAST(SESSION_CONTEXT(N'app_user_id') AS BIGINT)
                  AND r.[code] IN (N'ADMIN', N'MANAGEMENT', N'ACCOUNTS'))
        OR (
            (@principal_id IS NULL OR EXISTS (
                SELECT 1 FROM [core].[user_principal_access] upa
                WHERE upa.[app_user_id] = CAST(SESSION_CONTEXT(N'app_user_id') AS BIGINT)
                  AND upa.[principal_id] = @principal_id))
            AND
            (@branch_id IS NULL OR EXISTS (
                SELECT 1 FROM [core].[user_role] ur
                JOIN [core].[branch] b ON b.[id] = @branch_id
                WHERE ur.[app_user_id] = CAST(SESSION_CONTEXT(N'app_user_id') AS BIGINT)
                  AND (ur.[branch_id] IS NULL OR ur.[branch_id] = b.[id] OR ur.[branch_id] = b.[parent_warehouse_id])))
        );
GO

CREATE SECURITY POLICY [rls].[brand_branch_policy]
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], NULL) ON [core].[machine_unit],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], NULL) ON [svc].[service_contract],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], NULL) ON [svc].[checklist_template],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [svc].[service_call],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], NULL) ON [svc].[oem_call_reference],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], NULL) ON [svc].[sla_rule],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], NULL) ON [svc].[warranty_claim],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [inv].[stock_issue],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [pur].[purchase_request],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [pur].[purchase_order],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [pur].[grn],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [pur].[supplier_invoice],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], NULL) ON [sal].[price_list],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [sal].[quotation],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [sal].[sales_order],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [sal].[delivery_note],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [sal].[sales_invoice],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], NULL) ON [sal].[credit_note],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [pre].[lead],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [pre].[opportunity],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], NULL) ON [pre].[sop_stage],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [pre].[pipeline_snapshot],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [pre].[sales_target],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [acc].[cost_centre],
    ADD FILTER PREDICATE [rls].[fn_can_see]([principal_id], [branch_id]) ON [acc].[gl_entry]
WITH (STATE = OFF);
GO

-- Enable after testing:
-- ALTER SECURITY POLICY [rls].[brand_branch_policy] WITH (STATE = ON);

/* =====================================================================
   TRISHUL Integrated System - SQL Server DDL (dictionary v2)
   Table and column descriptions (MS_Description extended properties)
   Generated from the TRISHUL Database Dictionary. Do not edit by hand:
   change the dictionary and regenerate.
   Target: SQL Server 2019+ / Amazon RDS for SQL Server
   ===================================================================== */
USE [TrishulDev];
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
EXEC sys.sp_addextendedproperty N'MS_Description', N'Legal entity (e.g. TRISHUL). One row per company.', N'SCHEMA', N'core', N'TABLE', N'company';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Short company code', N'SCHEMA', N'core', N'TABLE', N'company', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Registered legal name', N'SCHEMA', N'core', N'TABLE', N'company', N'COLUMN', N'legal_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Trade name on invoices', N'SCHEMA', N'core', N'TABLE', N'company', N'COLUMN', N'trade_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company PAN', N'SCHEMA', N'core', N'TABLE', N'company', N'COLUMN', N'pan';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Corporate identity number', N'SCHEMA', N'core', N'TABLE', N'company', N'COLUMN', N'cin';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Registered office address', N'SCHEMA', N'core', N'TABLE', N'company', N'COLUMN', N'address';
EXEC sys.sp_addextendedproperty N'MS_Description', N'State of registered office', N'SCHEMA', N'core', N'TABLE', N'company', N'COLUMN', N'state_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Logo for documents and app', N'SCHEMA', N'core', N'TABLE', N'company', N'COLUMN', N'logo_url';
EXEC sys.sp_addextendedproperty N'MS_Description', N'4 = April', N'SCHEMA', N'core', N'TABLE', N'company', N'COLUMN', N'fiscal_year_start_month';
EXEC sys.sp_addextendedproperty N'MS_Description', N'OEM brands the master company sells and services (Tata Hitachi, Kaashi, ...). Every brand-specific master and document points here.', N'SCHEMA', N'core', N'TABLE', N'principal';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand code, e.g. TATA_HITACHI', N'SCHEMA', N'core', N'TABLE', N'principal', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand name', N'SCHEMA', N'core', N'TABLE', N'principal', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier record used to buy machines/parts from this OEM', N'SCHEMA', N'core', N'TABLE', N'principal', N'COLUMN', N'supplier_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Master company sells this brand', N'SCHEMA', N'core', N'TABLE', N'principal', N'COLUMN', N'handles_sales';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Master company services this brand', N'SCHEMA', N'core', N'TABLE', N'principal', N'COLUMN', N'handles_service';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Master company sells parts of this brand', N'SCHEMA', N'core', N'TABLE', N'principal', N'COLUMN', N'handles_parts';
EXEC sys.sp_addextendedproperty N'MS_Description', N'OEM dealer portal, e.g. E-DOST (SAP ByD)', N'SCHEMA', N'core', N'TABLE', N'principal', N'COLUMN', N'oem_portal_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Logo for documents', N'SCHEMA', N'core', N'TABLE', N'principal', N'COLUMN', N'logo_url';
EXEC sys.sp_addextendedproperty N'MS_Description', N'OEM website', N'SCHEMA', N'core', N'TABLE', N'principal', N'COLUMN', N'website';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Indian states and UTs with GST state code.', N'SCHEMA', N'core', N'TABLE', N'state';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GST state code, e.g. 21 = Odisha', N'SCHEMA', N'core', N'TABLE', N'state', N'COLUMN', N'gst_state_code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'State name', N'SCHEMA', N'core', N'TABLE', N'state', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Union territory flag', N'SCHEMA', N'core', N'TABLE', N'state', N'COLUMN', N'is_union_territory';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Districts within a state.', N'SCHEMA', N'core', N'TABLE', N'district';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Parent state', N'SCHEMA', N'core', N'TABLE', N'district', N'COLUMN', N'state_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'District name', N'SCHEMA', N'core', N'TABLE', N'district', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PIN codes with centroid coordinates for distance and nearby logic.', N'SCHEMA', N'core', N'TABLE', N'pincode';
EXEC sys.sp_addextendedproperty N'MS_Description', N'6-digit PIN code', N'SCHEMA', N'core', N'TABLE', N'pincode', N'COLUMN', N'pincode';
EXEC sys.sp_addextendedproperty N'MS_Description', N'District', N'SCHEMA', N'core', N'TABLE', N'pincode', N'COLUMN', N'district_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Post office / locality', N'SCHEMA', N'core', N'TABLE', N'pincode', N'COLUMN', N'area_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Centroid latitude', N'SCHEMA', N'core', N'TABLE', N'pincode', N'COLUMN', N'latitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Centroid longitude', N'SCHEMA', N'core', N'TABLE', N'pincode', N'COLUMN', N'longitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Head office, warehouse or branch. Branches point to the warehouse that supplies them.', N'SCHEMA', N'core', N'TABLE', N'branch';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Owning company', N'SCHEMA', N'core', N'TABLE', N'branch', N'COLUMN', N'company_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch code', N'SCHEMA', N'core', N'TABLE', N'branch', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch name', N'SCHEMA', N'core', N'TABLE', N'branch', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Head office, Warehouse, Branch, Service point.', N'SCHEMA', N'core', N'TABLE', N'branch', N'COLUMN', N'branch_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplying warehouse (for branches; blank for warehouses and head office)', N'SCHEMA', N'core', N'TABLE', N'branch', N'COLUMN', N'parent_warehouse_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Address', N'SCHEMA', N'core', N'TABLE', N'branch', N'COLUMN', N'address';
EXEC sys.sp_addextendedproperty N'MS_Description', N'State (drives GSTIN)', N'SCHEMA', N'core', N'TABLE', N'branch', N'COLUMN', N'state_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'District', N'SCHEMA', N'core', N'TABLE', N'branch', N'COLUMN', N'district_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PIN code', N'SCHEMA', N'core', N'TABLE', N'branch', N'COLUMN', N'pincode_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GSTIN used for this branch''s invoices', N'SCHEMA', N'core', N'TABLE', N'branch', N'COLUMN', N'gstin_registration_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Phone', N'SCHEMA', N'core', N'TABLE', N'branch', N'COLUMN', N'phone';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Email', N'SCHEMA', N'core', N'TABLE', N'branch', N'COLUMN', N'email';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Location latitude', N'SCHEMA', N'core', N'TABLE', N'branch', N'COLUMN', N'latitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Location longitude', N'SCHEMA', N'core', N'TABLE', N'branch', N'COLUMN', N'longitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Stock location inside a warehouse. Branches hold no stock; all stock is in the 3-4 warehouses.', N'SCHEMA', N'core', N'TABLE', N'location';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Warehouse (branch of type Warehouse)', N'SCHEMA', N'core', N'TABLE', N'location', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Location code', N'SCHEMA', N'core', N'TABLE', N'location', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Location name', N'SCHEMA', N'core', N'TABLE', N'location', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Main store, Transit, Quarantine, Scrap.', N'SCHEMA', N'core', N'TABLE', N'location', N'COLUMN', N'location_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Address', N'SCHEMA', N'core', N'TABLE', N'location', N'COLUMN', N'address';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Holds inventory', N'SCHEMA', N'core', N'TABLE', N'location', N'COLUMN', N'is_stock_location';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Sales area grouping for reports.', N'SCHEMA', N'core', N'TABLE', N'area';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Area code', N'SCHEMA', N'core', N'TABLE', N'area', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Area name', N'SCHEMA', N'core', N'TABLE', N'area', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'core', N'TABLE', N'area', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Service/sales territory covered by a team.', N'SCHEMA', N'core', N'TABLE', N'territory';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'core', N'TABLE', N'territory', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Territory code', N'SCHEMA', N'core', N'TABLE', N'territory', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Territory name', N'SCHEMA', N'core', N'TABLE', N'territory', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Notes', N'SCHEMA', N'core', N'TABLE', N'territory', N'COLUMN', N'description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PIN codes that fall inside a territory.', N'SCHEMA', N'core', N'TABLE', N'territory_pincode';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Territory', N'SCHEMA', N'core', N'TABLE', N'territory_pincode', N'COLUMN', N'territory_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PIN code', N'SCHEMA', N'core', N'TABLE', N'territory_pincode', N'COLUMN', N'pincode_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Service or sales team led by a Team Lead.', N'SCHEMA', N'core', N'TABLE', N'team';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'core', N'TABLE', N'team', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Team name', N'SCHEMA', N'core', N'TABLE', N'team', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Team type Allowed: Service, Sales, Back office.', N'SCHEMA', N'core', N'TABLE', N'team', N'COLUMN', N'team_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Team Lead', N'SCHEMA', N'core', N'TABLE', N'team', N'COLUMN', N'team_lead_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Engineers or salespeople in a team, with their territory.', N'SCHEMA', N'core', N'TABLE', N'team_member';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Team', N'SCHEMA', N'core', N'TABLE', N'team_member', N'COLUMN', N'team_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Member', N'SCHEMA', N'core', N'TABLE', N'team_member', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Main territory', N'SCHEMA', N'core', N'TABLE', N'team_member', N'COLUMN', N'territory_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Joined team on', N'SCHEMA', N'core', N'TABLE', N'team_member', N'COLUMN', N'from_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Left team on', N'SCHEMA', N'core', N'TABLE', N'team_member', N'COLUMN', N'to_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brands each warehouse/branch deals in, with the OEM dealer code for that outlet.', N'SCHEMA', N'core', N'TABLE', N'branch_principal';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch or warehouse', N'SCHEMA', N'core', N'TABLE', N'branch_principal', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand', N'SCHEMA', N'core', N'TABLE', N'branch_principal', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Dealer / outlet code given by the OEM', N'SCHEMA', N'core', N'TABLE', N'branch_principal', N'COLUMN', N'oem_dealer_code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Sells this brand', N'SCHEMA', N'core', N'TABLE', N'branch_principal', N'COLUMN', N'is_sales_authorised';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Services this brand', N'SCHEMA', N'core', N'TABLE', N'branch_principal', N'COLUMN', N'is_service_authorised';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Sells parts of this brand', N'SCHEMA', N'core', N'TABLE', N'branch_principal', N'COLUMN', N'is_parts_authorised';
EXEC sys.sp_addextendedproperty N'MS_Description', N'From', N'SCHEMA', N'core', N'TABLE', N'branch_principal', N'COLUMN', N'valid_from';
EXEC sys.sp_addextendedproperty N'MS_Description', N'To', N'SCHEMA', N'core', N'TABLE', N'branch_principal', N'COLUMN', N'valid_to';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Currencies (INR default).', N'SCHEMA', N'core', N'TABLE', N'currency';
EXEC sys.sp_addextendedproperty N'MS_Description', N'ISO code', N'SCHEMA', N'core', N'TABLE', N'currency', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name', N'SCHEMA', N'core', N'TABLE', N'currency', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Symbol', N'SCHEMA', N'core', N'TABLE', N'currency', N'COLUMN', N'symbol';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Decimal places', N'SCHEMA', N'core', N'TABLE', N'currency', N'COLUMN', N'decimals';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Credit terms for customers and suppliers.', N'SCHEMA', N'core', N'TABLE', N'payment_terms';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Code', N'SCHEMA', N'core', N'TABLE', N'payment_terms', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'e.g. 30 days', N'SCHEMA', N'core', N'TABLE', N'payment_terms', N'COLUMN', N'description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Days from document date', N'SCHEMA', N'core', N'TABLE', N'payment_terms', N'COLUMN', N'days_before_due';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Fixed day next month', N'SCHEMA', N'core', N'TABLE', N'payment_terms', N'COLUMN', N'day_in_following_month';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer (billing party).', N'SCHEMA', N'core', N'TABLE', N'customer';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company', N'SCHEMA', N'core', N'TABLE', N'customer', N'COLUMN', N'company_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer code', N'SCHEMA', N'core', N'TABLE', N'customer', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer / firm name', N'SCHEMA', N'core', N'TABLE', N'customer', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Individual, Contractor, Company, Government, Rental, Dealer.', N'SCHEMA', N'core', N'TABLE', N'customer', N'COLUMN', N'customer_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PAN', N'SCHEMA', N'core', N'TABLE', N'customer', N'COLUMN', N'pan';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GSTIN if registered', N'SCHEMA', N'core', N'TABLE', N'customer', N'COLUMN', N'gstin';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GST type Allowed: Regular, Composition, Unregistered, SEZ.', N'SCHEMA', N'core', N'TABLE', N'customer', N'COLUMN', N'gst_registration_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Billing address', N'SCHEMA', N'core', N'TABLE', N'customer', N'COLUMN', N'billing_address';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Billing state (place of supply)', N'SCHEMA', N'core', N'TABLE', N'customer', N'COLUMN', N'billing_state_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Billing PIN', N'SCHEMA', N'core', N'TABLE', N'customer', N'COLUMN', N'billing_pincode_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Main phone', N'SCHEMA', N'core', N'TABLE', N'customer', N'COLUMN', N'primary_phone';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Alternate phone', N'SCHEMA', N'core', N'TABLE', N'customer', N'COLUMN', N'alternate_phone';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Email', N'SCHEMA', N'core', N'TABLE', N'customer', N'COLUMN', N'email';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Sales area', N'SCHEMA', N'core', N'TABLE', N'customer', N'COLUMN', N'area_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Account owner', N'SCHEMA', N'core', N'TABLE', N'customer', N'COLUMN', N'salesman_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Default terms', N'SCHEMA', N'core', N'TABLE', N'customer', N'COLUMN', N'payment_terms_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Credit limit (INR)', N'SCHEMA', N'core', N'TABLE', N'customer', N'COLUMN', N'credit_limit';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Credit status (Phase 4)', N'SCHEMA', N'core', N'TABLE', N'customer', N'COLUMN', N'credit_status_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'ASC customer, attended first', N'SCHEMA', N'core', N'TABLE', N'customer', N'COLUMN', N'is_asc_customer';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Service priority Allowed: Key, Normal, Low.', N'SCHEMA', N'core', N'TABLE', N'customer', N'COLUMN', N'priority_tier';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer''s code in each OEM system (replaces byd_customer_id). One customer can buy several brands.', N'SCHEMA', N'core', N'TABLE', N'customer_principal';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer', N'SCHEMA', N'core', N'TABLE', N'customer_principal', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand', N'SCHEMA', N'core', N'TABLE', N'customer_principal', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer ID in the OEM system (e.g. SAP ByD for Tata Hitachi)', N'SCHEMA', N'core', N'TABLE', N'customer_principal', N'COLUMN', N'oem_customer_code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Salesperson for this brand', N'SCHEMA', N'core', N'TABLE', N'customer_principal', N'COLUMN', N'account_owner_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'First purchase of this brand', N'SCHEMA', N'core', N'TABLE', N'customer_principal', N'COLUMN', N'first_purchase_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Work sites where the customer''s machines operate.', N'SCHEMA', N'core', N'TABLE', N'customer_site';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer', N'SCHEMA', N'core', N'TABLE', N'customer_site', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Site / project name', N'SCHEMA', N'core', N'TABLE', N'customer_site', N'COLUMN', N'site_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Site address', N'SCHEMA', N'core', N'TABLE', N'customer_site', N'COLUMN', N'address';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PIN code', N'SCHEMA', N'core', N'TABLE', N'customer_site', N'COLUMN', N'pincode_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'District', N'SCHEMA', N'core', N'TABLE', N'customer_site', N'COLUMN', N'district_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'State', N'SCHEMA', N'core', N'TABLE', N'customer_site', N'COLUMN', N'state_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Site latitude', N'SCHEMA', N'core', N'TABLE', N'customer_site', N'COLUMN', N'latitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Site longitude', N'SCHEMA', N'core', N'TABLE', N'customer_site', N'COLUMN', N'longitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Person at site', N'SCHEMA', N'core', N'TABLE', N'customer_site', N'COLUMN', N'site_contact_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Phone at site', N'SCHEMA', N'core', N'TABLE', N'customer_site', N'COLUMN', N'site_contact_phone';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Default site', N'SCHEMA', N'core', N'TABLE', N'customer_site', N'COLUMN', N'is_default';
EXEC sys.sp_addextendedproperty N'MS_Description', N'People at a customer or supplier.', N'SCHEMA', N'core', N'TABLE', N'contact';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer (either customer or supplier)', N'SCHEMA', N'core', N'TABLE', N'contact', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier', N'SCHEMA', N'core', N'TABLE', N'contact', N'COLUMN', N'supplier_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Contact name', N'SCHEMA', N'core', N'TABLE', N'contact', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Designation', N'SCHEMA', N'core', N'TABLE', N'contact', N'COLUMN', N'designation';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Phone', N'SCHEMA', N'core', N'TABLE', N'contact', N'COLUMN', N'phone';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Alternate phone', N'SCHEMA', N'core', N'TABLE', N'contact', N'COLUMN', N'alternate_phone';
EXEC sys.sp_addextendedproperty N'MS_Description', N'WhatsApp number', N'SCHEMA', N'core', N'TABLE', N'contact', N'COLUMN', N'whatsapp_number';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Email', N'SCHEMA', N'core', N'TABLE', N'contact', N'COLUMN', N'email';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Language for messages Allowed: English, Odia, Hindi.', N'SCHEMA', N'core', N'TABLE', N'contact', N'COLUMN', N'preferred_language';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Primary contact', N'SCHEMA', N'core', N'TABLE', N'contact', N'COLUMN', N'is_primary';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier / vendor, including TATA HITACHI as OEM.', N'SCHEMA', N'core', N'TABLE', N'supplier';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company', N'SCHEMA', N'core', N'TABLE', N'supplier', N'COLUMN', N'company_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier code', N'SCHEMA', N'core', N'TABLE', N'supplier', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier name', N'SCHEMA', N'core', N'TABLE', N'supplier', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: OEM, Parts, Lubricants, Services, Transporter, Other.', N'SCHEMA', N'core', N'TABLE', N'supplier', N'COLUMN', N'supplier_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PAN', N'SCHEMA', N'core', N'TABLE', N'supplier', N'COLUMN', N'pan';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GSTIN', N'SCHEMA', N'core', N'TABLE', N'supplier', N'COLUMN', N'gstin';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GST type Allowed: Regular, Composition, Unregistered, SEZ, Overseas.', N'SCHEMA', N'core', N'TABLE', N'supplier', N'COLUMN', N'gst_registration_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Address', N'SCHEMA', N'core', N'TABLE', N'supplier', N'COLUMN', N'address';
EXEC sys.sp_addextendedproperty N'MS_Description', N'State', N'SCHEMA', N'core', N'TABLE', N'supplier', N'COLUMN', N'state_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PIN', N'SCHEMA', N'core', N'TABLE', N'supplier', N'COLUMN', N'pincode_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Phone', N'SCHEMA', N'core', N'TABLE', N'supplier', N'COLUMN', N'phone';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Email', N'SCHEMA', N'core', N'TABLE', N'supplier', N'COLUMN', N'email';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Terms', N'SCHEMA', N'core', N'TABLE', N'supplier', N'COLUMN', N'payment_terms_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Credit allowed by supplier', N'SCHEMA', N'core', N'TABLE', N'supplier', N'COLUMN', N'credit_limit';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Bank', N'SCHEMA', N'core', N'TABLE', N'supplier', N'COLUMN', N'bank_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Account number (encrypted)', N'SCHEMA', N'core', N'TABLE', N'supplier', N'COLUMN', N'bank_account_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'IFSC', N'SCHEMA', N'core', N'TABLE', N'supplier', N'COLUMN', N'ifsc';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Default TDS section', N'SCHEMA', N'core', N'TABLE', N'supplier', N'COLUMN', N'tds_section_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Units of measure.', N'SCHEMA', N'core', N'TABLE', N'uom';
EXEC sys.sp_addextendedproperty N'MS_Description', N'e.g. NOS, LTR, SET', N'SCHEMA', N'core', N'TABLE', N'uom', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name', N'SCHEMA', N'core', N'TABLE', N'uom', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Decimals allowed', N'SCHEMA', N'core', N'TABLE', N'uom', N'COLUMN', N'decimals';
EXEC sys.sp_addextendedproperty N'MS_Description', N'HSN (goods) and SAC (services) codes with GST rate.', N'SCHEMA', N'core', N'TABLE', N'hsn_sac';
EXEC sys.sp_addextendedproperty N'MS_Description', N'HSN or SAC code', N'SCHEMA', N'core', N'TABLE', N'hsn_sac', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Goods or service Allowed: HSN, SAC.', N'SCHEMA', N'core', N'TABLE', N'hsn_sac', N'COLUMN', N'code_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Description', N'SCHEMA', N'core', N'TABLE', N'hsn_sac', N'COLUMN', N'description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Applicable GST rate', N'SCHEMA', N'core', N'TABLE', N'hsn_sac', N'COLUMN', N'gst_rate_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item categories (hierarchical).', N'SCHEMA', N'core', N'TABLE', N'item_category';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Category code', N'SCHEMA', N'core', N'TABLE', N'item_category', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name', N'SCHEMA', N'core', N'TABLE', N'item_category', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Parent category', N'SCHEMA', N'core', N'TABLE', N'item_category', N'COLUMN', N'parent_category_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Nature Allowed: Machine, Spare part, Lubricant, Attachment, Service, Consumable.', N'SCHEMA', N'core', N'TABLE', N'item_category', N'COLUMN', N'item_nature';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Default unit', N'SCHEMA', N'core', N'TABLE', N'item_category', N'COLUMN', N'default_uom_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Default HSN/SAC', N'SCHEMA', N'core', N'TABLE', N'item_category', N'COLUMN', N'default_hsn_sac_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item master: machines, spare parts, lubricants, services. Brand items carry principal_id.', N'SCHEMA', N'core', N'TABLE', N'item';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company', N'SCHEMA', N'core', N'TABLE', N'item', N'COLUMN', N'company_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Internal item code', N'SCHEMA', N'core', N'TABLE', N'item', N'COLUMN', N'item_code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand (blank = common item, e.g. lubricants)', N'SCHEMA', N'core', N'TABLE', N'item', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'OEM part number', N'SCHEMA', N'core', N'TABLE', N'item', N'COLUMN', N'oem_part_number';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Short description', N'SCHEMA', N'core', N'TABLE', N'item', N'COLUMN', N'description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Long description', N'SCHEMA', N'core', N'TABLE', N'item', N'COLUMN', N'long_description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Category', N'SCHEMA', N'core', N'TABLE', N'item', N'COLUMN', N'category_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Stock unit', N'SCHEMA', N'core', N'TABLE', N'item', N'COLUMN', N'uom_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'HSN / SAC', N'SCHEMA', N'core', N'TABLE', N'item', N'COLUMN', N'hsn_sac_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Stock behaviour Allowed: Stock, Non stock, Service.', N'SCHEMA', N'core', N'TABLE', N'item', N'COLUMN', N'item_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Tracked by serial number', N'SCHEMA', N'core', N'TABLE', N'item', N'COLUMN', N'is_serialized';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Tracked by batch', N'SCHEMA', N'core', N'TABLE', N'item', N'COLUMN', N'is_batch_tracked';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Model, when the item is a machine', N'SCHEMA', N'core', N'TABLE', N'item', N'COLUMN', N'machine_model_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Standard cost', N'SCHEMA', N'core', N'TABLE', N'item', N'COLUMN', N'standard_cost';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Last purchase cost', N'SCHEMA', N'core', N'TABLE', N'item', N'COLUMN', N'last_purchase_cost';
EXEC sys.sp_addextendedproperty N'MS_Description', N'MRP', N'SCHEMA', N'core', N'TABLE', N'item', N'COLUMN', N'mrp';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Reorder level', N'SCHEMA', N'core', N'TABLE', N'item', N'COLUMN', N'reorder_level';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Reorder quantity', N'SCHEMA', N'core', N'TABLE', N'item', N'COLUMN', N'reorder_qty';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier lead time', N'SCHEMA', N'core', N'TABLE', N'item', N'COLUMN', N'lead_time_days';
EXEC sys.sp_addextendedproperty N'MS_Description', N'FSN/ABC class (Phase 2)', N'SCHEMA', N'core', N'TABLE', N'item', N'COLUMN', N'movement_class_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Machine models of every brand.', N'SCHEMA', N'core', N'TABLE', N'machine_model';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Model code, e.g. EX 200LC', N'SCHEMA', N'core', N'TABLE', N'machine_model', N'COLUMN', N'model_code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Model name', N'SCHEMA', N'core', N'TABLE', N'machine_model', N'COLUMN', N'model_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Product line Allowed: Excavator, Backhoe loader, Wheel loader, Mini excavator, Other.', N'SCHEMA', N'core', N'TABLE', N'machine_model', N'COLUMN', N'product_line';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand', N'SCHEMA', N'core', N'TABLE', N'machine_model', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Operating weight', N'SCHEMA', N'core', N'TABLE', N'machine_model', N'COLUMN', N'operating_weight_kg';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Engine model', N'SCHEMA', N'core', N'TABLE', N'machine_model', N'COLUMN', N'engine_model';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Standard warranty months', N'SCHEMA', N'core', N'TABLE', N'machine_model', N'COLUMN', N'default_warranty_months';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Standard warranty hours', N'SCHEMA', N'core', N'TABLE', N'machine_model', N'COLUMN', N'default_warranty_hours';
EXEC sys.sp_addextendedproperty N'MS_Description', N'One physical machine, identified by serial/chassis number. Shared by Service, Sales and Pre-Sales.', N'SCHEMA', N'core', N'TABLE', N'machine_unit';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Machine serial / chassis number', N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'serial_number';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Engine number', N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'engine_number';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Model', N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'model_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand (copied from model for filtering and access control)', N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item record for stock', N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Current owner', N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Current site', N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'customer_site_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Selling branch', N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'sold_by_branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Sale invoice (Phase 4)', N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'sale_invoice_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Sale date', N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'sale_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Commissioning date', N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'commissioning_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Warranty start', N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'warranty_start_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Warranty end', N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'warranty_end_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Warranty hour limit', N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'warranty_hours_limit';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Latest hour-meter reading', N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'current_hmr';
EXEC sys.sp_addextendedproperty N'MS_Description', N'When latest HMR was recorded', N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'hmr_updated_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Year', N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'year_of_manufacture';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Registration number if any', N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'registration_number';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: In stock, Sold, Transferred, Scrapped.', N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Machine ID in the OEM system', N'SCHEMA', N'core', N'TABLE', N'machine_unit', N'COLUMN', N'oem_registered_product_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Ownership history, for resold machines (old customers).', N'SCHEMA', N'core', N'TABLE', N'machine_ownership';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Machine', N'SCHEMA', N'core', N'TABLE', N'machine_ownership', N'COLUMN', N'machine_unit_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Owner', N'SCHEMA', N'core', N'TABLE', N'machine_ownership', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Owned from', N'SCHEMA', N'core', N'TABLE', N'machine_ownership', N'COLUMN', N'from_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Owned until', N'SCHEMA', N'core', N'TABLE', N'machine_ownership', N'COLUMN', N'to_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Reason', N'SCHEMA', N'core', N'TABLE', N'machine_ownership', N'COLUMN', N'transfer_reason';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Every hour-meter (HMR) reading. Drives scheduled services and warranty checks.', N'SCHEMA', N'core', N'TABLE', N'machine_meter_reading';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Machine', N'SCHEMA', N'core', N'TABLE', N'machine_meter_reading', N'COLUMN', N'machine_unit_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Hour-meter reading', N'SCHEMA', N'core', N'TABLE', N'machine_meter_reading', N'COLUMN', N'reading_hmr';
EXEC sys.sp_addextendedproperty N'MS_Description', N'When read', N'SCHEMA', N'core', N'TABLE', N'machine_meter_reading', N'COLUMN', N'reading_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Source Allowed: Service report, Customer, Import, Telematics.', N'SCHEMA', N'core', N'TABLE', N'machine_meter_reading', N'COLUMN', N'source';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Call during which it was read', N'SCHEMA', N'core', N'TABLE', N'machine_meter_reading', N'COLUMN', N'service_call_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Recorded by', N'SCHEMA', N'core', N'TABLE', N'machine_meter_reading', N'COLUMN', N'recorded_by_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Photo of meter', N'SCHEMA', N'core', N'TABLE', N'machine_meter_reading', N'COLUMN', N'photo_attachment_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee shell used by all modules. Full HR profile in hr.employee_profile.', N'SCHEMA', N'core', N'TABLE', N'employee';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company', N'SCHEMA', N'core', N'TABLE', N'employee', N'COLUMN', N'company_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee code', N'SCHEMA', N'core', N'TABLE', N'employee', N'COLUMN', N'employee_code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'First name', N'SCHEMA', N'core', N'TABLE', N'employee', N'COLUMN', N'first_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Last name', N'SCHEMA', N'core', N'TABLE', N'employee', N'COLUMN', N'last_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Mobile', N'SCHEMA', N'core', N'TABLE', N'employee', N'COLUMN', N'mobile';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Work email', N'SCHEMA', N'core', N'TABLE', N'employee', N'COLUMN', N'email';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'core', N'TABLE', N'employee', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Department', N'SCHEMA', N'core', N'TABLE', N'employee', N'COLUMN', N'department_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Designation', N'SCHEMA', N'core', N'TABLE', N'employee', N'COLUMN', N'designation_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Reports to', N'SCHEMA', N'core', N'TABLE', N'employee', N'COLUMN', N'reporting_manager_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Permanent, Contract, Trainee, Consultant.', N'SCHEMA', N'core', N'TABLE', N'employee', N'COLUMN', N'employee_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Joining date', N'SCHEMA', N'core', N'TABLE', N'employee', N'COLUMN', N'date_of_joining';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Exit date', N'SCHEMA', N'core', N'TABLE', N'employee', N'COLUMN', N'date_of_exit';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Active, Notice, Exited.', N'SCHEMA', N'core', N'TABLE', N'employee', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brands an engineer or salesperson is authorised or certified for. Used for assignment and targets.', N'SCHEMA', N'core', N'TABLE', N'employee_principal';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee', N'SCHEMA', N'core', N'TABLE', N'employee_principal', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand', N'SCHEMA', N'core', N'TABLE', N'employee_principal', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Work type Allowed: Service, Sales, Parts.', N'SCHEMA', N'core', N'TABLE', N'employee_principal', N'COLUMN', N'role_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'OEM training level', N'SCHEMA', N'core', N'TABLE', N'employee_principal', N'COLUMN', N'certification_level';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Certified', N'SCHEMA', N'core', N'TABLE', N'employee_principal', N'COLUMN', N'certified_on';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Valid until', N'SCHEMA', N'core', N'TABLE', N'employee_principal', N'COLUMN', N'valid_until';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Login account. Sign-in handled by AWS Cognito; no passwords here.', N'SCHEMA', N'core', N'TABLE', N'app_user';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee', N'SCHEMA', N'core', N'TABLE', N'app_user', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Cognito user ID', N'SCHEMA', N'core', N'TABLE', N'app_user', N'COLUMN', N'cognito_sub';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Username', N'SCHEMA', N'core', N'TABLE', N'app_user', N'COLUMN', N'username';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Email', N'SCHEMA', N'core', N'TABLE', N'app_user', N'COLUMN', N'email';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Mobile', N'SCHEMA', N'core', N'TABLE', N'app_user', N'COLUMN', N'mobile';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Default branch', N'SCHEMA', N'core', N'TABLE', N'app_user', N'COLUMN', N'default_branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Last login', N'SCHEMA', N'core', N'TABLE', N'app_user', N'COLUMN', N'last_login_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Locked', N'SCHEMA', N'core', N'TABLE', N'app_user', N'COLUMN', N'is_locked';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Roles: Admin, Back office, Team Lead, Service engineer, etc.', N'SCHEMA', N'core', N'TABLE', N'role';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Role code', N'SCHEMA', N'core', N'TABLE', N'role', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Role name', N'SCHEMA', N'core', N'TABLE', N'role', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Description', N'SCHEMA', N'core', N'TABLE', N'role', N'COLUMN', N'description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Built-in role', N'SCHEMA', N'core', N'TABLE', N'role', N'COLUMN', N'is_system';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Individual permission, e.g. svc.call.assign.', N'SCHEMA', N'core', N'TABLE', N'permission';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Permission code', N'SCHEMA', N'core', N'TABLE', N'permission', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Module', N'SCHEMA', N'core', N'TABLE', N'permission', N'COLUMN', N'module';
EXEC sys.sp_addextendedproperty N'MS_Description', N'What it allows', N'SCHEMA', N'core', N'TABLE', N'permission', N'COLUMN', N'description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Permissions granted to a role.', N'SCHEMA', N'core', N'TABLE', N'role_permission';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Role', N'SCHEMA', N'core', N'TABLE', N'role_permission', N'COLUMN', N'role_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Permission', N'SCHEMA', N'core', N'TABLE', N'role_permission', N'COLUMN', N'permission_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Roles given to a user, optionally limited to a branch.', N'SCHEMA', N'core', N'TABLE', N'user_role';
EXEC sys.sp_addextendedproperty N'MS_Description', N'User', N'SCHEMA', N'core', N'TABLE', N'user_role', N'COLUMN', N'app_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Role', N'SCHEMA', N'core', N'TABLE', N'user_role', N'COLUMN', N'role_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch scope (blank = all)', N'SCHEMA', N'core', N'TABLE', N'user_role', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brands a user may see. With branch scope, drives row-level security on every screen and report.', N'SCHEMA', N'core', N'TABLE', N'user_principal_access';
EXEC sys.sp_addextendedproperty N'MS_Description', N'User', N'SCHEMA', N'core', N'TABLE', N'user_principal_access', N'COLUMN', N'app_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand', N'SCHEMA', N'core', N'TABLE', N'user_principal_access', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Mobile devices for push notifications and offline sync.', N'SCHEMA', N'core', N'TABLE', N'user_device';
EXEC sys.sp_addextendedproperty N'MS_Description', N'User', N'SCHEMA', N'core', N'TABLE', N'user_device', N'COLUMN', N'app_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Device identifier', N'SCHEMA', N'core', N'TABLE', N'user_device', N'COLUMN', N'device_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Platform Allowed: Android, iOS, Web.', N'SCHEMA', N'core', N'TABLE', N'user_device', N'COLUMN', N'platform';
EXEC sys.sp_addextendedproperty N'MS_Description', N'App version', N'SCHEMA', N'core', N'TABLE', N'user_device', N'COLUMN', N'app_version';
EXEC sys.sp_addextendedproperty N'MS_Description', N'FCM / APNs token', N'SCHEMA', N'core', N'TABLE', N'user_device', N'COLUMN', N'push_token';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Last seen', N'SCHEMA', N'core', N'TABLE', N'user_device', N'COLUMN', N'last_seen_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Last successful sync', N'SCHEMA', N'core', N'TABLE', N'user_device', N'COLUMN', N'last_sync_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Types of dropdown lists (see Lookup Lists sheet).', N'SCHEMA', N'core', N'TABLE', N'lookup_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type code', N'SCHEMA', N'core', N'TABLE', N'lookup_type', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name', N'SCHEMA', N'core', N'TABLE', N'lookup_type', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Module', N'SCHEMA', N'core', N'TABLE', N'lookup_type', N'COLUMN', N'module';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Admin can edit values', N'SCHEMA', N'core', N'TABLE', N'lookup_type', N'COLUMN', N'is_editable';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Values in a dropdown list.', N'SCHEMA', N'core', N'TABLE', N'lookup_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'List', N'SCHEMA', N'core', N'TABLE', N'lookup_value', N'COLUMN', N'lookup_type_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Value code', N'SCHEMA', N'core', N'TABLE', N'lookup_value', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Display label', N'SCHEMA', N'core', N'TABLE', N'lookup_value', N'COLUMN', N'label';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Order', N'SCHEMA', N'core', N'TABLE', N'lookup_value', N'COLUMN', N'sort_order';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Parent value (dependent lists)', N'SCHEMA', N'core', N'TABLE', N'lookup_value', N'COLUMN', N'parent_value_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Document numbering per branch and fiscal year.', N'SCHEMA', N'core', N'TABLE', N'number_series';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company', N'SCHEMA', N'core', N'TABLE', N'number_series', N'COLUMN', N'company_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch (blank = company-wide)', N'SCHEMA', N'core', N'TABLE', N'number_series', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'e.g. SERVICE_CALL, SALES_INVOICE', N'SCHEMA', N'core', N'TABLE', N'number_series', N'COLUMN', N'document_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand-specific series (blank = shared)', N'SCHEMA', N'core', N'TABLE', N'number_series', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Fiscal year', N'SCHEMA', N'core', N'TABLE', N'number_series', N'COLUMN', N'fiscal_year_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Prefix, e.g. BBSR/SC/', N'SCHEMA', N'core', N'TABLE', N'number_series', N'COLUMN', N'prefix';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Next number', N'SCHEMA', N'core', N'TABLE', N'number_series', N'COLUMN', N'next_number';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Zero padding', N'SCHEMA', N'core', N'TABLE', N'number_series', N'COLUMN', N'padding';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Suffix', N'SCHEMA', N'core', N'TABLE', N'number_series', N'COLUMN', N'suffix';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Files stored in Amazon S3, linked to any record.', N'SCHEMA', N'core', N'TABLE', N'attachment';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Table the file belongs to', N'SCHEMA', N'core', N'TABLE', N'attachment', N'COLUMN', N'entity_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Record ID', N'SCHEMA', N'core', N'TABLE', N'attachment', N'COLUMN', N'entity_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Category Allowed: Photo, Signature, Report PDF, Document, Invoice, Other.', N'SCHEMA', N'core', N'TABLE', N'attachment', N'COLUMN', N'category';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Original file name', N'SCHEMA', N'core', N'TABLE', N'attachment', N'COLUMN', N'file_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'MIME type', N'SCHEMA', N'core', N'TABLE', N'attachment', N'COLUMN', N'content_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Size', N'SCHEMA', N'core', N'TABLE', N'attachment', N'COLUMN', N'file_size_bytes';
EXEC sys.sp_addextendedproperty N'MS_Description', N'S3 object key', N'SCHEMA', N'core', N'TABLE', N'attachment', N'COLUMN', N's3_key';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Where photo was taken', N'SCHEMA', N'core', N'TABLE', N'attachment', N'COLUMN', N'captured_latitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Where photo was taken', N'SCHEMA', N'core', N'TABLE', N'attachment', N'COLUMN', N'captured_longitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'When captured', N'SCHEMA', N'core', N'TABLE', N'attachment', N'COLUMN', N'captured_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Field-level change history for sensitive tables.', N'SCHEMA', N'core', N'TABLE', N'audit_log';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Table', N'SCHEMA', N'core', N'TABLE', N'audit_log', N'COLUMN', N'entity_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Record ID', N'SCHEMA', N'core', N'TABLE', N'audit_log', N'COLUMN', N'entity_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Action Allowed: Insert, Update, Delete.', N'SCHEMA', N'core', N'TABLE', N'audit_log', N'COLUMN', N'action';
EXEC sys.sp_addextendedproperty N'MS_Description', N'JSON of old values', N'SCHEMA', N'core', N'TABLE', N'audit_log', N'COLUMN', N'old_values';
EXEC sys.sp_addextendedproperty N'MS_Description', N'JSON of new values', N'SCHEMA', N'core', N'TABLE', N'audit_log', N'COLUMN', N'new_values';
EXEC sys.sp_addextendedproperty N'MS_Description', N'User', N'SCHEMA', N'core', N'TABLE', N'audit_log', N'COLUMN', N'changed_by_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'When', N'SCHEMA', N'core', N'TABLE', N'audit_log', N'COLUMN', N'changed_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Channel Allowed: Web, Android, iOS, API, Sync, System.', N'SCHEMA', N'core', N'TABLE', N'audit_log', N'COLUMN', N'source';
EXEC sys.sp_addextendedproperty N'MS_Description', N'IP address', N'SCHEMA', N'core', N'TABLE', N'audit_log', N'COLUMN', N'ip_address';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Generic status change log for documents other than service calls.', N'SCHEMA', N'core', N'TABLE', N'status_history';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Table', N'SCHEMA', N'core', N'TABLE', N'status_history', N'COLUMN', N'entity_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Record ID', N'SCHEMA', N'core', N'TABLE', N'status_history', N'COLUMN', N'entity_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Old status', N'SCHEMA', N'core', N'TABLE', N'status_history', N'COLUMN', N'from_status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'New status', N'SCHEMA', N'core', N'TABLE', N'status_history', N'COLUMN', N'to_status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'User', N'SCHEMA', N'core', N'TABLE', N'status_history', N'COLUMN', N'changed_by_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'When', N'SCHEMA', N'core', N'TABLE', N'status_history', N'COLUMN', N'changed_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Reason', N'SCHEMA', N'core', N'TABLE', N'status_history', N'COLUMN', N'reason_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Remarks', N'SCHEMA', N'core', N'TABLE', N'status_history', N'COLUMN', N'remarks';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Who must approve which documents, by value band.', N'SCHEMA', N'core', N'TABLE', N'approval_rule';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Document, e.g. QUOTATION, PURCHASE_ORDER', N'SCHEMA', N'core', N'TABLE', N'approval_rule', N'COLUMN', N'document_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch (blank = all)', N'SCHEMA', N'core', N'TABLE', N'approval_rule', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'From value', N'SCHEMA', N'core', N'TABLE', N'approval_rule', N'COLUMN', N'min_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Up to value', N'SCHEMA', N'core', N'TABLE', N'approval_rule', N'COLUMN', N'max_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Level', N'SCHEMA', N'core', N'TABLE', N'approval_rule', N'COLUMN', N'approval_level';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Approving role', N'SCHEMA', N'core', N'TABLE', N'approval_rule', N'COLUMN', N'approver_role_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Approval requests raised by documents.', N'SCHEMA', N'core', N'TABLE', N'approval_request';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Rule applied', N'SCHEMA', N'core', N'TABLE', N'approval_request', N'COLUMN', N'approval_rule_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Document type', N'SCHEMA', N'core', N'TABLE', N'approval_request', N'COLUMN', N'document_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Document ID', N'SCHEMA', N'core', N'TABLE', N'approval_request', N'COLUMN', N'document_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Level', N'SCHEMA', N'core', N'TABLE', N'approval_request', N'COLUMN', N'approval_level';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Requested by', N'SCHEMA', N'core', N'TABLE', N'approval_request', N'COLUMN', N'requested_by_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Requested at', N'SCHEMA', N'core', N'TABLE', N'approval_request', N'COLUMN', N'requested_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Approver', N'SCHEMA', N'core', N'TABLE', N'approval_request', N'COLUMN', N'approver_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Pending, Approved, Rejected, Cancelled.', N'SCHEMA', N'core', N'TABLE', N'approval_request', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Acted at', N'SCHEMA', N'core', N'TABLE', N'approval_request', N'COLUMN', N'acted_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Remarks', N'SCHEMA', N'core', N'TABLE', N'approval_request', N'COLUMN', N'remarks';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Message templates for push, WhatsApp, email, SMS.', N'SCHEMA', N'core', N'TABLE', N'notification_template';
EXEC sys.sp_addextendedproperty N'MS_Description', N'e.g. CALL_ASSIGNED', N'SCHEMA', N'core', N'TABLE', N'notification_template', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Channel Allowed: Push, WhatsApp, Email, SMS.', N'SCHEMA', N'core', N'TABLE', N'notification_template', N'COLUMN', N'channel';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Language Allowed: English, Odia, Hindi.', N'SCHEMA', N'core', N'TABLE', N'notification_template', N'COLUMN', N'language';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Subject / title', N'SCHEMA', N'core', N'TABLE', N'notification_template', N'COLUMN', N'subject';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Body with {placeholders}', N'SCHEMA', N'core', N'TABLE', N'notification_template', N'COLUMN', N'body';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Approved WhatsApp template', N'SCHEMA', N'core', N'TABLE', N'notification_template', N'COLUMN', N'whatsapp_template_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Every message sent, with delivery status.', N'SCHEMA', N'core', N'TABLE', N'notification';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Template', N'SCHEMA', N'core', N'TABLE', N'notification', N'COLUMN', N'template_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Channel Allowed: Push, WhatsApp, Email, SMS.', N'SCHEMA', N'core', N'TABLE', N'notification', N'COLUMN', N'channel';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Internal recipient', N'SCHEMA', N'core', N'TABLE', N'notification', N'COLUMN', N'recipient_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Phone or email for external recipient', N'SCHEMA', N'core', N'TABLE', N'notification', N'COLUMN', N'recipient_address';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Related table', N'SCHEMA', N'core', N'TABLE', N'notification', N'COLUMN', N'entity_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Related record', N'SCHEMA', N'core', N'TABLE', N'notification', N'COLUMN', N'entity_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Rendered message / data', N'SCHEMA', N'core', N'TABLE', N'notification', N'COLUMN', N'payload';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Queued, Sent, Delivered, Read, Failed.', N'SCHEMA', N'core', N'TABLE', N'notification', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Provider ID', N'SCHEMA', N'core', N'TABLE', N'notification', N'COLUMN', N'provider_message_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Sent at', N'SCHEMA', N'core', N'TABLE', N'notification', N'COLUMN', N'sent_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Error', N'SCHEMA', N'core', N'TABLE', N'notification', N'COLUMN', N'error_message';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Configurable settings per company.', N'SCHEMA', N'core', N'TABLE', N'system_setting';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company (blank = global)', N'SCHEMA', N'core', N'TABLE', N'system_setting', N'COLUMN', N'company_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Key', N'SCHEMA', N'core', N'TABLE', N'system_setting', N'COLUMN', N'setting_key';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Value', N'SCHEMA', N'core', N'TABLE', N'system_setting', N'COLUMN', N'setting_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Text, Number, Boolean, JSON.', N'SCHEMA', N'core', N'TABLE', N'system_setting', N'COLUMN', N'data_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Meaning', N'SCHEMA', N'core', N'TABLE', N'system_setting', N'COLUMN', N'description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'ASC / AMC / extended warranty / free-service contracts.', N'SCHEMA', N'svc', N'TABLE', N'service_contract';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company', N'SCHEMA', N'svc', N'TABLE', N'service_contract', N'COLUMN', N'company_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Contract number', N'SCHEMA', N'svc', N'TABLE', N'service_contract', N'COLUMN', N'contract_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand', N'SCHEMA', N'svc', N'TABLE', N'service_contract', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer', N'SCHEMA', N'svc', N'TABLE', N'service_contract', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: ASC, AMC, Extended warranty, Free service.', N'SCHEMA', N'svc', N'TABLE', N'service_contract', N'COLUMN', N'contract_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Start', N'SCHEMA', N'svc', N'TABLE', N'service_contract', N'COLUMN', N'start_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'End', N'SCHEMA', N'svc', N'TABLE', N'service_contract', N'COLUMN', N'end_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Hour limit', N'SCHEMA', N'svc', N'TABLE', N'service_contract', N'COLUMN', N'hours_limit';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Visits included', N'SCHEMA', N'svc', N'TABLE', N'service_contract', N'COLUMN', N'visits_included';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Visits used', N'SCHEMA', N'svc', N'TABLE', N'service_contract', N'COLUMN', N'visits_used';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Contract value', N'SCHEMA', N'svc', N'TABLE', N'service_contract', N'COLUMN', N'contract_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Invoice (Phase 4)', N'SCHEMA', N'svc', N'TABLE', N'service_contract', N'COLUMN', N'sales_invoice_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Active, Expired, Cancelled.', N'SCHEMA', N'svc', N'TABLE', N'service_contract', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Terms', N'SCHEMA', N'svc', N'TABLE', N'service_contract', N'COLUMN', N'terms';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Machines covered by a contract and what is covered.', N'SCHEMA', N'svc', N'TABLE', N'contract_coverage';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Contract', N'SCHEMA', N'svc', N'TABLE', N'contract_coverage', N'COLUMN', N'service_contract_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Machine', N'SCHEMA', N'svc', N'TABLE', N'contract_coverage', N'COLUMN', N'machine_unit_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Labour covered', N'SCHEMA', N'svc', N'TABLE', N'contract_coverage', N'COLUMN', N'covers_labour';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Parts covered', N'SCHEMA', N'svc', N'TABLE', N'contract_coverage', N'COLUMN', N'covers_parts';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Travel covered', N'SCHEMA', N'svc', N'TABLE', N'contract_coverage', N'COLUMN', N'covers_travel';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Parts discount', N'SCHEMA', N'svc', N'TABLE', N'contract_coverage', N'COLUMN', N'parts_discount_pct';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Inspection checklist by model and call type.', N'SCHEMA', N'svc', N'TABLE', N'checklist_template';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Checklist name', N'SCHEMA', N'svc', N'TABLE', N'checklist_template', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand (blank = all)', N'SCHEMA', N'svc', N'TABLE', N'checklist_template', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Model (blank = all)', N'SCHEMA', N'svc', N'TABLE', N'checklist_template', N'COLUMN', N'machine_model_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Call type', N'SCHEMA', N'svc', N'TABLE', N'checklist_template', N'COLUMN', N'call_type_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Questions in a checklist.', N'SCHEMA', N'svc', N'TABLE', N'checklist_template_item';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Checklist', N'SCHEMA', N'svc', N'TABLE', N'checklist_template_item', N'COLUMN', N'checklist_template_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Order', N'SCHEMA', N'svc', N'TABLE', N'checklist_template_item', N'COLUMN', N'sequence';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Check point', N'SCHEMA', N'svc', N'TABLE', N'checklist_template_item', N'COLUMN', N'item_text';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Answer type Allowed: OK Not OK, Number, Text, Photo.', N'SCHEMA', N'svc', N'TABLE', N'checklist_template_item', N'COLUMN', N'response_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Required', N'SCHEMA', N'svc', N'TABLE', N'checklist_template_item', N'COLUMN', N'is_mandatory';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Periodic service plan per model, e.g. 50 / 250 / 500 hours.', N'SCHEMA', N'svc', N'TABLE', N'service_schedule_template';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Model', N'SCHEMA', N'svc', N'TABLE', N'service_schedule_template', N'COLUMN', N'machine_model_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'e.g. 50 Hr First Service', N'SCHEMA', N'svc', N'TABLE', N'service_schedule_template', N'COLUMN', N'service_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Due at hour meter', N'SCHEMA', N'svc', N'TABLE', N'service_schedule_template', N'COLUMN', N'due_at_hmr';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Or due after days from sale', N'SCHEMA', N'svc', N'TABLE', N'service_schedule_template', N'COLUMN', N'due_after_days';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Allowed hours either side', N'SCHEMA', N'svc', N'TABLE', N'service_schedule_template', N'COLUMN', N'tolerance_hmr';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Free service', N'SCHEMA', N'svc', N'TABLE', N'service_schedule_template', N'COLUMN', N'is_free';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Checklist to use', N'SCHEMA', N'svc', N'TABLE', N'service_schedule_template', N'COLUMN', N'checklist_template_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Scheduled service due for a specific machine.', N'SCHEMA', N'svc', N'TABLE', N'planned_service';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Machine', N'SCHEMA', N'svc', N'TABLE', N'planned_service', N'COLUMN', N'machine_unit_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Schedule step', N'SCHEMA', N'svc', N'TABLE', N'planned_service', N'COLUMN', N'schedule_template_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Due HMR', N'SCHEMA', N'svc', N'TABLE', N'planned_service', N'COLUMN', N'due_hmr';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Due date', N'SCHEMA', N'svc', N'TABLE', N'planned_service', N'COLUMN', N'due_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Upcoming, Due, Overdue, Call raised, Done, Skipped.', N'SCHEMA', N'svc', N'TABLE', N'planned_service', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Call raised for it', N'SCHEMA', N'svc', N'TABLE', N'planned_service', N'COLUMN', N'service_call_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Service call (complaint / request). Replaces the register copy and Excel sheet.', N'SCHEMA', N'svc', N'TABLE', N'service_call';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'company_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch handling the call', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Our call number', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'call_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand (from the machine / model)', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'ID created on device (offline safe)', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'client_uuid';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Source: phone, email, WhatsApp, OEM customer care...', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'call_source_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Breakdown, periodic service, inspection, PDI...', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'call_type_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Complaint category', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'complaint_category_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Complaint as reported', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'complaint_description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Site', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'customer_site_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Contact person', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'contact_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Caller name', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'caller_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Caller phone', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'caller_phone';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Machine', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'machine_unit_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'HMR told by customer', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'reported_hmr';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Machine not working', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'is_machine_down';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Who pays Allowed: Warranty, Contract, Chargeable, Goodwill.', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'coverage_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Contract', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'service_contract_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Scheduled service', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'planned_service_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Priority Allowed: Critical, High, Normal, Low.', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'priority';
EXEC sys.sp_addextendedproperty N'MS_Description', N'ASC customer priority', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'is_asc_priority';
EXEC sys.sp_addextendedproperty N'MS_Description', N'When received', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'received_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Logged by', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'received_by_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Email subject, OEM customer care ref...', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'source_reference';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Current status Allowed: Logged, Assigned, Call ID linked, Customer contacted, Trip started, Reached site, In progress, Report submitted, Closed, Cancelled.', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'current_status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Team', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'team_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Current engineer', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'assigned_engineer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Call ID in the OEM portal (e.g. E-DOST for Tata Hitachi)', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'oem_call_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Must close by', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'sla_due_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'First customer contact', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'first_response_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Closed at', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'closed_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Closed by', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'closed_by_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'How closed Allowed: Resolved, Cancelled, Duplicate, Not reachable.', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'closure_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Original call if duplicate', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'duplicate_of_call_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'1-5 feedback', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'customer_rating';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Feedback', N'SCHEMA', N'svc', N'TABLE', N'service_call', N'COLUMN', N'customer_feedback';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Every status change on a call (drives the 24-hour rule and reports).', N'SCHEMA', N'svc', N'TABLE', N'call_status_log';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Call', N'SCHEMA', N'svc', N'TABLE', N'call_status_log', N'COLUMN', N'service_call_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Old status', N'SCHEMA', N'svc', N'TABLE', N'call_status_log', N'COLUMN', N'from_status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'New status', N'SCHEMA', N'svc', N'TABLE', N'call_status_log', N'COLUMN', N'to_status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'When', N'SCHEMA', N'svc', N'TABLE', N'call_status_log', N'COLUMN', N'changed_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'By', N'SCHEMA', N'svc', N'TABLE', N'call_status_log', N'COLUMN', N'changed_by_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Reason', N'SCHEMA', N'svc', N'TABLE', N'call_status_log', N'COLUMN', N'reason_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Remarks', N'SCHEMA', N'svc', N'TABLE', N'call_status_log', N'COLUMN', N'remarks';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Where (mobile)', N'SCHEMA', N'svc', N'TABLE', N'call_status_log', N'COLUMN', N'latitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Where (mobile)', N'SCHEMA', N'svc', N'TABLE', N'call_status_log', N'COLUMN', N'longitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Device ID', N'SCHEMA', N'svc', N'TABLE', N'call_status_log', N'COLUMN', N'client_uuid';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Engineer assignments and reassignments by the Team Lead.', N'SCHEMA', N'svc', N'TABLE', N'call_assignment';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Call', N'SCHEMA', N'svc', N'TABLE', N'call_assignment', N'COLUMN', N'service_call_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Engineer', N'SCHEMA', N'svc', N'TABLE', N'call_assignment', N'COLUMN', N'engineer_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Role on call Allowed: Primary, Support.', N'SCHEMA', N'svc', N'TABLE', N'call_assignment', N'COLUMN', N'assignment_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Team Lead', N'SCHEMA', N'svc', N'TABLE', N'call_assignment', N'COLUMN', N'assigned_by_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'When', N'SCHEMA', N'svc', N'TABLE', N'call_assignment', N'COLUMN', N'assigned_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Reassign reason', N'SCHEMA', N'svc', N'TABLE', N'call_assignment', N'COLUMN', N'reason_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Distance engineer-to-site', N'SCHEMA', N'svc', N'TABLE', N'call_assignment', N'COLUMN', N'distance_km_at_assignment';
EXEC sys.sp_addextendedproperty N'MS_Description', N'When removed', N'SCHEMA', N'svc', N'TABLE', N'call_assignment', N'COLUMN', N'unassigned_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Current assignment', N'SCHEMA', N'svc', N'TABLE', N'call_assignment', N'COLUMN', N'is_current';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Link to the call in the brand''s OEM portal (E-DOST / SAP ByD for Tata Hitachi; other portals for other brands).', N'SCHEMA', N'svc', N'TABLE', N'oem_call_reference';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Call', N'SCHEMA', N'svc', N'TABLE', N'oem_call_reference', N'COLUMN', N'service_call_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand', N'SCHEMA', N'svc', N'TABLE', N'oem_call_reference', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'OEM portal', N'SCHEMA', N'svc', N'TABLE', N'oem_call_reference', N'COLUMN', N'external_system_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Call ID in the OEM portal', N'SCHEMA', N'svc', N'TABLE', N'oem_call_reference', N'COLUMN', N'oem_call_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Ticket UUID (if API)', N'SCHEMA', N'svc', N'TABLE', N'oem_call_reference', N'COLUMN', N'oem_ticket_uuid';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Who created it Allowed: Back office, Engineer, API.', N'SCHEMA', N'svc', N'TABLE', N'oem_call_reference', N'COLUMN', N'created_in_oem_by';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Entered by', N'SCHEMA', N'svc', N'TABLE', N'oem_call_reference', N'COLUMN', N'entered_by_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Entered at', N'SCHEMA', N'svc', N'TABLE', N'oem_call_reference', N'COLUMN', N'entered_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Verified by back office', N'SCHEMA', N'svc', N'TABLE', N'oem_call_reference', N'COLUMN', N'verified_by_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Verified at', N'SCHEMA', N'svc', N'TABLE', N'oem_call_reference', N'COLUMN', N'verified_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Sync status Allowed: Manual, Pending, Synced, Failed.', N'SCHEMA', N'svc', N'TABLE', N'oem_call_reference', N'COLUMN', N'sync_status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Last sync attempt', N'SCHEMA', N'svc', N'TABLE', N'oem_call_reference', N'COLUMN', N'last_sync_log_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Each visit to site for a call (inspection, repair, parts fitment...).', N'SCHEMA', N'svc', N'TABLE', N'service_visit';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Call', N'SCHEMA', N'svc', N'TABLE', N'service_visit', N'COLUMN', N'service_call_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'1, 2, 3...', N'SCHEMA', N'svc', N'TABLE', N'service_visit', N'COLUMN', N'visit_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Device ID', N'SCHEMA', N'svc', N'TABLE', N'service_visit', N'COLUMN', N'client_uuid';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Purpose Allowed: Inspection, Repair, Parts fitment, Periodic service, Follow up, Installation.', N'SCHEMA', N'svc', N'TABLE', N'service_visit', N'COLUMN', N'visit_purpose';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Engineer', N'SCHEMA', N'svc', N'TABLE', N'service_visit', N'COLUMN', N'engineer_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Planned date', N'SCHEMA', N'svc', N'TABLE', N'service_visit', N'COLUMN', N'planned_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Engineer called customer', N'SCHEMA', N'svc', N'TABLE', N'service_visit', N'COLUMN', N'customer_contacted_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Planned, On the way, On site, Completed, Cancelled.', N'SCHEMA', N'svc', N'TABLE', N'service_visit', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Start service', N'SCHEMA', N'svc', N'TABLE', N'service_visit', N'COLUMN', N'service_started_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'End service', N'SCHEMA', N'svc', N'TABLE', N'service_visit', N'COLUMN', N'service_ended_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Location at start', N'SCHEMA', N'svc', N'TABLE', N'service_visit', N'COLUMN', N'site_latitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Location at start', N'SCHEMA', N'svc', N'TABLE', N'service_visit', N'COLUMN', N'site_longitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Next step Allowed: None, Parts required, Revisit, Escalate.', N'SCHEMA', N'svc', N'TABLE', N'service_visit', N'COLUMN', N'next_action';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Remarks', N'SCHEMA', N'svc', N'TABLE', N'service_visit', N'COLUMN', N'remarks';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Engineer''s trip for a visit: start, end, route, km, time.', N'SCHEMA', N'svc', N'TABLE', N'trip';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Visit', N'SCHEMA', N'svc', N'TABLE', N'trip', N'COLUMN', N'service_visit_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Engineer', N'SCHEMA', N'svc', N'TABLE', N'trip', N'COLUMN', N'engineer_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Device ID', N'SCHEMA', N'svc', N'TABLE', N'trip', N'COLUMN', N'client_uuid';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Trip type Allowed: To site, Return, Site to site.', N'SCHEMA', N'svc', N'TABLE', N'trip', N'COLUMN', N'trip_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Start trip', N'SCHEMA', N'svc', N'TABLE', N'trip', N'COLUMN', N'start_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Start point', N'SCHEMA', N'svc', N'TABLE', N'trip', N'COLUMN', N'start_latitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Start point', N'SCHEMA', N'svc', N'TABLE', N'trip', N'COLUMN', N'start_longitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'End trip', N'SCHEMA', N'svc', N'TABLE', N'trip', N'COLUMN', N'end_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'End point', N'SCHEMA', N'svc', N'TABLE', N'trip', N'COLUMN', N'end_latitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'End point', N'SCHEMA', N'svc', N'TABLE', N'trip', N'COLUMN', N'end_longitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Distance from GPS points', N'SCHEMA', N'svc', N'TABLE', N'trip', N'COLUMN', N'gps_distance_km';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Distance from Maps API', N'SCHEMA', N'svc', N'TABLE', N'trip', N'COLUMN', N'map_distance_km';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Travel time', N'SCHEMA', N'svc', N'TABLE', N'trip', N'COLUMN', N'duration_minutes';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Vehicle Allowed: Own bike, Own car, Company vehicle, Public transport.', N'SCHEMA', N'svc', N'TABLE', N'trip', N'COLUMN', N'vehicle_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: In progress, Completed, Auto closed.', N'SCHEMA', N'svc', N'TABLE', N'trip', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Encoded route', N'SCHEMA', N'svc', N'TABLE', N'trip', N'COLUMN', N'route_polyline';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GPS points during a trip. Very high volume: partition by month.', N'SCHEMA', N'svc', N'TABLE', N'trip_gps_point';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Trip', N'SCHEMA', N'svc', N'TABLE', N'trip_gps_point', N'COLUMN', N'trip_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Time', N'SCHEMA', N'svc', N'TABLE', N'trip_gps_point', N'COLUMN', N'recorded_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Latitude', N'SCHEMA', N'svc', N'TABLE', N'trip_gps_point', N'COLUMN', N'latitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Longitude', N'SCHEMA', N'svc', N'TABLE', N'trip_gps_point', N'COLUMN', N'longitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Accuracy', N'SCHEMA', N'svc', N'TABLE', N'trip_gps_point', N'COLUMN', N'accuracy_m';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Speed', N'SCHEMA', N'svc', N'TABLE', N'trip_gps_point', N'COLUMN', N'speed_kmph';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Phone battery', N'SCHEMA', N'svc', N'TABLE', N'trip_gps_point', N'COLUMN', N'battery_pct';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Fake-GPS detected', N'SCHEMA', N'svc', N'TABLE', N'trip_gps_point', N'COLUMN', N'is_mock_location';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Daily duty on / off for engineers (GPS runs only on duty).', N'SCHEMA', N'svc', N'TABLE', N'engineer_duty_log';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Engineer', N'SCHEMA', N'svc', N'TABLE', N'engineer_duty_log', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'svc', N'TABLE', N'engineer_duty_log', N'COLUMN', N'duty_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Device ID', N'SCHEMA', N'svc', N'TABLE', N'engineer_duty_log', N'COLUMN', N'client_uuid';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Duty on', N'SCHEMA', N'svc', N'TABLE', N'engineer_duty_log', N'COLUMN', N'duty_on_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Location', N'SCHEMA', N'svc', N'TABLE', N'engineer_duty_log', N'COLUMN', N'duty_on_latitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Location', N'SCHEMA', N'svc', N'TABLE', N'engineer_duty_log', N'COLUMN', N'duty_on_longitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Duty off', N'SCHEMA', N'svc', N'TABLE', N'engineer_duty_log', N'COLUMN', N'duty_off_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Location', N'SCHEMA', N'svc', N'TABLE', N'engineer_duty_log', N'COLUMN', N'duty_off_latitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Location', N'SCHEMA', N'svc', N'TABLE', N'engineer_duty_log', N'COLUMN', N'duty_off_longitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Km for the day', N'SCHEMA', N'svc', N'TABLE', N'engineer_duty_log', N'COLUMN', N'total_km';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Calls attended', N'SCHEMA', N'svc', N'TABLE', N'engineer_duty_log', N'COLUMN', N'calls_attended';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Service report submitted at the end of a visit.', N'SCHEMA', N'svc', N'TABLE', N'service_report';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Visit', N'SCHEMA', N'svc', N'TABLE', N'service_report', N'COLUMN', N'service_visit_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Report number', N'SCHEMA', N'svc', N'TABLE', N'service_report', N'COLUMN', N'report_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Device ID', N'SCHEMA', N'svc', N'TABLE', N'service_report', N'COLUMN', N'client_uuid';
EXEC sys.sp_addextendedproperty N'MS_Description', N'HMR at visit', N'SCHEMA', N'svc', N'TABLE', N'service_report', N'COLUMN', N'hmr_reading';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Condition', N'SCHEMA', N'svc', N'TABLE', N'service_report', N'COLUMN', N'machine_condition_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Complaint observed', N'SCHEMA', N'svc', N'TABLE', N'service_report', N'COLUMN', N'complaint_observed';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Findings', N'SCHEMA', N'svc', N'TABLE', N'service_report', N'COLUMN', N'findings';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Failure / root-cause code', N'SCHEMA', N'svc', N'TABLE', N'service_report', N'COLUMN', N'failure_code_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Action taken', N'SCHEMA', N'svc', N'TABLE', N'service_report', N'COLUMN', N'action_taken';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Parts needed', N'SCHEMA', N'svc', N'TABLE', N'service_report', N'COLUMN', N'is_parts_required';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Labour hours', N'SCHEMA', N'svc', N'TABLE', N'service_report', N'COLUMN', N'labour_hours';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Recommendations', N'SCHEMA', N'svc', N'TABLE', N'service_report', N'COLUMN', N'recommendations';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer name', N'SCHEMA', N'svc', N'TABLE', N'service_report', N'COLUMN', N'customer_signed_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer mobile', N'SCHEMA', N'svc', N'TABLE', N'service_report', N'COLUMN', N'customer_signed_mobile';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer signature', N'SCHEMA', N'svc', N'TABLE', N'service_report', N'COLUMN', N'customer_signature_attachment_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'OTP confirmed by customer', N'SCHEMA', N'svc', N'TABLE', N'service_report', N'COLUMN', N'is_closure_otp_verified';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Engineer signature', N'SCHEMA', N'svc', N'TABLE', N'service_report', N'COLUMN', N'engineer_signature_attachment_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Generated PDF', N'SCHEMA', N'svc', N'TABLE', N'service_report', N'COLUMN', N'pdf_attachment_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Submitted', N'SCHEMA', N'svc', N'TABLE', N'service_report', N'COLUMN', N'submitted_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Saved offline, synced later', N'SCHEMA', N'svc', N'TABLE', N'service_report', N'COLUMN', N'is_offline_submitted';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Checklist answers in a service report.', N'SCHEMA', N'svc', N'TABLE', N'report_checklist_item';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Report', N'SCHEMA', N'svc', N'TABLE', N'report_checklist_item', N'COLUMN', N'service_report_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Question', N'SCHEMA', N'svc', N'TABLE', N'report_checklist_item', N'COLUMN', N'checklist_template_item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Question text (copied)', N'SCHEMA', N'svc', N'TABLE', N'report_checklist_item', N'COLUMN', N'item_text';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Answer', N'SCHEMA', N'svc', N'TABLE', N'report_checklist_item', N'COLUMN', N'response_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'OK / Not OK', N'SCHEMA', N'svc', N'TABLE', N'report_checklist_item', N'COLUMN', N'is_ok';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Remarks', N'SCHEMA', N'svc', N'TABLE', N'report_checklist_item', N'COLUMN', N'remarks';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Photo', N'SCHEMA', N'svc', N'TABLE', N'report_checklist_item', N'COLUMN', N'photo_attachment_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Parts needed for a call. Captured in Phase 1; issued from stock in Phase 2.', N'SCHEMA', N'svc', N'TABLE', N'service_part_request';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Call', N'SCHEMA', N'svc', N'TABLE', N'service_part_request', N'COLUMN', N'service_call_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Visit', N'SCHEMA', N'svc', N'TABLE', N'service_part_request', N'COLUMN', N'service_visit_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Part', N'SCHEMA', N'svc', N'TABLE', N'service_part_request', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Description if part unknown', N'SCHEMA', N'svc', N'TABLE', N'service_part_request', N'COLUMN', N'part_description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Quantity', N'SCHEMA', N'svc', N'TABLE', N'service_part_request', N'COLUMN', N'quantity';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Unit', N'SCHEMA', N'svc', N'TABLE', N'service_part_request', N'COLUMN', N'uom_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Charged to customer', N'SCHEMA', N'svc', N'TABLE', N'service_part_request', N'COLUMN', N'is_chargeable';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Requested, Approved, Reserved, Issued, Fitted, Returned, Cancelled.', N'SCHEMA', N'svc', N'TABLE', N'service_part_request', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Requested by', N'SCHEMA', N'svc', N'TABLE', N'service_part_request', N'COLUMN', N'requested_by_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Needed by', N'SCHEMA', N'svc', N'TABLE', N'service_part_request', N'COLUMN', N'required_by_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Reservation (Phase 2)', N'SCHEMA', N'svc', N'TABLE', N'service_part_request', N'COLUMN', N'stock_reservation_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Chargeable items on a call, billed in Phase 4.', N'SCHEMA', N'svc', N'TABLE', N'service_charge';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Call', N'SCHEMA', N'svc', N'TABLE', N'service_charge', N'COLUMN', N'service_call_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Labour, Travel, Parts, Other.', N'SCHEMA', N'svc', N'TABLE', N'service_charge', N'COLUMN', N'charge_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Description', N'SCHEMA', N'svc', N'TABLE', N'service_charge', N'COLUMN', N'description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Quantity', N'SCHEMA', N'svc', N'TABLE', N'service_charge', N'COLUMN', N'quantity';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Rate', N'SCHEMA', N'svc', N'TABLE', N'service_charge', N'COLUMN', N'rate';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Amount', N'SCHEMA', N'svc', N'TABLE', N'service_charge', N'COLUMN', N'amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Bill to customer', N'SCHEMA', N'svc', N'TABLE', N'service_charge', N'COLUMN', N'is_billable';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Invoice (Phase 4)', N'SCHEMA', N'svc', N'TABLE', N'service_charge', N'COLUMN', N'sales_invoice_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Response and closure targets per brand (default 24 hours).', N'SCHEMA', N'svc', N'TABLE', N'sla_rule';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company', N'SCHEMA', N'svc', N'TABLE', N'sla_rule', N'COLUMN', N'company_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand (blank = all brands)', N'SCHEMA', N'svc', N'TABLE', N'sla_rule', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Call type (blank = all)', N'SCHEMA', N'svc', N'TABLE', N'sla_rule', N'COLUMN', N'call_type_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Priority Allowed: Critical, High, Normal, Low.', N'SCHEMA', N'svc', N'TABLE', N'sla_rule', N'COLUMN', N'priority';
EXEC sys.sp_addextendedproperty N'MS_Description', N'First contact within', N'SCHEMA', N'svc', N'TABLE', N'sla_rule', N'COLUMN', N'response_hours';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Close within', N'SCHEMA', N'svc', N'TABLE', N'sla_rule', N'COLUMN', N'resolution_hours';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Clock Allowed: Calendar, Working hours.', N'SCHEMA', N'svc', N'TABLE', N'sla_rule', N'COLUMN', N'clock_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Warn before breach', N'SCHEMA', N'svc', N'TABLE', N'sla_rule', N'COLUMN', N'alert_before_minutes';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Escalate to', N'SCHEMA', N'svc', N'TABLE', N'sla_rule', N'COLUMN', N'escalate_to_role_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Warnings, breaches and escalations raised on calls.', N'SCHEMA', N'svc', N'TABLE', N'sla_event';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Call', N'SCHEMA', N'svc', N'TABLE', N'sla_event', N'COLUMN', N'service_call_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Rule', N'SCHEMA', N'svc', N'TABLE', N'sla_event', N'COLUMN', N'sla_rule_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Event Allowed: Warning, Breached, Escalated.', N'SCHEMA', N'svc', N'TABLE', N'sla_event', N'COLUMN', N'event_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'When', N'SCHEMA', N'svc', N'TABLE', N'sla_event', N'COLUMN', N'event_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Notified', N'SCHEMA', N'svc', N'TABLE', N'sla_event', N'COLUMN', N'notified_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Warranty claim to the OEM for a failed part.', N'SCHEMA', N'svc', N'TABLE', N'warranty_claim';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Claim number', N'SCHEMA', N'svc', N'TABLE', N'warranty_claim', N'COLUMN', N'claim_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand (OEM the claim goes to)', N'SCHEMA', N'svc', N'TABLE', N'warranty_claim', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Call', N'SCHEMA', N'svc', N'TABLE', N'warranty_claim', N'COLUMN', N'service_call_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Machine', N'SCHEMA', N'svc', N'TABLE', N'warranty_claim', N'COLUMN', N'machine_unit_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Failure code', N'SCHEMA', N'svc', N'TABLE', N'warranty_claim', N'COLUMN', N'failure_code_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Claim date', N'SCHEMA', N'svc', N'TABLE', N'warranty_claim', N'COLUMN', N'claim_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Claimed', N'SCHEMA', N'svc', N'TABLE', N'warranty_claim', N'COLUMN', N'claimed_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Approved', N'SCHEMA', N'svc', N'TABLE', N'warranty_claim', N'COLUMN', N'approved_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Submitted, Approved, Rejected, Settled.', N'SCHEMA', N'svc', N'TABLE', N'warranty_claim', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Claim ref in the OEM portal', N'SCHEMA', N'svc', N'TABLE', N'warranty_claim', N'COLUMN', N'oem_claim_ref';
EXEC sys.sp_addextendedproperty N'MS_Description', N'OEM credit note', N'SCHEMA', N'svc', N'TABLE', N'warranty_claim', N'COLUMN', N'credit_note_ref';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Parts in a warranty claim.', N'SCHEMA', N'svc', N'TABLE', N'warranty_claim_part';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Claim', N'SCHEMA', N'svc', N'TABLE', N'warranty_claim_part', N'COLUMN', N'warranty_claim_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Part', N'SCHEMA', N'svc', N'TABLE', N'warranty_claim_part', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Qty', N'SCHEMA', N'svc', N'TABLE', N'warranty_claim_part', N'COLUMN', N'quantity';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Failed part serial', N'SCHEMA', N'svc', N'TABLE', N'warranty_claim_part', N'COLUMN', N'failed_part_serial';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Sent back', N'SCHEMA', N'svc', N'TABLE', N'warranty_claim_part', N'COLUMN', N'is_returned_to_oem';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Courier docket', N'SCHEMA', N'svc', N'TABLE', N'warranty_claim_part', N'COLUMN', N'return_docket_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Movement classes: Fast / Slow / Non-moving (FSN) or ABC.', N'SCHEMA', N'inv', N'TABLE', N'movement_class';
EXEC sys.sp_addextendedproperty N'MS_Description', N'e.g. F, S, N', N'SCHEMA', N'inv', N'TABLE', N'movement_class', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name', N'SCHEMA', N'inv', N'TABLE', N'movement_class', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'How assigned', N'SCHEMA', N'inv', N'TABLE', N'movement_class', N'COLUMN', N'criteria';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Threshold', N'SCHEMA', N'inv', N'TABLE', N'movement_class', N'COLUMN', N'min_issues_per_year';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Rack/shelf position inside a location.', N'SCHEMA', N'inv', N'TABLE', N'bin';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Location', N'SCHEMA', N'inv', N'TABLE', N'bin', N'COLUMN', N'location_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Bin code', N'SCHEMA', N'inv', N'TABLE', N'bin', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Rack', N'SCHEMA', N'inv', N'TABLE', N'bin', N'COLUMN', N'rack';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Shelf', N'SCHEMA', N'inv', N'TABLE', N'bin', N'COLUMN', N'shelf';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Notes', N'SCHEMA', N'inv', N'TABLE', N'bin', N'COLUMN', N'description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Types of stock movement.', N'SCHEMA', N'inv', N'TABLE', N'movement_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'e.g. GRN, ISSUE, TRANSFER_OUT', N'SCHEMA', N'inv', N'TABLE', N'movement_type', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name', N'SCHEMA', N'inv', N'TABLE', N'movement_type', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'In or out Allowed: In, Out.', N'SCHEMA', N'inv', N'TABLE', N'movement_type', N'COLUMN', N'direction';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Changes average cost', N'SCHEMA', N'inv', N'TABLE', N'movement_type', N'COLUMN', N'affects_cost';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Current quantity per item, location and bin.', N'SCHEMA', N'inv', N'TABLE', N'stock_balance';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'inv', N'TABLE', N'stock_balance', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Location', N'SCHEMA', N'inv', N'TABLE', N'stock_balance', N'COLUMN', N'location_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Bin', N'SCHEMA', N'inv', N'TABLE', N'stock_balance', N'COLUMN', N'bin_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'On hand', N'SCHEMA', N'inv', N'TABLE', N'stock_balance', N'COLUMN', N'qty_on_hand';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Reserved', N'SCHEMA', N'inv', N'TABLE', N'stock_balance', N'COLUMN', N'qty_reserved';
EXEC sys.sp_addextendedproperty N'MS_Description', N'In transit', N'SCHEMA', N'inv', N'TABLE', N'stock_balance', N'COLUMN', N'qty_in_transit';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Weighted average cost', N'SCHEMA', N'inv', N'TABLE', N'stock_balance', N'COLUMN', N'avg_cost';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Last movement', N'SCHEMA', N'inv', N'TABLE', N'stock_balance', N'COLUMN', N'last_movement_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Serial or batch number of a stock item.', N'SCHEMA', N'inv', N'TABLE', N'serial_batch';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'inv', N'TABLE', N'serial_batch', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Serial / batch', N'SCHEMA', N'inv', N'TABLE', N'serial_batch', N'COLUMN', N'serial_or_batch_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Serial, Batch.', N'SCHEMA', N'inv', N'TABLE', N'serial_batch', N'COLUMN', N'tracking_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Mfg date', N'SCHEMA', N'inv', N'TABLE', N'serial_batch', N'COLUMN', N'manufacture_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Expiry (lubricants)', N'SCHEMA', N'inv', N'TABLE', N'serial_batch', N'COLUMN', N'expiry_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Where now', N'SCHEMA', N'inv', N'TABLE', N'serial_batch', N'COLUMN', N'current_location_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: In stock, Reserved, Issued, Sold, Returned, Scrapped.', N'SCHEMA', N'inv', N'TABLE', N'serial_batch', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Received on', N'SCHEMA', N'inv', N'TABLE', N'serial_batch', N'COLUMN', N'grn_line_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Stock ledger: every quantity change. Insert only.', N'SCHEMA', N'inv', N'TABLE', N'stock_move';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company', N'SCHEMA', N'inv', N'TABLE', N'stock_move', N'COLUMN', N'company_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'When', N'SCHEMA', N'inv', N'TABLE', N'stock_move', N'COLUMN', N'move_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type', N'SCHEMA', N'inv', N'TABLE', N'stock_move', N'COLUMN', N'movement_type_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'inv', N'TABLE', N'stock_move', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Location', N'SCHEMA', N'inv', N'TABLE', N'stock_move', N'COLUMN', N'location_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Bin', N'SCHEMA', N'inv', N'TABLE', N'stock_move', N'COLUMN', N'bin_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Serial / batch', N'SCHEMA', N'inv', N'TABLE', N'stock_move', N'COLUMN', N'serial_batch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'+ in / - out', N'SCHEMA', N'inv', N'TABLE', N'stock_move', N'COLUMN', N'quantity';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Cost per unit', N'SCHEMA', N'inv', N'TABLE', N'stock_move', N'COLUMN', N'unit_cost';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Stock value change', N'SCHEMA', N'inv', N'TABLE', N'stock_move', N'COLUMN', N'value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'e.g. GRN, STOCK_ISSUE', N'SCHEMA', N'inv', N'TABLE', N'stock_move', N'COLUMN', N'source_document_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Document ID', N'SCHEMA', N'inv', N'TABLE', N'stock_move', N'COLUMN', N'source_document_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Line ID', N'SCHEMA', N'inv', N'TABLE', N'stock_move', N'COLUMN', N'source_line_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Document number', N'SCHEMA', N'inv', N'TABLE', N'stock_move', N'COLUMN', N'reference';
EXEC sys.sp_addextendedproperty N'MS_Description', N'By', N'SCHEMA', N'inv', N'TABLE', N'stock_move', N'COLUMN', N'performed_by_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Receipt layers for FIFO valuation (if FIFO is chosen).', N'SCHEMA', N'inv', N'TABLE', N'cost_layer';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'inv', N'TABLE', N'cost_layer', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Location', N'SCHEMA', N'inv', N'TABLE', N'cost_layer', N'COLUMN', N'location_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Receipt move', N'SCHEMA', N'inv', N'TABLE', N'cost_layer', N'COLUMN', N'stock_move_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Received', N'SCHEMA', N'inv', N'TABLE', N'cost_layer', N'COLUMN', N'received_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Qty received', N'SCHEMA', N'inv', N'TABLE', N'cost_layer', N'COLUMN', N'qty_received';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Qty left', N'SCHEMA', N'inv', N'TABLE', N'cost_layer', N'COLUMN', N'qty_remaining';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Cost', N'SCHEMA', N'inv', N'TABLE', N'cost_layer', N'COLUMN', N'unit_cost';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Barcodes for an item, incl. pack barcodes.', N'SCHEMA', N'inv', N'TABLE', N'item_barcode';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'inv', N'TABLE', N'item_barcode', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Barcode', N'SCHEMA', N'inv', N'TABLE', N'item_barcode', N'COLUMN', N'barcode';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Symbology Allowed: EAN13, Code128, QR.', N'SCHEMA', N'inv', N'TABLE', N'item_barcode', N'COLUMN', N'barcode_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Units per scan', N'SCHEMA', N'inv', N'TABLE', N'item_barcode', N'COLUMN', N'pack_qty';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Stock held for a service call or sales order.', N'SCHEMA', N'inv', N'TABLE', N'stock_reservation';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'inv', N'TABLE', N'stock_reservation', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Location', N'SCHEMA', N'inv', N'TABLE', N'stock_reservation', N'COLUMN', N'location_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Qty', N'SCHEMA', N'inv', N'TABLE', N'stock_reservation', N'COLUMN', N'quantity';
EXEC sys.sp_addextendedproperty N'MS_Description', N'For Allowed: Service call, Sales order.', N'SCHEMA', N'inv', N'TABLE', N'stock_reservation', N'COLUMN', N'reserved_for_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Call', N'SCHEMA', N'inv', N'TABLE', N'stock_reservation', N'COLUMN', N'service_call_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Order', N'SCHEMA', N'inv', N'TABLE', N'stock_reservation', N'COLUMN', N'sales_order_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'By', N'SCHEMA', N'inv', N'TABLE', N'stock_reservation', N'COLUMN', N'reserved_by_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Until', N'SCHEMA', N'inv', N'TABLE', N'stock_reservation', N'COLUMN', N'reserved_until';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Active, Consumed, Released.', N'SCHEMA', N'inv', N'TABLE', N'stock_reservation', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Parts issued from a warehouse to a service call or engineer (branches hold no stock).', N'SCHEMA', N'inv', N'TABLE', N'stock_issue';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Issue number', N'SCHEMA', N'inv', N'TABLE', N'stock_issue', N'COLUMN', N'issue_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'inv', N'TABLE', N'stock_issue', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'inv', N'TABLE', N'stock_issue', N'COLUMN', N'issue_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Service, Internal, Sample.', N'SCHEMA', N'inv', N'TABLE', N'stock_issue', N'COLUMN', N'issue_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand (blank = common items only)', N'SCHEMA', N'inv', N'TABLE', N'stock_issue', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Call', N'SCHEMA', N'inv', N'TABLE', N'stock_issue', N'COLUMN', N'service_call_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Engineer', N'SCHEMA', N'inv', N'TABLE', N'stock_issue', N'COLUMN', N'issued_to_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Warehouse location issued from (any warehouse)', N'SCHEMA', N'inv', N'TABLE', N'stock_issue', N'COLUMN', N'from_location_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Issued, Cancelled.', N'SCHEMA', N'inv', N'TABLE', N'stock_issue', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Parts in an issue.', N'SCHEMA', N'inv', N'TABLE', N'stock_issue_line';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Issue', N'SCHEMA', N'inv', N'TABLE', N'stock_issue_line', N'COLUMN', N'stock_issue_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'inv', N'TABLE', N'stock_issue_line', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Serial / batch', N'SCHEMA', N'inv', N'TABLE', N'stock_issue_line', N'COLUMN', N'serial_batch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Qty', N'SCHEMA', N'inv', N'TABLE', N'stock_issue_line', N'COLUMN', N'quantity';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Cost', N'SCHEMA', N'inv', N'TABLE', N'stock_issue_line', N'COLUMN', N'unit_cost';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Part request', N'SCHEMA', N'inv', N'TABLE', N'stock_issue_line', N'COLUMN', N'service_part_request_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Defective parts returned from the field.', N'SCHEMA', N'inv', N'TABLE', N'defective_return';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Number', N'SCHEMA', N'inv', N'TABLE', N'defective_return', N'COLUMN', N'return_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Call', N'SCHEMA', N'inv', N'TABLE', N'defective_return', N'COLUMN', N'service_call_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Claim', N'SCHEMA', N'inv', N'TABLE', N'defective_return', N'COLUMN', N'warranty_claim_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Part', N'SCHEMA', N'inv', N'TABLE', N'defective_return', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Serial', N'SCHEMA', N'inv', N'TABLE', N'defective_return', N'COLUMN', N'serial_batch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Qty', N'SCHEMA', N'inv', N'TABLE', N'defective_return', N'COLUMN', N'quantity';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Received at', N'SCHEMA', N'inv', N'TABLE', N'defective_return', N'COLUMN', N'received_location_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'When', N'SCHEMA', N'inv', N'TABLE', N'defective_return', N'COLUMN', N'received_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'What happens Allowed: Return to OEM, Scrap, Repair, Pending.', N'SCHEMA', N'inv', N'TABLE', N'defective_return', N'COLUMN', N'disposition';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Transfer between warehouses (same GSTIN, so delivery challan + e-way bill).', N'SCHEMA', N'inv', N'TABLE', N'stock_transfer';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Number', N'SCHEMA', N'inv', N'TABLE', N'stock_transfer', N'COLUMN', N'transfer_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'From', N'SCHEMA', N'inv', N'TABLE', N'stock_transfer', N'COLUMN', N'from_location_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'To', N'SCHEMA', N'inv', N'TABLE', N'stock_transfer', N'COLUMN', N'to_location_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'inv', N'TABLE', N'stock_transfer', N'COLUMN', N'transfer_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Dispatched, Received, Cancelled.', N'SCHEMA', N'inv', N'TABLE', N'stock_transfer', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Dispatched', N'SCHEMA', N'inv', N'TABLE', N'stock_transfer', N'COLUMN', N'dispatched_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Received', N'SCHEMA', N'inv', N'TABLE', N'stock_transfer', N'COLUMN', N'received_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'E-way bill', N'SCHEMA', N'inv', N'TABLE', N'stock_transfer', N'COLUMN', N'e_way_bill_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Items in a transfer.', N'SCHEMA', N'inv', N'TABLE', N'stock_transfer_line';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Transfer', N'SCHEMA', N'inv', N'TABLE', N'stock_transfer_line', N'COLUMN', N'stock_transfer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'inv', N'TABLE', N'stock_transfer_line', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Serial', N'SCHEMA', N'inv', N'TABLE', N'stock_transfer_line', N'COLUMN', N'serial_batch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Sent', N'SCHEMA', N'inv', N'TABLE', N'stock_transfer_line', N'COLUMN', N'qty_sent';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Received', N'SCHEMA', N'inv', N'TABLE', N'stock_transfer_line', N'COLUMN', N'qty_received';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Stock corrections with approval.', N'SCHEMA', N'inv', N'TABLE', N'stock_adjustment';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Number', N'SCHEMA', N'inv', N'TABLE', N'stock_adjustment', N'COLUMN', N'adjustment_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Location', N'SCHEMA', N'inv', N'TABLE', N'stock_adjustment', N'COLUMN', N'location_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'inv', N'TABLE', N'stock_adjustment', N'COLUMN', N'adjustment_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Reason', N'SCHEMA', N'inv', N'TABLE', N'stock_adjustment', N'COLUMN', N'reason_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'From stock count', N'SCHEMA', N'inv', N'TABLE', N'stock_adjustment', N'COLUMN', N'stock_count_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Pending approval, Posted, Rejected.', N'SCHEMA', N'inv', N'TABLE', N'stock_adjustment', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Lines of an adjustment.', N'SCHEMA', N'inv', N'TABLE', N'stock_adjustment_line';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Adjustment', N'SCHEMA', N'inv', N'TABLE', N'stock_adjustment_line', N'COLUMN', N'stock_adjustment_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'inv', N'TABLE', N'stock_adjustment_line', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Bin', N'SCHEMA', N'inv', N'TABLE', N'stock_adjustment_line', N'COLUMN', N'bin_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Serial', N'SCHEMA', N'inv', N'TABLE', N'stock_adjustment_line', N'COLUMN', N'serial_batch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'+ / -', N'SCHEMA', N'inv', N'TABLE', N'stock_adjustment_line', N'COLUMN', N'qty_change';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Cost', N'SCHEMA', N'inv', N'TABLE', N'stock_adjustment_line', N'COLUMN', N'unit_cost';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Remarks', N'SCHEMA', N'inv', N'TABLE', N'stock_adjustment_line', N'COLUMN', N'remarks';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Physical stock count (full or cycle).', N'SCHEMA', N'inv', N'TABLE', N'stock_count';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Number', N'SCHEMA', N'inv', N'TABLE', N'stock_count', N'COLUMN', N'count_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Location', N'SCHEMA', N'inv', N'TABLE', N'stock_count', N'COLUMN', N'location_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'inv', N'TABLE', N'stock_count', N'COLUMN', N'count_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Full, Cycle.', N'SCHEMA', N'inv', N'TABLE', N'stock_count', N'COLUMN', N'count_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Open, Counted, Adjusted, Cancelled.', N'SCHEMA', N'inv', N'TABLE', N'stock_count', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Counted quantities.', N'SCHEMA', N'inv', N'TABLE', N'stock_count_line';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Count', N'SCHEMA', N'inv', N'TABLE', N'stock_count_line', N'COLUMN', N'stock_count_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'inv', N'TABLE', N'stock_count_line', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Bin', N'SCHEMA', N'inv', N'TABLE', N'stock_count_line', N'COLUMN', N'bin_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'System qty', N'SCHEMA', N'inv', N'TABLE', N'stock_count_line', N'COLUMN', N'system_qty';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Counted qty', N'SCHEMA', N'inv', N'TABLE', N'stock_count_line', N'COLUMN', N'counted_qty';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Counted by', N'SCHEMA', N'inv', N'TABLE', N'stock_count_line', N'COLUMN', N'counted_by_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier prices and part numbers for items.', N'SCHEMA', N'pur', N'TABLE', N'supplier_item_price';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier', N'SCHEMA', N'pur', N'TABLE', N'supplier_item_price', N'COLUMN', N'supplier_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'pur', N'TABLE', N'supplier_item_price', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier part no.', N'SCHEMA', N'pur', N'TABLE', N'supplier_item_price', N'COLUMN', N'supplier_part_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier unit', N'SCHEMA', N'pur', N'TABLE', N'supplier_item_price', N'COLUMN', N'supplier_uom';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier unit to stock unit', N'SCHEMA', N'pur', N'TABLE', N'supplier_item_price', N'COLUMN', N'conversion_factor';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Price', N'SCHEMA', N'pur', N'TABLE', N'supplier_item_price', N'COLUMN', N'price';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Currency', N'SCHEMA', N'pur', N'TABLE', N'supplier_item_price', N'COLUMN', N'currency_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'From', N'SCHEMA', N'pur', N'TABLE', N'supplier_item_price', N'COLUMN', N'valid_from';
EXEC sys.sp_addextendedproperty N'MS_Description', N'To', N'SCHEMA', N'pur', N'TABLE', N'supplier_item_price', N'COLUMN', N'valid_to';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Lead time', N'SCHEMA', N'pur', N'TABLE', N'supplier_item_price', N'COLUMN', N'lead_time_days';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Internal request to buy (reorder, service need, manual).', N'SCHEMA', N'pur', N'TABLE', N'purchase_request';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Number', N'SCHEMA', N'pur', N'TABLE', N'purchase_request', N'COLUMN', N'pr_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'pur', N'TABLE', N'purchase_request', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand (blank = common items)', N'SCHEMA', N'pur', N'TABLE', N'purchase_request', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Requested by', N'SCHEMA', N'pur', N'TABLE', N'purchase_request', N'COLUMN', N'requested_by_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'pur', N'TABLE', N'purchase_request', N'COLUMN', N'request_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Needed by', N'SCHEMA', N'pur', N'TABLE', N'purchase_request', N'COLUMN', N'required_by';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Why Allowed: Reorder, Service call, Manual.', N'SCHEMA', N'pur', N'TABLE', N'purchase_request', N'COLUMN', N'source_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Call', N'SCHEMA', N'pur', N'TABLE', N'purchase_request', N'COLUMN', N'service_call_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Pending approval, Approved, Ordered, Rejected.', N'SCHEMA', N'pur', N'TABLE', N'purchase_request', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Items requested.', N'SCHEMA', N'pur', N'TABLE', N'purchase_request_line';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Request', N'SCHEMA', N'pur', N'TABLE', N'purchase_request_line', N'COLUMN', N'purchase_request_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'pur', N'TABLE', N'purchase_request_line', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Qty', N'SCHEMA', N'pur', N'TABLE', N'purchase_request_line', N'COLUMN', N'quantity';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Remarks', N'SCHEMA', N'pur', N'TABLE', N'purchase_request_line', N'COLUMN', N'remarks';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Purchase order to a supplier.', N'SCHEMA', N'pur', N'TABLE', N'purchase_order';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PO number', N'SCHEMA', N'pur', N'TABLE', N'purchase_order', N'COLUMN', N'po_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company', N'SCHEMA', N'pur', N'TABLE', N'purchase_order', N'COLUMN', N'company_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'pur', N'TABLE', N'purchase_order', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier', N'SCHEMA', N'pur', N'TABLE', N'purchase_order', N'COLUMN', N'supplier_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand (blank = common items from non-OEM supplier)', N'SCHEMA', N'pur', N'TABLE', N'purchase_order', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'pur', N'TABLE', N'purchase_order', N'COLUMN', N'po_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Expected', N'SCHEMA', N'pur', N'TABLE', N'purchase_order', N'COLUMN', N'expected_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Warehouse to deliver to', N'SCHEMA', N'pur', N'TABLE', N'purchase_order', N'COLUMN', N'delivery_location_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Terms', N'SCHEMA', N'pur', N'TABLE', N'purchase_order', N'COLUMN', N'payment_terms_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Place of supply', N'SCHEMA', N'pur', N'TABLE', N'purchase_order', N'COLUMN', N'place_of_supply_state_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Currency', N'SCHEMA', N'pur', N'TABLE', N'purchase_order', N'COLUMN', N'currency_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Before tax', N'SCHEMA', N'pur', N'TABLE', N'purchase_order', N'COLUMN', N'subtotal';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GST', N'SCHEMA', N'pur', N'TABLE', N'purchase_order', N'COLUMN', N'tax_total';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Total', N'SCHEMA', N'pur', N'TABLE', N'purchase_order', N'COLUMN', N'total';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Pending approval, Approved, Sent, Part received, Closed, Cancelled.', N'SCHEMA', N'pur', N'TABLE', N'purchase_order', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PO ref in the OEM portal', N'SCHEMA', N'pur', N'TABLE', N'purchase_order', N'COLUMN', N'oem_po_ref';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Remarks', N'SCHEMA', N'pur', N'TABLE', N'purchase_order', N'COLUMN', N'remarks';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PO lines.', N'SCHEMA', N'pur', N'TABLE', N'purchase_order_line';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PO', N'SCHEMA', N'pur', N'TABLE', N'purchase_order_line', N'COLUMN', N'purchase_order_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Line', N'SCHEMA', N'pur', N'TABLE', N'purchase_order_line', N'COLUMN', N'line_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'pur', N'TABLE', N'purchase_order_line', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Description', N'SCHEMA', N'pur', N'TABLE', N'purchase_order_line', N'COLUMN', N'description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Qty ordered', N'SCHEMA', N'pur', N'TABLE', N'purchase_order_line', N'COLUMN', N'quantity';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Unit', N'SCHEMA', N'pur', N'TABLE', N'purchase_order_line', N'COLUMN', N'uom_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Price', N'SCHEMA', N'pur', N'TABLE', N'purchase_order_line', N'COLUMN', N'unit_price';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Discount', N'SCHEMA', N'pur', N'TABLE', N'purchase_order_line', N'COLUMN', N'discount_pct';
EXEC sys.sp_addextendedproperty N'MS_Description', N'HSN', N'SCHEMA', N'pur', N'TABLE', N'purchase_order_line', N'COLUMN', N'hsn_sac_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GST rate', N'SCHEMA', N'pur', N'TABLE', N'purchase_order_line', N'COLUMN', N'gst_rate_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Taxable', N'SCHEMA', N'pur', N'TABLE', N'purchase_order_line', N'COLUMN', N'taxable_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Tax', N'SCHEMA', N'pur', N'TABLE', N'purchase_order_line', N'COLUMN', N'tax_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Total', N'SCHEMA', N'pur', N'TABLE', N'purchase_order_line', N'COLUMN', N'line_total';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Received', N'SCHEMA', N'pur', N'TABLE', N'purchase_order_line', N'COLUMN', N'qty_received';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Invoiced', N'SCHEMA', N'pur', N'TABLE', N'purchase_order_line', N'COLUMN', N'qty_invoiced';
EXEC sys.sp_addextendedproperty N'MS_Description', N'From request', N'SCHEMA', N'pur', N'TABLE', N'purchase_order_line', N'COLUMN', N'purchase_request_line_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Goods receipt note.', N'SCHEMA', N'pur', N'TABLE', N'grn';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GRN number', N'SCHEMA', N'pur', N'TABLE', N'grn', N'COLUMN', N'grn_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'pur', N'TABLE', N'grn', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier', N'SCHEMA', N'pur', N'TABLE', N'grn', N'COLUMN', N'supplier_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PO', N'SCHEMA', N'pur', N'TABLE', N'grn', N'COLUMN', N'purchase_order_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand', N'SCHEMA', N'pur', N'TABLE', N'grn', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'pur', N'TABLE', N'grn', N'COLUMN', N'grn_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Warehouse location received at', N'SCHEMA', N'pur', N'TABLE', N'grn', N'COLUMN', N'location_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier invoice no.', N'SCHEMA', N'pur', N'TABLE', N'grn', N'COLUMN', N'supplier_invoice_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier invoice date', N'SCHEMA', N'pur', N'TABLE', N'grn', N'COLUMN', N'supplier_invoice_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Vehicle', N'SCHEMA', N'pur', N'TABLE', N'grn', N'COLUMN', N'vehicle_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Lorry receipt', N'SCHEMA', N'pur', N'TABLE', N'grn', N'COLUMN', N'lr_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Posted, Cancelled.', N'SCHEMA', N'pur', N'TABLE', N'grn', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Items received.', N'SCHEMA', N'pur', N'TABLE', N'grn_line';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GRN', N'SCHEMA', N'pur', N'TABLE', N'grn_line', N'COLUMN', N'grn_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PO line', N'SCHEMA', N'pur', N'TABLE', N'grn_line', N'COLUMN', N'purchase_order_line_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'pur', N'TABLE', N'grn_line', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Received', N'SCHEMA', N'pur', N'TABLE', N'grn_line', N'COLUMN', N'qty_received';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Accepted', N'SCHEMA', N'pur', N'TABLE', N'grn_line', N'COLUMN', N'qty_accepted';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Rejected', N'SCHEMA', N'pur', N'TABLE', N'grn_line', N'COLUMN', N'qty_rejected';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Put-away bin', N'SCHEMA', N'pur', N'TABLE', N'grn_line', N'COLUMN', N'bin_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Cost', N'SCHEMA', N'pur', N'TABLE', N'grn_line', N'COLUMN', N'unit_cost';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Reason', N'SCHEMA', N'pur', N'TABLE', N'grn_line', N'COLUMN', N'rejection_reason';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier bill (accounts payable).', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Internal number', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'invoice_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier''s number', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'supplier_invoice_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier''s date', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'supplier_invoice_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'supplier_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PO', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'purchase_order_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GRN', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'grn_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Place of supply', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'place_of_supply_state_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'RCM', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'is_reverse_charge';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Taxable', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'taxable_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'CGST', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'cgst';
EXEC sys.sp_addextendedproperty N'MS_Description', N'SGST', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'sgst';
EXEC sys.sp_addextendedproperty N'MS_Description', N'IGST', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'igst';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Cess', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'cess';
EXEC sys.sp_addextendedproperty N'MS_Description', N'TDS', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'tds_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Round off', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'round_off';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Total', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'total';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Due', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'due_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Paid', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'amount_paid';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Posted, Part paid, Paid, Cancelled.', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Ledger posting', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'journal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Ref in the OEM portal', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice', N'COLUMN', N'oem_invoice_ref';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier bill lines.', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice_line';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Bill', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice_line', N'COLUMN', N'supplier_invoice_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GRN line', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice_line', N'COLUMN', N'grn_line_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PO line', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice_line', N'COLUMN', N'purchase_order_line_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice_line', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Expense account (non-stock)', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice_line', N'COLUMN', N'gl_account_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Description', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice_line', N'COLUMN', N'description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Qty', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice_line', N'COLUMN', N'quantity';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Price', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice_line', N'COLUMN', N'unit_price';
EXEC sys.sp_addextendedproperty N'MS_Description', N'HSN', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice_line', N'COLUMN', N'hsn_sac_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GST rate', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice_line', N'COLUMN', N'gst_rate_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Taxable', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice_line', N'COLUMN', N'taxable_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Tax', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice_line', N'COLUMN', N'tax_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Total', N'SCHEMA', N'pur', N'TABLE', N'supplier_invoice_line', N'COLUMN', N'line_total';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Payment made to a supplier.', N'SCHEMA', N'pur', N'TABLE', N'supplier_payment';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Number', N'SCHEMA', N'pur', N'TABLE', N'supplier_payment', N'COLUMN', N'payment_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier', N'SCHEMA', N'pur', N'TABLE', N'supplier_payment', N'COLUMN', N'supplier_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'pur', N'TABLE', N'supplier_payment', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'pur', N'TABLE', N'supplier_payment', N'COLUMN', N'payment_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Mode Allowed: NEFT, RTGS, Cheque, Cash, UPI.', N'SCHEMA', N'pur', N'TABLE', N'supplier_payment', N'COLUMN', N'payment_mode';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Paid from', N'SCHEMA', N'pur', N'TABLE', N'supplier_payment', N'COLUMN', N'bank_account_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Cheque', N'SCHEMA', N'pur', N'TABLE', N'supplier_payment', N'COLUMN', N'cheque_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'UTR / ref', N'SCHEMA', N'pur', N'TABLE', N'supplier_payment', N'COLUMN', N'reference_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Amount', N'SCHEMA', N'pur', N'TABLE', N'supplier_payment', N'COLUMN', N'amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'TDS', N'SCHEMA', N'pur', N'TABLE', N'supplier_payment', N'COLUMN', N'tds_deducted';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Posted, Cancelled.', N'SCHEMA', N'pur', N'TABLE', N'supplier_payment', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Ledger posting', N'SCHEMA', N'pur', N'TABLE', N'supplier_payment', N'COLUMN', N'journal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Purchase return / debit note to supplier.', N'SCHEMA', N'pur', N'TABLE', N'debit_note';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Number', N'SCHEMA', N'pur', N'TABLE', N'debit_note', N'COLUMN', N'debit_note_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier', N'SCHEMA', N'pur', N'TABLE', N'debit_note', N'COLUMN', N'supplier_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Against bill', N'SCHEMA', N'pur', N'TABLE', N'debit_note', N'COLUMN', N'supplier_invoice_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Against GRN', N'SCHEMA', N'pur', N'TABLE', N'debit_note', N'COLUMN', N'grn_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'pur', N'TABLE', N'debit_note', N'COLUMN', N'note_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Reason', N'SCHEMA', N'pur', N'TABLE', N'debit_note', N'COLUMN', N'reason_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Taxable', N'SCHEMA', N'pur', N'TABLE', N'debit_note', N'COLUMN', N'taxable_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Tax', N'SCHEMA', N'pur', N'TABLE', N'debit_note', N'COLUMN', N'tax_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Total', N'SCHEMA', N'pur', N'TABLE', N'debit_note', N'COLUMN', N'total';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Posted, Cancelled.', N'SCHEMA', N'pur', N'TABLE', N'debit_note', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Ledger posting', N'SCHEMA', N'pur', N'TABLE', N'debit_note', N'COLUMN', N'journal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Returned items.', N'SCHEMA', N'pur', N'TABLE', N'debit_note_line';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Debit note', N'SCHEMA', N'pur', N'TABLE', N'debit_note_line', N'COLUMN', N'debit_note_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'pur', N'TABLE', N'debit_note_line', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Serial', N'SCHEMA', N'pur', N'TABLE', N'debit_note_line', N'COLUMN', N'serial_batch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Qty', N'SCHEMA', N'pur', N'TABLE', N'debit_note_line', N'COLUMN', N'quantity';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Price', N'SCHEMA', N'pur', N'TABLE', N'debit_note_line', N'COLUMN', N'unit_price';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GST rate', N'SCHEMA', N'pur', N'TABLE', N'debit_note_line', N'COLUMN', N'gst_rate_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Tax', N'SCHEMA', N'pur', N'TABLE', N'debit_note_line', N'COLUMN', N'tax_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Total', N'SCHEMA', N'pur', N'TABLE', N'debit_note_line', N'COLUMN', N'line_total';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Matches payments and debit notes to supplier bills.', N'SCHEMA', N'pur', N'TABLE', N'supplier_allocation';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Bill', N'SCHEMA', N'pur', N'TABLE', N'supplier_allocation', N'COLUMN', N'supplier_invoice_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Payment', N'SCHEMA', N'pur', N'TABLE', N'supplier_allocation', N'COLUMN', N'supplier_payment_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Debit note', N'SCHEMA', N'pur', N'TABLE', N'supplier_allocation', N'COLUMN', N'debit_note_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Amount', N'SCHEMA', N'pur', N'TABLE', N'supplier_allocation', N'COLUMN', N'amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'pur', N'TABLE', N'supplier_allocation', N'COLUMN', N'allocated_on';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer credit status.', N'SCHEMA', N'sal', N'TABLE', N'credit_status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Code', N'SCHEMA', N'sal', N'TABLE', N'credit_status', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'e.g. Good, On hold', N'SCHEMA', N'sal', N'TABLE', N'credit_status', N'COLUMN', N'description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Block invoicing', N'SCHEMA', N'sal', N'TABLE', N'credit_status', N'COLUMN', N'disallow_invoicing';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Price lists (retail, dealer, government, service labour).', N'SCHEMA', N'sal', N'TABLE', N'price_list';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Code', N'SCHEMA', N'sal', N'TABLE', N'price_list', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name', N'SCHEMA', N'sal', N'TABLE', N'price_list', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand (blank = common)', N'SCHEMA', N'sal', N'TABLE', N'price_list', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Retail, Dealer, Government, Service labour.', N'SCHEMA', N'sal', N'TABLE', N'price_list', N'COLUMN', N'price_list_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Currency', N'SCHEMA', N'sal', N'TABLE', N'price_list', N'COLUMN', N'currency_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Prices include GST', N'SCHEMA', N'sal', N'TABLE', N'price_list', N'COLUMN', N'includes_tax';
EXEC sys.sp_addextendedproperty N'MS_Description', N'From', N'SCHEMA', N'sal', N'TABLE', N'price_list', N'COLUMN', N'valid_from';
EXEC sys.sp_addextendedproperty N'MS_Description', N'To', N'SCHEMA', N'sal', N'TABLE', N'price_list', N'COLUMN', N'valid_to';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item price in a price list.', N'SCHEMA', N'sal', N'TABLE', N'price_list_item';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Price list', N'SCHEMA', N'sal', N'TABLE', N'price_list_item', N'COLUMN', N'price_list_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'sal', N'TABLE', N'price_list_item', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Price', N'SCHEMA', N'sal', N'TABLE', N'price_list_item', N'COLUMN', N'unit_price';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Min qty', N'SCHEMA', N'sal', N'TABLE', N'price_list_item', N'COLUMN', N'min_qty';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Quotation for machines, parts or service.', N'SCHEMA', N'sal', N'TABLE', N'quotation';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Number', N'SCHEMA', N'sal', N'TABLE', N'quotation', N'COLUMN', N'quotation_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand', N'SCHEMA', N'sal', N'TABLE', N'quotation', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'sal', N'TABLE', N'quotation', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer', N'SCHEMA', N'sal', N'TABLE', N'quotation', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Contact', N'SCHEMA', N'sal', N'TABLE', N'quotation', N'COLUMN', N'contact_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Opportunity (Phase 5)', N'SCHEMA', N'sal', N'TABLE', N'quotation', N'COLUMN', N'opportunity_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Service call (service quote)', N'SCHEMA', N'sal', N'TABLE', N'quotation', N'COLUMN', N'service_call_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Machine, Parts, Service.', N'SCHEMA', N'sal', N'TABLE', N'quotation', N'COLUMN', N'quotation_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'sal', N'TABLE', N'quotation', N'COLUMN', N'quotation_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Valid until', N'SCHEMA', N'sal', N'TABLE', N'quotation', N'COLUMN', N'valid_until';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Salesperson', N'SCHEMA', N'sal', N'TABLE', N'quotation', N'COLUMN', N'salesperson_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Price list', N'SCHEMA', N'sal', N'TABLE', N'quotation', N'COLUMN', N'price_list_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Place of supply', N'SCHEMA', N'sal', N'TABLE', N'quotation', N'COLUMN', N'place_of_supply_state_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Before discount', N'SCHEMA', N'sal', N'TABLE', N'quotation', N'COLUMN', N'subtotal';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Discount', N'SCHEMA', N'sal', N'TABLE', N'quotation', N'COLUMN', N'discount_total';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GST', N'SCHEMA', N'sal', N'TABLE', N'quotation', N'COLUMN', N'tax_total';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Total', N'SCHEMA', N'sal', N'TABLE', N'quotation', N'COLUMN', N'total';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Latest version', N'SCHEMA', N'sal', N'TABLE', N'quotation', N'COLUMN', N'current_version';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Pending approval, Sent, Accepted, Rejected, Expired.', N'SCHEMA', N'sal', N'TABLE', N'quotation', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Terms', N'SCHEMA', N'sal', N'TABLE', N'quotation', N'COLUMN', N'terms';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Each revision sent to the customer.', N'SCHEMA', N'sal', N'TABLE', N'quotation_version';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Quotation', N'SCHEMA', N'sal', N'TABLE', N'quotation_version', N'COLUMN', N'quotation_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Version', N'SCHEMA', N'sal', N'TABLE', N'quotation_version', N'COLUMN', N'version_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Total in this version', N'SCHEMA', N'sal', N'TABLE', N'quotation_version', N'COLUMN', N'total';
EXEC sys.sp_addextendedproperty N'MS_Description', N'What changed', N'SCHEMA', N'sal', N'TABLE', N'quotation_version', N'COLUMN', N'change_note';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PDF', N'SCHEMA', N'sal', N'TABLE', N'quotation_version', N'COLUMN', N'pdf_attachment_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Sent', N'SCHEMA', N'sal', N'TABLE', N'quotation_version', N'COLUMN', N'sent_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Sent via Allowed: Email, WhatsApp, Print.', N'SCHEMA', N'sal', N'TABLE', N'quotation_version', N'COLUMN', N'sent_via';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Quotation lines (per version).', N'SCHEMA', N'sal', N'TABLE', N'quotation_line';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Quotation', N'SCHEMA', N'sal', N'TABLE', N'quotation_line', N'COLUMN', N'quotation_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Version', N'SCHEMA', N'sal', N'TABLE', N'quotation_line', N'COLUMN', N'version_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Line', N'SCHEMA', N'sal', N'TABLE', N'quotation_line', N'COLUMN', N'line_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'sal', N'TABLE', N'quotation_line', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Model (machine quote)', N'SCHEMA', N'sal', N'TABLE', N'quotation_line', N'COLUMN', N'machine_model_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Description', N'SCHEMA', N'sal', N'TABLE', N'quotation_line', N'COLUMN', N'description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Qty', N'SCHEMA', N'sal', N'TABLE', N'quotation_line', N'COLUMN', N'quantity';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Unit', N'SCHEMA', N'sal', N'TABLE', N'quotation_line', N'COLUMN', N'uom_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Price', N'SCHEMA', N'sal', N'TABLE', N'quotation_line', N'COLUMN', N'unit_price';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Discount %', N'SCHEMA', N'sal', N'TABLE', N'quotation_line', N'COLUMN', N'discount_pct';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Discount', N'SCHEMA', N'sal', N'TABLE', N'quotation_line', N'COLUMN', N'discount_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'HSN', N'SCHEMA', N'sal', N'TABLE', N'quotation_line', N'COLUMN', N'hsn_sac_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GST rate', N'SCHEMA', N'sal', N'TABLE', N'quotation_line', N'COLUMN', N'gst_rate_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Taxable', N'SCHEMA', N'sal', N'TABLE', N'quotation_line', N'COLUMN', N'taxable_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Tax', N'SCHEMA', N'sal', N'TABLE', N'quotation_line', N'COLUMN', N'tax_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Total', N'SCHEMA', N'sal', N'TABLE', N'quotation_line', N'COLUMN', N'line_total';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Confirmed customer order.', N'SCHEMA', N'sal', N'TABLE', N'sales_order';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Number', N'SCHEMA', N'sal', N'TABLE', N'sales_order', N'COLUMN', N'order_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand', N'SCHEMA', N'sal', N'TABLE', N'sales_order', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'sal', N'TABLE', N'sales_order', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer', N'SCHEMA', N'sal', N'TABLE', N'sales_order', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'From quotation', N'SCHEMA', N'sal', N'TABLE', N'sales_order', N'COLUMN', N'quotation_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'sal', N'TABLE', N'sales_order', N'COLUMN', N'order_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer PO', N'SCHEMA', N'sal', N'TABLE', N'sales_order', N'COLUMN', N'customer_po_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PO date', N'SCHEMA', N'sal', N'TABLE', N'sales_order', N'COLUMN', N'customer_po_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Salesperson', N'SCHEMA', N'sal', N'TABLE', N'sales_order', N'COLUMN', N'salesperson_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Deliver to', N'SCHEMA', N'sal', N'TABLE', N'sales_order', N'COLUMN', N'delivery_site_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Expected delivery', N'SCHEMA', N'sal', N'TABLE', N'sales_order', N'COLUMN', N'expected_delivery_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Terms', N'SCHEMA', N'sal', N'TABLE', N'sales_order', N'COLUMN', N'payment_terms_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Payment mode Allowed: Cash, Financed.', N'SCHEMA', N'sal', N'TABLE', N'sales_order', N'COLUMN', N'finance_mode';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Finance (Phase 6)', N'SCHEMA', N'sal', N'TABLE', N'sales_order', N'COLUMN', N'finance_application_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Before tax', N'SCHEMA', N'sal', N'TABLE', N'sales_order', N'COLUMN', N'subtotal';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GST', N'SCHEMA', N'sal', N'TABLE', N'sales_order', N'COLUMN', N'tax_total';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Total', N'SCHEMA', N'sal', N'TABLE', N'sales_order', N'COLUMN', N'total';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Advance', N'SCHEMA', N'sal', N'TABLE', N'sales_order', N'COLUMN', N'advance_received';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Confirmed, Part delivered, Delivered, Invoiced, Cancelled.', N'SCHEMA', N'sal', N'TABLE', N'sales_order', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Order lines.', N'SCHEMA', N'sal', N'TABLE', N'sales_order_line';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Order', N'SCHEMA', N'sal', N'TABLE', N'sales_order_line', N'COLUMN', N'sales_order_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Line', N'SCHEMA', N'sal', N'TABLE', N'sales_order_line', N'COLUMN', N'line_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'sal', N'TABLE', N'sales_order_line', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Description', N'SCHEMA', N'sal', N'TABLE', N'sales_order_line', N'COLUMN', N'description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Qty', N'SCHEMA', N'sal', N'TABLE', N'sales_order_line', N'COLUMN', N'quantity';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Price', N'SCHEMA', N'sal', N'TABLE', N'sales_order_line', N'COLUMN', N'unit_price';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Discount', N'SCHEMA', N'sal', N'TABLE', N'sales_order_line', N'COLUMN', N'discount_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'HSN', N'SCHEMA', N'sal', N'TABLE', N'sales_order_line', N'COLUMN', N'hsn_sac_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GST rate', N'SCHEMA', N'sal', N'TABLE', N'sales_order_line', N'COLUMN', N'gst_rate_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Taxable', N'SCHEMA', N'sal', N'TABLE', N'sales_order_line', N'COLUMN', N'taxable_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Tax', N'SCHEMA', N'sal', N'TABLE', N'sales_order_line', N'COLUMN', N'tax_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Total', N'SCHEMA', N'sal', N'TABLE', N'sales_order_line', N'COLUMN', N'line_total';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Delivered', N'SCHEMA', N'sal', N'TABLE', N'sales_order_line', N'COLUMN', N'qty_delivered';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Invoiced', N'SCHEMA', N'sal', N'TABLE', N'sales_order_line', N'COLUMN', N'qty_invoiced';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Chassis allocated', N'SCHEMA', N'sal', N'TABLE', N'sales_order_line', N'COLUMN', N'allocated_machine_unit_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Old machine taken in exchange.', N'SCHEMA', N'sal', N'TABLE', N'exchange_machine';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Order', N'SCHEMA', N'sal', N'TABLE', N'exchange_machine', N'COLUMN', N'sales_order_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer', N'SCHEMA', N'sal', N'TABLE', N'exchange_machine', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Make', N'SCHEMA', N'sal', N'TABLE', N'exchange_machine', N'COLUMN', N'make';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Model', N'SCHEMA', N'sal', N'TABLE', N'exchange_machine', N'COLUMN', N'model';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Serial', N'SCHEMA', N'sal', N'TABLE', N'exchange_machine', N'COLUMN', N'serial_number';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Year', N'SCHEMA', N'sal', N'TABLE', N'exchange_machine', N'COLUMN', N'year_of_manufacture';
EXEC sys.sp_addextendedproperty N'MS_Description', N'HMR', N'SCHEMA', N'sal', N'TABLE', N'exchange_machine', N'COLUMN', N'hmr';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Evaluated', N'SCHEMA', N'sal', N'TABLE', N'exchange_machine', N'COLUMN', N'evaluated_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Agreed', N'SCHEMA', N'sal', N'TABLE', N'exchange_machine', N'COLUMN', N'agreed_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Evaluator', N'SCHEMA', N'sal', N'TABLE', N'exchange_machine', N'COLUMN', N'evaluated_by_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Evaluated, Agreed, Received, Cancelled.', N'SCHEMA', N'sal', N'TABLE', N'exchange_machine', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Delivery of goods / machine.', N'SCHEMA', N'sal', N'TABLE', N'delivery_note';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Number', N'SCHEMA', N'sal', N'TABLE', N'delivery_note', N'COLUMN', N'delivery_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand', N'SCHEMA', N'sal', N'TABLE', N'delivery_note', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'sal', N'TABLE', N'delivery_note', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Order', N'SCHEMA', N'sal', N'TABLE', N'delivery_note', N'COLUMN', N'sales_order_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer', N'SCHEMA', N'sal', N'TABLE', N'delivery_note', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'sal', N'TABLE', N'delivery_note', N'COLUMN', N'delivery_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Warehouse location dispatched from', N'SCHEMA', N'sal', N'TABLE', N'delivery_note', N'COLUMN', N'from_location_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'To site', N'SCHEMA', N'sal', N'TABLE', N'delivery_note', N'COLUMN', N'delivery_site_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Vehicle', N'SCHEMA', N'sal', N'TABLE', N'delivery_note', N'COLUMN', N'vehicle_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Transporter', N'SCHEMA', N'sal', N'TABLE', N'delivery_note', N'COLUMN', N'transporter';
EXEC sys.sp_addextendedproperty N'MS_Description', N'E-way bill', N'SCHEMA', N'sal', N'TABLE', N'delivery_note', N'COLUMN', N'e_way_bill_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Dispatched, Delivered, Cancelled.', N'SCHEMA', N'sal', N'TABLE', N'delivery_note', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Delivered items.', N'SCHEMA', N'sal', N'TABLE', N'delivery_note_line';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Delivery', N'SCHEMA', N'sal', N'TABLE', N'delivery_note_line', N'COLUMN', N'delivery_note_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Order line', N'SCHEMA', N'sal', N'TABLE', N'delivery_note_line', N'COLUMN', N'sales_order_line_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'sal', N'TABLE', N'delivery_note_line', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Serial', N'SCHEMA', N'sal', N'TABLE', N'delivery_note_line', N'COLUMN', N'serial_batch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Machine', N'SCHEMA', N'sal', N'TABLE', N'delivery_note_line', N'COLUMN', N'machine_unit_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Qty', N'SCHEMA', N'sal', N'TABLE', N'delivery_note_line', N'COLUMN', N'quantity';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Pre-delivery inspection, installation and commissioning.', N'SCHEMA', N'sal', N'TABLE', N'pdi_installation';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Machine', N'SCHEMA', N'sal', N'TABLE', N'pdi_installation', N'COLUMN', N'machine_unit_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Delivery', N'SCHEMA', N'sal', N'TABLE', N'pdi_installation', N'COLUMN', N'delivery_note_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Done via service call', N'SCHEMA', N'sal', N'TABLE', N'pdi_installation', N'COLUMN', N'service_call_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: PDI, Installation, Commissioning.', N'SCHEMA', N'sal', N'TABLE', N'pdi_installation', N'COLUMN', N'record_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Engineer', N'SCHEMA', N'sal', N'TABLE', N'pdi_installation', N'COLUMN', N'done_by_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'When', N'SCHEMA', N'sal', N'TABLE', N'pdi_installation', N'COLUMN', N'done_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'HMR', N'SCHEMA', N'sal', N'TABLE', N'pdi_installation', N'COLUMN', N'hmr';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Report', N'SCHEMA', N'sal', N'TABLE', N'pdi_installation', N'COLUMN', N'report_attachment_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer signature', N'SCHEMA', N'sal', N'TABLE', N'pdi_installation', N'COLUMN', N'customer_signature_attachment_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Remarks', N'SCHEMA', N'sal', N'TABLE', N'pdi_installation', N'COLUMN', N'remarks';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GST tax invoice to customer.', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Invoice number (GST max 16 chars)', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'invoice_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand (one brand per invoice)', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'company_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Our GSTIN', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'gstin_registration_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Billing address', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'bill_to_address';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Ship to', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'ship_to_site_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Place of supply', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'place_of_supply_state_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Tax invoice, Bill of supply, Export.', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'invoice_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Origin Allowed: Sales order, Service call, Counter sale, Contract.', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'source_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Order', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'sales_order_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Service call', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'service_call_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Delivery', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'delivery_note_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'invoice_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Due', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'due_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'RCM', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'is_reverse_charge';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Taxable', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'taxable_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'CGST', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'cgst';
EXEC sys.sp_addextendedproperty N'MS_Description', N'SGST', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'sgst';
EXEC sys.sp_addextendedproperty N'MS_Description', N'IGST', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'igst';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Cess', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'cess';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Round off', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'round_off';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Total', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'total';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Received', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'amount_received';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Posted, Part paid, Paid, Cancelled.', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'E-invoice (IRN)', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'e_invoice_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Ledger posting', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice', N'COLUMN', N'journal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Invoice lines.', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice_line';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Invoice', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice_line', N'COLUMN', N'sales_invoice_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Line', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice_line', N'COLUMN', N'line_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice_line', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Machine sold', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice_line', N'COLUMN', N'machine_unit_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Serial', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice_line', N'COLUMN', N'serial_batch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Order line', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice_line', N'COLUMN', N'sales_order_line_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Service charge', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice_line', N'COLUMN', N'service_charge_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Description', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice_line', N'COLUMN', N'description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'HSN / SAC', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice_line', N'COLUMN', N'hsn_sac_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Qty', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice_line', N'COLUMN', N'quantity';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Unit', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice_line', N'COLUMN', N'uom_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Price', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice_line', N'COLUMN', N'unit_price';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Discount', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice_line', N'COLUMN', N'discount_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Taxable', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice_line', N'COLUMN', N'taxable_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GST rate', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice_line', N'COLUMN', N'gst_rate_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'CGST', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice_line', N'COLUMN', N'cgst_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'SGST', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice_line', N'COLUMN', N'sgst_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'IGST', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice_line', N'COLUMN', N'igst_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Total', N'SCHEMA', N'sal', N'TABLE', N'sales_invoice_line', N'COLUMN', N'line_total';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Money received from customer, incl. advances and finance disbursement. Brand-neutral: split by brand through allocations to invoices.', N'SCHEMA', N'sal', N'TABLE', N'receipt';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Number', N'SCHEMA', N'sal', N'TABLE', N'receipt', N'COLUMN', N'receipt_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'sal', N'TABLE', N'receipt', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer', N'SCHEMA', N'sal', N'TABLE', N'receipt', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'sal', N'TABLE', N'receipt', N'COLUMN', N'receipt_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Against invoice, Advance, Order advance.', N'SCHEMA', N'sal', N'TABLE', N'receipt', N'COLUMN', N'receipt_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Mode Allowed: Cash, Cheque, NEFT, RTGS, UPI, Finance disbursement.', N'SCHEMA', N'sal', N'TABLE', N'receipt', N'COLUMN', N'payment_mode';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Deposited to', N'SCHEMA', N'sal', N'TABLE', N'receipt', N'COLUMN', N'bank_account_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Cheque', N'SCHEMA', N'sal', N'TABLE', N'receipt', N'COLUMN', N'cheque_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Financer (disbursement)', N'SCHEMA', N'sal', N'TABLE', N'receipt', N'COLUMN', N'financer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'UTR / ref', N'SCHEMA', N'sal', N'TABLE', N'receipt', N'COLUMN', N'reference_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Amount', N'SCHEMA', N'sal', N'TABLE', N'receipt', N'COLUMN', N'amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'TDS by customer', N'SCHEMA', N'sal', N'TABLE', N'receipt', N'COLUMN', N'tds_deducted';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Posted, Bounced, Cancelled.', N'SCHEMA', N'sal', N'TABLE', N'receipt', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Ledger posting', N'SCHEMA', N'sal', N'TABLE', N'receipt', N'COLUMN', N'journal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Sales return / price adjustment.', N'SCHEMA', N'sal', N'TABLE', N'credit_note';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Number', N'SCHEMA', N'sal', N'TABLE', N'credit_note', N'COLUMN', N'credit_note_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand', N'SCHEMA', N'sal', N'TABLE', N'credit_note', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer', N'SCHEMA', N'sal', N'TABLE', N'credit_note', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Against invoice', N'SCHEMA', N'sal', N'TABLE', N'credit_note', N'COLUMN', N'sales_invoice_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'sal', N'TABLE', N'credit_note', N'COLUMN', N'note_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Sales return, Price adjustment, Discount.', N'SCHEMA', N'sal', N'TABLE', N'credit_note', N'COLUMN', N'note_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Reason', N'SCHEMA', N'sal', N'TABLE', N'credit_note', N'COLUMN', N'reason_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Taxable', N'SCHEMA', N'sal', N'TABLE', N'credit_note', N'COLUMN', N'taxable_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Tax', N'SCHEMA', N'sal', N'TABLE', N'credit_note', N'COLUMN', N'tax_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Total', N'SCHEMA', N'sal', N'TABLE', N'credit_note', N'COLUMN', N'total';
EXEC sys.sp_addextendedproperty N'MS_Description', N'E-invoice', N'SCHEMA', N'sal', N'TABLE', N'credit_note', N'COLUMN', N'e_invoice_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Posted, Cancelled.', N'SCHEMA', N'sal', N'TABLE', N'credit_note', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Ledger posting', N'SCHEMA', N'sal', N'TABLE', N'credit_note', N'COLUMN', N'journal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Credit note lines.', N'SCHEMA', N'sal', N'TABLE', N'credit_note_line';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Credit note', N'SCHEMA', N'sal', N'TABLE', N'credit_note_line', N'COLUMN', N'credit_note_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Invoice line', N'SCHEMA', N'sal', N'TABLE', N'credit_note_line', N'COLUMN', N'sales_invoice_line_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Item', N'SCHEMA', N'sal', N'TABLE', N'credit_note_line', N'COLUMN', N'item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Serial', N'SCHEMA', N'sal', N'TABLE', N'credit_note_line', N'COLUMN', N'serial_batch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Qty', N'SCHEMA', N'sal', N'TABLE', N'credit_note_line', N'COLUMN', N'quantity';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Price', N'SCHEMA', N'sal', N'TABLE', N'credit_note_line', N'COLUMN', N'unit_price';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Tax', N'SCHEMA', N'sal', N'TABLE', N'credit_note_line', N'COLUMN', N'tax_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Total', N'SCHEMA', N'sal', N'TABLE', N'credit_note_line', N'COLUMN', N'line_total';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Returned to', N'SCHEMA', N'sal', N'TABLE', N'credit_note_line', N'COLUMN', N'return_location_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Matches receipts and credit notes to invoices.', N'SCHEMA', N'sal', N'TABLE', N'customer_allocation';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Invoice', N'SCHEMA', N'sal', N'TABLE', N'customer_allocation', N'COLUMN', N'sales_invoice_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Receipt', N'SCHEMA', N'sal', N'TABLE', N'customer_allocation', N'COLUMN', N'receipt_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Credit note', N'SCHEMA', N'sal', N'TABLE', N'customer_allocation', N'COLUMN', N'credit_note_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Amount', N'SCHEMA', N'sal', N'TABLE', N'customer_allocation', N'COLUMN', N'amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'sal', N'TABLE', N'customer_allocation', N'COLUMN', N'allocated_on';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Credit holds when limit or overdue is exceeded.', N'SCHEMA', N'sal', N'TABLE', N'credit_hold';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer', N'SCHEMA', N'sal', N'TABLE', N'credit_hold', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Held at', N'SCHEMA', N'sal', N'TABLE', N'credit_hold', N'COLUMN', N'hold_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Reason Allowed: Over limit, Overdue, Manual.', N'SCHEMA', N'sal', N'TABLE', N'credit_hold', N'COLUMN', N'reason';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Outstanding', N'SCHEMA', N'sal', N'TABLE', N'credit_hold', N'COLUMN', N'outstanding_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Limit', N'SCHEMA', N'sal', N'TABLE', N'credit_hold', N'COLUMN', N'credit_limit';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Released by', N'SCHEMA', N'sal', N'TABLE', N'credit_hold', N'COLUMN', N'released_by_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Released at', N'SCHEMA', N'sal', N'TABLE', N'credit_hold', N'COLUMN', N'released_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Remarks', N'SCHEMA', N'sal', N'TABLE', N'credit_hold', N'COLUMN', N'release_remarks';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Salesperson incentive per invoice, paid via payroll.', N'SCHEMA', N'sal', N'TABLE', N'sales_incentive';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Salesperson', N'SCHEMA', N'sal', N'TABLE', N'sales_incentive', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Month (1st day)', N'SCHEMA', N'sal', N'TABLE', N'sales_incentive', N'COLUMN', N'period_month';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Invoice', N'SCHEMA', N'sal', N'TABLE', N'sales_incentive', N'COLUMN', N'sales_invoice_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Basis', N'SCHEMA', N'sal', N'TABLE', N'sales_incentive', N'COLUMN', N'basis_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'%', N'SCHEMA', N'sal', N'TABLE', N'sales_incentive', N'COLUMN', N'incentive_pct';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Amount', N'SCHEMA', N'sal', N'TABLE', N'sales_incentive', N'COLUMN', N'incentive_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Calculated, Approved, Paid.', N'SCHEMA', N'sal', N'TABLE', N'sales_incentive', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Paid in payroll', N'SCHEMA', N'sal', N'TABLE', N'sales_incentive', N'COLUMN', N'payroll_run_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Where leads come from.', N'SCHEMA', N'pre', N'TABLE', N'lead_source';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Code', N'SCHEMA', N'pre', N'TABLE', N'lead_source', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name', N'SCHEMA', N'pre', N'TABLE', N'lead_source', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Referral, Walk in, Campaign, Service engineer, TATA HITACHI, Website, Old customer, Other.', N'SCHEMA', N'pre', N'TABLE', N'lead_source', N'COLUMN', N'source_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Expos, demos, melas, digital campaigns.', N'SCHEMA', N'pre', N'TABLE', N'campaign';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name', N'SCHEMA', N'pre', N'TABLE', N'campaign', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Expo, Demo, Mela, Digital, Other.', N'SCHEMA', N'pre', N'TABLE', N'campaign', N'COLUMN', N'campaign_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'pre', N'TABLE', N'campaign', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Start', N'SCHEMA', N'pre', N'TABLE', N'campaign', N'COLUMN', N'start_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'End', N'SCHEMA', N'pre', N'TABLE', N'campaign', N'COLUMN', N'end_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Budget', N'SCHEMA', N'pre', N'TABLE', N'campaign', N'COLUMN', N'budget';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Notes', N'SCHEMA', N'pre', N'TABLE', N'campaign', N'COLUMN', N'notes';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Competitor brands.', N'SCHEMA', N'pre', N'TABLE', N'competitor';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name, e.g. JCB, CAT, Komatsu', N'SCHEMA', N'pre', N'TABLE', N'competitor', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Notes', N'SCHEMA', N'pre', N'TABLE', N'competitor', N'COLUMN', N'notes';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Enquiry / referral before qualification.', N'SCHEMA', N'pre', N'TABLE', N'lead';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Number', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'lead_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Device ID', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'client_uuid';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand of interest (can be blank at first)', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Source', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'lead_source_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Campaign', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'campaign_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Referring customer', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'referred_by_customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Referring employee (e.g. service engineer)', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'referred_by_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Prospect', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'prospect_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Firm', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'company_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Phone', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'phone';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Alt phone', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'alternate_phone';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Email', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'email';
EXEC sys.sp_addextendedproperty N'MS_Description', N'District', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'district_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PIN', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'pincode_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Model', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'interested_model_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Units', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'quantity';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Mining, road, irrigation...', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'application_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Expected month', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'expected_purchase_month';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Salesperson', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'assigned_to_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: New, Contacted, Qualified, Converted, Lost.', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Lost reason', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'lost_reason_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer created', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'converted_customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Where captured', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'captured_latitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Where captured', N'SCHEMA', N'pre', N'TABLE', N'lead', N'COLUMN', N'captured_longitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Qualified deal moving through the SOP stages.', N'SCHEMA', N'pre', N'TABLE', N'opportunity';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Number', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'opportunity_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'From lead', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'lead_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Contact', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'contact_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Model', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'machine_model_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Units', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'quantity';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Value', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'estimated_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Probability', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'probability_pct';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Expected close', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'expected_close_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Salesperson', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'salesperson_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Current stage (Phase 6)', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'current_sop_stage_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'In stage since', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'stage_entered_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Payment mode Allowed: Cash, Financed.', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'finance_mode';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Exchange', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'is_exchange_offered';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Main competitor', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'competitor_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Competitor price', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'competitor_price';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Open, Won, Lost, On hold.', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Order when won', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'won_sales_order_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Lost reason', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'lost_reason_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Lost to', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'lost_to_competitor_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Closed', N'SCHEMA', N'pre', N'TABLE', N'opportunity', N'COLUMN', N'closed_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Stage changes for pipeline ageing.', N'SCHEMA', N'pre', N'TABLE', N'opportunity_stage_log';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Opportunity', N'SCHEMA', N'pre', N'TABLE', N'opportunity_stage_log', N'COLUMN', N'opportunity_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'From', N'SCHEMA', N'pre', N'TABLE', N'opportunity_stage_log', N'COLUMN', N'from_stage_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'To', N'SCHEMA', N'pre', N'TABLE', N'opportunity_stage_log', N'COLUMN', N'to_stage_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'When', N'SCHEMA', N'pre', N'TABLE', N'opportunity_stage_log', N'COLUMN', N'changed_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'By', N'SCHEMA', N'pre', N'TABLE', N'opportunity_stage_log', N'COLUMN', N'changed_by_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Days spent', N'SCHEMA', N'pre', N'TABLE', N'opportunity_stage_log', N'COLUMN', N'days_in_previous_stage';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Remarks', N'SCHEMA', N'pre', N'TABLE', N'opportunity_stage_log', N'COLUMN', N'remarks';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Calls, visits, demos, meetings by salespeople.', N'SCHEMA', N'pre', N'TABLE', N'sales_activity';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Salesperson', N'SCHEMA', N'pre', N'TABLE', N'sales_activity', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Device ID', N'SCHEMA', N'pre', N'TABLE', N'sales_activity', N'COLUMN', N'client_uuid';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Lead', N'SCHEMA', N'pre', N'TABLE', N'sales_activity', N'COLUMN', N'lead_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Opportunity', N'SCHEMA', N'pre', N'TABLE', N'sales_activity', N'COLUMN', N'opportunity_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer', N'SCHEMA', N'pre', N'TABLE', N'sales_activity', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Call, Visit, Demo, Meeting, WhatsApp, Email.', N'SCHEMA', N'pre', N'TABLE', N'sales_activity', N'COLUMN', N'activity_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Planned', N'SCHEMA', N'pre', N'TABLE', N'sales_activity', N'COLUMN', N'planned_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Started', N'SCHEMA', N'pre', N'TABLE', N'sales_activity', N'COLUMN', N'started_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Ended', N'SCHEMA', N'pre', N'TABLE', N'sales_activity', N'COLUMN', N'ended_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Outcome', N'SCHEMA', N'pre', N'TABLE', N'sales_activity', N'COLUMN', N'outcome_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Notes', N'SCHEMA', N'pre', N'TABLE', N'sales_activity', N'COLUMN', N'notes';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Next follow-up', N'SCHEMA', N'pre', N'TABLE', N'sales_activity', N'COLUMN', N'next_follow_up_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Live-location check-in/out to verify visits.', N'SCHEMA', N'pre', N'TABLE', N'location_check';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee', N'SCHEMA', N'pre', N'TABLE', N'location_check', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Activity', N'SCHEMA', N'pre', N'TABLE', N'location_check', N'COLUMN', N'sales_activity_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Check in, Check out.', N'SCHEMA', N'pre', N'TABLE', N'location_check', N'COLUMN', N'check_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'When', N'SCHEMA', N'pre', N'TABLE', N'location_check', N'COLUMN', N'captured_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Latitude', N'SCHEMA', N'pre', N'TABLE', N'location_check', N'COLUMN', N'latitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Longitude', N'SCHEMA', N'pre', N'TABLE', N'location_check', N'COLUMN', N'longitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Accuracy', N'SCHEMA', N'pre', N'TABLE', N'location_check', N'COLUMN', N'accuracy_m';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Expected place', N'SCHEMA', N'pre', N'TABLE', N'location_check', N'COLUMN', N'target_latitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Expected place', N'SCHEMA', N'pre', N'TABLE', N'location_check', N'COLUMN', N'target_longitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Distance from expected', N'SCHEMA', N'pre', N'TABLE', N'location_check', N'COLUMN', N'distance_from_target_m';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Within allowed radius', N'SCHEMA', N'pre', N'TABLE', N'location_check', N'COLUMN', N'is_within_geofence';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Fake GPS', N'SCHEMA', N'pre', N'TABLE', N'location_check', N'COLUMN', N'is_mock_location';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Selfie / site photo', N'SCHEMA', N'pre', N'TABLE', N'location_check', N'COLUMN', N'photo_attachment_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'WhatsApp messages with leads and customers.', N'SCHEMA', N'pre', N'TABLE', N'whatsapp_log';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Direction Allowed: Outbound, Inbound.', N'SCHEMA', N'pre', N'TABLE', N'whatsapp_log', N'COLUMN', N'direction';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Phone', N'SCHEMA', N'pre', N'TABLE', N'whatsapp_log', N'COLUMN', N'phone';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer', N'SCHEMA', N'pre', N'TABLE', N'whatsapp_log', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Lead', N'SCHEMA', N'pre', N'TABLE', N'whatsapp_log', N'COLUMN', N'lead_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Opportunity', N'SCHEMA', N'pre', N'TABLE', N'whatsapp_log', N'COLUMN', N'opportunity_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee', N'SCHEMA', N'pre', N'TABLE', N'whatsapp_log', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Template', N'SCHEMA', N'pre', N'TABLE', N'whatsapp_log', N'COLUMN', N'template_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Text', N'SCHEMA', N'pre', N'TABLE', N'whatsapp_log', N'COLUMN', N'message_text';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Media', N'SCHEMA', N'pre', N'TABLE', N'whatsapp_log', N'COLUMN', N'media_attachment_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Provider ID', N'SCHEMA', N'pre', N'TABLE', N'whatsapp_log', N'COLUMN', N'provider_message_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Sent, Delivered, Read, Failed, Received.', N'SCHEMA', N'pre', N'TABLE', N'whatsapp_log', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Sent', N'SCHEMA', N'pre', N'TABLE', N'whatsapp_log', N'COLUMN', N'sent_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Read', N'SCHEMA', N'pre', N'TABLE', N'whatsapp_log', N'COLUMN', N'read_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Pre-sale SOP stages up to order advance.', N'SCHEMA', N'pre', N'TABLE', N'sop_stage';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand (blank = all brands)', N'SCHEMA', N'pre', N'TABLE', N'sop_stage', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Order', N'SCHEMA', N'pre', N'TABLE', N'sop_stage', N'COLUMN', N'sequence';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Code', N'SCHEMA', N'pre', N'TABLE', N'sop_stage', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Enquiry, Demo, Quotation, Negotiation, Finance, Order advance...', N'SCHEMA', N'pre', N'TABLE', N'sop_stage', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Target days in stage', N'SCHEMA', N'pre', N'TABLE', N'sop_stage', N'COLUMN', N'expected_days';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Cannot skip', N'SCHEMA', N'pre', N'TABLE', N'sop_stage', N'COLUMN', N'is_mandatory';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Tasks required in each SOP stage.', N'SCHEMA', N'pre', N'TABLE', N'sop_checklist_item';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Stage', N'SCHEMA', N'pre', N'TABLE', N'sop_checklist_item', N'COLUMN', N'sop_stage_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Order', N'SCHEMA', N'pre', N'TABLE', N'sop_checklist_item', N'COLUMN', N'sequence';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Task', N'SCHEMA', N'pre', N'TABLE', N'sop_checklist_item', N'COLUMN', N'item_text';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Proof needed', N'SCHEMA', N'pre', N'TABLE', N'sop_checklist_item', N'COLUMN', N'requires_attachment';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Required', N'SCHEMA', N'pre', N'TABLE', N'sop_checklist_item', N'COLUMN', N'is_mandatory';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Completion of SOP tasks per opportunity.', N'SCHEMA', N'pre', N'TABLE', N'sop_progress';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Opportunity', N'SCHEMA', N'pre', N'TABLE', N'sop_progress', N'COLUMN', N'opportunity_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Task', N'SCHEMA', N'pre', N'TABLE', N'sop_progress', N'COLUMN', N'sop_checklist_item_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Done', N'SCHEMA', N'pre', N'TABLE', N'sop_progress', N'COLUMN', N'is_done';
EXEC sys.sp_addextendedproperty N'MS_Description', N'When', N'SCHEMA', N'pre', N'TABLE', N'sop_progress', N'COLUMN', N'done_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'By', N'SCHEMA', N'pre', N'TABLE', N'sop_progress', N'COLUMN', N'done_by_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Proof', N'SCHEMA', N'pre', N'TABLE', N'sop_progress', N'COLUMN', N'attachment_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Remarks', N'SCHEMA', N'pre', N'TABLE', N'sop_progress', N'COLUMN', N'remarks';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Banks / NBFCs financing machines.', N'SCHEMA', N'pre', N'TABLE', N'financer';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Code', N'SCHEMA', N'pre', N'TABLE', N'financer', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name', N'SCHEMA', N'pre', N'TABLE', N'financer', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Bank, NBFC, OEM captive.', N'SCHEMA', N'pre', N'TABLE', N'financer', N'COLUMN', N'financer_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Contact', N'SCHEMA', N'pre', N'TABLE', N'financer', N'COLUMN', N'contact_person';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Phone', N'SCHEMA', N'pre', N'TABLE', N'financer', N'COLUMN', N'phone';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Email', N'SCHEMA', N'pre', N'TABLE', N'financer', N'COLUMN', N'email';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Address', N'SCHEMA', N'pre', N'TABLE', N'financer', N'COLUMN', N'branch_address';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Tie-up', N'SCHEMA', N'pre', N'TABLE', N'financer', N'COLUMN', N'is_empanelled';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Loan application for a deal.', N'SCHEMA', N'pre', N'TABLE', N'finance_application';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Number', N'SCHEMA', N'pre', N'TABLE', N'finance_application', N'COLUMN', N'application_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Opportunity', N'SCHEMA', N'pre', N'TABLE', N'finance_application', N'COLUMN', N'opportunity_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer', N'SCHEMA', N'pre', N'TABLE', N'finance_application', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Financer', N'SCHEMA', N'pre', N'TABLE', N'finance_application', N'COLUMN', N'financer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Loan', N'SCHEMA', N'pre', N'TABLE', N'finance_application', N'COLUMN', N'loan_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Down payment', N'SCHEMA', N'pre', N'TABLE', N'finance_application', N'COLUMN', N'down_payment';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Tenure', N'SCHEMA', N'pre', N'TABLE', N'finance_application', N'COLUMN', N'tenure_months';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Rate', N'SCHEMA', N'pre', N'TABLE', N'finance_application', N'COLUMN', N'interest_rate';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Applied', N'SCHEMA', N'pre', N'TABLE', N'finance_application', N'COLUMN', N'applied_on';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Docs pending, Submitted, Sanctioned, Rejected, Disbursed.', N'SCHEMA', N'pre', N'TABLE', N'finance_application', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Sanctioned', N'SCHEMA', N'pre', N'TABLE', N'finance_application', N'COLUMN', N'sanctioned_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Sanction date', N'SCHEMA', N'pre', N'TABLE', N'finance_application', N'COLUMN', N'sanctioned_on';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Disbursed', N'SCHEMA', N'pre', N'TABLE', N'finance_application', N'COLUMN', N'disbursed_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Disbursal date', N'SCHEMA', N'pre', N'TABLE', N'finance_application', N'COLUMN', N'disbursed_on';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Financer ref', N'SCHEMA', N'pre', N'TABLE', N'finance_application', N'COLUMN', N'financer_reference';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Booking advance received at the end of the SOP.', N'SCHEMA', N'pre', N'TABLE', N'order_advance';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Opportunity', N'SCHEMA', N'pre', N'TABLE', N'order_advance', N'COLUMN', N'opportunity_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer', N'SCHEMA', N'pre', N'TABLE', N'order_advance', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Receipt', N'SCHEMA', N'pre', N'TABLE', N'order_advance', N'COLUMN', N'receipt_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Amount', N'SCHEMA', N'pre', N'TABLE', N'order_advance', N'COLUMN', N'amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'pre', N'TABLE', N'order_advance', N'COLUMN', N'received_on';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Received, Adjusted, Refunded.', N'SCHEMA', N'pre', N'TABLE', N'order_advance', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Daily pipeline totals for trend and ageing reports.', N'SCHEMA', N'pre', N'TABLE', N'pipeline_snapshot';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'pre', N'TABLE', N'pipeline_snapshot', N'COLUMN', N'snapshot_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand', N'SCHEMA', N'pre', N'TABLE', N'pipeline_snapshot', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'pre', N'TABLE', N'pipeline_snapshot', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Salesperson', N'SCHEMA', N'pre', N'TABLE', N'pipeline_snapshot', N'COLUMN', N'salesperson_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Stage', N'SCHEMA', N'pre', N'TABLE', N'pipeline_snapshot', N'COLUMN', N'sop_stage_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Count', N'SCHEMA', N'pre', N'TABLE', N'pipeline_snapshot', N'COLUMN', N'opportunity_count';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Value', N'SCHEMA', N'pre', N'TABLE', N'pipeline_snapshot', N'COLUMN', N'pipeline_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Value x probability', N'SCHEMA', N'pre', N'TABLE', N'pipeline_snapshot', N'COLUMN', N'weighted_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Average age', N'SCHEMA', N'pre', N'TABLE', N'pipeline_snapshot', N'COLUMN', N'avg_age_days';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Monthly targets per salesperson and model.', N'SCHEMA', N'pre', N'TABLE', N'sales_target';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Salesperson', N'SCHEMA', N'pre', N'TABLE', N'sales_target', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand', N'SCHEMA', N'pre', N'TABLE', N'sales_target', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'pre', N'TABLE', N'sales_target', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Month', N'SCHEMA', N'pre', N'TABLE', N'sales_target', N'COLUMN', N'period_month';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Model (blank = all)', N'SCHEMA', N'pre', N'TABLE', N'sales_target', N'COLUMN', N'machine_model_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Units', N'SCHEMA', N'pre', N'TABLE', N'sales_target', N'COLUMN', N'target_units';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Value', N'SCHEMA', N'pre', N'TABLE', N'sales_target', N'COLUMN', N'target_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Departments.', N'SCHEMA', N'hr', N'TABLE', N'department';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Code', N'SCHEMA', N'hr', N'TABLE', N'department', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name', N'SCHEMA', N'hr', N'TABLE', N'department', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Parent', N'SCHEMA', N'hr', N'TABLE', N'department', N'COLUMN', N'parent_department_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Head', N'SCHEMA', N'hr', N'TABLE', N'department', N'COLUMN', N'head_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Designations and grades.', N'SCHEMA', N'hr', N'TABLE', N'designation';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Code', N'SCHEMA', N'hr', N'TABLE', N'designation', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name', N'SCHEMA', N'hr', N'TABLE', N'designation', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Grade', N'SCHEMA', N'hr', N'TABLE', N'designation', N'COLUMN', N'grade';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Department', N'SCHEMA', N'hr', N'TABLE', N'designation', N'COLUMN', N'department_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Personal, statutory and bank details (1:1 with employee).', N'SCHEMA', N'hr', N'TABLE', N'employee_profile';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee', N'SCHEMA', N'hr', N'TABLE', N'employee_profile', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date of birth', N'SCHEMA', N'hr', N'TABLE', N'employee_profile', N'COLUMN', N'date_of_birth';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Gender Allowed: Male, Female, Other.', N'SCHEMA', N'hr', N'TABLE', N'employee_profile', N'COLUMN', N'gender';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Personal email', N'SCHEMA', N'hr', N'TABLE', N'employee_profile', N'COLUMN', N'personal_email';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Current address', N'SCHEMA', N'hr', N'TABLE', N'employee_profile', N'COLUMN', N'current_address';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Permanent address', N'SCHEMA', N'hr', N'TABLE', N'employee_profile', N'COLUMN', N'permanent_address';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Emergency contact', N'SCHEMA', N'hr', N'TABLE', N'employee_profile', N'COLUMN', N'emergency_contact_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Emergency phone', N'SCHEMA', N'hr', N'TABLE', N'employee_profile', N'COLUMN', N'emergency_contact_phone';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PAN (encrypted)', N'SCHEMA', N'hr', N'TABLE', N'employee_profile', N'COLUMN', N'pan';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Last 4 digits only', N'SCHEMA', N'hr', N'TABLE', N'employee_profile', N'COLUMN', N'aadhaar_masked';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PF UAN', N'SCHEMA', N'hr', N'TABLE', N'employee_profile', N'COLUMN', N'uan';
EXEC sys.sp_addextendedproperty N'MS_Description', N'ESIC number', N'SCHEMA', N'hr', N'TABLE', N'employee_profile', N'COLUMN', N'esic_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Salary bank', N'SCHEMA', N'hr', N'TABLE', N'employee_profile', N'COLUMN', N'bank_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Account (encrypted)', N'SCHEMA', N'hr', N'TABLE', N'employee_profile', N'COLUMN', N'bank_account_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'IFSC', N'SCHEMA', N'hr', N'TABLE', N'employee_profile', N'COLUMN', N'ifsc';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PF', N'SCHEMA', N'hr', N'TABLE', N'employee_profile', N'COLUMN', N'is_pf_applicable';
EXEC sys.sp_addextendedproperty N'MS_Description', N'ESI', N'SCHEMA', N'hr', N'TABLE', N'employee_profile', N'COLUMN', N'is_esi_applicable';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Professional tax state', N'SCHEMA', N'hr', N'TABLE', N'employee_profile', N'COLUMN', N'pt_state_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Income-tax regime Allowed: Old, New.', N'SCHEMA', N'hr', N'TABLE', N'employee_profile', N'COLUMN', N'tax_regime';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Joining, confirmation, transfer, promotion, exit.', N'SCHEMA', N'hr', N'TABLE', N'employment_history';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee', N'SCHEMA', N'hr', N'TABLE', N'employment_history', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Event Allowed: Joined, Confirmed, Transferred, Promoted, Resigned, Terminated, Retired.', N'SCHEMA', N'hr', N'TABLE', N'employment_history', N'COLUMN', N'event_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Effective', N'SCHEMA', N'hr', N'TABLE', N'employment_history', N'COLUMN', N'effective_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'From branch', N'SCHEMA', N'hr', N'TABLE', N'employment_history', N'COLUMN', N'from_branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'To branch', N'SCHEMA', N'hr', N'TABLE', N'employment_history', N'COLUMN', N'to_branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'From designation', N'SCHEMA', N'hr', N'TABLE', N'employment_history', N'COLUMN', N'from_designation_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'To designation', N'SCHEMA', N'hr', N'TABLE', N'employment_history', N'COLUMN', N'to_designation_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Remarks', N'SCHEMA', N'hr', N'TABLE', N'employment_history', N'COLUMN', N'remarks';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee documents (offer letter, ID proof, licence).', N'SCHEMA', N'hr', N'TABLE', N'employee_document';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee', N'SCHEMA', N'hr', N'TABLE', N'employee_document', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Document type', N'SCHEMA', N'hr', N'TABLE', N'employee_document', N'COLUMN', N'document_type_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Masked number', N'SCHEMA', N'hr', N'TABLE', N'employee_document', N'COLUMN', N'document_number_masked';
EXEC sys.sp_addextendedproperty N'MS_Description', N'File', N'SCHEMA', N'hr', N'TABLE', N'employee_document', N'COLUMN', N'attachment_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Expiry', N'SCHEMA', N'hr', N'TABLE', N'employee_document', N'COLUMN', N'valid_until';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Onboarding and offboarding checklist.', N'SCHEMA', N'hr', N'TABLE', N'onboarding_task';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee', N'SCHEMA', N'hr', N'TABLE', N'onboarding_task', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Onboarding, Offboarding.', N'SCHEMA', N'hr', N'TABLE', N'onboarding_task', N'COLUMN', N'task_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Task', N'SCHEMA', N'hr', N'TABLE', N'onboarding_task', N'COLUMN', N'task_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Responsible', N'SCHEMA', N'hr', N'TABLE', N'onboarding_task', N'COLUMN', N'owner_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Due', N'SCHEMA', N'hr', N'TABLE', N'onboarding_task', N'COLUMN', N'due_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Done', N'SCHEMA', N'hr', N'TABLE', N'onboarding_task', N'COLUMN', N'completed_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Pending, Done, Not applicable.', N'SCHEMA', N'hr', N'TABLE', N'onboarding_task', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Work shifts.', N'SCHEMA', N'hr', N'TABLE', N'shift';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Code', N'SCHEMA', N'hr', N'TABLE', N'shift', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name', N'SCHEMA', N'hr', N'TABLE', N'shift', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Start', N'SCHEMA', N'hr', N'TABLE', N'shift', N'COLUMN', N'start_time';
EXEC sys.sp_addextendedproperty N'MS_Description', N'End', N'SCHEMA', N'hr', N'TABLE', N'shift', N'COLUMN', N'end_time';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Grace', N'SCHEMA', N'hr', N'TABLE', N'shift', N'COLUMN', N'grace_minutes';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Half-day threshold', N'SCHEMA', N'hr', N'TABLE', N'shift', N'COLUMN', N'half_day_hours';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Shift and weekly off per employee.', N'SCHEMA', N'hr', N'TABLE', N'employee_shift';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee', N'SCHEMA', N'hr', N'TABLE', N'employee_shift', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Shift', N'SCHEMA', N'hr', N'TABLE', N'employee_shift', N'COLUMN', N'shift_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'e.g. SUN', N'SCHEMA', N'hr', N'TABLE', N'employee_shift', N'COLUMN', N'weekly_off_days';
EXEC sys.sp_addextendedproperty N'MS_Description', N'From', N'SCHEMA', N'hr', N'TABLE', N'employee_shift', N'COLUMN', N'from_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'To', N'SCHEMA', N'hr', N'TABLE', N'employee_shift', N'COLUMN', N'to_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Holiday calendar.', N'SCHEMA', N'hr', N'TABLE', N'holiday';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch (blank = all)', N'SCHEMA', N'hr', N'TABLE', N'holiday', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'hr', N'TABLE', N'holiday', N'COLUMN', N'holiday_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Holiday', N'SCHEMA', N'hr', N'TABLE', N'holiday', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: National, Festival, Optional.', N'SCHEMA', N'hr', N'TABLE', N'holiday', N'COLUMN', N'holiday_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Daily attendance (app, biometric, or engineer duty log).', N'SCHEMA', N'hr', N'TABLE', N'attendance';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee', N'SCHEMA', N'hr', N'TABLE', N'attendance', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'hr', N'TABLE', N'attendance', N'COLUMN', N'attendance_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Shift', N'SCHEMA', N'hr', N'TABLE', N'attendance', N'COLUMN', N'shift_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'In', N'SCHEMA', N'hr', N'TABLE', N'attendance', N'COLUMN', N'check_in_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'In location', N'SCHEMA', N'hr', N'TABLE', N'attendance', N'COLUMN', N'check_in_latitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'In location', N'SCHEMA', N'hr', N'TABLE', N'attendance', N'COLUMN', N'check_in_longitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Out', N'SCHEMA', N'hr', N'TABLE', N'attendance', N'COLUMN', N'check_out_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Out location', N'SCHEMA', N'hr', N'TABLE', N'attendance', N'COLUMN', N'check_out_latitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Out location', N'SCHEMA', N'hr', N'TABLE', N'attendance', N'COLUMN', N'check_out_longitude';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Source Allowed: App, Biometric, Duty log, Manual.', N'SCHEMA', N'hr', N'TABLE', N'attendance', N'COLUMN', N'source';
EXEC sys.sp_addextendedproperty N'MS_Description', N'From engineer duty log', N'SCHEMA', N'hr', N'TABLE', N'attendance', N'COLUMN', N'duty_log_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Hours', N'SCHEMA', N'hr', N'TABLE', N'attendance', N'COLUMN', N'worked_hours';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Present, Absent, Half day, Leave, Holiday, Week off, On duty.', N'SCHEMA', N'hr', N'TABLE', N'attendance', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Corrected', N'SCHEMA', N'hr', N'TABLE', N'attendance', N'COLUMN', N'is_regularized';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Requests to correct attendance.', N'SCHEMA', N'hr', N'TABLE', N'attendance_regularization';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Attendance', N'SCHEMA', N'hr', N'TABLE', N'attendance_regularization', N'COLUMN', N'attendance_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee', N'SCHEMA', N'hr', N'TABLE', N'attendance_regularization', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Requested', N'SCHEMA', N'hr', N'TABLE', N'attendance_regularization', N'COLUMN', N'requested_status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Reason', N'SCHEMA', N'hr', N'TABLE', N'attendance_regularization', N'COLUMN', N'reason';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Pending, Approved, Rejected.', N'SCHEMA', N'hr', N'TABLE', N'attendance_regularization', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Approver', N'SCHEMA', N'hr', N'TABLE', N'attendance_regularization', N'COLUMN', N'approver_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Leave types.', N'SCHEMA', N'hr', N'TABLE', N'leave_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'e.g. CL, SL, EL', N'SCHEMA', N'hr', N'TABLE', N'leave_type', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name', N'SCHEMA', N'hr', N'TABLE', N'leave_type', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Per year', N'SCHEMA', N'hr', N'TABLE', N'leave_type', N'COLUMN', N'annual_quota';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Max carry forward', N'SCHEMA', N'hr', N'TABLE', N'leave_type', N'COLUMN', N'carry_forward_max';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Paid', N'SCHEMA', N'hr', N'TABLE', N'leave_type', N'COLUMN', N'is_paid';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Encashable', N'SCHEMA', N'hr', N'TABLE', N'leave_type', N'COLUMN', N'is_encashable';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Leave balance per employee per year.', N'SCHEMA', N'hr', N'TABLE', N'leave_balance';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee', N'SCHEMA', N'hr', N'TABLE', N'leave_balance', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type', N'SCHEMA', N'hr', N'TABLE', N'leave_balance', N'COLUMN', N'leave_type_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Year', N'SCHEMA', N'hr', N'TABLE', N'leave_balance', N'COLUMN', N'leave_year';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Opening', N'SCHEMA', N'hr', N'TABLE', N'leave_balance', N'COLUMN', N'opening';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Accrued', N'SCHEMA', N'hr', N'TABLE', N'leave_balance', N'COLUMN', N'accrued';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Availed', N'SCHEMA', N'hr', N'TABLE', N'leave_balance', N'COLUMN', N'availed';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Encashed', N'SCHEMA', N'hr', N'TABLE', N'leave_balance', N'COLUMN', N'encashed';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Closing', N'SCHEMA', N'hr', N'TABLE', N'leave_balance', N'COLUMN', N'closing';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Leave applications.', N'SCHEMA', N'hr', N'TABLE', N'leave_request';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee', N'SCHEMA', N'hr', N'TABLE', N'leave_request', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type', N'SCHEMA', N'hr', N'TABLE', N'leave_request', N'COLUMN', N'leave_type_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'From', N'SCHEMA', N'hr', N'TABLE', N'leave_request', N'COLUMN', N'from_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'To', N'SCHEMA', N'hr', N'TABLE', N'leave_request', N'COLUMN', N'to_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Half day', N'SCHEMA', N'hr', N'TABLE', N'leave_request', N'COLUMN', N'is_half_day';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Days', N'SCHEMA', N'hr', N'TABLE', N'leave_request', N'COLUMN', N'days';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Reason', N'SCHEMA', N'hr', N'TABLE', N'leave_request', N'COLUMN', N'reason';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Pending, Approved, Rejected, Cancelled.', N'SCHEMA', N'hr', N'TABLE', N'leave_request', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Approver', N'SCHEMA', N'hr', N'TABLE', N'leave_request', N'COLUMN', N'approver_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Acted', N'SCHEMA', N'hr', N'TABLE', N'leave_request', N'COLUMN', N'acted_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Earnings, deductions and employer contributions.', N'SCHEMA', N'hr', N'TABLE', N'salary_component';
EXEC sys.sp_addextendedproperty N'MS_Description', N'e.g. BASIC, HRA, PF_EE', N'SCHEMA', N'hr', N'TABLE', N'salary_component', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name', N'SCHEMA', N'hr', N'TABLE', N'salary_component', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Earning, Deduction, Employer contribution.', N'SCHEMA', N'hr', N'TABLE', N'salary_component', N'COLUMN', N'component_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Calculation Allowed: Fixed, Percent of basic, Formula, Statutory.', N'SCHEMA', N'hr', N'TABLE', N'salary_component', N'COLUMN', N'calculation_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Taxable', N'SCHEMA', N'hr', N'TABLE', N'salary_component', N'COLUMN', N'is_taxable';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Counts for PF', N'SCHEMA', N'hr', N'TABLE', N'salary_component', N'COLUMN', N'is_pf_wage';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Counts for ESI', N'SCHEMA', N'hr', N'TABLE', N'salary_component', N'COLUMN', N'is_esi_wage';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Ledger account', N'SCHEMA', N'hr', N'TABLE', N'salary_component', N'COLUMN', N'gl_account_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee salary structure with effective dates.', N'SCHEMA', N'hr', N'TABLE', N'salary_structure';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee', N'SCHEMA', N'hr', N'TABLE', N'salary_structure', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'From', N'SCHEMA', N'hr', N'TABLE', N'salary_structure', N'COLUMN', N'effective_from';
EXEC sys.sp_addextendedproperty N'MS_Description', N'To', N'SCHEMA', N'hr', N'TABLE', N'salary_structure', N'COLUMN', N'effective_to';
EXEC sys.sp_addextendedproperty N'MS_Description', N'CTC', N'SCHEMA', N'hr', N'TABLE', N'salary_structure', N'COLUMN', N'annual_ctc';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Gross per month', N'SCHEMA', N'hr', N'TABLE', N'salary_structure', N'COLUMN', N'monthly_gross';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Components in a structure.', N'SCHEMA', N'hr', N'TABLE', N'salary_structure_line';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Structure', N'SCHEMA', N'hr', N'TABLE', N'salary_structure_line', N'COLUMN', N'salary_structure_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Component', N'SCHEMA', N'hr', N'TABLE', N'salary_structure_line', N'COLUMN', N'salary_component_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Amount', N'SCHEMA', N'hr', N'TABLE', N'salary_structure_line', N'COLUMN', N'monthly_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'%', N'SCHEMA', N'hr', N'TABLE', N'salary_structure_line', N'COLUMN', N'percentage';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Formula', N'SCHEMA', N'hr', N'TABLE', N'salary_structure_line', N'COLUMN', N'formula';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PF, ESI, PT, LWF, TDS rates and ceilings.', N'SCHEMA', N'hr', N'TABLE', N'statutory_config';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company', N'SCHEMA', N'hr', N'TABLE', N'statutory_config', N'COLUMN', N'company_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: PF, ESI, PT, LWF, TDS.', N'SCHEMA', N'hr', N'TABLE', N'statutory_config', N'COLUMN', N'config_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'State (PT, LWF)', N'SCHEMA', N'hr', N'TABLE', N'statutory_config', N'COLUMN', N'state_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'From', N'SCHEMA', N'hr', N'TABLE', N'statutory_config', N'COLUMN', N'effective_from';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee rate', N'SCHEMA', N'hr', N'TABLE', N'statutory_config', N'COLUMN', N'employee_rate';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employer rate', N'SCHEMA', N'hr', N'TABLE', N'statutory_config', N'COLUMN', N'employer_rate';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Ceiling', N'SCHEMA', N'hr', N'TABLE', N'statutory_config', N'COLUMN', N'wage_ceiling';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Slabs (PT / TDS)', N'SCHEMA', N'hr', N'TABLE', N'statutory_config', N'COLUMN', N'slab_json';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Monthly payroll run.', N'SCHEMA', N'hr', N'TABLE', N'payroll_run';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company', N'SCHEMA', N'hr', N'TABLE', N'payroll_run', N'COLUMN', N'company_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch (blank = all)', N'SCHEMA', N'hr', N'TABLE', N'payroll_run', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Month', N'SCHEMA', N'hr', N'TABLE', N'payroll_run', N'COLUMN', N'period_month';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Run date', N'SCHEMA', N'hr', N'TABLE', N'payroll_run', N'COLUMN', N'run_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Processed, Approved, Paid, Locked.', N'SCHEMA', N'hr', N'TABLE', N'payroll_run', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Gross', N'SCHEMA', N'hr', N'TABLE', N'payroll_run', N'COLUMN', N'total_gross';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Deductions', N'SCHEMA', N'hr', N'TABLE', N'payroll_run', N'COLUMN', N'total_deductions';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Net', N'SCHEMA', N'hr', N'TABLE', N'payroll_run', N'COLUMN', N'total_net';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Ledger posting', N'SCHEMA', N'hr', N'TABLE', N'payroll_run', N'COLUMN', N'journal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Payslip per employee per run.', N'SCHEMA', N'hr', N'TABLE', N'payslip';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Run', N'SCHEMA', N'hr', N'TABLE', N'payslip', N'COLUMN', N'payroll_run_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee', N'SCHEMA', N'hr', N'TABLE', N'payslip', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Paid days', N'SCHEMA', N'hr', N'TABLE', N'payslip', N'COLUMN', N'paid_days';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Loss of pay', N'SCHEMA', N'hr', N'TABLE', N'payslip', N'COLUMN', N'lop_days';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Gross', N'SCHEMA', N'hr', N'TABLE', N'payslip', N'COLUMN', N'gross';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Deductions', N'SCHEMA', N'hr', N'TABLE', N'payslip', N'COLUMN', N'total_deductions';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Net', N'SCHEMA', N'hr', N'TABLE', N'payslip', N'COLUMN', N'net_pay';
EXEC sys.sp_addextendedproperty N'MS_Description', N'PDF', N'SCHEMA', N'hr', N'TABLE', N'payslip', N'COLUMN', N'pdf_attachment_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Bank ref', N'SCHEMA', N'hr', N'TABLE', N'payslip', N'COLUMN', N'payment_reference';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Component amounts in a payslip.', N'SCHEMA', N'hr', N'TABLE', N'payslip_line';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Payslip', N'SCHEMA', N'hr', N'TABLE', N'payslip_line', N'COLUMN', N'payslip_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Component', N'SCHEMA', N'hr', N'TABLE', N'payslip_line', N'COLUMN', N'salary_component_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Amount', N'SCHEMA', N'hr', N'TABLE', N'payslip_line', N'COLUMN', N'amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Loans and salary advances.', N'SCHEMA', N'hr', N'TABLE', N'employee_loan';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee', N'SCHEMA', N'hr', N'TABLE', N'employee_loan', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Loan, Salary advance.', N'SCHEMA', N'hr', N'TABLE', N'employee_loan', N'COLUMN', N'loan_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Amount', N'SCHEMA', N'hr', N'TABLE', N'employee_loan', N'COLUMN', N'amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'hr', N'TABLE', N'employee_loan', N'COLUMN', N'sanctioned_on';
EXEC sys.sp_addextendedproperty N'MS_Description', N'EMI', N'SCHEMA', N'hr', N'TABLE', N'employee_loan', N'COLUMN', N'emi_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Installments', N'SCHEMA', N'hr', N'TABLE', N'employee_loan', N'COLUMN', N'installments';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Balance', N'SCHEMA', N'hr', N'TABLE', N'employee_loan', N'COLUMN', N'balance';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Active, Closed.', N'SCHEMA', N'hr', N'TABLE', N'employee_loan', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Expense claims (travel km from trips, food, lodging).', N'SCHEMA', N'hr', N'TABLE', N'expense_claim';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Number', N'SCHEMA', N'hr', N'TABLE', N'expense_claim', N'COLUMN', N'claim_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee', N'SCHEMA', N'hr', N'TABLE', N'expense_claim', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'hr', N'TABLE', N'expense_claim', N'COLUMN', N'claim_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'From', N'SCHEMA', N'hr', N'TABLE', N'expense_claim', N'COLUMN', N'period_from';
EXEC sys.sp_addextendedproperty N'MS_Description', N'To', N'SCHEMA', N'hr', N'TABLE', N'expense_claim', N'COLUMN', N'period_to';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Claimed', N'SCHEMA', N'hr', N'TABLE', N'expense_claim', N'COLUMN', N'total_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Approved', N'SCHEMA', N'hr', N'TABLE', N'expense_claim', N'COLUMN', N'approved_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Submitted, Approved, Rejected, Paid.', N'SCHEMA', N'hr', N'TABLE', N'expense_claim', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Paid via Allowed: Payroll, Direct.', N'SCHEMA', N'hr', N'TABLE', N'expense_claim', N'COLUMN', N'paid_via';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Payroll', N'SCHEMA', N'hr', N'TABLE', N'expense_claim', N'COLUMN', N'payroll_run_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Ledger posting', N'SCHEMA', N'hr', N'TABLE', N'expense_claim', N'COLUMN', N'journal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Claim lines; travel lines link to trips.', N'SCHEMA', N'hr', N'TABLE', N'expense_claim_line';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Claim', N'SCHEMA', N'hr', N'TABLE', N'expense_claim_line', N'COLUMN', N'expense_claim_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type', N'SCHEMA', N'hr', N'TABLE', N'expense_claim_line', N'COLUMN', N'expense_type_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'hr', N'TABLE', N'expense_claim_line', N'COLUMN', N'expense_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Trip', N'SCHEMA', N'hr', N'TABLE', N'expense_claim_line', N'COLUMN', N'trip_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Km', N'SCHEMA', N'hr', N'TABLE', N'expense_claim_line', N'COLUMN', N'km';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Rate', N'SCHEMA', N'hr', N'TABLE', N'expense_claim_line', N'COLUMN', N'rate_per_km';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Amount', N'SCHEMA', N'hr', N'TABLE', N'expense_claim_line', N'COLUMN', N'amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Bill', N'SCHEMA', N'hr', N'TABLE', N'expense_claim_line', N'COLUMN', N'receipt_attachment_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Remarks', N'SCHEMA', N'hr', N'TABLE', N'expense_claim_line', N'COLUMN', N'remarks';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company assets given to employees (phone, laptop, tool kit, SIM).', N'SCHEMA', N'hr', N'TABLE', N'asset';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Tag', N'SCHEMA', N'hr', N'TABLE', N'asset', N'COLUMN', N'asset_tag';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type', N'SCHEMA', N'hr', N'TABLE', N'asset', N'COLUMN', N'asset_type_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Description', N'SCHEMA', N'hr', N'TABLE', N'asset', N'COLUMN', N'description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Serial', N'SCHEMA', N'hr', N'TABLE', N'asset', N'COLUMN', N'serial_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Bought', N'SCHEMA', N'hr', N'TABLE', N'asset', N'COLUMN', N'purchase_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Value', N'SCHEMA', N'hr', N'TABLE', N'asset', N'COLUMN', N'purchase_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: In store, Assigned, Repair, Retired.', N'SCHEMA', N'hr', N'TABLE', N'asset', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Who holds which asset.', N'SCHEMA', N'hr', N'TABLE', N'asset_assignment';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Asset', N'SCHEMA', N'hr', N'TABLE', N'asset_assignment', N'COLUMN', N'asset_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee', N'SCHEMA', N'hr', N'TABLE', N'asset_assignment', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Assigned', N'SCHEMA', N'hr', N'TABLE', N'asset_assignment', N'COLUMN', N'assigned_on';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Returned', N'SCHEMA', N'hr', N'TABLE', N'asset_assignment', N'COLUMN', N'returned_on';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Condition', N'SCHEMA', N'hr', N'TABLE', N'asset_assignment', N'COLUMN', N'condition_on_return';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Periodic performance reviews.', N'SCHEMA', N'hr', N'TABLE', N'performance_review';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee', N'SCHEMA', N'hr', N'TABLE', N'performance_review', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'e.g. FY2026-27 H1', N'SCHEMA', N'hr', N'TABLE', N'performance_review', N'COLUMN', N'review_period';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Reviewer', N'SCHEMA', N'hr', N'TABLE', N'performance_review', N'COLUMN', N'reviewer_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Rating', N'SCHEMA', N'hr', N'TABLE', N'performance_review', N'COLUMN', N'rating';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Goals and scores', N'SCHEMA', N'hr', N'TABLE', N'performance_review', N'COLUMN', N'goals_json';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Comments', N'SCHEMA', N'hr', N'TABLE', N'performance_review', N'COLUMN', N'comments';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Self review, Manager review, Closed.', N'SCHEMA', N'hr', N'TABLE', N'performance_review', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Open positions.', N'SCHEMA', N'hr', N'TABLE', N'job_opening';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Title', N'SCHEMA', N'hr', N'TABLE', N'job_opening', N'COLUMN', N'title';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Designation', N'SCHEMA', N'hr', N'TABLE', N'job_opening', N'COLUMN', N'designation_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'hr', N'TABLE', N'job_opening', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Positions', N'SCHEMA', N'hr', N'TABLE', N'job_opening', N'COLUMN', N'openings';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Open, On hold, Closed.', N'SCHEMA', N'hr', N'TABLE', N'job_opening', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Applicants for an opening.', N'SCHEMA', N'hr', N'TABLE', N'candidate';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Opening', N'SCHEMA', N'hr', N'TABLE', N'candidate', N'COLUMN', N'job_opening_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name', N'SCHEMA', N'hr', N'TABLE', N'candidate', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Phone', N'SCHEMA', N'hr', N'TABLE', N'candidate', N'COLUMN', N'phone';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Email', N'SCHEMA', N'hr', N'TABLE', N'candidate', N'COLUMN', N'email';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Resume', N'SCHEMA', N'hr', N'TABLE', N'candidate', N'COLUMN', N'resume_attachment_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Stage Allowed: Applied, Screening, Interview, Offered, Joined, Rejected.', N'SCHEMA', N'hr', N'TABLE', N'candidate', N'COLUMN', N'stage';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee record once joined', N'SCHEMA', N'hr', N'TABLE', N'candidate', N'COLUMN', N'joined_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Exit settlement.', N'SCHEMA', N'hr', N'TABLE', N'full_final_settlement';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee', N'SCHEMA', N'hr', N'TABLE', N'full_final_settlement', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Last day', N'SCHEMA', N'hr', N'TABLE', N'full_final_settlement', N'COLUMN', N'last_working_day';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Leave encashment', N'SCHEMA', N'hr', N'TABLE', N'full_final_settlement', N'COLUMN', N'leave_encashment';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Gratuity', N'SCHEMA', N'hr', N'TABLE', N'full_final_settlement', N'COLUMN', N'gratuity';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Notice recovery', N'SCHEMA', N'hr', N'TABLE', N'full_final_settlement', N'COLUMN', N'notice_recovery';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Loan recovery', N'SCHEMA', N'hr', N'TABLE', N'full_final_settlement', N'COLUMN', N'loan_recovery';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Net', N'SCHEMA', N'hr', N'TABLE', N'full_final_settlement', N'COLUMN', N'net_payable';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Approved, Paid.', N'SCHEMA', N'hr', N'TABLE', N'full_final_settlement', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Paid', N'SCHEMA', N'hr', N'TABLE', N'full_final_settlement', N'COLUMN', N'paid_on';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee queries to HR / admin.', N'SCHEMA', N'hr', N'TABLE', N'helpdesk_ticket';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Raised by', N'SCHEMA', N'hr', N'TABLE', N'helpdesk_ticket', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Category', N'SCHEMA', N'hr', N'TABLE', N'helpdesk_ticket', N'COLUMN', N'category_lookup_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Subject', N'SCHEMA', N'hr', N'TABLE', N'helpdesk_ticket', N'COLUMN', N'subject';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Details', N'SCHEMA', N'hr', N'TABLE', N'helpdesk_ticket', N'COLUMN', N'description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Handler', N'SCHEMA', N'hr', N'TABLE', N'helpdesk_ticket', N'COLUMN', N'assigned_to_employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Open, In progress, Resolved, Closed.', N'SCHEMA', N'hr', N'TABLE', N'helpdesk_ticket', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Resolved', N'SCHEMA', N'hr', N'TABLE', N'helpdesk_ticket', N'COLUMN', N'resolved_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Financial years (April-March).', N'SCHEMA', N'acc', N'TABLE', N'fiscal_year';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company', N'SCHEMA', N'acc', N'TABLE', N'fiscal_year', N'COLUMN', N'company_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'e.g. FY2026-27', N'SCHEMA', N'acc', N'TABLE', N'fiscal_year', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Start', N'SCHEMA', N'acc', N'TABLE', N'fiscal_year', N'COLUMN', N'start_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'End', N'SCHEMA', N'acc', N'TABLE', N'fiscal_year', N'COLUMN', N'end_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Closed', N'SCHEMA', N'acc', N'TABLE', N'fiscal_year', N'COLUMN', N'is_closed';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Monthly periods; locking stops back-dated postings.', N'SCHEMA', N'acc', N'TABLE', N'accounting_period';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Year', N'SCHEMA', N'acc', N'TABLE', N'accounting_period', N'COLUMN', N'fiscal_year_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Month', N'SCHEMA', N'acc', N'TABLE', N'accounting_period', N'COLUMN', N'period_month';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Locked', N'SCHEMA', N'acc', N'TABLE', N'accounting_period', N'COLUMN', N'is_locked';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Locked by', N'SCHEMA', N'acc', N'TABLE', N'accounting_period', N'COLUMN', N'locked_by_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Locked at', N'SCHEMA', N'acc', N'TABLE', N'accounting_period', N'COLUMN', N'locked_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company GST registrations (one per state).', N'SCHEMA', N'acc', N'TABLE', N'gstin_registration';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company', N'SCHEMA', N'acc', N'TABLE', N'gstin_registration', N'COLUMN', N'company_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GSTIN', N'SCHEMA', N'acc', N'TABLE', N'gstin_registration', N'COLUMN', N'gstin';
EXEC sys.sp_addextendedproperty N'MS_Description', N'State', N'SCHEMA', N'acc', N'TABLE', N'gstin_registration', N'COLUMN', N'state_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Legal name', N'SCHEMA', N'acc', N'TABLE', N'gstin_registration', N'COLUMN', N'legal_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Trade name', N'SCHEMA', N'acc', N'TABLE', N'gstin_registration', N'COLUMN', N'trade_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Principal place', N'SCHEMA', N'acc', N'TABLE', N'gstin_registration', N'COLUMN', N'address';
EXEC sys.sp_addextendedproperty N'MS_Description', N'E-invoicing applicable', N'SCHEMA', N'acc', N'TABLE', N'gstin_registration', N'COLUMN', N'is_e_invoice_enabled';
EXEC sys.sp_addextendedproperty N'MS_Description', N'AWS Secrets Manager key for GST portal / IRP', N'SCHEMA', N'acc', N'TABLE', N'gstin_registration', N'COLUMN', N'credential_secret_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GST rate slabs with CGST/SGST/IGST split and ledger accounts.', N'SCHEMA', N'acc', N'TABLE', N'gst_rate';
EXEC sys.sp_addextendedproperty N'MS_Description', N'e.g. GST18', N'SCHEMA', N'acc', N'TABLE', N'gst_rate', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Description', N'SCHEMA', N'acc', N'TABLE', N'gst_rate', N'COLUMN', N'description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Total %', N'SCHEMA', N'acc', N'TABLE', N'gst_rate', N'COLUMN', N'total_rate';
EXEC sys.sp_addextendedproperty N'MS_Description', N'CGST %', N'SCHEMA', N'acc', N'TABLE', N'gst_rate', N'COLUMN', N'cgst_rate';
EXEC sys.sp_addextendedproperty N'MS_Description', N'SGST %', N'SCHEMA', N'acc', N'TABLE', N'gst_rate', N'COLUMN', N'sgst_rate';
EXEC sys.sp_addextendedproperty N'MS_Description', N'IGST %', N'SCHEMA', N'acc', N'TABLE', N'gst_rate', N'COLUMN', N'igst_rate';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Cess %', N'SCHEMA', N'acc', N'TABLE', N'gst_rate', N'COLUMN', N'cess_rate';
EXEC sys.sp_addextendedproperty N'MS_Description', N'From', N'SCHEMA', N'acc', N'TABLE', N'gst_rate', N'COLUMN', N'effective_from';
EXEC sys.sp_addextendedproperty N'MS_Description', N'To', N'SCHEMA', N'acc', N'TABLE', N'gst_rate', N'COLUMN', N'effective_to';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Output tax account', N'SCHEMA', N'acc', N'TABLE', N'gst_rate', N'COLUMN', N'output_gl_account_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Input credit account', N'SCHEMA', N'acc', N'TABLE', N'gst_rate', N'COLUMN', N'input_gl_account_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Tax treatment: intra-state, inter-state, exempt, export, RCM.', N'SCHEMA', N'acc', N'TABLE', N'tax_group';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Code', N'SCHEMA', N'acc', N'TABLE', N'tax_group', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name', N'SCHEMA', N'acc', N'TABLE', N'tax_group', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Description', N'SCHEMA', N'acc', N'TABLE', N'tax_group', N'COLUMN', N'description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'TDS sections and rates.', N'SCHEMA', N'acc', N'TABLE', N'tds_section';
EXEC sys.sp_addextendedproperty N'MS_Description', N'e.g. 194C, 194J, 194Q, 192', N'SCHEMA', N'acc', N'TABLE', N'tds_section', N'COLUMN', N'section_code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Nature of payment', N'SCHEMA', N'acc', N'TABLE', N'tds_section', N'COLUMN', N'description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Rate (individual/HUF)', N'SCHEMA', N'acc', N'TABLE', N'tds_section', N'COLUMN', N'rate_individual';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Rate (others)', N'SCHEMA', N'acc', N'TABLE', N'tds_section', N'COLUMN', N'rate_company';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Single payment threshold', N'SCHEMA', N'acc', N'TABLE', N'tds_section', N'COLUMN', N'threshold_single';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Annual threshold', N'SCHEMA', N'acc', N'TABLE', N'tds_section', N'COLUMN', N'threshold_annual';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Top-level classes.', N'SCHEMA', N'acc', N'TABLE', N'account_class';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Code', N'SCHEMA', N'acc', N'TABLE', N'account_class', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name', N'SCHEMA', N'acc', N'TABLE', N'account_class', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Asset, Liability, Equity, Income, Expense.', N'SCHEMA', N'acc', N'TABLE', N'account_class', N'COLUMN', N'class_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Account groups (Tally-style).', N'SCHEMA', N'acc', N'TABLE', N'account_group';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Code', N'SCHEMA', N'acc', N'TABLE', N'account_group', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'e.g. Sundry Debtors', N'SCHEMA', N'acc', N'TABLE', N'account_group', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Class', N'SCHEMA', N'acc', N'TABLE', N'account_group', N'COLUMN', N'account_class_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Parent', N'SCHEMA', N'acc', N'TABLE', N'account_group', N'COLUMN', N'parent_group_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Chart of accounts (ledgers).', N'SCHEMA', N'acc', N'TABLE', N'gl_account';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company', N'SCHEMA', N'acc', N'TABLE', N'gl_account', N'COLUMN', N'company_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Code', N'SCHEMA', N'acc', N'TABLE', N'gl_account', N'COLUMN', N'account_code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name', N'SCHEMA', N'acc', N'TABLE', N'gl_account', N'COLUMN', N'account_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Group', N'SCHEMA', N'acc', N'TABLE', N'gl_account', N'COLUMN', N'account_group_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Behaviour Allowed: Bank, Cash, Receivable, Payable, Tax, Stock, Income, Expense, General.', N'SCHEMA', N'acc', N'TABLE', N'gl_account', N'COLUMN', N'account_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Sub-ledger control (debtors, creditors)', N'SCHEMA', N'acc', N'TABLE', N'gl_account', N'COLUMN', N'is_control_account';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Manual journals allowed', N'SCHEMA', N'acc', N'TABLE', N'gl_account', N'COLUMN', N'allow_manual_entry';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Tally ledger', N'SCHEMA', N'acc', N'TABLE', N'gl_account', N'COLUMN', N'tally_ledger_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'SAP GL code', N'SCHEMA', N'acc', N'TABLE', N'gl_account', N'COLUMN', N'sap_gl_code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Cost centres by branch and business line.', N'SCHEMA', N'acc', N'TABLE', N'cost_centre';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Code', N'SCHEMA', N'acc', N'TABLE', N'cost_centre', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name', N'SCHEMA', N'acc', N'TABLE', N'cost_centre', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'acc', N'TABLE', N'cost_centre', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand', N'SCHEMA', N'acc', N'TABLE', N'cost_centre', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Branch, Warehouse, Machines, Parts, Service, Admin.', N'SCHEMA', N'acc', N'TABLE', N'cost_centre', N'COLUMN', N'cost_centre_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Journal header: one per posting document.', N'SCHEMA', N'acc', N'TABLE', N'journal';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Number', N'SCHEMA', N'acc', N'TABLE', N'journal', N'COLUMN', N'journal_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company', N'SCHEMA', N'acc', N'TABLE', N'journal', N'COLUMN', N'company_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch', N'SCHEMA', N'acc', N'TABLE', N'journal', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'acc', N'TABLE', N'journal', N'COLUMN', N'journal_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Year', N'SCHEMA', N'acc', N'TABLE', N'journal', N'COLUMN', N'fiscal_year_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Sales, Purchase, Receipt, Payment, Payroll, Stock, Manual, Opening, Contra.', N'SCHEMA', N'acc', N'TABLE', N'journal', N'COLUMN', N'journal_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'e.g. SALES_INVOICE', N'SCHEMA', N'acc', N'TABLE', N'journal', N'COLUMN', N'source_document_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Document ID', N'SCHEMA', N'acc', N'TABLE', N'journal', N'COLUMN', N'source_document_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Narration', N'SCHEMA', N'acc', N'TABLE', N'journal', N'COLUMN', N'narration';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Debit total', N'SCHEMA', N'acc', N'TABLE', N'journal', N'COLUMN', N'total_debit';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Credit total (must equal debit)', N'SCHEMA', N'acc', N'TABLE', N'journal', N'COLUMN', N'total_credit';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Draft, Posted, Reversed.', N'SCHEMA', N'acc', N'TABLE', N'journal', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Reversal of', N'SCHEMA', N'acc', N'TABLE', N'journal', N'COLUMN', N'reversed_journal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Posted by', N'SCHEMA', N'acc', N'TABLE', N'journal', N'COLUMN', N'posted_by_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Posted', N'SCHEMA', N'acc', N'TABLE', N'journal', N'COLUMN', N'posted_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Ledger lines (double entry).', N'SCHEMA', N'acc', N'TABLE', N'gl_entry';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Journal', N'SCHEMA', N'acc', N'TABLE', N'gl_entry', N'COLUMN', N'journal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Line', N'SCHEMA', N'acc', N'TABLE', N'gl_entry', N'COLUMN', N'line_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'acc', N'TABLE', N'gl_entry', N'COLUMN', N'entry_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Account', N'SCHEMA', N'acc', N'TABLE', N'gl_entry', N'COLUMN', N'gl_account_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Debit', N'SCHEMA', N'acc', N'TABLE', N'gl_entry', N'COLUMN', N'debit';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Credit', N'SCHEMA', N'acc', N'TABLE', N'gl_entry', N'COLUMN', N'credit';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Cost centre', N'SCHEMA', N'acc', N'TABLE', N'gl_entry', N'COLUMN', N'cost_centre_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand (for brand-wise P&L)', N'SCHEMA', N'acc', N'TABLE', N'gl_entry', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Branch (for warehouse / branch roll-up)', N'SCHEMA', N'acc', N'TABLE', N'gl_entry', N'COLUMN', N'branch_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Party type Allowed: Customer, Supplier, Employee.', N'SCHEMA', N'acc', N'TABLE', N'gl_entry', N'COLUMN', N'party_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer', N'SCHEMA', N'acc', N'TABLE', N'gl_entry', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier', N'SCHEMA', N'acc', N'TABLE', N'gl_entry', N'COLUMN', N'supplier_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee', N'SCHEMA', N'acc', N'TABLE', N'gl_entry', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Line narration', N'SCHEMA', N'acc', N'TABLE', N'gl_entry', N'COLUMN', N'narration';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Opening balances by account and party at go-live.', N'SCHEMA', N'acc', N'TABLE', N'opening_balance';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company', N'SCHEMA', N'acc', N'TABLE', N'opening_balance', N'COLUMN', N'company_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Year', N'SCHEMA', N'acc', N'TABLE', N'opening_balance', N'COLUMN', N'fiscal_year_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Account', N'SCHEMA', N'acc', N'TABLE', N'opening_balance', N'COLUMN', N'gl_account_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Party type Allowed: Customer, Supplier, Employee.', N'SCHEMA', N'acc', N'TABLE', N'opening_balance', N'COLUMN', N'party_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Customer', N'SCHEMA', N'acc', N'TABLE', N'opening_balance', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Supplier', N'SCHEMA', N'acc', N'TABLE', N'opening_balance', N'COLUMN', N'supplier_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Old bill number', N'SCHEMA', N'acc', N'TABLE', N'opening_balance', N'COLUMN', N'reference_document_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Bill date', N'SCHEMA', N'acc', N'TABLE', N'opening_balance', N'COLUMN', N'document_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Due', N'SCHEMA', N'acc', N'TABLE', N'opening_balance', N'COLUMN', N'due_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Debit', N'SCHEMA', N'acc', N'TABLE', N'opening_balance', N'COLUMN', N'debit';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Credit', N'SCHEMA', N'acc', N'TABLE', N'opening_balance', N'COLUMN', N'credit';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Opening journal', N'SCHEMA', N'acc', N'TABLE', N'opening_balance', N'COLUMN', N'journal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Company bank and cash accounts.', N'SCHEMA', N'acc', N'TABLE', N'bank_account';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Ledger', N'SCHEMA', N'acc', N'TABLE', N'bank_account', N'COLUMN', N'gl_account_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Bank', N'SCHEMA', N'acc', N'TABLE', N'bank_account', N'COLUMN', N'bank_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Account name', N'SCHEMA', N'acc', N'TABLE', N'bank_account', N'COLUMN', N'account_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Number (masked in UI)', N'SCHEMA', N'acc', N'TABLE', N'bank_account', N'COLUMN', N'account_number';
EXEC sys.sp_addextendedproperty N'MS_Description', N'IFSC', N'SCHEMA', N'acc', N'TABLE', N'bank_account', N'COLUMN', N'ifsc';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Bank branch', N'SCHEMA', N'acc', N'TABLE', N'bank_account', N'COLUMN', N'branch_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Current, Cash credit, Overdraft, Savings, Cash.', N'SCHEMA', N'acc', N'TABLE', N'bank_account', N'COLUMN', N'account_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Currency', N'SCHEMA', N'acc', N'TABLE', N'bank_account', N'COLUMN', N'currency_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Reconciled up to', N'SCHEMA', N'acc', N'TABLE', N'bank_account', N'COLUMN', N'last_reconciled_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Balance at last reconciliation', N'SCHEMA', N'acc', N'TABLE', N'bank_account', N'COLUMN', N'reconciled_balance';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Imported bank statement lines for reconciliation.', N'SCHEMA', N'acc', N'TABLE', N'bank_statement_line';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Account', N'SCHEMA', N'acc', N'TABLE', N'bank_statement_line', N'COLUMN', N'bank_account_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'acc', N'TABLE', N'bank_statement_line', N'COLUMN', N'statement_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Narration', N'SCHEMA', N'acc', N'TABLE', N'bank_statement_line', N'COLUMN', N'description';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Ref', N'SCHEMA', N'acc', N'TABLE', N'bank_statement_line', N'COLUMN', N'reference';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Withdrawal', N'SCHEMA', N'acc', N'TABLE', N'bank_statement_line', N'COLUMN', N'debit';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Deposit', N'SCHEMA', N'acc', N'TABLE', N'bank_statement_line', N'COLUMN', N'credit';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Balance', N'SCHEMA', N'acc', N'TABLE', N'bank_statement_line', N'COLUMN', N'balance';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Import batch', N'SCHEMA', N'acc', N'TABLE', N'bank_statement_line', N'COLUMN', N'file_import_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Bank / cash book entries.', N'SCHEMA', N'acc', N'TABLE', N'bank_txn';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Account', N'SCHEMA', N'acc', N'TABLE', N'bank_txn', N'COLUMN', N'bank_account_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'acc', N'TABLE', N'bank_txn', N'COLUMN', N'txn_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Value date', N'SCHEMA', N'acc', N'TABLE', N'bank_txn', N'COLUMN', N'value_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Type Allowed: Receipt, Payment, Transfer, Charges, Interest.', N'SCHEMA', N'acc', N'TABLE', N'bank_txn', N'COLUMN', N'txn_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Amount (+ in / - out)', N'SCHEMA', N'acc', N'TABLE', N'bank_txn', N'COLUMN', N'amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Ref', N'SCHEMA', N'acc', N'TABLE', N'bank_txn', N'COLUMN', N'reference_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Journal', N'SCHEMA', N'acc', N'TABLE', N'bank_txn', N'COLUMN', N'journal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Source', N'SCHEMA', N'acc', N'TABLE', N'bank_txn', N'COLUMN', N'source_document_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Source ID', N'SCHEMA', N'acc', N'TABLE', N'bank_txn', N'COLUMN', N'source_document_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Reconciled', N'SCHEMA', N'acc', N'TABLE', N'bank_txn', N'COLUMN', N'is_reconciled';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Reconciled date', N'SCHEMA', N'acc', N'TABLE', N'bank_txn', N'COLUMN', N'reconciled_on';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Matched statement line', N'SCHEMA', N'acc', N'TABLE', N'bank_txn', N'COLUMN', N'bank_statement_line_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Monthly budget per account and cost centre.', N'SCHEMA', N'acc', N'TABLE', N'budget';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Year', N'SCHEMA', N'acc', N'TABLE', N'budget', N'COLUMN', N'fiscal_year_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Account', N'SCHEMA', N'acc', N'TABLE', N'budget', N'COLUMN', N'gl_account_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Cost centre', N'SCHEMA', N'acc', N'TABLE', N'budget', N'COLUMN', N'cost_centre_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Month', N'SCHEMA', N'acc', N'TABLE', N'budget', N'COLUMN', N'period_month';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Budget', N'SCHEMA', N'acc', N'TABLE', N'budget', N'COLUMN', N'amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'GST split per document line (for GSTR reports).', N'SCHEMA', N'acc', N'TABLE', N'doc_tax_line';
EXEC sys.sp_addextendedproperty N'MS_Description', N'e.g. SALES_INVOICE', N'SCHEMA', N'acc', N'TABLE', N'doc_tax_line', N'COLUMN', N'document_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Document', N'SCHEMA', N'acc', N'TABLE', N'doc_tax_line', N'COLUMN', N'document_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Line', N'SCHEMA', N'acc', N'TABLE', N'doc_tax_line', N'COLUMN', N'document_line_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Rate', N'SCHEMA', N'acc', N'TABLE', N'doc_tax_line', N'COLUMN', N'gst_rate_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Component Allowed: CGST, SGST, IGST, Cess.', N'SCHEMA', N'acc', N'TABLE', N'doc_tax_line', N'COLUMN', N'tax_component';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Taxable', N'SCHEMA', N'acc', N'TABLE', N'doc_tax_line', N'COLUMN', N'taxable_value';
EXEC sys.sp_addextendedproperty N'MS_Description', N'%', N'SCHEMA', N'acc', N'TABLE', N'doc_tax_line', N'COLUMN', N'rate';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Tax', N'SCHEMA', N'acc', N'TABLE', N'doc_tax_line', N'COLUMN', N'tax_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Input credit allowed', N'SCHEMA', N'acc', N'TABLE', N'doc_tax_line', N'COLUMN', N'is_itc_eligible';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Tax account', N'SCHEMA', N'acc', N'TABLE', N'doc_tax_line', N'COLUMN', N'gl_account_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'TDS deducted by us or deducted from us.', N'SCHEMA', N'acc', N'TABLE', N'tds_entry';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Section', N'SCHEMA', N'acc', N'TABLE', N'tds_entry', N'COLUMN', N'tds_section_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Direction Allowed: Deducted by us, Deducted from us.', N'SCHEMA', N'acc', N'TABLE', N'tds_entry', N'COLUMN', N'direction';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Deductee supplier', N'SCHEMA', N'acc', N'TABLE', N'tds_entry', N'COLUMN', N'supplier_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Deductor customer', N'SCHEMA', N'acc', N'TABLE', N'tds_entry', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Employee (salary TDS)', N'SCHEMA', N'acc', N'TABLE', N'tds_entry', N'COLUMN', N'employee_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Source document', N'SCHEMA', N'acc', N'TABLE', N'tds_entry', N'COLUMN', N'document_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Source ID', N'SCHEMA', N'acc', N'TABLE', N'tds_entry', N'COLUMN', N'document_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Base', N'SCHEMA', N'acc', N'TABLE', N'tds_entry', N'COLUMN', N'base_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Rate', N'SCHEMA', N'acc', N'TABLE', N'tds_entry', N'COLUMN', N'tds_rate';
EXEC sys.sp_addextendedproperty N'MS_Description', N'TDS', N'SCHEMA', N'acc', N'TABLE', N'tds_entry', N'COLUMN', N'tds_amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'acc', N'TABLE', N'tds_entry', N'COLUMN', N'deduction_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Challan', N'SCHEMA', N'acc', N'TABLE', N'tds_entry', N'COLUMN', N'challan_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Challan date', N'SCHEMA', N'acc', N'TABLE', N'tds_entry', N'COLUMN', N'challan_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'e.g. 2026-Q2', N'SCHEMA', N'acc', N'TABLE', N'tds_entry', N'COLUMN', N'quarter';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Cheques and post-dated cheques received or issued.', N'SCHEMA', N'acc', N'TABLE', N'cheque';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Cheque number', N'SCHEMA', N'acc', N'TABLE', N'cheque', N'COLUMN', N'cheque_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Drawn on', N'SCHEMA', N'acc', N'TABLE', N'cheque', N'COLUMN', N'bank_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Date', N'SCHEMA', N'acc', N'TABLE', N'cheque', N'COLUMN', N'cheque_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Amount', N'SCHEMA', N'acc', N'TABLE', N'cheque', N'COLUMN', N'amount';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Direction Allowed: Received, Issued.', N'SCHEMA', N'acc', N'TABLE', N'cheque', N'COLUMN', N'direction';
EXEC sys.sp_addextendedproperty N'MS_Description', N'From customer', N'SCHEMA', N'acc', N'TABLE', N'cheque', N'COLUMN', N'customer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'To supplier', N'SCHEMA', N'acc', N'TABLE', N'cheque', N'COLUMN', N'supplier_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Our account', N'SCHEMA', N'acc', N'TABLE', N'cheque', N'COLUMN', N'bank_account_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: PDC, In hand, Deposited, Cleared, Bounced, Cancelled.', N'SCHEMA', N'acc', N'TABLE', N'cheque', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Deposited', N'SCHEMA', N'acc', N'TABLE', N'cheque', N'COLUMN', N'deposit_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Cleared', N'SCHEMA', N'acc', N'TABLE', N'cheque', N'COLUMN', N'clearing_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Bounce reason', N'SCHEMA', N'acc', N'TABLE', N'cheque', N'COLUMN', N'bounce_reason';
EXEC sys.sp_addextendedproperty N'MS_Description', N'IRN and QR from the GST e-invoice portal.', N'SCHEMA', N'acc', N'TABLE', N'e_invoice';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Invoice', N'SCHEMA', N'acc', N'TABLE', N'e_invoice', N'COLUMN', N'sales_invoice_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Credit note', N'SCHEMA', N'acc', N'TABLE', N'e_invoice', N'COLUMN', N'credit_note_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Invoice reference number', N'SCHEMA', N'acc', N'TABLE', N'e_invoice', N'COLUMN', N'irn';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Ack number', N'SCHEMA', N'acc', N'TABLE', N'e_invoice', N'COLUMN', N'ack_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Ack date', N'SCHEMA', N'acc', N'TABLE', N'e_invoice', N'COLUMN', N'ack_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Signed QR', N'SCHEMA', N'acc', N'TABLE', N'e_invoice', N'COLUMN', N'signed_qr_code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Generated, Cancelled, Failed.', N'SCHEMA', N'acc', N'TABLE', N'e_invoice', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Cancel reason', N'SCHEMA', N'acc', N'TABLE', N'e_invoice', N'COLUMN', N'cancel_reason';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Cancelled', N'SCHEMA', N'acc', N'TABLE', N'e_invoice', N'COLUMN', N'cancelled_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Request', N'SCHEMA', N'acc', N'TABLE', N'e_invoice', N'COLUMN', N'request_json';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Response', N'SCHEMA', N'acc', N'TABLE', N'e_invoice', N'COLUMN', N'response_json';
EXEC sys.sp_addextendedproperty N'MS_Description', N'E-way bills for invoices, deliveries and transfers.', N'SCHEMA', N'acc', N'TABLE', N'e_way_bill';
EXEC sys.sp_addextendedproperty N'MS_Description', N'E-way bill number', N'SCHEMA', N'acc', N'TABLE', N'e_way_bill', N'COLUMN', N'ewb_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Generated', N'SCHEMA', N'acc', N'TABLE', N'e_way_bill', N'COLUMN', N'ewb_date';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Valid until', N'SCHEMA', N'acc', N'TABLE', N'e_way_bill', N'COLUMN', N'valid_until';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Against Allowed: Invoice, Delivery challan, Stock transfer.', N'SCHEMA', N'acc', N'TABLE', N'e_way_bill', N'COLUMN', N'document_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Invoice', N'SCHEMA', N'acc', N'TABLE', N'e_way_bill', N'COLUMN', N'sales_invoice_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Delivery', N'SCHEMA', N'acc', N'TABLE', N'e_way_bill', N'COLUMN', N'delivery_note_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Transfer', N'SCHEMA', N'acc', N'TABLE', N'e_way_bill', N'COLUMN', N'stock_transfer_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'From PIN', N'SCHEMA', N'acc', N'TABLE', N'e_way_bill', N'COLUMN', N'from_pincode';
EXEC sys.sp_addextendedproperty N'MS_Description', N'To PIN', N'SCHEMA', N'acc', N'TABLE', N'e_way_bill', N'COLUMN', N'to_pincode';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Distance', N'SCHEMA', N'acc', N'TABLE', N'e_way_bill', N'COLUMN', N'distance_km';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Vehicle', N'SCHEMA', N'acc', N'TABLE', N'e_way_bill', N'COLUMN', N'vehicle_no';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Transporter ID', N'SCHEMA', N'acc', N'TABLE', N'e_way_bill', N'COLUMN', N'transporter_gstin';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Active, Cancelled, Expired.', N'SCHEMA', N'acc', N'TABLE', N'e_way_bill', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Connected systems. Credentials stay in AWS Secrets Manager.', N'SCHEMA', N'int', N'TABLE', N'external_system';
EXEC sys.sp_addextendedproperty N'MS_Description', N'e.g. TH_EDOST_BYD, KAASHI_PORTAL, TALLY, WHATSAPP, MAPS, GST_IRP', N'SCHEMA', N'int', N'TABLE', N'external_system', N'COLUMN', N'code';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Brand whose portal this is (blank = general)', N'SCHEMA', N'int', N'TABLE', N'external_system', N'COLUMN', N'principal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Name', N'SCHEMA', N'int', N'TABLE', N'external_system', N'COLUMN', N'name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'API base URL', N'SCHEMA', N'int', N'TABLE', N'external_system', N'COLUMN', N'base_url';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Auth Allowed: Basic, OAuth2, API key, Certificate, None.', N'SCHEMA', N'int', N'TABLE', N'external_system', N'COLUMN', N'auth_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Secrets Manager key', N'SCHEMA', N'int', N'TABLE', N'external_system', N'COLUMN', N'credential_secret_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Enabled', N'SCHEMA', N'int', N'TABLE', N'external_system', N'COLUMN', N'is_enabled';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Our ID to external ID mapping (replaces the byd_* columns; works for every OEM portal).', N'SCHEMA', N'int', N'TABLE', N'sync_mapping';
EXEC sys.sp_addextendedproperty N'MS_Description', N'System', N'SCHEMA', N'int', N'TABLE', N'sync_mapping', N'COLUMN', N'external_system_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Table', N'SCHEMA', N'int', N'TABLE', N'sync_mapping', N'COLUMN', N'entity_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Our ID', N'SCHEMA', N'int', N'TABLE', N'sync_mapping', N'COLUMN', N'internal_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Their ID', N'SCHEMA', N'int', N'TABLE', N'sync_mapping', N'COLUMN', N'external_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Their UUID', N'SCHEMA', N'int', N'TABLE', N'sync_mapping', N'COLUMN', N'external_uuid';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Last sync', N'SCHEMA', N'int', N'TABLE', N'sync_mapping', N'COLUMN', N'last_synced_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Every API call to or from an external system, with retry state.', N'SCHEMA', N'int', N'TABLE', N'sync_log';
EXEC sys.sp_addextendedproperty N'MS_Description', N'System', N'SCHEMA', N'int', N'TABLE', N'sync_log', N'COLUMN', N'external_system_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Table', N'SCHEMA', N'int', N'TABLE', N'sync_log', N'COLUMN', N'entity_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Record', N'SCHEMA', N'int', N'TABLE', N'sync_log', N'COLUMN', N'entity_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Direction Allowed: Outbound, Inbound.', N'SCHEMA', N'int', N'TABLE', N'sync_log', N'COLUMN', N'direction';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Operation Allowed: Create, Update, Read, Delete.', N'SCHEMA', N'int', N'TABLE', N'sync_log', N'COLUMN', N'operation';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Request', N'SCHEMA', N'int', N'TABLE', N'sync_log', N'COLUMN', N'request_payload';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Response', N'SCHEMA', N'int', N'TABLE', N'sync_log', N'COLUMN', N'response_payload';
EXEC sys.sp_addextendedproperty N'MS_Description', N'HTTP status', N'SCHEMA', N'int', N'TABLE', N'sync_log', N'COLUMN', N'http_status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Success, Failed, Retrying.', N'SCHEMA', N'int', N'TABLE', N'sync_log', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Attempts', N'SCHEMA', N'int', N'TABLE', N'sync_log', N'COLUMN', N'attempt_count';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Next retry', N'SCHEMA', N'int', N'TABLE', N'sync_log', N'COLUMN', N'next_retry_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Error', N'SCHEMA', N'int', N'TABLE', N'sync_log', N'COLUMN', N'error_message';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Start', N'SCHEMA', N'int', N'TABLE', N'sync_log', N'COLUMN', N'started_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'End', N'SCHEMA', N'int', N'TABLE', N'sync_log', N'COLUMN', N'finished_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Excel/CSV imports (masters, ByD exports, bank statements).', N'SCHEMA', N'int', N'TABLE', N'file_import';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Source system', N'SCHEMA', N'int', N'TABLE', N'file_import', N'COLUMN', N'external_system_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'What Allowed: Customers, Machines, Items, Open calls, Registered products, Service tickets, Bank statement, Opening balances.', N'SCHEMA', N'int', N'TABLE', N'file_import', N'COLUMN', N'import_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'File', N'SCHEMA', N'int', N'TABLE', N'file_import', N'COLUMN', N'file_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Stored file', N'SCHEMA', N'int', N'TABLE', N'file_import', N'COLUMN', N's3_key';
EXEC sys.sp_addextendedproperty N'MS_Description', N'By', N'SCHEMA', N'int', N'TABLE', N'file_import', N'COLUMN', N'uploaded_by_user_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'When', N'SCHEMA', N'int', N'TABLE', N'file_import', N'COLUMN', N'uploaded_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Rows', N'SCHEMA', N'int', N'TABLE', N'file_import', N'COLUMN', N'total_rows';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Imported', N'SCHEMA', N'int', N'TABLE', N'file_import', N'COLUMN', N'success_rows';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Failed', N'SCHEMA', N'int', N'TABLE', N'file_import', N'COLUMN', N'error_rows';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Uploaded, Validating, Imported, Failed.', N'SCHEMA', N'int', N'TABLE', N'file_import', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Error report', N'SCHEMA', N'int', N'TABLE', N'file_import', N'COLUMN', N'error_report_attachment_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Row-level import errors.', N'SCHEMA', N'int', N'TABLE', N'file_import_error';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Import', N'SCHEMA', N'int', N'TABLE', N'file_import_error', N'COLUMN', N'file_import_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Row', N'SCHEMA', N'int', N'TABLE', N'file_import_error', N'COLUMN', N'row_number';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Column', N'SCHEMA', N'int', N'TABLE', N'file_import_error', N'COLUMN', N'column_name';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Error', N'SCHEMA', N'int', N'TABLE', N'file_import_error', N'COLUMN', N'error_message';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Row data', N'SCHEMA', N'int', N'TABLE', N'file_import_error', N'COLUMN', N'raw_row_json';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Inbound events (WhatsApp replies, ByD notifications).', N'SCHEMA', N'int', N'TABLE', N'webhook_event';
EXEC sys.sp_addextendedproperty N'MS_Description', N'System', N'SCHEMA', N'int', N'TABLE', N'webhook_event', N'COLUMN', N'external_system_id';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Event', N'SCHEMA', N'int', N'TABLE', N'webhook_event', N'COLUMN', N'event_type';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Payload', N'SCHEMA', N'int', N'TABLE', N'webhook_event', N'COLUMN', N'payload';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Received', N'SCHEMA', N'int', N'TABLE', N'webhook_event', N'COLUMN', N'received_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Processed', N'SCHEMA', N'int', N'TABLE', N'webhook_event', N'COLUMN', N'processed_at';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Status Allowed: Received, Processed, Failed, Ignored.', N'SCHEMA', N'int', N'TABLE', N'webhook_event', N'COLUMN', N'status';
EXEC sys.sp_addextendedproperty N'MS_Description', N'Error', N'SCHEMA', N'int', N'TABLE', N'webhook_event', N'COLUMN', N'error_message';
GO
