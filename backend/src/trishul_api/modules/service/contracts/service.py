"""ASC master: contracts (one machine each) and the plan price list.

A contract takes its customer and brand from the machine it covers. Picking a plan fills what wasn't
given: end date (start + the plan's months - 1 day), visits and value (plan price with GST). Two live
ASCs on one machine may not overlap. Renewing makes a new contract linked to the old one; cancelling
keeps the record (status Cancelled) so the history stays.

visits_used is the contract's total. It starts from what the register or the form says, and the ASC
Manager adds to it from completed service calls (svc.contract_visit, one row per call). It never goes
past visits_included, and a contract with no visits_included has no limit to check.
"""

import calendar
import datetime as dt
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser, RequestScope
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import AlreadyExists, ApiError, NotFound
from trishul_api.common.numbering import next_document_no
from trishul_api.db.models import (
    ContractCoverage,
    ContractPlan,
    ContractVisit,
    Customer,
    Principal,
    ServiceCall,
    ServiceContract,
)
from trishul_api.modules.service.contracts.repository import (
    ASC,
    COUNTABLE_STATUSES,
    ContractRepository,
    plan_item,
    plan_total,
)
from trishul_api.modules.service.contracts.schemas import (
    AscCallVisit,
    AscCallVisitSet,
    ContractPlanCreate,
    ContractPlanItem,
    ContractPlanUpdate,
    ServiceContractCreate,
    ServiceContractDetail,
    ServiceContractRenew,
    ServiceContractUpdate,
)

DOCUMENT_TYPE = "SERVICE_CONTRACT"
DEFAULT_PRINCIPAL_CODE = "TATA_HITACHI"
DEFAULT_PARTS_DISCOUNT_PCT = 5
_PLAN_FIELDS = (
    "name",
    "machine_class",
    "duration_months",
    "visits_included",
    "price",
    "gst_pct",
    "parts_discount_pct",
    "covers_labour",
    "covers_parts",
    "covers_travel",
    "service_priority",
    "terms",
)
_CONTRACT_FIELDS = ("visits_used", "book_no", "oem_contract_id", "receipt_no", "invoice_ref", "is_renewal", "terms")


def add_months(day: dt.date, months: int) -> dt.date:
    """The same day `months` later, clamped to the month's end (31 Jan + 1 month = 28/29 Feb)."""
    index = day.month - 1 + months
    year, month = day.year + index // 12, index % 12 + 1
    return day.replace(year=year, month=month, day=min(day.day, calendar.monthrange(year, month)[1]))


def plan_end_date(start: dt.date, months: int) -> dt.date:
    """The last day of a plan that runs `months` from `start`: 05-04-2026 for 6 months ends 04-10-2026."""
    return add_months(start, months) - dt.timedelta(days=1)


