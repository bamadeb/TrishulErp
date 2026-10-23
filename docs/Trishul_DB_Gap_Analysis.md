# Trishul ERP: database gap analysis (schema v2 to v3)

**Inputs reviewed**
- *Trishul Desk – Core Flow of the System* infographic (primary reference)
- *Service Management System – Workflow*, 18 steps (document and diagram)
- *Service Requirement* notes: current process, open questions, master data
- SQL scripts `00`–`11` and `ALL_IN_ONE.sql`: dictionary v2, 197 tables, 594 foreign keys

**Deliverables**

| File | Purpose |
|---|---|
| `database/12_gap_remediation.sql` | Adds 22 new tables and the `rpt` schema. Changes 35 existing tables (columns, CHECKs, FKs). Adds missing integrity constraints and indexes. |
| `database/13_gap_seed_views_security.sql` | Missing lookups, brand and connected-system seeds, permissions, KPI catalogue, 5 reporting views, row-level security for the new tables, table descriptions. |

Both scripts run after `00`–`11`. They are safe to re-run, because every step checks the catalog first. Every batch has been checked against the RDS server in parse-only mode, but **neither script has yet been executed against a built v2 database**. Do that on a test database first (section 10).

---

## 1. Summary

The v2 schema is a solid base. It is normalised, every table has a surrogate key, audit columns and a rowversion, it supports multiple brands through `principal_id`, it has row-level security, and its foreign keys are indexed. It covers most of the core service, inventory, purchase, sales, accounting and HR flows.

**It is not complete against the requirements.** It falls short in four ways.

**1. Key workflows can't be recorded.**
- **Reopening a call on the same Call ID.** There is no "Reopened" status and no reopen history. A one-OEM-ID-per-call unique index also blocks recording a new OEM case for a reopened call.
- **Skill-based technician assignment.** There is no skills master.
- **Workflow steps 10–17 (parts and second visit).** Statuses such as Awaiting parts, Revisit scheduled, Pending OEM closure and Completed don't exist. Nothing links a part request to its quotation and dispatch, and there is no staging table for the BYD case and service lists.
- **Allocating receipts to opening-balance bills.** Allocations can only point to a sales invoice, so receivables by age are wrong from go-live.

**2. Infographic modules have no tables at all:**
- Customer portal
- Machine sensors and alerts
- OEM ratings
- Cash-mismatch control
- KPI / KRI and balanced scorecard
- Vehicles
- OEM price check
- AMC instalment billing

**3. The schema is tied to Tata Hitachi equipment.** The infographic is built around **Atlas Copco**, which sells compressors, but `machine_model.product_line` only allows earth-moving machines. Meter readings also have no way to record loaded hours.

**4. Integrity rules are missing.** Examples:
- Unbalanced journals and negative stock are allowed.
- An allocation can point to nothing.
- A contact can belong to both a customer and a supplier.
- A call can have two current primary engineers.

The v3 scripts close all of these. Twelve items still depend on business decisions; they are listed in section 9.

---

## 2. Module-by-module coverage (infographic)

Legend: ✅ covered by v2 · 🟡 partial, fixed in v3 · ❌ missing, added in v3 · ❓ needs a decision

### 2.1 Customer & opportunity management

| Requirement | v2 tables | Status | v3 change |
|---|---|---|---|
| Customer master, new / existing | `core.customer`, `customer_principal` | ✅ | — |
| Contact and site details | `core.contact`, `core.customer_site` | 🟡 | CHECK that a contact belongs to exactly one customer **or** one supplier |
| Customer portal / history | none | ❌ | `core.customer_portal_user`; call source `CUSTOMER_PORTAL`. History is read from calls, invoices and machines. |
| Leads / enquiries, follow-ups, conversion | `pre.lead`, `pre.sales_activity` (`next_follow_up_at`), `pre.opportunity`, `lead.converted_customer_id` | ✅ | — |

### 2.2 Sales & quotation

| Requirement | v2 tables | Status | v3 change |
|---|---|---|---|
| Create quotation, with versions | `sal.quotation`, `quotation_version`, `quotation_line` | ✅ | — |
| Price check against the OEM (Atlas Copco) | none | ❌ | `sal.quotation_price_check`: OEM price, quoted price, variance, source |
| Approvals for discount and credit | `core.approval_rule` / `approval_request`, value bands only | 🟡 | `approval_rule.approval_type` (Value / Discount / Credit / Price override), plus `min_discount_pct` and `max_discount_pct` |
| Convert to sales order | `sal.sales_order.quotation_id` | ✅ | — |

