import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import Field

from trishul_api.common.schemas import ApiModel, InputModel, PageQuery, RowVersion, UtcDateTime
from trishul_api.db.models.generated.svc import ContractPlanServicePriority

AscState = Literal["Active", "Upcoming", "Expired", "Cancelled"]
"""Where a contract stands today: worked out from its dates; only Cancelled is stored."""
ContractStatusFilter = Literal["live", "expiring", "expired", "cancelled", "all"]
PlanStatusFilter = Literal["active", "inactive", "all"]
ImportAction = Literal["insert", "update", "skip"]


# ---------------------------------------------------------------------------------------------- plans


class ContractPlanQuery(ApiModel):
    status: PlanStatusFilter = "active"


class ContractPlanItem(ApiModel):
    """An ASC package from the price list. price excludes GST; total_price includes it."""

    id: int
    code: str
    name: str
    machine_class: str | None
    duration_months: int
    visits_included: int | None
    price: Decimal | None
    gst_pct: Decimal | None
    total_price: Decimal | None
    parts_discount_pct: Decimal | None
    covers_labour: bool
    covers_parts: bool
    covers_travel: bool
    service_priority: ContractPlanServicePriority
    terms: str | None
    is_active: bool
    row_version: RowVersion


class ContractPlanCreate(InputModel):
    code: str = Field(min_length=1, max_length=20, description="Unique, e.g. ASC12-20T.")
    name: str = Field(min_length=1, max_length=100)
    machine_class: str | None = Field(None, max_length=40, description="Price-list row, e.g. '20 Ton (ZX)'.")
    duration_months: int = Field(ge=1, le=60)
    visits_included: int | None = Field(None, ge=0, le=200)
    price: Decimal = Field(ge=0, max_digits=18, decimal_places=2, description="Before GST.")
    gst_pct: Decimal = Field(Decimal(18), ge=0, le=100, max_digits=5, decimal_places=2)
    parts_discount_pct: Decimal | None = Field(None, ge=0, le=100, max_digits=5, decimal_places=2)
    covers_labour: bool = True
    covers_parts: bool = False
    covers_travel: bool = True
    service_priority: ContractPlanServicePriority = "High"
    terms: str | None = Field(None, max_length=2000)


class ContractPlanUpdate(InputModel):
    """Only the fields sent are changed."""

    code: str | None = Field(None, min_length=1, max_length=20)
    name: str | None = Field(None, min_length=1, max_length=100)
    machine_class: str | None = Field(None, max_length=40)
    duration_months: int | None = Field(None, ge=1, le=60)
    visits_included: int | None = Field(None, ge=0, le=200)
    price: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=2)
    gst_pct: Decimal | None = Field(None, ge=0, le=100, max_digits=5, decimal_places=2)
    parts_discount_pct: Decimal | None = Field(None, ge=0, le=100, max_digits=5, decimal_places=2)
    covers_labour: bool | None = None
    covers_parts: bool | None = None
    covers_travel: bool | None = None
    service_priority: ContractPlanServicePriority | None = None
    terms: str | None = Field(None, max_length=2000)


# ------------------------------------------------------------------------------------------ contracts


class ServiceContractQuery(PageQuery):
    """status: live = not cancelled and not ended (includes ones starting later); expiring = live and
    ending within 30 days; expired = ended, not cancelled. search: contract no, book no, serial,
    customer name or code."""

    status: ContractStatusFilter = "live"
    branch_id: int | None = None
    machine_unit_id: int | None = None


class ServiceContractListItem(ApiModel):
    id: int
    contract_no: str
    state: AscState
    branch_id: int | None
    branch_name: str | None
    customer_id: int
    customer_code: str
    customer_name: str
    machine_unit_id: int | None
    machine_serial_no: str | None
    machine_model: str | None
    contract_plan_id: int | None
    plan_name: str | None
    start_date: dt.date
    end_date: dt.date
    visits_included: int | None
    visits_used: int
    visits_remaining: int | None = Field(description="Visits still available; null when the ASC sets no limit.")
    contract_value: Decimal | None
    is_renewal: bool
    engineer_name: str | None
    book_no: str | None


class ServiceContractDetail(ServiceContractListItem):
    principal_id: int
    principal_code: str
    oem_contract_id: str | None
    receipt_no: str | None
    invoice_ref: str | None
    terms: str | None
    engineer_employee_id: int | None
    renewed_from_contract_id: int | None
    renewed_from_contract_no: str | None
    renewed_by_contract_id: int | None = Field(description="The contract that renewed this one, if any.")
    created_at: UtcDateTime
    row_version: RowVersion


