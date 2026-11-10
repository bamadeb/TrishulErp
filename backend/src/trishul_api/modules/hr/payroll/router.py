"""Salary component routes, shown in Swagger under the payroll tag."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE
from trishul_api.common.schemas import Page
from trishul_api.modules.hr.payroll.run_schemas import PayrollRunItem, PayrollRunRequest
from trishul_api.modules.hr.payroll.run_service import PayrollRunService
from trishul_api.modules.hr.payroll.schemas import (
    SalaryComponentDetail,
    SalaryComponentListItem,
    SalaryComponentQuery,
    SalaryComponentStatus,
    SalaryComponentSummary,
    SalaryComponentUpdate,
    SalaryComponentWrite,
)
from trishul_api.modules.hr.payroll.service import SalaryComponentService
from trishul_api.modules.hr.payroll.statutory_schemas import (
    Scheme,
    StatutoryContribution,
    StatutoryContributionQuery,
    StatutoryRule,
    StatutoryRuleWrite,
    StatutorySummary,
    StatutorySummaryQuery,
)
from trishul_api.modules.hr.payroll.statutory_service import StatutoryService
from trishul_api.modules.hr.payroll.structure_schemas import (
    SalaryStructureDetail,
    SalaryStructureListItem,
    SalaryStructureQuery,
    SalaryStructureSummary,
    SalaryStructureWrite,
)
from trishul_api.modules.hr.payroll.structure_service import SalaryStructureService

router = APIRouter(prefix="/hr", tags=["payroll"])

CAN_VIEW = Depends(
    require_permission(
        "hr.salary_component.view",
        "hr.salary_component.manage",
        "core.employee.view",
        "core.employee.manage",
    )
)
CAN_MANAGE = Depends(require_permission("hr.salary_component.manage", "core.employee.manage"))
ComponentId = Annotated[int, Path(alias="componentId", gt=0)]
QueryModel = Annotated[SalaryComponentQuery, Query()]
Match = Annotated[bytes, Depends(if_match_row_version)]


def get_salary_component_service(db: DbSession) -> SalaryComponentService:
    return SalaryComponentService(db)


Components = Annotated[SalaryComponentService, Depends(get_salary_component_service)]


@router.get("/salary-components/summary", summary="Salary component counts", dependencies=[CAN_VIEW])
def salary_component_summary(components: Components) -> SalaryComponentSummary:
    return components.summary()


@router.get("/salary-components", summary="Salary components, filtered and paged", dependencies=[CAN_VIEW])
def list_salary_components(query: QueryModel, components: Components) -> Page[SalaryComponentListItem]:
    return components.list_components(query)


@router.get(
    "/salary-components/{componentId}",
    summary="One salary component",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def get_salary_component(component_id: ComponentId, components: Components) -> SalaryComponentDetail:
    return components.get_component(component_id)


@router.post("/salary-components", summary="Add a salary component", status_code=201, dependencies=[CAN_MANAGE])
def create_salary_component(
    data: SalaryComponentWrite, actor: CurrentUserDep, components: Components, response: Response
) -> SalaryComponentDetail:
    created = components.create_component(actor, data)
    response.headers["Location"] = f"salary-components/{created.id}"
    return created


@router.patch(
    "/salary-components/{componentId}",
    summary="Change a salary component",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_salary_component(
    component_id: ComponentId,
    data: SalaryComponentUpdate,
    actor: CurrentUserDep,
    components: Components,
    row_version: Match,
) -> SalaryComponentDetail:
    return components.update_component(actor, component_id, row_version, data)


@router.patch(
    "/salary-components/{componentId}/status",
    summary="Activate or deactivate a salary component",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def set_salary_component_status(
    component_id: ComponentId,
    data: SalaryComponentStatus,
    actor: CurrentUserDep,
    components: Components,
    row_version: Match,
) -> SalaryComponentDetail:
    return components.set_status(actor, component_id, row_version, data)


def get_salary_structure_service(db: DbSession) -> SalaryStructureService:
    return SalaryStructureService(db)


Structures = Annotated[SalaryStructureService, Depends(get_salary_structure_service)]
EmployeeId = Annotated[int, Path(alias="employeeId", gt=0)]
StructureQuery = Annotated[SalaryStructureQuery, Query()]


@router.get("/salary-structures/summary", summary="Salary structure counts", dependencies=[CAN_VIEW])
def salary_structure_summary(structures: Structures) -> SalaryStructureSummary:
    return structures.summary()


@router.get("/salary-structures", summary="Employees and their salary structures", dependencies=[CAN_VIEW])
def list_salary_structures(query: StructureQuery, structures: Structures) -> Page[SalaryStructureListItem]:
    return structures.list_structures(query)


@router.get(
    "/salary-structures/{employeeId}",
    summary="One employee salary structure",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def get_salary_structure(employee_id: EmployeeId, structures: Structures) -> SalaryStructureDetail:
    return structures.get_structure(employee_id)


@router.post(
    "/salary-structures/{employeeId}",
    summary="Add an employee salary structure",
    status_code=201,
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def create_salary_structure(
    employee_id: EmployeeId,
    data: SalaryStructureWrite,
    actor: CurrentUserDep,
    structures: Structures,
    response: Response,
) -> SalaryStructureDetail:
    created = structures.save_structure(actor, employee_id, None, data)
    response.headers["Location"] = f"salary-structures/{created.employee_id}"
    return created


@router.patch(
    "/salary-structures/{employeeId}",
    summary="Change an employee salary structure",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_salary_structure(
    employee_id: EmployeeId,
    data: SalaryStructureWrite,
    actor: CurrentUserDep,
    structures: Structures,
    row_version: Match,
) -> SalaryStructureDetail:
    return structures.save_structure(actor, employee_id, row_version, data)


def get_statutory_service(db: DbSession) -> StatutoryService:
    return StatutoryService(db)


Statutory = Annotated[StatutoryService, Depends(get_statutory_service)]
SummaryQuery = Annotated[StatutorySummaryQuery, Query()]
ContributionQuery = Annotated[StatutoryContributionQuery, Query()]
RuleId = Annotated[int, Path(alias="ruleId", gt=0)]


@router.get("/statutory/summary", summary="Statutory compliance for a month", dependencies=[CAN_VIEW])
def statutory_summary(query: SummaryQuery, statutory: Statutory) -> StatutorySummary:
    return statutory.summary(query)


@router.get("/statutory/rules", summary="Saved statutory rules", dependencies=[CAN_VIEW])
def list_statutory_rules(
    statutory: Statutory, scheme: Annotated[Scheme | None, Query()] = None
) -> list[StatutoryRule]:
    return statutory.rules(scheme)


@router.post("/statutory/rules", summary="Add a statutory rule", status_code=201, dependencies=[CAN_MANAGE])
def create_statutory_rule(data: StatutoryRuleWrite, actor: CurrentUserDep, statutory: Statutory) -> StatutoryRule:
    return statutory.save_rule(actor, data)


@router.patch(
    "/statutory/rules/{ruleId}",
    summary="Change a statutory rule",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_statutory_rule(
    rule_id: RuleId,
    data: StatutoryRuleWrite,
    actor: CurrentUserDep,
    statutory: Statutory,
    row_version: Match,
) -> StatutoryRule:
    return statutory.update_rule(actor, rule_id, row_version, data)


@router.get("/statutory/contributions", summary="Employees for a statutory scheme", dependencies=[CAN_VIEW])
def list_statutory_contributions(query: ContributionQuery, statutory: Statutory) -> Page[StatutoryContribution]:
    return statutory.contributions(query)


def get_payroll_run_service(db: DbSession) -> PayrollRunService:
    return PayrollRunService(db)


Runs = Annotated[PayrollRunService, Depends(get_payroll_run_service)]


@router.get("/payroll-runs", summary="Processed payroll months", dependencies=[CAN_VIEW])
def list_payroll_runs(runs: Runs) -> list[PayrollRunItem]:
    return runs.list_runs()


@router.post("/payroll-runs", summary="Process a payroll month", status_code=201, dependencies=[CAN_MANAGE])
def process_payroll_run(data: PayrollRunRequest, actor: CurrentUserDep, runs: Runs) -> list[PayrollRunItem]:
    return runs.process(actor, data)