### 2.3 Order & delivery

| Requirement | v2 tables | Status | v3 change |
|---|---|---|---|
| Sales order | `sal.sales_order` / `_line` | ✅ | — |
| Check stock / purchase need | `inv.stock_reservation.sales_order_id` | 🟡 | `purchase_request.sales_order_id`; source type `Sales order` |
| Arrange delivery / dispatch | `sal.delivery_note` (vehicle, transporter, status) | 🟡 | `dispatched_at`, `lr_no`, `courier_docket_no`, `delivered_at`, `received_by_name`, `pod_attachment_id` (proof of delivery), `service_call_id` |
| Invoice generation (Tally) | `sal.sales_invoice`; `int.sync_mapping` / `sync_log` hold the Tally voucher link | 🟡 ❓ | `TALLY` connected-system seed. Which system issues invoices is still open (Q3). |
| Payment confirmation | `sal.receipt` (status Posted / Bounced) | 🟡 | Receipt status `Pending confirmation` with `confirmed_by_user_id` / `confirmed_at`. Sales order gets `is_payment_confirmed`, `payment_confirmed_by_user_id` / `_at`. |

### 2.4 Service & call management

| Requirement | v2 tables | Status | v3 change |
|---|---|---|---|
| Call / ticket generation, all sources | `svc.service_call`, `call_status_log`, lookup `CALL_SOURCE` | 🟡 | The notes list "service engineer" as a call source, but it isn't in the lookup. Added it, plus `CUSTOMER_PORTAL` and `MACHINE_ALERT`. E-mail and WhatsApp calls are captured in `int.inbound_message`. |
| Check warranty / OOW | `machine_unit.warranty_*`, `service_call.coverage_type` | 🟡 | `warranty_checked_at`, `warranty_checked_by_user_id`, `coverage_remarks` |
| Schedule service every 3/6/9/12 months | `svc.planned_service`, which only supports HMR templates | 🟡 | `planned_service.service_contract_id` and `plan_label`; `schedule_template_id` is now optional; CHECK that at least one is set. `svc.v_upcoming_service` view. |
| Assign technician by skill | `call_assignment`; `employee_principal` holds brand certification only | ❌ | `hr.skill`, `hr.employee_skill`, `svc.skill_rule`, `svc.call_required_skill`. Unique index allowing only one current primary engineer per call. |
| Parts request via WhatsApp / e-mail | `svc.service_part_request` | 🟡 | `request_channel`, plus the full parts lifecycle (section 3) |
| Service report and close (48 hrs) | `service_report`, `sla_rule` (default 24 h) | ❓ | The SLA is configurable, but the infographic says 48 h and the notes say 24 h (Q5) |

### 2.5 Field service (mobile app) and customer-site machine

| Requirement | v2 tables | Status | v3 change |
|---|---|---|---|
| Trip start / end | `svc.trip`, `trip_gps_point` | ✅ | `trip.vehicle_id` links to the new `hr.vehicle` |
| Job start / complete | `service_visit.service_started_at` / `_ended_at` | ✅ | — |
| Location tracking | `trip_gps_point`, which needs a trip | 🟡 ❓ | `svc.duty_gps_point` records points while on duty between trips (Q6) |
| View call details / update service report | `service_call`, `service_report`, `report_checklist_item`, `attachment` | ✅ | — |
| Machine sensors / alerts | only a `Telematics` value on meter readings | ❌ | `core.machine_telemetry` (raw readings), `svc.machine_alert`, `machine_unit.telematics_device_id` |
| Upcoming service | `planned_service` | ✅ | Alerts with source `Service schedule`; view `v_upcoming_service` |
| Delay alerts | `svc.sla_event` | ✅ | Alerts with source `SLA delay` |
| Compressor machines and meters | `machine_model.product_line` allows earth-moving equipment only | ❌ | product_line adds Air compressor, Dryer, Generator, Vacuum pump, Blower and Air treatment. `machine_meter_reading.meter_type` can be HMR, Running hours, Loaded hours or Odometer. |

### 2.6 External integrations

