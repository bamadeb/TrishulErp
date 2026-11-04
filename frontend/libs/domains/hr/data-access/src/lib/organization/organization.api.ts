import { Injectable, inject } from '@angular/core';
import { Observable, forkJoin, map, switchMap } from 'rxjs';
import {
  ApiClient,
  BranchDetail,
  CompanyDetail,
  CompanyOption,
  DepartmentDetail,
  DepartmentOption,
  DesignationDetail,
  DesignationOption,
  EmployeeListItem,
  GradeDetail,
  HierarchyDetail,
  PageBranchListItem,
  PageCompanyListItem,
  PageDepartmentListItem,
  PageDesignationListItem,
  PageGradeListItem,
  PageHierarchyListItem,
  StateOption,
  createOrganizationBranch,
  createOrganizationCompany,
  createOrganizationDepartment,
  createOrganizationDesignation,
  createOrganizationGrade,
  createOrganizationHierarchyLink,
  getCustomerFormOptions,
  getOrganizationBranch,
  getOrganizationCompany,
  getOrganizationDepartment,
  getOrganizationDesignation,
  getOrganizationGrade,
  getOrganizationHierarchyMember,
  listCompanies,
  listDepartments,
  listDesignations,
  listEmployees,
  listOrganizationBranches,
  listOrganizationCompanies,
  listOrganizationDepartments,
  listOrganizationDesignations,
  listOrganizationGrades,
  listOrganizationHierarchy,
  renameOrganizationGrade,
  updateOrganizationBranch,
  updateOrganizationCompany,
  updateOrganizationDepartment,
  updateOrganizationDesignation,
  updateOrganizationHierarchy,
  withRowVersion,
} from '@trishul/core-api';
import type {
  BranchCreate,
  BranchUpdate,
  CompanyCreate,
  CompanyUpdate,
  DepartmentCreate,
  DepartmentUpdate,
  DesignationCreate,
  DesignationUpdate,
  GradeCreate,
  HierarchyCreate,
  HierarchyUpdate,
} from '@trishul/core-api';
import { OrgCounts, OrgQuery, OrgTabId } from './organization.models';

function params(query: OrgQuery): {
  page: number;
  pageSize: number;
  search?: string;
  status: OrgQuery['status'];
} {
  const search = query.search.trim();
  return {
    page: query.page,
    pageSize: query.pageSize,
    status: query.status,
    ...(search ? { search } : {}),
  };
}

/** /hr organization masters, plus the existing dropdown APIs those forms already use. */
@Injectable({ providedIn: 'root' })
export class OrganizationApi {
  private readonly api = inject(ApiClient);

  listDepartments(query: OrgQuery): Observable<PageDepartmentListItem> {
    return this.api.call(listOrganizationDepartments, params(query));
  }

  getDepartment(departmentId: number): Observable<DepartmentDetail> {
    return this.api.call(getOrganizationDepartment, { departmentId });
  }

  createDepartment(body: DepartmentCreate): Observable<DepartmentDetail> {
    return this.api.call(createOrganizationDepartment, { body });
  }

  updateDepartment(
    departmentId: number,
    rowVersion: string,
    body: DepartmentUpdate,
  ): Observable<DepartmentDetail> {
    return this.api.call(
      updateOrganizationDepartment,
      { departmentId, body },
      withRowVersion(rowVersion),
    );
  }

  listDesignations(query: OrgQuery): Observable<PageDesignationListItem> {
    return this.api.call(listOrganizationDesignations, params(query));
  }

  getDesignation(designationId: number): Observable<DesignationDetail> {
    return this.api.call(getOrganizationDesignation, { designationId });
  }

  createDesignation(body: DesignationCreate): Observable<DesignationDetail> {
    return this.api.call(createOrganizationDesignation, { body });
  }

  updateDesignation(
    designationId: number,
    rowVersion: string,
    body: DesignationUpdate,
  ): Observable<DesignationDetail> {
    return this.api.call(
      updateOrganizationDesignation,
      { designationId, body },
      withRowVersion(rowVersion),
    );
  }

  listGrades(query: OrgQuery): Observable<PageGradeListItem> {
    return this.api.call(listOrganizationGrades, params(query));
  }

  getGrade(grade: string): Observable<GradeDetail> {
    return this.api.call(getOrganizationGrade, { grade });
  }

  createGrade(body: GradeCreate): Observable<GradeDetail> {
    return this.api.call(createOrganizationGrade, { body });
  }

  renameGrade(grade: string, next: string): Observable<GradeDetail> {
    return this.api.call(renameOrganizationGrade, { grade, body: { grade: next } });
  }

