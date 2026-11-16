import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiConfiguration } from '@trishul/core-api';

export interface SalaryTemplateLine {
  salaryComponentId: number;
  code: string;
  name: string;
  componentType: string;
  calculationMethod: string;
  calculationBasis: string | null;
  monthlyAmount: string | null;
  percentage: string | null;
  formula: string | null;
  displayOrder: number;
  estimatedAmount: string | null;
}

export interface SalaryTemplateEmployee {
  employeeId: number;
  employeeCode: string;
  fullName: string;
  department: string | null;
  effectiveFrom: string;
  effectiveTo: string | null;
  monthlyGross: string;
}

export interface SalaryTemplateHistory {
  action: string;
  changedAt: string;
  changedBy: string | null;
  summary: string;
}

export interface NamedOption {
  id: number;
  name: string;
}

export interface SalaryTemplateSummary {
  total: number;
  active: number;
  inactive: number;
  assignedEmployees: number;
  departments: NamedOption[];
  designations: NamedOption[];
}

export interface SalaryTemplateListItem {
  id: number;
  code: string;
  name: string;
  description: string | null;
  employeeCategory: string | null;
  department: string | null;
  designation: string | null;
  designationIds: number[];
  grades: string[];
  assignedEmployees: number;
  isActive: boolean;
  rowVersion: string;
}

export interface SalaryTemplateDetail extends SalaryTemplateListItem {
  templateType: 'Monthly';
  departmentId: number | null;
  designationId: number | null;
  effectiveFrom: string;
  effectiveTo: string | null;
  monthlyGross: string;
  employeeDeductions: string;
  netSalary: string;
  employerContribution: string;
  annualCtc: string;
  lines: SalaryTemplateLine[];
  employees: SalaryTemplateEmployee[];
  history: SalaryTemplateHistory[];
}

export interface SalaryTemplateLineWrite {
  salaryComponentId: number;
  monthlyAmount?: string | null;
  percentage?: string | null;
  formula?: string | null;
  displayOrder: number;
}

export interface SalaryTemplateWrite {
  code: string;
  name: string;
  description?: string | null;
  templateType: 'Monthly';
  employeeCategory?: string | null;
  departmentId?: number | null;
  designationId?: number | null;
  designationIds?: number[];
  grades?: string[];
  effectiveFrom: string;
  effectiveTo?: string | null;
  isActive: boolean;
  lines: SalaryTemplateLineWrite[];
}

export interface SalaryTemplateQuery {
  search: string;
  status: 'all' | 'active' | 'inactive';
  departmentId: number | null;
  designationId: number | null;
  grade: string | null;
  employeeCategory: string | null;
  page: number;
  pageSize: number;
}

/** Saved salary packages. Payroll continues to use the employee salary structure. */
@Injectable({ providedIn: 'root' })
export class SalaryTemplatesApi {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  summary(): Observable<SalaryTemplateSummary> {
    return this.http.get<SalaryTemplateSummary>(`${this.config.rootUrl}/hr/salary-templates/summary`);
  }

  list(query: SalaryTemplateQuery): Observable<{ items: SalaryTemplateListItem[]; total: number }> {
    const params: Record<string, string> = {
      page: String(query.page),
      pageSize: String(query.pageSize),
      status: query.status,
    };
    const search = query.search.trim();
    if (search) params['search'] = search;
    if (query.departmentId != null) params['departmentId'] = String(query.departmentId);
    if (query.designationId != null) params['designationId'] = String(query.designationId);
    if (query.grade) params['grade'] = query.grade;
    if (query.employeeCategory) params['employeeCategory'] = query.employeeCategory;
    return this.http.get<{ items: SalaryTemplateListItem[]; total: number }>(
      `${this.config.rootUrl}/hr/salary-templates`,
      { params },
    );
  }

  get(id: number): Observable<SalaryTemplateDetail> {
    return this.http.get<SalaryTemplateDetail>(`${this.config.rootUrl}/hr/salary-templates/${id}`);
  }

  create(body: SalaryTemplateWrite): Observable<SalaryTemplateDetail> {
    return this.http.post<SalaryTemplateDetail>(`${this.config.rootUrl}/hr/salary-templates`, body);
  }

  update(id: number, rowVersion: string, body: SalaryTemplateWrite): Observable<SalaryTemplateDetail> {
    return this.http.patch<SalaryTemplateDetail>(`${this.config.rootUrl}/hr/salary-templates/${id}`, body, {
      headers: new HttpHeaders({ 'If-Match': `"${rowVersion}"` }),
    });
  }

  setStatus(id: number, rowVersion: string, isActive: boolean): Observable<SalaryTemplateDetail> {
    return this.http.patch<SalaryTemplateDetail>(
      `${this.config.rootUrl}/hr/salary-templates/${id}/status`,
      { isActive },
      { headers: new HttpHeaders({ 'If-Match': `"${rowVersion}"` }) },
    );
  }
}