| Integration | v2 | Status | v3 change |
|---|---|---|---|
| Atlas Copco portal (DMS) | generic `int.external_system`, `sync_mapping`, `sync_log` | 🟡 | `ATLAS_DMS` seed; price check table |
| Tally (billing and stock) | generic | 🟡 ❓ | `TALLY` seed; direction of sync still open (Q3) |
| SAP / BYD (E-DOST) | `svc.oem_call_reference`, `int.file_import` | 🟡 | `int.oem_ticket_import_line` staging and matching (workflow steps 8, 16, 17). New import types `OEM case list` and `OEM service list`. |
| E-mail / WhatsApp | `core.notification` (outbound), `int.webhook_event` (raw inbound), `pre.whatsapp_log` | 🟡 | `int.inbound_message`: parsed inbound messages linked to a call or part request |
| Grey8 HR | generic | ✅ | `GREY8` seed |

### 2.7 Inventory & purchase

| Requirement | v2 tables | Status | v3 change |
|---|---|---|---|
| Stock check 2–3 times a month | `inv.stock_count` / `_line`, `stock_adjustment` | ✅ | — |
| Item location / storage | `core.location`, `inv.bin`, `stock_balance.bin_id` | ✅ | — |
| GRN / transit GRN | `pur.grn` (status Draft / Posted / Cancelled) | 🟡 | `grn_type` (Regular / Transit), `expected_arrival_date`, status `In transit` |
| Purchase order (OEM / local) | `pur.purchase_order.principal_id` | 🟡 | `po_type` (OEM / Local / Import) |
| Stock transfer (HSN) | `inv.stock_transfer` / `_line`, which have no HSN or value | 🟡 | Lines get `hsn_sac_id`, `unit_value` and `taxable_value` for the delivery challan and e-way bill. Header gets `delivery_challan_no`. |
| Stock ageing and reserved stock | `inv.cost_layer`, `stock_balance.qty_reserved` | 🟡 ❓ | `inv.v_stock_ageing` view. It relies on FIFO layers (Q11). |
| Claims (manual / Excel) | `svc.warranty_claim` / `_part` | 🟡 | `claim_source`, `file_import_id`; import type `Warranty claims` |

### 2.8 Finance & billing (Tally)

| Requirement | v2 tables | Status | v3 change |
|---|---|---|---|
| Stock and price verification | stock tables; no price verification | 🟡 | `sal.quotation_price_check` |
| GST and tax compliance | `acc.gst_rate`, `hsn_sac`, `doc_tax_line`, `e_invoice`, `e_way_bill`, `gstin_registration` | ✅ | — |
| Invoicing and billing | `sal.sales_invoice` / `_line` | ✅ | — |
| Payments and receipts | `sal.receipt`, `customer_allocation`, `acc.cheque`, `bank_txn` | 🟡 | Allocation to opening-balance bills; payment confirmation; `receipt.collected_by_employee_id` for field cash |
| Credit management | `customer.credit_limit`, `credit_status`, `sal.credit_hold` | 🟡 | `sal.credit_limit_change` (history and approver); `sales_order.credit_check_status` and override approver |
| Negative billing checks | none | ❌ | CHECKs on invoice lines (quantity > 0, no negative amounts); `sales_invoice_line.unit_cost` for below-cost checks; non-negative stock CHECK (Q12) |
| Receivables by age | `sales_invoice.due_date` / `amount_received` | 🟡 | `acc.v_receivables_ageing` covers invoices and opening bills, net of allocations, in buckets Not due / 1-30 / 31-60 / 61-90 / 91-180 / 180+. A matching `acc.v_payables_ageing` view. |
| AMC billing | `service_contract.sales_invoice_id`, one invoice only | 🟡 | `svc.contract_billing_schedule` holds instalments, each with its invoice |

### 2.9 HR & field management

| Requirement | v2 tables | Status | v3 change |
|---|---|---|---|
| Service engineer master | `core.employee`, `hr.employee_profile`, `team`, `team_member` | ✅ | `employee.mobile_platform` (Android / iOS), which the master-data template asks for |
| Skills and assignment | none | ❌ | `hr.skill`, `hr.employee_skill` |
| Attendance, manual now and automatic later | `hr.attendance` (sources App / Biometric / Duty log / Manual), `attendance_regularization` | ✅ | CHECK on `requested_status` |
| Travel / shift / vehicle | `hr.shift`, `employee_shift`, `expense_claim_line.trip_id`; vehicle type is text only | 🟡 | `hr.vehicle` (registration, ownership, rate per km, insurance, PUC); `trip.vehicle_id` |
| Performance and reports | `hr.performance_review`, payroll tables | ✅ | KPI tables (2.11) |
| Grey8 integration | generic integration tables | ✅ | — |

