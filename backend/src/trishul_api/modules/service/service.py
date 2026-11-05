"""Service calls: logging a new call (office), team-lead triage, and status changes.

call_no, status (Logged) and received_by are set here; branch and brand default to the ones the user has
selected (the request scope). References are validated up front for clear field errors. Every change of a
call's status is recorded in svc.call_status_log (see status_log.py) and shown as the call's history.
"""

import logging
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser, RequestScope
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import ApiError, Forbidden, NotFound
from trishul_api.common.numbering import next_document_no
from trishul_api.db.models import (
    Branch,
    Customer,
    Employee,
    LookupType,
    LookupValue,
    MachineUnit,
    Principal,
    ServiceCall,
)
from trishul_api.modules.alerts.engine import AlertEngine
from trishul_api.modules.service import sla
from trishul_api.modules.service.access import CallVisibility, allowed_statuses, call_visibility
from trishul_api.modules.service.assignment import assignees, plan_visit, set_engineers, support_ids
from trishul_api.modules.service.contracts.repository import ContractRepository
from trishul_api.modules.service.repository import ServiceCallRepository
from trishul_api.modules.service.schemas import (
    CallStatusLogItem,
    ServiceCallCreate,
    ServiceCallDetail,
    ServiceCallListItem,
    ServiceCallStatusChange,
    ServiceCallTriageUpdate,
)
from trishul_api.modules.service.status_log import record_status_change
from trishul_api.modules.service.workload import leave_on

log = logging.getLogger(__name__)


