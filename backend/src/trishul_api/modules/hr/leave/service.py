"""Leave type and policy changes. Approval and balances are later phases."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from trishul_api.auth import CurrentUser
from trishul_api.common.concurrency import check_row_version
from trishul_api.common.errors import AlreadyExists, NotFound
from trishul_api.common.schemas import Page
from trishul_api.db.models import LeavePolicy, LeavePolicyLine, LeaveType, LeaveTypeSetting
from trishul_api.modules.hr.leave.calculation import rule_summary
from trishul_api.modules.hr.leave.repository import LeaveRepository
from trishul_api.modules.hr.leave.schemas import (
    LeavePolicyItem,
    LeavePolicyLineItem,
    LeavePolicyQuery,
    LeavePolicyWrite,
    LeaveTypeItem,
    LeaveTypeQuery,
    LeaveTypeWrite,
)


class LeaveService:
    def __init__(self, db: Session) -> None:
        self._repo = LeaveRepository(db)
        self._db = db

    def list_types(self, query: LeaveTypeQuery) -> Page[LeaveTypeItem]:
        rows, total = self._repo.search_types(query)
        return Page(
            items=[_type_item(leave_type, setting) for leave_type, setting in rows],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    def get_type(self, leave_type_id: int) -> LeaveTypeItem:
        leave_type = self._repo.leave_type(leave_type_id)
        if leave_type is None:
            raise NotFound("Leave type")
        return _type_item(leave_type, self._repo.setting(leave_type_id))

    def create_type(self, actor: CurrentUser, data: LeaveTypeWrite) -> LeaveTypeItem:
        owner = self._repo.code_owner(data.code)
        if owner is not None:
            raise AlreadyExists(f"Leave type '{data.code}' is already in use.")
        row = LeaveType(
            code=data.code,
            name=data.name,
            annual_quota=data.annual_quota,
            carry_forward_max=data.carry_forward_max,
            is_paid=data.is_paid,
            is_encashable=data.is_encashable,
            is_active=data.is_active,
            created_by_user_id=actor.id,
        )
        self._repo.add(row)
        self._repo.add(_setting(row.id, data))
        self._db.commit()
        self._db.refresh(row)
        return self.get_type(row.id)

    def update_type(
        self, actor: CurrentUser, leave_type_id: int, expected: bytes, data: LeaveTypeWrite
    ) -> LeaveTypeItem:
        row = self._repo.leave_type(leave_type_id)
        if row is None:
            raise NotFound("Leave type")
        check_row_version(row.row_version, expected)
        owner = self._repo.code_owner(data.code)
        if owner is not None and owner != leave_type_id:
            raise AlreadyExists(f"Leave type '{data.code}' is already in use.")
        row.code = data.code
        row.name = data.name
        row.annual_quota = data.annual_quota
        row.carry_forward_max = data.carry_forward_max
        row.is_paid = data.is_paid
        row.is_encashable = data.is_encashable
        row.is_active = data.is_active
        row.updated_at = datetime.now(UTC).replace(tzinfo=None)
        row.updated_by_user_id = actor.id
        setting = self._repo.setting(leave_type_id) or LeaveTypeSetting(leave_type_id=leave_type_id)
        _apply_setting(setting, data)
        self._repo.add(setting)
        self._db.commit()
        return self.get_type(leave_type_id)

    def list_policies(self, query: LeavePolicyQuery) -> Page[LeavePolicyItem]:
        rows, total = self._repo.search_policies(query)
        return Page(
            items=[self._policy_item(row) for row in rows],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    def get_policy(self, policy_id: int) -> LeavePolicyItem:
        row = self._repo.policy(policy_id)
        if row is None:
            raise NotFound("Leave policy")
        return self._policy_item(row)

    def create_policy(self, actor: CurrentUser, data: LeavePolicyWrite) -> LeavePolicyItem:
        self._policy_refs(data)
        if self._repo.policy_name_owner(data.name) is not None:
            raise AlreadyExists(f"Leave policy '{data.name}' is already in use.")
        row = LeavePolicy(
            name=data.name,
            employee_type=data.employee_type,
            department_id=data.department_id,
            branch_id=data.branch_id,
            state_id=data.state_id,
            year_basis=data.year_basis,
            assignment_mode=data.assignment_mode,
            applies_during_probation=data.applies_during_probation,
            negative_balance_allowed=data.negative_balance_allowed,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
            is_active=data.is_active,
            created_by_user_id=actor.id,
        )
        self._repo.add(row)
        self._save_lines(row.id, actor, data)
        self._db.commit()
        return self.get_policy(row.id)

    def update_policy(
        self, actor: CurrentUser, policy_id: int, expected: bytes, data: LeavePolicyWrite
    ) -> LeavePolicyItem:
        row = self._repo.policy(policy_id)
        if row is None:
            raise NotFound("Leave policy")
        check_row_version(row.row_version, expected)
        self._policy_refs(data)
        owner = self._repo.policy_name_owner(data.name)
        if owner is not None and owner != policy_id:
            raise AlreadyExists(f"Leave policy '{data.name}' is already in use.")
        row.name = data.name
        row.employee_type = data.employee_type
        row.department_id = data.department_id
        row.branch_id = data.branch_id
        row.state_id = data.state_id
        row.year_basis = data.year_basis
        row.assignment_mode = data.assignment_mode
        row.applies_during_probation = data.applies_during_probation
        row.negative_balance_allowed = data.negative_balance_allowed
        row.effective_from = data.effective_from
        row.effective_to = data.effective_to
        row.is_active = data.is_active
        row.updated_at = datetime.now(UTC).replace(tzinfo=None)
        row.updated_by_user_id = actor.id
        self._save_lines(policy_id, actor, data)
        self._db.commit()
        return self.get_policy(policy_id)

    def _policy_refs(self, data: LeavePolicyWrite) -> None:
        if data.department_id is not None and not self._repo.department_exists(data.department_id):
            raise NotFound("Department")
        if data.branch_id is not None and not self._repo.branch_exists(data.branch_id):
            raise NotFound("Branch")
        if data.state_id is not None and not self._repo.state_exists(data.state_id):
            raise NotFound("State")
        for line in data.lines:
            if self._repo.leave_type(line.leave_type_id) is None:
                raise NotFound("Leave type")

    def _save_lines(self, policy_id: int, actor: CurrentUser, data: LeavePolicyWrite) -> None:
        existing = {leave_type.id: line for line, leave_type in self._repo.lines(policy_id, active_only=False)}
        keep = {line.leave_type_id for line in data.lines}
        for leave_type_id, stored in existing.items():
            if leave_type_id not in keep:
                stored.is_active = False
        for line in data.lines:
            stored = existing.get(line.leave_type_id)
            if stored is None:
                self._repo.add(
                    LeavePolicyLine(
                        leave_policy_id=policy_id,
                        leave_type_id=line.leave_type_id,
                        annual_entitlement=line.annual_entitlement,
                        accrual_frequency=line.accrual_frequency,
                        carry_forward=line.carry_forward,
                        max_accumulation=line.max_accumulation,
                        encashment_eligible=line.encashment_eligible,
                        calculation_method=line.calculation_method,
                        credit_days=line.credit_days,
                        qualifying_days_per_credit=line.qualifying_days_per_credit,
                        minimum_qualifying_days=line.minimum_qualifying_days,
                        joining_year_rule=line.joining_year_rule,
                        minimum_service_months=line.minimum_service_months,
                        adolescent_max_accumulation=line.adolescent_max_accumulation,
                        exclude_boundary_holidays=line.exclude_boundary_holidays,
                        document_required=line.document_required,
                        benefit_class=line.benefit_class,
                        compensatory_basis=line.compensatory_basis,
                        compensatory_expiry_months=line.compensatory_expiry_months,
                        max_backdate_days=line.max_backdate_days,
                        backdate_requires_authorization=line.backdate_requires_authorization,
                        created_by_user_id=actor.id,
                    )
                )
                continue
            stored.annual_entitlement = line.annual_entitlement
            stored.accrual_frequency = line.accrual_frequency
            stored.carry_forward = line.carry_forward
            stored.max_accumulation = line.max_accumulation
            stored.encashment_eligible = line.encashment_eligible
            stored.calculation_method = line.calculation_method
            stored.credit_days = line.credit_days
            stored.qualifying_days_per_credit = line.qualifying_days_per_credit
            stored.minimum_qualifying_days = line.minimum_qualifying_days
            stored.joining_year_rule = line.joining_year_rule
            stored.minimum_service_months = line.minimum_service_months
            stored.adolescent_max_accumulation = line.adolescent_max_accumulation
            stored.exclude_boundary_holidays = line.exclude_boundary_holidays
            stored.document_required = line.document_required
            stored.benefit_class = line.benefit_class
            stored.compensatory_basis = line.compensatory_basis
            stored.compensatory_expiry_months = line.compensatory_expiry_months
            stored.max_backdate_days = line.max_backdate_days
            stored.backdate_requires_authorization = line.backdate_requires_authorization
            stored.is_active = True
            stored.updated_by_user_id = actor.id

    def _policy_item(self, row: LeavePolicy) -> LeavePolicyItem:
        lines = [
            LeavePolicyLineItem(
                id=line.id,
                leave_type_id=leave_type.id,
                leave_type_code=leave_type.code,
                leave_type_name=leave_type.name,
                annual_entitlement=line.annual_entitlement,
                accrual_frequency=line.accrual_frequency,  # type: ignore[arg-type]
                carry_forward=line.carry_forward,
                max_accumulation=line.max_accumulation,
                encashment_eligible=line.encashment_eligible,
                calculation_method=line.calculation_method,  # type: ignore[arg-type]
                credit_days=line.credit_days,
                qualifying_days_per_credit=line.qualifying_days_per_credit,
                minimum_qualifying_days=line.minimum_qualifying_days,
                joining_year_rule=line.joining_year_rule,  # type: ignore[arg-type]
                minimum_service_months=line.minimum_service_months,
                adolescent_max_accumulation=line.adolescent_max_accumulation,
                exclude_boundary_holidays=line.exclude_boundary_holidays,
                document_required=line.document_required,
                benefit_class=line.benefit_class,  # type: ignore[arg-type]
                compensatory_basis=line.compensatory_basis,  # type: ignore[arg-type]
                compensatory_expiry_months=line.compensatory_expiry_months,
                max_backdate_days=line.max_backdate_days,
                backdate_requires_authorization=line.backdate_requires_authorization,
                rule_summary=rule_summary(line),
            )
            for line, leave_type in self._repo.lines(row.id)
        ]
        return LeavePolicyItem(
            id=row.id,
            name=row.name,
            employee_type=row.employee_type,
            department_id=row.department_id,
            department_name=self._repo.department_name(row.department_id),
            branch_id=row.branch_id,
            branch_name=self._repo.branch_name(row.branch_id),
            state_id=row.state_id,
            state_name=self._repo.state_name(row.state_id),
            year_basis=row.year_basis,  # type: ignore[arg-type]
            assignment_mode=row.assignment_mode,  # type: ignore[arg-type]
            applies_during_probation=row.applies_during_probation,
            negative_balance_allowed=row.negative_balance_allowed,
            effective_from=row.effective_from,
            effective_to=row.effective_to,
            is_active=row.is_active,
            lines=lines,
            row_version=row.row_version,
        )


def _setting(leave_type_id: int, data: LeaveTypeWrite) -> LeaveTypeSetting:
    row = LeaveTypeSetting(leave_type_id=leave_type_id)
    _apply_setting(row, data)
    return row


def _apply_setting(row: LeaveTypeSetting, data: LeaveTypeWrite) -> None:
    row.description = data.description
    row.accrual_applicable = data.accrual_applicable
    row.half_day_allowed = data.half_day_allowed
    row.attachment_required = data.attachment_required
    row.max_consecutive_days = data.max_consecutive_days


def _type_item(leave_type: LeaveType, setting: LeaveTypeSetting | None) -> LeaveTypeItem:
    return LeaveTypeItem(
        id=leave_type.id,
        code=leave_type.code,
        name=leave_type.name,
        description=None if setting is None else setting.description,
        annual_quota=leave_type.annual_quota,
        carry_forward_max=leave_type.carry_forward_max,
        is_paid=leave_type.is_paid,
        is_encashable=leave_type.is_encashable,
        accrual_applicable=False if setting is None else setting.accrual_applicable,
        half_day_allowed=True if setting is None else setting.half_day_allowed,
        attachment_required=False if setting is None else setting.attachment_required,
        max_consecutive_days=None if setting is None else setting.max_consecutive_days,
        is_active=leave_type.is_active,
        row_version=leave_type.row_version,
    )
