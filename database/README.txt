TRISHUL Integrated System - SQL Server scripts (dictionary v2)
=================================================================

Run in this order on a new database (SQL Server 2019+ or Amazon RDS for SQL Server):

  00_database_and_schemas.sql        creates database TrishulDev and schemas core, svc, inv, pur, sal, pre, hr, acc, int, rls
  01_core_setup.sql                  Core Setup tables
  02_phase1_call_service.sql         Phase 1
  03_phase2_inventory.sql            Phase 2
  04_phase3_purchase_hr.sql          Phase 3 (Purchase) + HR
  05_phase4_sales.sql                Phase 4
  06_phase5_presales.sql             Phase 5
  07_phase6_presales_completion.sql  Phase 6
  08_performance_indexes.sql         extra indexes for common screens (run after 07)
  09_seed_data.sql                   lookup lists, roles, movement types, INR
  10_row_level_security.sql          brand + branch security policy (created OFF)
  11_descriptions.sql                table/column descriptions for SSMS and documentation tools

  ALL_IN_ONE.sql                     00-11 joined, for a full build

Deploying phase by phase
  Each phase file creates its tables, then adds every foreign key that becomes possible in that
  phase - including keys from earlier tables to the new ones (for example core.machine_unit.sale_invoice_id
  -> sal.sales_invoice is added in 05). Until then those columns exist and stay empty.
  08 references tables from every phase; run it after the last phase you deploy, or trim it.

Conventions
  - Every table: id BIGINT IDENTITY primary key + created_at, created_by_user_id, updated_at,
    updated_by_user_id, is_active, row_version (except insert-only logs).
  - Fixed value lists are CHECK constraints; editable lists live in core.lookup_value.
  - Unique columns that allow NULL use filtered unique indexes.
  - Header -> line tables use ON DELETE CASCADE; everything else NO ACTION.
  - READ_COMMITTED_SNAPSHOT is switched on to avoid reader/writer blocking.
  - svc.trip_gps_point should be partitioned by month on recorded_at in production.

Totals: 197 tables, 594 foreign keys.