  listBranches(query: OrgQuery): Observable<PageBranchListItem> {
    return this.api.call(listOrganizationBranches, params(query));
  }

  getBranch(branchId: number): Observable<BranchDetail> {
    return this.api.call(getOrganizationBranch, { branchId });
  }

  createBranch(body: BranchCreate): Observable<BranchDetail> {
    return this.api.call(createOrganizationBranch, { body });
  }

  updateBranch(
    branchId: number,
    rowVersion: string,
    body: BranchUpdate,
  ): Observable<BranchDetail> {
    return this.api.call(updateOrganizationBranch, { branchId, body }, withRowVersion(rowVersion));
  }

  listCompaniesPage(query: OrgQuery): Observable<PageCompanyListItem> {
    return this.api.call(listOrganizationCompanies, params(query));
  }

  getCompany(companyId: number): Observable<CompanyDetail> {
    return this.api.call(getOrganizationCompany, { companyId });
  }

  createCompany(body: CompanyCreate): Observable<CompanyDetail> {
    return this.api.call(createOrganizationCompany, { body });
  }

  updateCompany(
    companyId: number,
    rowVersion: string,
    body: CompanyUpdate,
  ): Observable<CompanyDetail> {
    return this.api.call(
      updateOrganizationCompany,
      { companyId, body },
      withRowVersion(rowVersion),
    );
  }

  listHierarchy(query: OrgQuery): Observable<PageHierarchyListItem> {
    return this.api.call(listOrganizationHierarchy, params(query));
  }

  getHierarchyMember(employeeId: number): Observable<HierarchyDetail> {
    return this.api.call(getOrganizationHierarchyMember, { employeeId });
  }

  createHierarchyLink(body: HierarchyCreate): Observable<HierarchyDetail> {
    return this.api.call(createOrganizationHierarchyLink, { body });
  }

  updateHierarchy(
    employeeId: number,
    rowVersion: string,
    body: HierarchyUpdate,
  ): Observable<HierarchyDetail> {
    return this.api.call(
      updateOrganizationHierarchy,
      { employeeId, body },
      withRowVersion(rowVersion),
    );
  }

  /** Reads the current row version, then sets is_active. Grades and hierarchy have no such flag here. */
  setActive(tab: OrgTabId, id: number, isActive: boolean): Observable<unknown> {
    switch (tab) {
      case 'departments':
        return this.getDepartment(id).pipe(
          switchMap((row) => this.updateDepartment(id, row.rowVersion, { isActive })),
        );
      case 'designations':
        return this.getDesignation(id).pipe(
          switchMap((row) => this.updateDesignation(id, row.rowVersion, { isActive })),
        );
      case 'locations':
        return this.getBranch(id).pipe(
          switchMap((row) => this.updateBranch(id, row.rowVersion, { isActive })),
        );
      case 'companies':
        return this.getCompany(id).pipe(
          switchMap((row) => this.updateCompany(id, row.rowVersion, { isActive })),
        );
      case 'grades':
      case 'hierarchy':
        throw new Error(`${tab} cannot be activated from Organization Management.`);
    }
  }

  /** Card totals ignore the table search and status filter. */
  counts(): Observable<OrgCounts> {
    const query: OrgQuery = { page: 1, pageSize: 1, search: '', status: 'all' };
    return forkJoin({
      departments: this.listDepartments(query),
      designations: this.listDesignations(query),
      grades: this.listGrades(query),
      locations: this.listBranches(query),
      hierarchy: this.listHierarchy(query),
    }).pipe(
      map((pages) => ({
        departments: pages.departments.total,
        designations: pages.designations.total,
        grades: pages.grades.total,
        locations: pages.locations.total,
        hierarchy: pages.hierarchy.total,
      })),
    );
  }

  departmentOptions(): Observable<DepartmentOption[]> {
    return this.api.call(listDepartments);
  }

  designationOptions(): Observable<DesignationOption[]> {
    return this.api.call(listDesignations);
  }

  companyOptions(): Observable<CompanyOption[]> {
    return this.api.call(listCompanies);
  }

  /** Active employees for department heads and reporting managers. */
  employeeOptions(): Observable<EmployeeListItem[]> {
    return this.api
      .call(listEmployees, { page: 1, pageSize: 200, status: 'active', sort: 'firstName' })
      .pipe(map((page) => page.items));
  }

  /** States from the customer form's master list. */
  stateOptions(): Observable<StateOption[]> {
    return this.api.call(getCustomerFormOptions).pipe(map((options) => options.states));
  }
}