class ServiceContractCreate(InputModel):
    """An ASC for one machine; the customer and brand are the machine's. Picking a plan fills the end
    date, visits and value that are not sent."""

    machine_unit_id: int
    contract_plan_id: int | None = None
    start_date: dt.date
    end_date: dt.date | None = Field(None, description="Defaults to start + the plan's months - 1 day.")
    visits_included: int | None = Field(None, ge=0, le=200)
    visits_used: int = Field(0, ge=0, le=200)
    contract_value: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=2)
    branch_id: int | None = Field(None, description="Defaults to the selected branch.")
    book_no: str | None = Field(None, max_length=20)
    oem_contract_id: str | None = Field(None, max_length=40)
    receipt_no: str | None = Field(None, max_length=60)
    invoice_ref: str | None = Field(None, max_length=60)
    is_renewal: bool = False
    engineer_employee_id: int | None = None
    terms: str | None = Field(None, max_length=2000)


class ServiceContractUpdate(InputModel):
    """Only the fields sent are changed. The machine can't be changed: cancel and add a new contract."""

    contract_plan_id: int | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    visits_included: int | None = Field(None, ge=0, le=200)
    visits_used: int | None = Field(None, ge=0, le=200)
    contract_value: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=2)
    branch_id: int | None = None
    book_no: str | None = Field(None, max_length=20)
    oem_contract_id: str | None = Field(None, max_length=40)
    receipt_no: str | None = Field(None, max_length=60)
    invoice_ref: str | None = Field(None, max_length=60)
    is_renewal: bool | None = None
    engineer_employee_id: int | None = None
    terms: str | None = Field(None, max_length=2000)


class ServiceContractRenew(InputModel):
    """A new contract for the same machine, starting the day after this one ends unless given."""

    contract_plan_id: int | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    visits_included: int | None = Field(None, ge=0, le=200)
    contract_value: Decimal | None = Field(None, ge=0, max_digits=18, decimal_places=2)
    book_no: str | None = Field(None, max_length=20)
    receipt_no: str | None = Field(None, max_length=60)
    invoice_ref: str | None = Field(None, max_length=60)


class ContractEngineerOption(ApiModel):
    id: int
    name: str
    employee_code: str


class ContractFormOptions(ApiModel):
    """Everything the ASC form needs: active plans of the selected brand and the branch's engineers."""

    plans: list[ContractPlanItem]
    engineers: list[ContractEngineerOption]


class MachineAsc(ApiModel):
    """A machine's ASC as a service call shows it: the one running today, else the next one to start,
    else the last one that ended. Cancelled contracts are left out."""

    contract_id: int
    contract_no: str
    state: AscState
    plan_name: str | None
    start_date: dt.date
    end_date: dt.date
    visits_included: int | None
    visits_used: int
    visits_remaining: int | None = Field(description="Visits still available; null when the ASC sets no limit.")


class AscCallVisit(ApiModel):
    """A finished service call under an ASC and the visits counted for it (0 = not counted yet)."""

    service_call_id: int
    call_no: str
    current_status: str
    complaint_description: str
    engineer_name: str | None
    received_at: UtcDateTime
    finished_at: UtcDateTime | None
    visits: int
    remarks: str | None
    countable: bool = Field(description="False when a counted call was reopened: finish it to change the count.")


class AscCallVisitSet(InputModel):
    """The actual visits a completed call took; replaces what was recorded for it."""

    visits: int = Field(ge=0, le=200, description="0 takes the call off the ASC's count.")
    remarks: str | None = Field(None, max_length=300)


# --------------------------------------------------------------------------------------------- import


class AscImportRow(ApiModel):
    """What the importer decided for one row of the ASC register."""

    row_number: int
    branch: str | None
    customer_name: str | None
    customer_code: str | None
    serial_number: str | None
    model: str | None
    start_date: dt.date | None
    end_date: dt.date | None
    action: ImportAction
    contract_id: int | None = None
    contract_no: str | None = None
    new_customer: bool = False
    new_machine: bool = False
    new_model: bool = False
    messages: list[str] = Field(default_factory=list)


class AscImportSummary(ApiModel):
    file_name: str
    sheet_name: str
    total: int
    inserts: int
    updates: int
    skips: int
    new_customers: int
    new_machines: int
    new_models: int


class AscImportResult(ApiModel):
    """Preview (applied = false, nothing written) or the outcome of an applied import."""

    applied: bool
    summary: AscImportSummary
    rows: list[AscImportRow]