### 2.10 Reporting & analytics

| Requirement | Status | v3 change |
|---|---|---|
| Daily service reports | 🟡 | `svc.v_call_turnaround` gives response hours, closure hours, SLA met, visit count and reopen count |
| Sales and collection reports | ✅ | Existing tables plus the ageing views |
| Inventory reports | 🟡 | `inv.v_stock_ageing` |
| Service performance (KPI / KRI), target vs achievement | 🟡 | v2 only had sales targets (`pre.sales_target`). New `rpt.kpi_definition`, `kpi_target`, `kpi_actual`, with 15 seeded KPIs. |
| Management dashboard | ✅ | Built on the views and `rpt.kpi_actual` |

### 2.11 Management & compliance

| Requirement | Status | v3 change |
|---|---|---|
| Approval workflows | 🟡 | `approval_type` and discount bands (2.2) |
| Audit trail / history | ✅ | `core.audit_log`, `status_history`, `call_status_log`. These have no triggers; the API must write them. |
| Document verification | ❌ | `core.attachment` gets `verification_status`, `verified_by_user_id`, `verified_at`, `verification_remarks` |
| OEM ratings ("DEM ratings" in the infographic) | ❌ ❓ | `core.oem_rating` (Q8) |
| Gaps / cash mismatch | ❌ | `acc.cash_reconciliation`, with a persisted `difference_amount` column and approval |
| Balanced scorecard | ❌ | `rpt.kpi_definition.perspective` groups KPIs as Financial / Customer / Internal process / Learning and growth |

---

## 3. Service workflow trace (18 steps)

| # | Step | Tables in v3 | Status of the call / part request |
|---|---|---|---|
| 1 | Call creation / import | `service_call`, `int.file_import` (Open calls), `int.inbound_message` | Logged |
| 2 | Customer and machine master | `core.customer`, `customer_site`, `machine_unit`, `machine_ownership` | — |
| 3 | ASC priority and management | `svc.contract_plan`, `contract_plan_entitlement`, `service_contract`, `contract_coverage`, `service_call.is_asc_priority`, `sla_rule` | — |
| 4 | Customer and machine mapping | `service_call.customer_id` / `machine_unit_id` / `service_contract_id` | — |
| 5 | Engineer assignment (location, priority, availability, workload) | `call_assignment`, `call_required_skill`, `employee_skill`, `engineer_duty_log`, `pincode` latitude/longitude | Assigned |
| 6 | Engineer's call list | index `IX_svc_service_call_engineer` | — |
| 7 | First visit trip | `service_visit` (visit 1), `trip`, `trip_gps_point` | Trip started → Reached site |
| 8 | BYD case ID update / import | `oem_call_reference`, `int.oem_ticket_import_line` | Call ID linked |
| 9 | Inspection and service report | `service_report`, `report_checklist_item`, `attachment` | Report submitted |
| 10 | Part request | `service_part_request` (`request_channel`, `quotation_id`) | Awaiting parts / part: Requested → Quoted → Customer approved |
| 11 | Inventory verification | `service_part_request` (`reviewed_by_user_id`, `available_qty`, `fulfilment_source`, `expected_available_date`), `stock_reservation`, `purchase_request` | part: Under review → Reserved / Ordered |
| 12 | Next visit (optional) | `service_visit.planned_date` (visit 2) | Revisit scheduled |
| 13 | Parts at site, reassignment | `inv.stock_issue` (dispatch fields, `delivered_to_site_id`), `call_assignment` | part: Dispatched → Delivered to site; call: Parts ready |
| 14 | Second visit trip | `service_visit` (visit 2), `trip` | Trip started → Reached site |
| 15 | Final inspection and report | `service_report` (visit 2) | Closed |
| 16 | OEM service list import | `int.file_import` (OEM service list), `oem_ticket_import_line` | Pending OEM closure |
| 17 | Final status update | `oem_ticket_import_line.match_status = Updated`, `service_call.completed_at` | Completed |
| — | Reopen on the same Call ID | `svc.call_reopen`, `service_call.reopen_count` / `last_reopened_at`, `oem_call_reference.is_current` | Reopened → back to Assigned |

