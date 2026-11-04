"""Organization Management routes, shown in Swagger under the organization tag."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from trishul_api.auth import CurrentUserDep, DbSession, require_permission
from trishul_api.common.concurrency import if_match_row_version
from trishul_api.common.errors import CONCURRENCY_RESPONSES, NOT_FOUND_RESPONSE
from trishul_api.common.schemas import Page
from trishul_api.modules.hr.organization.schemas import (
    BranchCreate,
    BranchDetail,
    BranchListItem,
    BranchUpdate,
    CompanyCreate,
    CompanyDetail,
    CompanyListItem,
    CompanyUpdate,
    DepartmentCreate,
    DepartmentDetail,
    DepartmentListItem,
    DepartmentUpdate,
    DesignationCreate,
    DesignationDetail,
    DesignationListItem,
    DesignationUpdate,
    GradeCreate,
    GradeDetail,
    GradeListItem,
    GradeUpdate,
    HierarchyCreate,
    HierarchyDetail,
    HierarchyListItem,
    HierarchyUpdate,
    OrganizationQuery,
)
from trishul_api.modules.hr.organization.service import OrganizationService

router = APIRouter(prefix="/hr", tags=["organization"])

CAN_VIEW = Depends(require_permission("hr.organization.view", "hr.organization.manage"))
CAN_MANAGE = Depends(require_permission("hr.organization.manage"))

DepartmentId = Annotated[int, Path(alias="departmentId", gt=0)]
DesignationId = Annotated[int, Path(alias="designationId", gt=0)]
BranchId = Annotated[int, Path(alias="branchId", gt=0)]
CompanyId = Annotated[int, Path(alias="companyId", gt=0)]
EmployeeId = Annotated[int, Path(alias="employeeId", gt=0)]
GradeKey = Annotated[str, Path(alias="grade", min_length=1, max_length=10)]


def get_organization_service(db: DbSession) -> OrganizationService:
    return OrganizationService(db)


Organization = Annotated[OrganizationService, Depends(get_organization_service)]
QueryModel = Annotated[OrganizationQuery, Query()]
Match = Annotated[bytes, Depends(if_match_row_version)]


@router.get("/departments", summary="Departments, filtered and paged", dependencies=[CAN_VIEW])
def list_organization_departments(query: QueryModel, organization: Organization) -> Page[DepartmentListItem]:
    return organization.list_departments(query)


@router.get(
    "/departments/{departmentId}",
    summary="One department",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def get_organization_department(department_id: DepartmentId, organization: Organization) -> DepartmentDetail:
    return organization.get_department(department_id)


@router.post("/departments", summary="Add a department", status_code=201, dependencies=[CAN_MANAGE])
def create_organization_department(
    data: DepartmentCreate, actor: CurrentUserDep, organization: Organization, response: Response
) -> DepartmentDetail:
    created = organization.create_department(actor, data)
    response.headers["Location"] = f"departments/{created.id}"
    return created


@router.patch(
    "/departments/{departmentId}",
    summary="Change a department",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_organization_department(
    department_id: DepartmentId,
    data: DepartmentUpdate,
    actor: CurrentUserDep,
    organization: Organization,
    row_version: Match,
) -> DepartmentDetail:
    return organization.update_department(actor, department_id, row_version, data)


@router.get("/designations", summary="Designations, filtered and paged", dependencies=[CAN_VIEW])
def list_organization_designations(query: QueryModel, organization: Organization) -> Page[DesignationListItem]:
    return organization.list_designations(query)


@router.get(
    "/designations/{designationId}",
    summary="One designation",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def get_organization_designation(designation_id: DesignationId, organization: Organization) -> DesignationDetail:
    return organization.get_designation(designation_id)


@router.post("/designations", summary="Add a designation", status_code=201, dependencies=[CAN_MANAGE])
def create_organization_designation(
    data: DesignationCreate, actor: CurrentUserDep, organization: Organization, response: Response
) -> DesignationDetail:
    created = organization.create_designation(actor, data)
    response.headers["Location"] = f"designations/{created.id}"
    return created


@router.patch(
    "/designations/{designationId}",
    summary="Change a designation",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_organization_designation(
    designation_id: DesignationId,
    data: DesignationUpdate,
    actor: CurrentUserDep,
    organization: Organization,
    row_version: Match,
) -> DesignationDetail:
    return organization.update_designation(actor, designation_id, row_version, data)


@router.get("/grades", summary="Grades stored on designations, filtered and paged", dependencies=[CAN_VIEW])
def list_organization_grades(query: QueryModel, organization: Organization) -> Page[GradeListItem]:
    return organization.list_grades(query)


@router.get(
    "/grades/{grade}",
    summary="One grade and the designations that use it",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def get_organization_grade(grade: GradeKey, organization: Organization) -> GradeDetail:
    return organization.get_grade(grade)


@router.post("/grades", summary="Set a grade on an existing designation", status_code=201, dependencies=[CAN_MANAGE])
def create_organization_grade(data: GradeCreate, actor: CurrentUserDep, organization: Organization) -> GradeDetail:
    return organization.create_grade(actor, data)


@router.post(
    "/grades/{grade}/rename",
    summary="Rename a grade on every designation that uses it",
    dependencies=[CAN_MANAGE],
    responses=NOT_FOUND_RESPONSE,
)
def rename_organization_grade(
    grade: GradeKey, data: GradeUpdate, actor: CurrentUserDep, organization: Organization
) -> GradeDetail:
    return organization.rename_grade(actor, grade, data)


@router.get("/branches", summary="Locations and branches, filtered and paged", dependencies=[CAN_VIEW])
def list_organization_branches(query: QueryModel, organization: Organization) -> Page[BranchListItem]:
    return organization.list_branches(query)


@router.get(
    "/branches/{branchId}",
    summary="One location or branch",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def get_organization_branch(branch_id: BranchId, organization: Organization) -> BranchDetail:
    return organization.get_branch(branch_id)


@router.post("/branches", summary="Add a location or branch", status_code=201, dependencies=[CAN_MANAGE])
def create_organization_branch(
    data: BranchCreate, actor: CurrentUserDep, organization: Organization, response: Response
) -> BranchDetail:
    created = organization.create_branch(actor, data)
    response.headers["Location"] = f"branches/{created.id}"
    return created


@router.patch(
    "/branches/{branchId}",
    summary="Change a location or branch",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_organization_branch(
    branch_id: BranchId,
    data: BranchUpdate,
    actor: CurrentUserDep,
    organization: Organization,
    row_version: Match,
) -> BranchDetail:
    return organization.update_branch(actor, branch_id, row_version, data)


@router.get("/companies", summary="Companies, filtered and paged", dependencies=[CAN_VIEW])
def list_organization_companies(query: QueryModel, organization: Organization) -> Page[CompanyListItem]:
    return organization.list_companies(query)


@router.get(
    "/companies/{companyId}",
    summary="One company",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def get_organization_company(company_id: CompanyId, organization: Organization) -> CompanyDetail:
    return organization.get_company(company_id)


@router.post("/companies", summary="Add a company", status_code=201, dependencies=[CAN_MANAGE])
def create_organization_company(
    data: CompanyCreate, actor: CurrentUserDep, organization: Organization, response: Response
) -> CompanyDetail:
    created = organization.create_company(actor, data)
    response.headers["Location"] = f"companies/{created.id}"
    return created


@router.patch(
    "/companies/{companyId}",
    summary="Change a company",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_organization_company(
    company_id: CompanyId,
    data: CompanyUpdate,
    actor: CurrentUserDep,
    organization: Organization,
    row_version: Match,
) -> CompanyDetail:
    return organization.update_company(actor, company_id, row_version, data)


@router.get("/hierarchy", summary="Reporting hierarchy from each employee's manager", dependencies=[CAN_VIEW])
def list_organization_hierarchy(query: QueryModel, organization: Organization) -> Page[HierarchyListItem]:
    return organization.list_hierarchy(query)


@router.get(
    "/hierarchy/{employeeId}",
    summary="One employee in the reporting hierarchy",
    dependencies=[CAN_VIEW],
    responses=NOT_FOUND_RESPONSE,
)
def get_organization_hierarchy_member(employee_id: EmployeeId, organization: Organization) -> HierarchyDetail:
    return organization.get_hierarchy_member(employee_id)


@router.post(
    "/hierarchy",
    summary="Set who an existing employee reports to",
    status_code=201,
    dependencies=[CAN_MANAGE],
)
def create_organization_hierarchy_link(
    data: HierarchyCreate, actor: CurrentUserDep, organization: Organization
) -> HierarchyDetail:
    return organization.create_hierarchy_link(actor, data)


@router.patch(
    "/hierarchy/{employeeId}",
    summary="Change who an employee reports to",
    dependencies=[CAN_MANAGE],
    responses={**NOT_FOUND_RESPONSE, **CONCURRENCY_RESPONSES},
)
def update_organization_hierarchy(
    employee_id: EmployeeId,
    data: HierarchyUpdate,
    actor: CurrentUserDep,
    organization: Organization,
    row_version: Match,
) -> HierarchyDetail:
    return organization.update_hierarchy(actor, employee_id, row_version, data)
