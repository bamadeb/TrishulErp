import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  PageEmployeeListItem,
  activateEmployee,
  createEmployee,
  deactivateEmployee,
  getEmployee,
  listCompanies,
  listDepartments,
  listDesignations,
  listEmployees,
  updateEmployee,
  withRowVersion,
} from '@trishul/core-api';
import {
  CompanyOption,
  DepartmentOption,
  DesignationOption,
  EmployeeCreate,
  EmployeeDetail,
  EmployeeQuery,
  EmployeeUpdate,
} from './employees.models';

/** /core/employees and the form's option lists, through ApiClient and the generated functions. */
@Injectable({ providedIn: 'root' })
export class EmployeesApi {
  private readonly api = inject(ApiClient);

  list(query: EmployeeQuery): Observable<PageEmployeeListItem> {
    return this.api.call(listEmployees, query);
  }

  get(employeeId: number): Observable<EmployeeDetail> {
    return this.api.call(getEmployee, { employeeId });
  }

  create(body: EmployeeCreate): Observable<EmployeeDetail> {
    return this.api.call(createEmployee, { body });
  }

  /** rowVersion from when the employee was loaded; a newer change by someone else gives 409. */
  update(
    employeeId: number,
    rowVersion: string,
    body: EmployeeUpdate,
  ): Observable<EmployeeDetail> {
    return this.api.call(
      updateEmployee,
      { employeeId, body },
      withRowVersion(rowVersion),
    );
  }

  deactivate(employeeId: number): Observable<EmployeeDetail> {
    return this.api.call(deactivateEmployee, { employeeId });
  }

  activate(employeeId: number): Observable<EmployeeDetail> {
    return this.api.call(activateEmployee, { employeeId });
  }

  companies(): Observable<CompanyOption[]> {
    return this.api.call(listCompanies);
  }

  departments(): Observable<DepartmentOption[]> {
    return this.api.call(listDepartments);
  }

  designations(): Observable<DesignationOption[]> {
    return this.api.call(listDesignations);
  }
}
