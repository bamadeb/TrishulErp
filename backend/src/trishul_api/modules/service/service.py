"""Service calls: logging a new call (office), team-lead triage, and status changes.

call_no, status (Logged) and received_by are set here; branch and brand default to the ones the user has
selected (the request scope). References are validated up front for clear field errors. Every change of a
call's status is recorded in svc.call_status_log (see status_log.py) and shown as the call's history.
"""

from datetime import UTC, datetime

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
from trishul_api.modules.service.access import allowed_statuses, can_see_call
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


class ServiceCallService:
    def __init__(self, db: Session, actor: CurrentUser) -> None:
        self._db = db
        self._actor = actor
        self._repo = ServiceCallRepository(db)

    def create(self, scope: RequestScope, data: ServiceCallCreate) -> ServiceCallListItem:
        branch = self._resolve_branch(data.branch_id, scope)
        principal = self._resolve_principal(data.principal_id, scope)
        self._check_references(data, branch.company_id)

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
            is_asc_priority=False,
            priority=data.priority,
            received_at=data.received_at.replace(tzinfo=None) if data.received_at else _now(),
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
        """A team lead reassigns and/or re-prioritises a call from the register."""
        call = self._db.get(ServiceCall, call_id)
        if call is None or not call.is_active:
            raise NotFound("Service call not found.")
        check_row_version(call.row_version, expected_row_version)
        changed = data.model_fields_set
        status_before = call.current_status

        if "priority" in changed and data.priority is not None:
            call.priority = data.priority
        if "engineer_id" in changed:
            if data.engineer_id is not None:
                if (
                    self._db.scalars(
                        select(Employee.id).where(Employee.id == data.engineer_id, Employee.is_active).limit(1)
                    ).first()
                    is None
                ):
                    raise ApiError(
                        "That engineer doesn't exist.",
                        errors={"engineerId": [f"Unknown or inactive employee {data.engineer_id}"]},
                    )
                call.assigned_engineer_id = data.engineer_id
                if call.current_status == "Logged":
                    call.current_status = "Assigned"
            else:
                call.assigned_engineer_id = None
                if call.current_status == "Assigned":
                    call.current_status = "Logged"
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

        call.updated_at = _now()
        call.updated_by_user_id = self._actor.id
        if call.current_status != status_before:  # assigning / unassigning moved the status
            record_status_change(
                self._db, call.id, status_before, call.current_status, self._actor.id, "Engineer assignment changed"
            )
        self._db.commit()
        return self._repo.get_list_item(call_id)

    def detail(self, call_id: int) -> ServiceCallDetail:
        """One call in full, with the statuses this user may move it to."""
        detail = self._repo.detail(call_id)
        if detail is None or not can_see_call(self._actor, detail.assigned_engineer_id):
            raise NotFound("Service call not found.")
        detail.allowed_statuses = allowed_statuses(  # type: ignore[assignment]
            self._actor, detail.current_status, detail.assigned_engineer_id
        )
        return detail

    def status_history(self, call_id: int) -> list[CallStatusLogItem]:
        exists, assignee = self._repo.assignment(call_id)
        if not exists or not can_see_call(self._actor, assignee):
            raise NotFound("Service call not found.")
        return self._repo.status_history(call_id)

    def change_status(
        self, call_id: int, expected_row_version: bytes, data: ServiceCallStatusChange
    ) -> ServiceCallDetail:
        """Move a call to another status (team lead: any call; engineer: their own) and record it."""
        call = self._db.get(ServiceCall, call_id)
        if call is None or not call.is_active or not can_see_call(self._actor, call.assigned_engineer_id):
            raise NotFound("Service call not found.")
        check_row_version(call.row_version, expected_row_version)
        if data.status == call.current_status:
            raise ApiError(
                "The call is already in that status.", errors={"status": [f"Already '{call.current_status}'."]}
            )
        if data.status not in allowed_statuses(self._actor, call.current_status, call.assigned_engineer_id):
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
        self._db.commit()
        return self.detail(call_id)

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

    def _check_references(self, data: ServiceCallCreate, company_id: int) -> None:
        errors: dict[str, list[str]] = {}
        customer_company = self._db.scalars(
            select(Customer.company_id).where(Customer.id == data.customer_id, Customer.is_active).limit(1)
        ).first()
        if customer_company is None:
            errors["customerId"] = [f"Unknown or inactive customer {data.customer_id}"]
        elif customer_company != company_id:
            errors["customerId"] = ["That customer belongs to another company."]
        if (
            data.machine_unit_id is not None
            and self._db.scalars(
                select(MachineUnit.id).where(MachineUnit.id == data.machine_unit_id, MachineUnit.is_active).limit(1)
            ).first()
            is None
        ):
            errors["machineUnitId"] = [f"Unknown or inactive machine {data.machine_unit_id}"]
        if not self._lookup_of_type(data.call_type_lookup_id, "CALL_TYPE"):
            errors["callTypeLookupId"] = ["Not a valid call type."]
        if not self._lookup_of_type(data.call_source_lookup_id, "CALL_SOURCE"):
            errors["callSourceLookupId"] = ["Not a valid call source."]
        if errors:
            raise ApiError("Some of the selected values don't exist.", errors=errors)

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