class ServiceCallService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor
        self._repo = ServiceCallRepository(db)
        self._visibility: CallVisibility | None = None

    @property
    def visibility(self) -> CallVisibility:
        """Which calls this user sees (access.call_visibility); looked up once per request."""
        if self._visibility is None:
            self._visibility = call_visibility(self._actor, self._repo.team_members)
        return self._visibility

    def create(self, scope: RequestScope, data: ServiceCallCreate) -> ServiceCallListItem:
        branch = self._resolve_branch(data.branch_id, scope)
        principal = self._resolve_principal(data.principal_id, scope)
        self._check_references(data, branch.company_id, principal.id)

        received_at = data.received_at.replace(tzinfo=None) if data.received_at else _now()
        # A machine under ASC on the day of the call: link the contract and attend it first.
        contract_id = (
            ContractRepository(self._db).active_contract_id(data.machine_unit_id, received_at.date())
            if data.machine_unit_id is not None
            else None
        )
        # SLA due time comes from svc.sla_rule only (see sla.py); no matching rule leaves it blank.
        sla_target = sla.match_rule(
            sla.active_rules(self._db, branch.company_id),
            company_id=branch.company_id,
            principal_id=principal.id,
            call_type_lookup_id=data.call_type_lookup_id,
            priority=data.priority,
        )
        call = ServiceCall(
            company_id=branch.company_id,
            branch_id=branch.id,
            principal_id=principal.id,
            call_no=next_document_no(
                self._db,
                company_id=branch.company_id,
                document_type="SERVICE_CALL",
                branch_id=branch.id,
                principal_id=principal.id,
            ),
            call_source_lookup_id=data.call_source_lookup_id,
            call_type_lookup_id=data.call_type_lookup_id,
            complaint_description=data.complaint_description,
            customer_id=data.customer_id,
            machine_unit_id=data.machine_unit_id,
            caller_name=data.caller_name,
            caller_phone=data.caller_phone,
            is_machine_down=data.is_machine_down,
            is_asc_priority=contract_id is not None,
            service_contract_id=contract_id,
            coverage_type="Contract" if contract_id is not None else None,
            priority=data.priority,
            received_at=received_at,
            sla_due_at=sla.due_at(received_at, sla_target),
            received_by_user_id=self._actor.id,
            current_status="Logged",
            created_by_user_id=self._actor.id,
        )
        self._db.add(call)
        self._db.flush()
        call_id = call.id
        record_status_change(self._db, call_id, None, "Logged", self._actor.id, "Call logged")
        self._db.commit()
        return self._repo.get_list_item(call_id)

    def update_triage(
        self, call_id: int, expected_row_version: bytes, data: ServiceCallTriageUpdate
    ) -> ServiceCallListItem:
        """A team lead changes the engineers and/or re-prioritises a call from the register."""
        call = self._db.get(ServiceCall, call_id)
        if call is None or not call.is_active or not self.visibility.allows(assignees(self._db, call)):
            raise NotFound("Service call not found.")
        check_row_version(call.row_version, expected_row_version)
        changed = data.model_fields_set
        status_before = call.current_status

        if "priority" in changed and data.priority is not None:
            call.priority = data.priority
        if "engineer_id" in changed or "support_engineer_ids" in changed:
            self._assign(call, data)
        if data.visit_date is not None:
            self._plan_visit(call, data.visit_date)
        if "customer_id" in changed and data.customer_id is not None:
            linked = self._db.scalars(
                select(Customer.id)
                .where(
                    Customer.id == data.customer_id,
                    Customer.is_active,
                    Customer.company_id == call.company_id,
                )
                .limit(1)
            ).first()
            if linked is None:
                raise ApiError(
                    "That customer doesn't exist.",
                    errors={"customerId": [f"Unknown or inactive customer {data.customer_id}"]},
                )
            call.customer_id = data.customer_id
            call.external_account_name = None  # now linked to a real customer master
            call.needs_master_linking = call.machine_unit_id is None and call.external_product_id is not None
        # Checked after the customer: the machine has to be the customer's being linked here.
        if "machine_unit_id" in changed and data.machine_unit_id != call.machine_unit_id:
            self._link_machine(call, data.machine_unit_id)

        call.updated_at = _now()
        call.updated_by_user_id = self._actor.id
        if call.current_status != status_before:  # assigning / unassigning moved the status
            record_status_change(
                self._db, call.id, status_before, call.current_status, self._actor.id, "Engineer assignment changed"
            )
        self._db.commit()
        return self._repo.get_list_item(call_id)

    def _plan_visit(self, call: ServiceCall, day: date) -> None:
        """Everyone on the call gets the day, so it counts in each engineer's workload."""
        if call.assigned_engineer_id is None:
            raise ApiError("Assign an engineer before planning a visit.", errors={"engineerId": ["Required."]})
        if day < date.today():
            raise ApiError("A visit can't be planned in the past.", errors={"visitDate": ["Pick today or later."]})
        team = sorted(assignees(self._db, call))
        if False in leave_on(self._db, team, day).values():
            raise ApiError("Someone on this call is on leave that day.", errors={"visitDate": ["On approved leave."]})
        for engineer in team:
            plan_visit(self._db, call, engineer, day, self._actor.id, _now())

    def _link_machine(self, call: ServiceCall, machine_id: int | None) -> None:
        """Put the machine on the call (or take it off), and follow its ASC on the day the call came in."""
        contract_id = None
        if machine_id is not None:
            problem = self._machine_problem(machine_id, call.customer_id, call.principal_id)
            if problem:
                raise ApiError("That machine can't be linked to this call.", errors={"machineUnitId": [problem]})
            contract_id = ContractRepository(self._db).active_contract_id(machine_id, call.received_at.date())
            call.external_product_id = None  # now linked to a real machine
        call.machine_unit_id = machine_id
        call.service_contract_id = contract_id
        call.is_asc_priority = contract_id is not None
        if call.coverage_type != "Warranty":  # warranty comes from BYD and doesn't depend on the ASC
            call.coverage_type = "Contract" if contract_id is not None else None
        call.needs_master_linking = call.external_account_name is not None or (
            call.machine_unit_id is None and call.external_product_id is not None
        )

    def _assign(self, call: ServiceCall, data: ServiceCallTriageUpdate) -> None:
        """Apply the lead and support engineers sent; the one left out keeps its current value."""
        changed = data.model_fields_set
        lead = data.engineer_id if "engineer_id" in changed else call.assigned_engineer_id
        support = (
            set(data.support_engineer_ids) if "support_engineer_ids" in changed else support_ids(self._db, call.id)
        )
        if lead is None:
            if "support_engineer_ids" in changed and support:
                raise ApiError(
                    "Choose a lead engineer for this call.", errors={"engineerId": ["Required with support engineers."]}
                )
            support = set()
        wanted = support if lead is None else support | {lead}

        # Only people being added are checked: a team lead can keep someone an office user put on the call.
        for engineer in sorted(wanted - assignees(self._db, call)):
            self._check_engineer(engineer, "engineerId" if engineer == lead else "supportEngineerIds")
        set_engineers(self._db, call, lead, support - {lead}, self._actor.id, _now())
        if lead is not None and call.current_status == "Logged":
            call.current_status = "Assigned"
        elif lead is None and call.current_status == "Assigned":
            call.current_status = "Logged"

    def _check_engineer(self, engineer_id: int, field: str) -> None:
        if (
            self._db.scalars(select(Employee.id).where(Employee.id == engineer_id, Employee.is_active).limit(1)).first()
            is None
        ):
            raise ApiError(
                "That engineer doesn't exist.", errors={field: [f"Unknown or inactive employee {engineer_id}"]}
            )
        if not self.visibility.allows({engineer_id}):
            # A team lead assigns within their team; otherwise the call could drop off their list.
            raise ApiError("That engineer isn't in your team.", errors={field: ["Pick an engineer from your team."]})

    def detail(self, call_id: int) -> ServiceCallDetail:
        """One call in full, with the statuses this user may move it to."""
        detail = self._repo.detail(call_id)
        if detail is None:
            raise NotFound("Service call not found.")
        on_call = {engineer.id for engineer in detail.support_engineers}
        if detail.assigned_engineer_id is not None:
            on_call.add(detail.assigned_engineer_id)
        if not self.visibility.allows(on_call):
            raise NotFound("Service call not found.")
        detail.allowed_statuses = allowed_statuses(  # type: ignore[assignment]
            self._actor, detail.current_status, on_call
        )
        if detail.machine_unit_id is not None:
            detail.asc = ContractRepository(self._db).machine_asc([detail.machine_unit_id], date.today()).get(
                detail.machine_unit_id
            )
        return detail

    def status_history(self, call_id: int) -> list[CallStatusLogItem]:
        call = self._db.get(ServiceCall, call_id)
        if call is None or not call.is_active or not self.visibility.allows(assignees(self._db, call)):
            raise NotFound("Service call not found.")
        return self._repo.status_history(call_id)

    def change_status(
        self, call_id: int, expected_row_version: bytes, data: ServiceCallStatusChange
    ) -> ServiceCallDetail:
        """Move a call to another status (team lead: any call; engineer: their own) and record it."""
        call = self._db.get(ServiceCall, call_id)
        if call is None or not call.is_active:
            raise NotFound("Service call not found.")
        on_call = assignees(self._db, call)
        if not self.visibility.allows(on_call):
            raise NotFound("Service call not found.")
        check_row_version(call.row_version, expected_row_version)
        if data.status == call.current_status:
            raise ApiError(
                "The call is already in that status.", errors={"status": [f"Already '{call.current_status}'."]}
            )
        if data.status not in allowed_statuses(self._actor, call.current_status, on_call):
            raise Forbidden(f"You can't change this call to '{data.status}'.")

        previous = call.current_status
        now = _now()
        call.current_status = data.status
        if data.status == "Closed":
            call.closed_at = now
            call.closed_by_user_id = self._actor.id
        elif data.status == "Completed":
            call.completed_at = now
        elif data.status == "Reopened":
            call.reopen_count = (call.reopen_count or 0) + 1
            call.last_reopened_at = now
            call.closed_at = None
            call.closed_by_user_id = None
        elif data.status == "Customer contacted" and call.first_response_at is None:
            call.first_response_at = now
        call.updated_at = now
        call.updated_by_user_id = self._actor.id
        record_status_change(self._db, call.id, previous, data.status, self._actor.id, data.remarks)
        if data.status == "Reopened":
            self._raise_event_alerts("SVC_CALL_REOPENED", call.id)
        self._db.commit()
        return self.detail(call_id)

    def _raise_event_alerts(self, alert_type: str, call_id: int) -> None:
        """Raise event alerts in the same transaction; a failure here never blocks the status change."""
        try:
            with self._db.begin_nested():
                AlertEngine(self._db).raise_event(alert_type, call_id)
        except Exception:
            log.exception("Raising %s alerts for call %s failed", alert_type, call_id)

    # ------------------------------------------------------------------ helpers

    def _resolve_branch(self, branch_id: int | None, scope: RequestScope) -> Branch:
        chosen = branch_id if branch_id is not None else scope.branch_id
        if chosen is None:
            raise ApiError("Choose the branch this call belongs to.", errors={"branchId": ["Required."]})
        if not self._actor.can_use_branch(chosen):
            raise ApiError("You do not have access to that branch.", errors={"branchId": ["Not one of your branches."]})
        branch = self._db.get(Branch, chosen)
        if branch is None or not branch.is_active:
            raise ApiError("That branch doesn't exist.", errors={"branchId": [f"Unknown branch {chosen}"]})
        return branch

    def _resolve_principal(self, principal_id: int | None, scope: RequestScope) -> Principal:
        chosen = principal_id if principal_id is not None else scope.principal_id
        if chosen is None:
            raise ApiError("Choose the brand for this call.", errors={"principalId": ["Required."]})
        if not self._actor.can_see_principal(chosen):
            raise ApiError("You do not have access to that brand.", errors={"principalId": ["Not one of your brands."]})
        principal = self._db.get(Principal, chosen)
        if principal is None or not principal.is_active:
            raise ApiError("That brand doesn't exist.", errors={"principalId": [f"Unknown brand {chosen}"]})
        return principal

    def _check_references(self, data: ServiceCallCreate, company_id: int, principal_id: int) -> None:
        errors: dict[str, list[str]] = {}
        customer_company = self._db.scalars(
            select(Customer.company_id).where(Customer.id == data.customer_id, Customer.is_active).limit(1)
        ).first()
        if customer_company is None:
            errors["customerId"] = [f"Unknown or inactive customer {data.customer_id}"]
        elif customer_company != company_id:
            errors["customerId"] = ["That customer belongs to another company."]
        if data.machine_unit_id is not None:
            problem = self._machine_problem(data.machine_unit_id, data.customer_id, principal_id)
            if problem:
                errors["machineUnitId"] = [problem]
        if not self._lookup_of_type(data.call_type_lookup_id, "CALL_TYPE"):
            errors["callTypeLookupId"] = ["Not a valid call type."]
        if not self._lookup_of_type(data.call_source_lookup_id, "CALL_SOURCE"):
            errors["callSourceLookupId"] = ["Not a valid call source."]
        if errors:
            raise ApiError("Some of the selected values don't exist.", errors=errors)

    def _machine_problem(self, machine_id: int, customer_id: int, principal_id: int) -> str | None:
        """Why this machine can't go on a call: a deactivated one can't be picked, and it must be the customer's."""
        machine = self._db.execute(
            select(MachineUnit.customer_id, MachineUnit.principal_id)
            .where(MachineUnit.id == machine_id, MachineUnit.is_active)
            .limit(1)
        ).first()
        if machine is None:
            return f"Unknown or inactive machine {machine_id}"
        if machine.customer_id != customer_id:
            return "That machine is not registered to this customer."
        if machine.principal_id != principal_id:
            return "That machine is of another brand."
        return None

    def _lookup_of_type(self, value_id: int, type_code: str) -> bool:
        return (
            self._db.scalars(
                select(LookupValue.id)
                .join(LookupType, LookupType.id == LookupValue.lookup_type_id)
                .where(LookupValue.id == value_id, LookupType.code == type_code, LookupValue.is_active)
                .limit(1)
            ).first()
            is not None
        )


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
