import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  PageSalaryStructureListItem,
  SalaryStructureDetail,
  SalaryStructureSummary,
  SalaryStructureWrite,
  createSalaryStructure,
  getSalaryStructure,
  listSalaryStructures,
  salaryStructureSummary,
  updateSalaryStructure,
  withRowVersion,
} from '@trishul/core-api';

export const SALARY_STRUCTURE_MANAGE = [
  'hr.salary_component.manage',
  'core.employee.manage',
] as const;

export type StructureAssignment = 'all' | 'assigned' | 'unassigned';

export interface SalaryStructureQuery {
  search: string;
  assignment: StructureAssignment;
  page: number;
  pageSize: number;
}

/** Employee salary structures. Lines use the salary components already saved. */
@Injectable({ providedIn: 'root' })
export class SalaryStructuresApi {
  private readonly api = inject(ApiClient);

  summary(): Observable<SalaryStructureSummary> {
    return this.api.call(salaryStructureSummary);
  }

  list(query: SalaryStructureQuery): Observable<PageSalaryStructureListItem> {
    const search = query.search.trim();
    return this.api.call(listSalaryStructures, {
      page: query.page,
      pageSize: query.pageSize,
      sort: 'employeeCode',
      assignment: query.assignment,
      ...(search ? { search } : {}),
    });
  }

  get(employeeId: number): Observable<SalaryStructureDetail> {
    return this.api.call(getSalaryStructure, { employeeId });
  }

  create(employeeId: number, body: SalaryStructureWrite): Observable<SalaryStructureDetail> {
    return this.api.call(createSalaryStructure, { employeeId, body });
  }

  update(
    employeeId: number,
    rowVersion: string,
    body: SalaryStructureWrite,
  ): Observable<SalaryStructureDetail> {
    return this.api.call(updateSalaryStructure, { employeeId, body }, withRowVersion(rowVersion));
  }
}
