import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiConfiguration, withRowVersion } from '@trishul/core-api';

export const STATUTORY_MANAGE = ['hr.salary_component.manage', 'core.employee.manage'] as const;

export type StatutoryScheme = 'PF' | 'ESI' | 'PT' | 'TDS';

export interface StatutorySchemeStatus {
  scheme: StatutoryScheme;
  name: string;
  configurationStatus: 'Configured' | 'Not configured';
  calculationStatus: 'Calculated' | 'Not calculated' | 'Not applicable';
  filingStatus: 'Not filed';
}

export interface StatutoryChoice {
  id: number;
  name: string;
}

export interface StatutorySummary {
  month: string;
  financialYear: string;
  eligibleEmployees: number;
  employeeContribution: string | null;
  employerContribution: string | null;
  totalLiability: string | null;
  configurationStatus: 'Configured' | 'Partial' | 'Not configured';
  calculationStatus: 'Calculated' | 'Not calculated' | 'Not applicable';
  filingStatus: 'Not filed';
  schemes: StatutorySchemeStatus[];
  states: StatutoryChoice[];
  departments: StatutoryChoice[];
}

export interface StatutoryRule {
  id: number;
  configType: StatutoryScheme | 'LWF';
  stateId: number | null;
  stateName: string | null;
  effectiveFrom: string;
  effectiveTo: string | null;
  employeeRate: string | null;
  employerRate: string | null;
  wageCeiling: string | null;
  slabJson: string | null;
  isActive: boolean;
  createdAt: string;
  createdBy: string | null;
  updatedAt: string | null;
  updatedBy: string | null;
  rowVersion: string;
}

export interface StatutoryRuleWrite {
  configType: StatutoryScheme;
  stateId: number | null;
  effectiveFrom: string;
  employeeRate: string | null;
  employerRate: string | null;
  wageCeiling: string | null;
  slabJson: string | null;
  isActive: boolean;
}

export interface StatutoryContribution {
  employeeId: number;
  employeeCode: string;
  fullName: string;
  department: string | null;
  location: string | null;
  applicableWages: string | null;
  employeeContribution: string | null;
  employerContribution: string | null;
  totalContribution: string | null;
  calculationStatus: 'Calculated' | 'Not calculated' | 'Not applicable';
  reason: string | null;
}

export interface StatutoryContributionPage {
  items: StatutoryContribution[];
  total: number;
  page: number;
  pageSize: number;
}

/** Statutory rules saved in hr.statutory_config, and the employees a month's payroll can cover. */
@Injectable({ providedIn: 'root' })
export class StatutoryApi {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  summary(month: string, scheme?: StatutoryScheme): Observable<StatutorySummary> {
    let params = new HttpParams().set('month', month);
    if (scheme) params = params.set('scheme', scheme);
    return this.http.get<StatutorySummary>(`${this.config.rootUrl}/hr/statutory/summary`, { params });
  }

  rules(scheme: StatutoryScheme): Observable<StatutoryRule[]> {
    return this.http.get<StatutoryRule[]>(`${this.config.rootUrl}/hr/statutory/rules`, { params: { scheme } });
  }

  create(body: StatutoryRuleWrite): Observable<StatutoryRule> {
    return this.http.post<StatutoryRule>(`${this.config.rootUrl}/hr/statutory/rules`, body);
  }

  update(ruleId: number, rowVersion: string, body: StatutoryRuleWrite): Observable<StatutoryRule> {
    return this.http.patch<StatutoryRule>(`${this.config.rootUrl}/hr/statutory/rules/${ruleId}`, body, {
      context: withRowVersion(rowVersion),
    });
  }

  contributions(query: {
    month: string;
    scheme: StatutoryScheme;
    search: string;
    departmentId: number | null;
    stateId: number | null;
    page: number;
    pageSize: number;
  }): Observable<StatutoryContributionPage> {
    let params = new HttpParams()
      .set('month', query.month)
      .set('scheme', query.scheme)
      .set('page', query.page)
      .set('pageSize', query.pageSize)
      .set('sort', 'employeeCode');
    const search = query.search.trim();
    if (search) params = params.set('search', search);
    if (query.departmentId != null) params = params.set('departmentId', query.departmentId);
    if (query.stateId != null) params = params.set('stateId', query.stateId);
    return this.http.get<StatutoryContributionPage>(`${this.config.rootUrl}/hr/statutory/contributions`, { params });
  }
}