**How a reopen works:**
1. Insert a `call_reopen` row holding the previous status, close date, closure type and engineer.
2. Increment `reopen_count`, set the status to `Reopened`, and clear `closed_at` and `closure_type`.
3. Log the change in `call_status_log`.
4. The next visit gets `visit_no + 1`.
5. If the OEM issues a new case ID, add a new `oem_call_reference` row with `is_current = 1` and set the old row to 0. The filtered unique index allows only one current OEM ID per call.

The `call_no` never changes.

---

## 4. Business lifecycle checks requested

| Lifecycle | Before (v2) | After (v3) |
|---|---|---|
| Call management | Good; missing sources, reopen and skills | Complete |
| Service management | No parts or second-visit states, no OEM closure import | Complete (section 3) |
| Parts and quotations | `sal.quotation.service_call_id` existed, but part requests weren't linked to quotations | `service_part_request.quotation_id` / `purchase_request_id`, extended statuses, `sales_order.service_call_id` |
| Payments | Receipts and allocations to invoices only | Payment confirmation, opening-bill allocation, field cash collector |
| Dispatch | Delivery note without tracking; parts to site not tracked | Dispatch / LR / docket / proof-of-delivery fields on `delivery_note` and `stock_issue` |
| Tally billing | Generic sync tables only | Seeded connected system; direction to confirm (Q3) |
| AMC | Contract and coverage; one invoice; no plan or schedule | Plans, entitlements, frequency, renewal chain, instalment billing, contract-driven planned services |
| Credit management | Limit, status, hold | Plus change history, credit check on sales orders, override approver |
| Payment confirmation | None | Receipt and sales-order confirmation fields |
| Reopen with same Call ID | Impossible: no status, and the unique index blocked new OEM IDs | Supported (section 3) |
| HR | Strong | Plus skills, vehicles, attendance CHECK |
| Receivables by age | Derivable only for invoices; opening bills couldn't be settled | `acc.v_receivables_ageing` (and payables) |

---

## 5. Defects found in the v2 DDL

| # | Defect | Risk | Fix |
|---|---|---|---|
| D1 | `UX_svc_oem_call_reference_service_call_id` allows only one OEM reference per call | Reopen with a new OEM case fails | Replaced by a filtered unique index on current references plus a unique index on (principal, OEM ID) |
| D2 | `customer_allocation.sales_invoice_id` and `supplier_allocation.supplier_invoice_id` are NOT NULL | Go-live outstanding bills can't be settled, so ageing is wrong | Made nullable, added `opening_balance_id`, CHECK exactly one target |
| D3 | No CHECK on `gl_entry` debit/credit or `journal` balance | Unbalanced books | `CK_acc_gl_entry_amounts`, `CK_acc_journal_balanced`, `CK_acc_opening_balance_amounts` |
| D4 | `stock_balance` quantities can go negative | Phantom stock, negative billing | `CK_inv_stock_balance_non_negative` (Q12) |
| D5 | `contact` can have no owner, or both a customer and a supplier | Orphan contacts | `CK_core_contact_owner` |
| D6 | Several current primary engineers per call possible | Duplicate work, wrong engineer list | Filtered unique index `UX_svc_call_assignment_current_primary` |
| D7 | `planned_service.schedule_template_id` NOT NULL | Month-based AMC/ASC visits can't be stored | Nullable plus `service_contract_id` |
| D8 | `machine_model.product_line` CHECK excludes compressors | Atlas Copco machines can't be stored | Widened |
| D9 | `hr.attendance_regularization.requested_status` unconstrained | Bad data | CHECK |
| D10 | No CHECK on invoice amounts, contract dates, fiscal year dates or rating range | Bad data | CHECKs added |
| D11 | `sal.sales_invoice.invoice_no` unique globally at 16 chars | Fine only if the number includes the FY and branch prefix | No change; enforce via `core.number_series` prefixes (Q10) |
| D12 | `core.attachment` has no index on (entity_type, entity_id) | Slow loading of attachments for any record | `IX_core_attachment_entity` |
| D13 | Allocation rows can have no receipt / credit note and amount ≤ 0 | Bad allocations | Covered by the D2 CHECK |

---

## 6. Duplicate and redundant structures

