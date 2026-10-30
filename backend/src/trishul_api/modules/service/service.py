"""Logging a new service call (office). call_no, status (Logged) and received_by are set here; branch
and brand default to the ones the user has selected (the request scope). References are validated up
front for clear field errors."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser, RequestScope
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import ApiError, NotFound
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
from trishul_api.modules.service.repository import ServiceCallRepository
from trishul_api.modules.service.schemas import (
    ServiceCallCreate,
    ServiceCallListItem,
    ServiceCallTriageUpdate,
)


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

        call.updated_at = _now()
        call.updated_by_user_id = self._actor.id
        self._db.commit()
        return self._repo.get_list_item(call_id)

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
