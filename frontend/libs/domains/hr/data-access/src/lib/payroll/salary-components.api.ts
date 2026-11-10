import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  PageSalaryComponentListItem,
  SalaryComponentDetail,
  SalaryComponentSummary,
  SalaryComponentUpdate,
  SalaryComponentWrite,
  createSalaryComponent,
  getSalaryComponent,
  listSalaryComponents,
  salaryComponentSummary,
  setSalaryComponentStatus,
  updateSalaryComponent,
  withRowVersion,
} from '@trishul/core-api';

export const SALARY_COMPONENT_MANAGE = [
  'hr.salary_component.manage',
  'core.employee.manage',
] as const;

export type ComponentType = SalaryComponentWrite['componentType'];
export type CalculationMethod = SalaryComponentWrite['calculationMethod'];
export type CalculationBasis = Exclude<SalaryComponentWrite['calculationBasis'], null | undefined>;
export type ComponentStatus = 'active' | 'inactive' | 'all';

export const COMPONENT_TYPES: readonly ComponentType[] = [
  'Earning',
  'Employee Deduction',
  'Employer Contribution',
  'Reimbursement',
  'Informational',
];

export const CALCULATION_METHODS: readonly CalculationMethod[] = [
  'Fixed Amount',
  'Percentage',
  'Formula',
  'Manual Entry',
];

export const BASIS_FOR_METHOD: Record<CalculationMethod, readonly CalculationBasis[]> = {
  'Fixed Amount': ['Fixed Monthly Amount', 'Attendance / Effective Workdays'],
  Percentage: ['Basic Salary', 'Gross Earnings', 'Eligible PF Wages', 'Eligible ESI Wages'],
  Formula: [
    'Basic Salary',
    'Gross Earnings',
    'Eligible PF Wages',
    'Eligible ESI Wages',
    'Attendance / Effective Workdays',
    'Custom Formula',
  ],
  'Manual Entry': [],
};

export interface SalaryComponentQuery {
  search: string;
  componentType: ComponentType | null;
  calculationMethod: CalculationMethod | null;
  status: ComponentStatus;
  page: number;
  pageSize: number;
}

/** Salary component master. The 14 opening components come from the database, not this client. */
@Injectable({ providedIn: 'root' })
export class SalaryComponentsApi {
  private readonly api = inject(ApiClient);

  summary(): Observable<SalaryComponentSummary> {
    return this.api.call(salaryComponentSummary);
  }

  list(query: SalaryComponentQuery): Observable<PageSalaryComponentListItem> {
    const search = query.search.trim();
    return this.api.call(listSalaryComponents, {
      page: query.page,
      pageSize: query.pageSize,
      sort: 'displayOrder',
      status: query.status,
      ...(search ? { search } : {}),
      ...(query.componentType ? { componentType: query.componentType } : {}),
      ...(query.calculationMethod ? { calculationMethod: query.calculationMethod } : {}),
    });
  }

  get(componentId: number): Observable<SalaryComponentDetail> {
    return this.api.call(getSalaryComponent, { componentId });
  }

  create(body: SalaryComponentWrite): Observable<SalaryComponentDetail> {
    return this.api.call(createSalaryComponent, { body });
  }

  update(
    componentId: number,
    rowVersion: string,
    body: SalaryComponentUpdate,
  ): Observable<SalaryComponentDetail> {
    return this.api.call(updateSalaryComponent, { componentId, body }, withRowVersion(rowVersion));
  }

  setStatus(
    componentId: number,
    rowVersion: string,
    isActive: boolean,
  ): Observable<SalaryComponentDetail> {
    return this.api.call(
      setSalaryComponentStatus,
      { componentId, body: { isActive } },
      withRowVersion(rowVersion),
    );
  }
}