| Item | Assessment | Recommendation |
|---|---|---|
| `service_call.oem_call_id` and `oem_call_reference.oem_call_id` | Denormalised copy | Keep it as a *cached current value* for search. The API must update it whenever `is_current` changes. Index added. |
| `customer.is_asc_customer` and active ASC rows in `service_contract` | Derived flag that can drift | Keep it for fast prioritisation, but recompute it in the nightly job, or replace it with a view if drift appears. |
| `sales_invoice.amount_received` and `sales_order.advance_received` | Cached sums of allocations / receipts | Keep them; reports should use the views, which compute from allocations. |
| `pre.order_advance` and `sal.receipt` (type Order advance) | Overlap | Keep `order_advance` as the opportunity-to-receipt link only. Don't store a second amount truth: `amount` must equal the receipt amount. |
| `pre.whatsapp_log`, `core.notification` and `int.webhook_event` | Three places for messages | Outbound messages go to `core.notification`. Inbound raw payloads go to `int.webhook_event`, and parsed ones to `int.inbound_message` (new). `pre.whatsapp_log` should become a read view over these, or hold only sales conversations. |
| `core.status_history` and `svc.call_status_log` | Same pattern | Intentional: calls need GPS and client UUID. Keep both. |
| `hr.asset` (type VEHICLE) and `hr.vehicle` | Overlap | `hr.vehicle.asset_id` links them; company vehicles are also assets. |
| `ALL_IN_ONE.sql` and files `00`–`11` | Same DDL twice | Generate `ALL_IN_ONE` from the parts in CI; never edit it by hand. |

No table needs to be dropped.

---

## 7. Production readiness

**Security**
- Row-level security is created **OFF**. The v3 tables are added to the policy. Switch it on only after the API sets `SESSION_CONTEXT('app_user_id')` on every connection.
- Customer-portal users need their own predicate (their customer only). Enforce this in the API, or add a second policy.
- Some columns are marked "(encrypted)": `supplier.bank_account_no`, `employee_profile.pan` and `employee_profile.bank_account_no`. They are `NVARCHAR(30)`, too small for application-level ciphertext. Either use **Always Encrypted** (available in Express), which needs no length change, or widen them to `VARBINARY(256)`.
- The application should connect with a least-privilege login, not `admin`.

**Scalability**
- `svc.trip_gps_point`, `svc.duty_gps_point`, `core.machine_telemetry`, `core.audit_log` and `int.sync_log` are high-volume. Partition them by month, or archive them to S3 / Athena.
- **SQL Server Express limits:**
  - Per-database size cap: 10 GB on 2022, raised in 2025 (verify on the RDS instance).
  - About 1.4 GB buffer pool.
  - No SQL Server Agent.

  Plan to move to Standard Edition once telemetry and GPS volume grows.

**Scheduled jobs**
Express has no SQL Agent, so these must run from the application side (for example EventBridge plus Lambda, or a worker):
- SLA warnings and breaches
- Planned-service generation
- Machine alerts
- `pipeline_snapshot`
- `rpt.kpi_actual`
- The `is_asc_customer` refresh
- Contract expiry

**Concurrency and integrity**
- `READ_COMMITTED_SNAPSHOT` is on, which is good.
- `core.number_series` must be incremented with `UPDLOCK` / `HOLDLOCK`, or use SEQUENCE objects.
- Accounting period locks and `audit_log` writes have no triggers. Enforce them in the API, or add triggers on the posting tables.

**Normalisation**
The schema is in 3NF apart from the cached columns listed in section 6. Polymorphic links (`attachment`, `audit_log`, `approval_request`, `journal.source_*`) can't have FKs. The API must validate them.

---

## 8. Inventory of v3 changes

**22 new tables:**
- `hr`: `skill`, `employee_skill`, `vehicle`
- `svc`: `skill_rule`, `call_required_skill`, `call_reopen`, `contract_plan`, `contract_plan_entitlement`, `contract_billing_schedule`, `machine_alert`, `duty_gps_point`
- `core`: `machine_telemetry`, `customer_portal_user`, `oem_rating`
- `int`: `inbound_message`, `oem_ticket_import_line`
- `sal`: `quotation_price_check`, `credit_limit_change`
- `acc`: `cash_reconciliation`
- `rpt`: `kpi_definition`, `kpi_target`, `kpi_actual`

New schema: `rpt`. Total after v3: **219 tables**.

**Existing tables changed:**

