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