class ContractService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor
        self._repo = ContractRepository(db)

    # ------------------------------------------------------------------ contracts

    def get(self, contract_id: int) -> ServiceContractDetail:
        self._require(contract_id)
        return self._detail(contract_id)

    def create(self, scope: RequestScope, data: ServiceContractCreate) -> ServiceContractDetail:
        machine = self._repo.machine(data.machine_unit_id)
        if machine is None:
            raise ApiError("That machine doesn't exist.", errors={"machineUnitId": ["Unknown or inactive machine."]})
        if machine.customer_id is None:
            raise ApiError(
                "Link the machine to its customer before adding an ASC.",
                errors={"machineUnitId": ["The machine has no customer."]},
            )
        if not self._actor.can_see_principal(machine.principal_id):
            raise ApiError(
                "You do not have access to that brand.", errors={"machineUnitId": ["Not one of your brands."]}
            )
        branch_id = self._check_branch(data.branch_id if data.branch_id is not None else scope.branch_id)
        plan = self._check_plan(data.contract_plan_id)
        end = data.end_date or self._default_end(data.start_date, plan)
        self._check_dates(data.start_date, end)
        self._check_overlap(machine.id, data.start_date, end, None)

        contract = ServiceContract(
            company_id=self._company_id(machine.customer_id),
            contract_no=next_document_no(
                self._db,
                company_id=self._company_id(machine.customer_id),
                document_type=DOCUMENT_TYPE,
                branch_id=branch_id,
            ),
            principal_id=machine.principal_id,
            customer_id=machine.customer_id,
            contract_type=ASC,
            start_date=data.start_date,
            end_date=end,
            visits_included=data.visits_included if data.visits_included is not None else _plan_visits(plan),
            contract_value=data.contract_value if data.contract_value is not None else _plan_value(plan),
            status="Active",
            contract_plan_id=plan.id if plan else None,
            branch_id=branch_id,
            enrolled_on=dt.date.today(),
            created_by_user_id=self._actor.id,
            **{field: getattr(data, field) for field in _CONTRACT_FIELDS},
        )
        self._check_within_limit(contract)
        self._set_engineer(contract, data.engineer_employee_id)
        self._db.add(contract)
        self._db.flush()
        self._db.add(_coverage(contract.id, machine.id, plan, self._actor.id))
        self._mark_asc_customer(machine.customer_id)
        self._db.commit()
        return self._detail(contract.id)

    def update(
        self, contract_id: int, expected_row_version: bytes, data: ServiceContractUpdate
    ) -> ServiceContractDetail:
        contract = self._require(contract_id)
        check_row_version(contract.row_version, expected_row_version)
        if contract.status == "Cancelled":
            raise ApiError("A cancelled ASC can't be changed.")
        changed = data.model_fields_set
        visits_before = (contract.visits_used, contract.visits_included)

        if "contract_plan_id" in changed:
            plan = self._check_plan(data.contract_plan_id)
            contract.contract_plan_id = plan.id if plan else None
        if "branch_id" in changed:
            if data.branch_id is None:
                raise ApiError("A branch is required.", errors={"branchId": ["Required."]})
            contract.branch_id = self._check_branch(data.branch_id)
        if "start_date" in changed and data.start_date is not None:
            contract.start_date = data.start_date
        if "end_date" in changed and data.end_date is not None:
            contract.end_date = data.end_date
        self._check_dates(contract.start_date, contract.end_date)
        machine_id = self._repo.covered_machine(contract.id)
        if machine_id is not None and changed & {"start_date", "end_date"}:
            self._check_overlap(machine_id, contract.start_date, contract.end_date, contract.id)
        if "visits_included" in changed:
            contract.visits_included = data.visits_included
        if "contract_value" in changed:
            contract.contract_value = data.contract_value
        if "engineer_employee_id" in changed:
            self._set_engineer(contract, data.engineer_employee_id)
        for field in _CONTRACT_FIELDS:
            if field in changed and getattr(data, field) is not None:
                setattr(contract, field, getattr(data, field))
        # Only a real change is checked: the form sends these with every save.
        if (contract.visits_used, contract.visits_included) != visits_before:
            self._check_within_limit(contract)
            if contract.visits_used < self._repo.visits_counted(contract.id):
                raise ApiError(
                    "Service calls already count for more visits than that. Change them in the ASC's call list.",
                    errors={"visitsUsed": ["Lower than the visits counted from service calls."]},
                )
        self._touch(contract)
        self._db.commit()
        return self._detail(contract_id)

    def call_visits(self, contract_id: int) -> list[AscCallVisit]:
        return self._repo.call_visits(self._require(contract_id))

    def set_call_visits(
        self, contract_id: int, call_id: int, expected_row_version: bytes, data: AscCallVisitSet
    ) -> ServiceContractDetail:
        """Record how many visits a completed call took. Only the difference moves the contract's total, so
        changing a call from 1 to 2 takes one more visit, and 0 gives its visits back."""
        self._require(contract_id)
        contract = self._repo.lock(contract_id)
        check_row_version(contract.row_version, expected_row_version)
        if contract.status == "Cancelled":
            raise ApiError("A cancelled ASC can't take visits.")
        record = self._repo.visit_record(call_id)
        if record is not None and record.service_contract_id != contract.id:
            other = self._repo.contract_no(record.service_contract_id)
            raise ApiError(f"This call's visits are counted on ASC {other}.")
        # A counted call stays on the ASC even if its machine was changed afterwards.
        call = self._db.get(ServiceCall, call_id) if record else self._repo.call_under_contract(contract, call_id)
        if call is None:
            raise NotFound("That service call isn't under this ASC.")
        if call.current_status not in COUNTABLE_STATUSES:
            raise ApiError("Only a completed service call can be counted.")

        change = data.visits - (record.visits if record is not None else 0)
        if change > 0 and contract.visits_included is not None:
            left = max(contract.visits_included - contract.visits_used, 0)
            if change > left:
                raise ApiError(
                    f"Only {left} of {contract.visits_included} visits are left on this ASC.",
                    errors={"visits": [f"At most {left} more."]},
                )
        now = _now()
        if data.visits == 0:
            if record is not None:
                self._db.delete(record)
        elif record is None:
            self._db.add(
                ContractVisit(
                    service_contract_id=contract.id,
                    service_call_id=call_id,
                    visits=data.visits,
                    remarks=data.remarks,
                    created_at=now,
                    created_by_user_id=self._actor.id,
                )
            )
        else:
            record.visits = data.visits
            record.remarks = data.remarks
            record.updated_at = now
            record.updated_by_user_id = self._actor.id
        contract.visits_used += change
        self._touch(contract)
        self._db.commit()
        return self._detail(contract_id)

    def renew(self, contract_id: int, data: ServiceContractRenew) -> ServiceContractDetail:
        old = self._require(contract_id)
        if old.status == "Cancelled":
            raise ApiError("A cancelled ASC can't be renewed. Add a new one for the machine instead.")
        machine_id = self._repo.covered_machine(old.id)
        if machine_id is None:
            raise ApiError("This ASC isn't linked to a machine.")
        plan = self._check_plan(data.contract_plan_id if data.contract_plan_id is not None else old.contract_plan_id)
        start = data.start_date or old.end_date + dt.timedelta(days=1)
        end = data.end_date or self._default_end(start, plan, months_if_no_plan=_months(old.start_date, old.end_date))
        self._check_dates(start, end)
        self._check_overlap(machine_id, start, end, None)

        new = ServiceContract(
            company_id=old.company_id,
            contract_no=next_document_no(
                self._db, company_id=old.company_id, document_type=DOCUMENT_TYPE, branch_id=old.branch_id
            ),
            principal_id=old.principal_id,
            customer_id=old.customer_id,
            contract_type=ASC,
            start_date=start,
            end_date=end,
            visits_included=(
                data.visits_included if data.visits_included is not None else _plan_visits(plan) or old.visits_included
            ),
            contract_value=data.contract_value if data.contract_value is not None else _plan_value(plan),
            status="Active",
            contract_plan_id=plan.id if plan else None,
            branch_id=old.branch_id,
            renewed_from_contract_id=old.id,
            is_renewal=True,
            book_no=data.book_no,
            receipt_no=data.receipt_no,
            invoice_ref=data.invoice_ref,
            engineer_employee_id=old.engineer_employee_id,
            engineer_name=old.engineer_name,
            terms=old.terms,
            enrolled_on=dt.date.today(),
            created_by_user_id=self._actor.id,
        )
        self._db.add(new)
        self._db.flush()
        self._db.add(_coverage(new.id, machine_id, plan, self._actor.id))
        self._db.commit()
        return self._detail(new.id)

    def cancel(self, contract_id: int) -> ServiceContractDetail:
        contract = self._require(contract_id)
        if contract.status != "Cancelled":
            contract.status = "Cancelled"
            self._touch(contract)
            self._db.commit()
        return self._detail(contract_id)

    # ------------------------------------------------------------------ plans

    def create_plan(self, scope: RequestScope, data: ContractPlanCreate) -> ContractPlanItem:
        """The plan belongs to the selected brand, or Tata Hitachi (ASC is a Tata Hitachi offer) when none is."""
        principal_id = scope.principal_id
        if principal_id is None:
            principal_id = self._db.scalar(
                select(Principal.id).where(Principal.code == DEFAULT_PRINCIPAL_CODE, Principal.is_active)
            )
        if principal_id is None:
            raise ApiError("Choose a brand first: plans belong to a brand.")
        self._check_plan_code(data.code, None)
        plan = ContractPlan(
            code=data.code,
            principal_id=principal_id,
            contract_type=ASC,
            visit_frequency_months=1,
            created_by_user_id=self._actor.id,
            **{field: getattr(data, field) for field in _PLAN_FIELDS},
        )
        self._db.add(plan)
        self._save_plan()
        return plan_item(plan)

    def update_plan(self, plan_id: int, expected_row_version: bytes, data: ContractPlanUpdate) -> ContractPlanItem:
        plan = self._require_plan(plan_id)
        check_row_version(plan.row_version, expected_row_version)
        changed = data.model_fields_set
        if "code" in changed and data.code:
            self._check_plan_code(data.code, plan.id)
            plan.code = data.code
        for field in _PLAN_FIELDS:
            if field not in changed:
                continue
            value = getattr(data, field)
            if value is None and field in (
                "name",
                "duration_months",
                "covers_labour",
                "covers_parts",
                "covers_travel",
                "service_priority",
            ):
                continue  # required columns: null means "leave as is"
            setattr(plan, field, value)
        plan.updated_at = _now()
        plan.updated_by_user_id = self._actor.id
        self._save_plan()
        return plan_item(plan)

    def set_plan_active(self, plan_id: int, active: bool) -> ContractPlanItem:
        plan = self._require_plan(plan_id)
        if plan.is_active != active:
            plan.is_active = active
            plan.updated_at = _now()
            plan.updated_by_user_id = self._actor.id
            self._db.commit()
        return plan_item(plan)

    # ------------------------------------------------------------------ helpers

    def _require(self, contract_id: int) -> ServiceContract:
        contract = self._repo.get(contract_id)
        if contract is None or (contract.branch_id is not None and not self._actor.can_use_branch(contract.branch_id)):
            raise NotFound("ASC not found.")
        return contract

    def _require_plan(self, plan_id: int) -> ContractPlan:
        plan = self._repo.get_plan(plan_id)
        if plan is None:
            raise NotFound("Plan not found.")
        return plan

    def _detail(self, contract_id: int) -> ServiceContractDetail:
        detail = self._repo.detail(contract_id, dt.date.today())
        if detail is None:
            raise NotFound("ASC not found.")
        return detail

    def _check_plan(self, plan_id: int | None) -> ContractPlan | None:
        if plan_id is None:
            return None
        plan = self._repo.get_plan(plan_id)
        if plan is None or not plan.is_active:
            raise ApiError("That plan doesn't exist.", errors={"contractPlanId": ["Unknown or inactive plan."]})
        return plan

    def _check_branch(self, branch_id: int | None) -> int:
        if branch_id is None:
            raise ApiError("Choose a branch.", errors={"branchId": ["Required."]})
        if self._repo.active_branch(branch_id) is None or not self._actor.can_use_branch(branch_id):
            raise ApiError("You can't use that branch.", errors={"branchId": ["Not one of your branches."]})
        return branch_id

    def _check_dates(self, start: dt.date, end: dt.date) -> None:
        if end < start:
            raise ApiError(
                "The end date is before the start date.", errors={"endDate": ["Must be on or after the start."]}
            )

    def _check_within_limit(self, contract: ServiceContract) -> None:
        if contract.visits_included is not None and contract.visits_used > contract.visits_included:
            raise ApiError(
                "Visits done can't be more than the visits included.",
                errors={"visitsUsed": [f"At most {contract.visits_included}."]},
            )

    def _check_overlap(self, machine_id: int, start: dt.date, end: dt.date, exclude_id: int | None) -> None:
        other = self._repo.overlapping(machine_id, start, end, exclude_id)
        if other is not None:
            raise ApiError(
                f"This machine already has ASC {other} for part of those dates.",
                errors={"startDate": [f"Overlaps ASC {other}."]},
            )

    def _default_end(self, start: dt.date, plan: ContractPlan | None, months_if_no_plan: int | None = None) -> dt.date:
        months = plan.duration_months if plan else months_if_no_plan
        if not months:
            raise ApiError("Pick a plan or enter the end date.", errors={"endDate": ["Required without a plan."]})
        return plan_end_date(start, months)

    def _set_engineer(self, contract: ServiceContract, employee_id: int | None) -> None:
        if employee_id is None:
            contract.engineer_employee_id = None
            contract.engineer_name = None
            return
        name = self._repo.employee_name(employee_id)
        if name is None:
            raise ApiError("That engineer doesn't exist.", errors={"engineerEmployeeId": ["Unknown or inactive."]})
        contract.engineer_employee_id = employee_id
        contract.engineer_name = name[:100]

    def _check_plan_code(self, code: str, plan_id: int | None) -> None:
        owner = self._repo.plan_code_owner(code)
        if owner is not None and owner != plan_id:
            raise AlreadyExists(f"Plan code '{code}' is already used.")

    def _save_plan(self) -> None:
        try:
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise AlreadyExists("Another plan already has this code.") from error

    def _company_id(self, customer_id: int) -> int:
        customer = self._db.get(Customer, customer_id)
        if customer is None:
            raise NotFound("Customer not found.")
        return customer.company_id

    def _mark_asc_customer(self, customer_id: int) -> None:
        customer = self._db.get(Customer, customer_id)
        if customer is not None and not customer.is_asc_customer:
            customer.is_asc_customer = True

    def _touch(self, contract: ServiceContract) -> None:
        contract.updated_at = _now()
        contract.updated_by_user_id = self._actor.id


def _coverage(contract_id: int, machine_id: int, plan: ContractPlan | None, user_id: int) -> ContractCoverage:
    return ContractCoverage(
        service_contract_id=contract_id,
        machine_unit_id=machine_id,
        covers_labour=plan.covers_labour if plan else True,
        covers_parts=plan.covers_parts if plan else False,
        covers_travel=plan.covers_travel if plan else True,
        parts_discount_pct=plan.parts_discount_pct if plan else DEFAULT_PARTS_DISCOUNT_PCT,
        created_by_user_id=user_id,
    )


def _plan_visits(plan: ContractPlan | None) -> int | None:
    return plan.visits_included if plan else None


def _plan_value(plan: ContractPlan | None) -> Decimal | None:
    return plan_total(plan.price, plan.gst_pct) if plan else None


def _months(start: dt.date, end: dt.date) -> int:
    """Whole months from start to the day after end: a 05-04 to 04-10 contract is 6 months."""
    after = end + dt.timedelta(days=1)
    return max(1, (after.year - start.year) * 12 + after.month - start.month)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