| Schema | Tables |
|---|---|
| core | `employee`, `machine_unit`, `machine_model`, `machine_meter_reading`, `attachment`, `approval_rule`, `contact` |
| svc | `service_call`, `oem_call_reference`, `call_assignment`, `service_part_request`, `planned_service`, `service_contract`, `trip`, `warranty_claim` |
| inv | `stock_issue`, `stock_transfer`, `stock_transfer_line`, `stock_balance` |
| pur | `purchase_request`, `purchase_order`, `grn`, `supplier_allocation` |
| sal | `sales_order`, `delivery_note`, `receipt`, `sales_invoice`, `sales_invoice_line`, `customer_allocation` |
| acc | `gl_entry`, `journal`, `opening_balance`, `fiscal_year` |
| hr | `attendance_regularization` |
| int | `file_import` |

**Views:**
- `acc.v_receivables_ageing`
- `acc.v_payables_ageing`
- `inv.v_stock_ageing`
- `svc.v_upcoming_service`
- `svc.v_call_turnaround`

**Seeds:**
- Lookups: call sources, `REOPEN_REASON`, `PART_REJECT_REASON`
- Brands: `TATA_HITACHI`, `ATLAS_COPCO`
- 8 connected systems
- 24 permissions with role grants
- Roles: `INVENTORY`, `COORDINATOR`
- 15 KPIs

---

## 9. Clarifications needed from the client

| # | Question | Affects |
|---|---|---|
| Q1 | Which brands are in scope? The notes describe Tata Hitachi / E-DOST / BYD; the infographic describes Atlas Copco. Are both handled by the same company and branches? The schema references Kaashi too. | `core.principal` seed, product lines, OEM portals |
| Q2 | **"ASC"**: the workflow defines it as *Annual Service Contract*, but the notes say "customers **or partners** count as ASC", which suggests *Authorised Service Centre*. Which is it? If partners are service centres, we need a partner master and call routing to partners. | `contract_plan`, possibly a new `core.service_partner` |
| Q3 | Tally: does the ERP create invoices and push them to Tally, or are invoices made in Tally and imported? Does stock live in Tally or in the ERP? | Invoice numbering, `sync_mapping` direction, stock master of record |
| Q4 | Can a service engineer enter or generate the E-DOST Call ID and log new calls from the field? (Asked in the notes; permissions are seeded both ways.) | Role grants |
| Q5 | Closure SLA: 24 h (notes) or 48 h (infographic)? Clock hours or working hours? Who is alerted and who gets escalations? | `svc.sla_rule` rows |
| Q6 | Should GPS run for the whole duty period or only during trips? This matters for privacy, battery use and data volume. | `svc.duty_gps_point` use |
| Q7 | Who closes a call: automatically on report submission, after back-office verification, or only after the OEM list import (step 17)? | Status flow `Closed` → `Pending OEM closure` → `Completed` |
| Q8 | "DEM Ratings" in the infographic: is this the OEM (dealer) rating, or something else? | `core.oem_rating` |
| Q9 | Sensors / alerts: is there a real telematics feed (Atlas Copco SMARTLINK, Tata Hitachi telematics)? Through an API or file? Which metrics? | `machine_telemetry`, `machine_alert` |
| Q10 | Invoice number format per GSTIN and fiscal year (16-character GST limit) | `core.number_series` |
| Q11 | Inventory valuation: FIFO or weighted average? The stock-ageing view needs FIFO layers, or a receipt date per serial / batch. | `inv.cost_layer` usage |
| Q12 | Is negative stock ever allowed, for example billing before the GRN is posted? If yes, drop `CK_inv_stock_balance_non_negative` and flag it instead. | Inventory posting |
| Q13 | Cash collection: do engineers collect cash or cheques at the site? How often is cash reconciled? | `receipt.collected_by_employee_id`, `cash_reconciliation` |
| Q14 | "Nearby" for priority: a km radius or a branch service area? | Assignment logic (data already supports both) |
| Q15 | What is the "Customer Portal" scope: view history only, or also raise calls and approve quotations online? | `customer_portal_user`, permissions |

---

## 10. How to deploy

1. Create the database on a **test** instance and run `00`–`11` (or `ALL_IN_ONE.sql`).
2. Run `12_gap_remediation.sql`, then `13_gap_seed_views_security.sql`.
3. Re-run both scripts to confirm they are idempotent; nothing should change.
4. Smoke tests:
   - Insert a call, reopen it, and add a second OEM reference.
   - Allocate a receipt to an opening bill and check `acc.v_receivables_ageing`.
   - Try an unbalanced journal; it must fail.
5. Copy files `00`–`11` into `database/` next to `12` and `13`, so the full build lives in one folder under version control.
