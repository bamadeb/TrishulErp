import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiConfiguration, withRowVersion } from '@trishul/core-api';

export const LEAVE_VIEW_PERMISSIONS = ['hr.leave.view', 'hr.leave.manage'] as const;
export const LEAVE_MANAGE_PERMISSION = 'hr.leave.manage';
/** The Leave Requests queue: approvers (team lead), HR, and employee-view roles as before. */
export const LEAVE_REQUEST_PERMISSIONS = [
  'hr.leave.approve',
  'hr.leave.manage',
  'core.employee.view',
  'core.employee.manage',
] as const;

export interface LeaveTypeItem {
  id: number;
  code: string;
  name: string;
  description: string | null;
  annualQuota: string | null;
  carryForwardMax: string | null;
  isPaid: boolean;
  isEncashable: boolean;
  accrualApplicable: boolean;
  halfDayAllowed: boolean;
  attachmentRequired: boolean;
  maxConsecutiveDays: number | null;
  isActive: boolean;
  rowVersion: string;
}

export interface LeaveTypeWrite {
  code: string;
  name: string;
  description?: string | null;
  annualQuota?: string | null;
  carryForwardMax?: string | null;
  isPaid: boolean;
  isEncashable: boolean;
  accrualApplicable: boolean;
  halfDayAllowed: boolean;
  attachmentRequired: boolean;
  maxConsecutiveDays?: number | null;
  isActive: boolean;
}

export type LeaveYearBasis = 'FINANCIAL' | 'CALENDAR';
export type LeaveAssignmentMode = 'AUTOMATIC' | 'EXPLICIT';
export type LeaveCalculationMethod = 'FIXED' | 'FORMULA' | 'ELIGIBILITY';
export type LeaveBenefitClass = 'STANDARD' | 'STATUTORY' | 'COMPANY';
export type LeaveCompensatoryBasis = 'NONE' | 'STATUTORY_WEEKLY_REST' | 'COMPANY_COMP_OFF';

export interface LeavePolicyLine {
  id: number;
  leaveTypeId: number;
  leaveTypeCode: string;
  leaveTypeName: string;
  annualEntitlement: string;
  accrualFrequency: 'None' | 'Monthly' | 'Yearly';
  carryForward: boolean;
  maxAccumulation: string | null;
  encashmentEligible: boolean;
  calculationMethod: LeaveCalculationMethod;
  creditDays: string | null;
  qualifyingDaysPerCredit: number | null;
  minimumQualifyingDays: number | null;
  joiningYearRule: 'NONE' | 'TWO_THIRDS_REMAINDER';
  minimumServiceMonths: number | null;
  adolescentMaxAccumulation: string | null;
  excludeBoundaryHolidays: boolean;
  documentRequired: boolean;
  benefitClass: LeaveBenefitClass;
  compensatoryBasis: LeaveCompensatoryBasis;
  compensatoryExpiryMonths: number | null;
  maxBackdateDays: number | null;
  backdateRequiresAuthorization: boolean;
  ruleSummary: string[];
}

export interface LeavePolicyItem {
  id: number;
  name: string;
  employeeType: string | null;
  departmentId: number | null;
  departmentName: string | null;
  branchId: number | null;
  branchName: string | null;
  stateId: number | null;
  stateName: string | null;
  yearBasis: LeaveYearBasis;
  assignmentMode: LeaveAssignmentMode;
  appliesDuringProbation: boolean;
  negativeBalanceAllowed: boolean;
  effectiveFrom: string;
  effectiveTo: string | null;
  isActive: boolean;
  lines: LeavePolicyLine[];
  rowVersion: string;
}

export interface LeaveDashboardQuery {
  year: number;
  month: number;
  departmentId?: number | null;
  leaveTypeId?: number | null;
  status?: string | null;
  upcoming?: boolean;
  search?: string | null;
  page: number;
  pageSize: number;
  sort?: string | null;
}

export interface LeaveRequestRow {
  requestId: number;
  employeeCode: string;
  employeeName: string;
  department: string | null;
  leaveType: string;
  fromDate: string;
  toDate: string;
  days: string;
  reason: string | null;
  status: string;
}

export interface LeaveDashboard {
  year: number;
  month: number;
  asOf: string;
  organisationWide: boolean;
  activeEmployees: number;
  onLeaveToday: number;
  pendingRequests: number;
  approvedRequests: number;
  rejectedRequests: number;
  upcomingLeaves: number;
  overview: { working: number; onLeave: number; pending: number };
  trend: { month: string; days: string }[];
  balances: { code: string; name: string; entitlement: string; used: string; closing: string }[];
  requests: { items: LeaveRequestRow[]; total: number; page: number; pageSize: number };
  mine: { balances: { code: string; name: string; closing: string }[]; requests: LeaveRequestRow[]; history: LeaveRequestRow[] };
  departmentOptions: { id: number; name: string }[];
  leaveTypeOptions: { id: number; name: string }[];
}

export interface LeavePolicyWrite {
  name: string;
  employeeType?: string | null;
  departmentId?: number | null;
  branchId?: number | null;
  stateId?: number | null;
  yearBasis?: LeaveYearBasis;
  assignmentMode?: LeaveAssignmentMode;
  appliesDuringProbation: boolean;
  negativeBalanceAllowed: boolean;
  effectiveFrom: string;
  effectiveTo?: string | null;
  isActive: boolean;
  lines: LeavePolicyLineWrite[];
}

export interface LeavePolicyLineWrite {
  leaveTypeId: number;
  annualEntitlement: string;
  accrualFrequency: 'None' | 'Monthly' | 'Yearly';
  carryForward: boolean;
  maxAccumulation?: string | null;
  encashmentEligible: boolean;
  calculationMethod?: LeaveCalculationMethod;
  creditDays?: string | null;
  qualifyingDaysPerCredit?: number | null;
  minimumQualifyingDays?: number | null;
  joiningYearRule?: 'NONE' | 'TWO_THIRDS_REMAINDER';
  minimumServiceMonths?: number | null;
  adolescentMaxAccumulation?: string | null;
  excludeBoundaryHolidays?: boolean;
  documentRequired?: boolean;
  benefitClass?: LeaveBenefitClass;
  compensatoryBasis?: LeaveCompensatoryBasis;
  compensatoryExpiryMonths?: number | null;
  maxBackdateDays?: number | null;
  backdateRequiresAuthorization?: boolean;
}

export interface LeaveAssignmentItem {
  id: number;
  leavePolicyId: number;
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  effectiveFrom: string;
  effectiveTo: string | null;
  isActive: boolean;
}

export interface LeaveAssignmentWrite {
  employeeId: number;
  effectiveFrom: string;
  effectiveTo?: string | null;
}

export interface AttendanceClassItem {
  attendanceStatus: string;
  configured: boolean;
}

export interface BalanceBucket {
  opening: string;
  credited: string;
  used: string;
  balance: string;
}

export interface BalanceEmployee {
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  department: string | null;
  designation: string | null;
  el: BalanceBucket;
  sl: BalanceBucket;
  cl: BalanceBucket;
  compOffBalance: string;
}

export interface BalanceBoard {
  year: number;
  policyId: number | null;
  policyName: string | null;
  warning: string | null;
  summary: { totalEmployees: number; withAssignedPolicy: number; entitlementGenerated: number; requiresReview: number };
  items: BalanceEmployee[];
  total: number;
  page: number;
  pageSize: number;
}

export interface BalanceDetail {
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  year: number;
  types: {
    code: string;
    name: string;
    leaveTypeId: number | null;
    opening: string;
    annualEntitlement: string | null;
    credited: string;
    consumed: string;
    adjustments: string;
    expired: string;
    closing: string;
  }[];
  transactions: { id: number; code: string; on: string; kind: string; days: string; reference: string | null; remarks: string | null }[];
  leaveHistory: { id: number; code: string; fromDate: string; toDate: string; days: string; status: string }[];
}

export interface EntitlementPreviewBoard {
  policyName: string;
  year: number;
  warning: string | null;
  employees: {
    employeeId: number;
    employeeCode: string;
    employeeName: string;
    requiresReview: boolean;
    lines: { code: string; credited: string; eligibilityDays: string | null; daysWorked: string | null; blocked: boolean; review: boolean; message: string | null }[];
  }[];
}

@Injectable({ providedIn: 'root' })
export class LeaveApi {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ApiConfiguration);

  types(search = ''): Observable<{ items: LeaveTypeItem[]; total: number }> {
    const params: Record<string, string> = { page: '1', pageSize: '100', status: 'all' };
    if (search.trim()) params['search'] = search.trim();
    return this.http.get<{ items: LeaveTypeItem[]; total: number }>(`${this.config.rootUrl}/hr/leave/types`, { params });
  }

  createType(body: LeaveTypeWrite): Observable<LeaveTypeItem> {
    return this.http.post<LeaveTypeItem>(`${this.config.rootUrl}/hr/leave/types`, body);
  }

  updateType(id: number, rowVersion: string, body: LeaveTypeWrite): Observable<LeaveTypeItem> {
    return this.http.patch<LeaveTypeItem>(`${this.config.rootUrl}/hr/leave/types/${id}`, body, {
      headers: new HttpHeaders({ 'If-Match': `"${rowVersion}"` }),
    });
  }

  balanceBoard(params: Record<string, string>): Observable<BalanceBoard> {
    return this.http.get<BalanceBoard>(`${this.config.rootUrl}/hr/leave/balances`, { params });
  }

  balanceDetail(employeeId: number, year: number): Observable<BalanceDetail> {
    return this.http.get<BalanceDetail>(`${this.config.rootUrl}/hr/leave/balances/${employeeId}`, { params: { year: String(year) } });
  }

  adjustBalance(employeeId: number, body: { leaveTypeId: number; year: number; days: string; reason: string }): Observable<BalanceDetail> {
    return this.http.post<BalanceDetail>(`${this.config.rootUrl}/hr/leave/balances/${employeeId}/adjustments`, body);
  }

  previewEntitlement(body: { policyId: number; year: number; generationType: string }): Observable<EntitlementPreviewBoard> {
    return this.http.post<EntitlementPreviewBoard>(`${this.config.rootUrl}/hr/leave/balances/entitlement-preview`, body);
  }

  generateEntitlements(body: { policyId: number; year: number; generationType: string }): Observable<{ creditedEmployees: number; skippedDuplicates: number; blocked: number }> {
    return this.http.post<{ creditedEmployees: number; skippedDuplicates: number; blocked: number }>(
      `${this.config.rootUrl}/hr/leave/balances/entitlements`, body,
    );
  }

  policies(status = 'all'): Observable<{ items: LeavePolicyItem[]; total: number }> {
    return this.http.get<{ items: LeavePolicyItem[]; total: number }>(`${this.config.rootUrl}/hr/leave/policies`, {
      params: { page: '1', pageSize: '100', status },
    });
  }

  attendanceClasses(): Observable<AttendanceClassItem[]> {
    return this.http.get<AttendanceClassItem[]>(`${this.config.rootUrl}/hr/leave/attendance-classes`);
  }

  createPolicy(body: LeavePolicyWrite): Observable<LeavePolicyItem> {
    return this.http.post<LeavePolicyItem>(`${this.config.rootUrl}/hr/leave/policies`, body);
  }

  dashboard(query: LeaveDashboardQuery): Observable<LeaveDashboard> {
    const params: Record<string, string> = {
      year: String(query.year),
      month: String(query.month),
      page: String(query.page),
      pageSize: String(query.pageSize),
    };
    if (query.departmentId != null) params['departmentId'] = String(query.departmentId);
    if (query.leaveTypeId != null) params['leaveTypeId'] = String(query.leaveTypeId);
    if (query.status) params['status'] = query.status;
    if (query.upcoming) params['upcoming'] = 'true';
    if (query.search?.trim()) params['search'] = query.search.trim();
    if (query.sort) params['sort'] = query.sort;
    return this.http.get<LeaveDashboard>(`${this.config.rootUrl}/hr/leave/dashboard`, { params });
  }

  assignments(policyId: number): Observable<LeaveAssignmentItem[]> {
    return this.http.get<LeaveAssignmentItem[]>(`${this.config.rootUrl}/hr/leave/policies/${policyId}/assignments`);
  }

  assignEmployee(policyId: number, body: LeaveAssignmentWrite): Observable<LeaveAssignmentItem> {
    return this.http.post<LeaveAssignmentItem>(`${this.config.rootUrl}/hr/leave/policies/${policyId}/assign`, body);
  }

  updatePolicy(id: number, rowVersion: string, body: LeavePolicyWrite): Observable<LeavePolicyItem> {
    return this.http.patch<LeavePolicyItem>(`${this.config.rootUrl}/hr/leave/policies/${id}`, body, {
      headers: new HttpHeaders({ 'If-Match': `"${rowVersion}"` }),
    });
  }

  mineProfile(): Observable<MineProfile> {
    return this.http.get<MineProfile>(`${this.config.rootUrl}/hr/leave/mine/profile`);
  }

  mineBalances(financialYear: number): Observable<MineBalances> {
    return this.http.get<MineBalances>(`${this.config.rootUrl}/hr/leave/mine/balances`, {
      params: { financialYear: String(financialYear) },
    });
  }

  compOffReports(): Observable<CompOffReport[]> {
    return this.http.get<CompOffReport[]>(`${this.config.rootUrl}/hr/leave/comp-off/reports`);
  }

  compOffAuthorizations(scope: 'mine' | 'team' = 'mine'): Observable<CompOffAuthorizationItem[]> {
    return this.http.get<CompOffAuthorizationItem[]>(`${this.config.rootUrl}/hr/leave/comp-off/authorizations`, {
      params: { scope },
    });
  }

  authorizeCompOff(body: { employeeId?: number | null; employeeCode?: string | null; workDate: string; remarks?: string | null }): Observable<CompOffAuthorizationItem> {
    return this.http.post<CompOffAuthorizationItem>(`${this.config.rootUrl}/hr/leave/comp-off/authorizations`, body);
  }

  mineCompOff(financialYear: number): Observable<MineCompOff> {
    return this.http.get<MineCompOff>(`${this.config.rootUrl}/hr/leave/mine/comp-off`, {
      params: { financialYear: String(financialYear) },
    });
  }

  mineHolidays(financialYear: number): Observable<MineHoliday[]> {
    return this.http.get<MineHoliday[]>(`${this.config.rootUrl}/hr/leave/mine/holidays`, {
      params: { financialYear: String(financialYear) },
    });
  }

  mineRequests(financialYear: number): Observable<MineRequestPage> {
    return this.http.get<MineRequestPage>(`${this.config.rootUrl}/hr/leave/mine/requests`, {
      params: { financialYear: String(financialYear), page: '1', pageSize: '200' },
    });
  }

  mineRequest(requestId: number): Observable<MineRequestDetail> {
    return this.http.get<MineRequestDetail>(`${this.config.rootUrl}/hr/leave/mine/requests/${requestId}`);
  }

  applyLeave(body: MineApply): Observable<MineRequestDetail> {
    return this.http.post<MineRequestDetail>(`${this.config.rootUrl}/hr/leave/mine/requests`, body);
  }

  previewLeaveDays(
    body: Omit<MineApply, 'reason' | 'contact'> & { excludeRequestId?: number | null },
  ): Observable<{ days: string }> {
    return this.http.post<{ days: string }>(`${this.config.rootUrl}/hr/leave/mine/day-count`, body);
  }

  updateMineRequest(requestId: number, body: MineApply): Observable<MineRequestDetail> {
    return this.http.patch<MineRequestDetail>(`${this.config.rootUrl}/hr/leave/mine/requests/${requestId}`, body);
  }

  cancelMineRequest(requestId: number): Observable<MineRequestDetail> {
    return this.http.post<MineRequestDetail>(`${this.config.rootUrl}/hr/leave/mine/requests/${requestId}/cancel`, {});
  }

  leaveRequestSummary(query: LeaveRequestFilterQuery): Observable<LeaveRequestSummary> {
    return this.http.get<LeaveRequestSummary>(`${this.config.rootUrl}/hr/leave/requests/summary`, {
      params: this.requestParams(query),
    });
  }

  leaveRequests(query: LeaveRequestListQuery): Observable<LeaveRequestPage> {
    return this.http.get<LeaveRequestPage>(`${this.config.rootUrl}/hr/leave/requests`, {
      params: this.requestParams(query),
    });
  }

  leaveRequest(requestId: number): Observable<LeaveRequestDetail> {
    return this.http.get<LeaveRequestDetail>(`${this.config.rootUrl}/hr/leave/requests/${requestId}`);
  }

  approveLeaveRequest(requestId: number): Observable<LeaveRequestDetail> {
    return this.http.post<LeaveRequestDetail>(`${this.config.rootUrl}/hr/leave/requests/${requestId}/approve`, {});
  }

  rejectLeaveRequest(requestId: number, remarks: string): Observable<LeaveRequestDetail> {
    return this.http.post<LeaveRequestDetail>(`${this.config.rootUrl}/hr/leave/requests/${requestId}/reject`, { remarks });
  }

  commentLeaveRequest(requestId: number, remarks: string): Observable<LeaveRequestDetail> {
    return this.http.post<LeaveRequestDetail>(`${this.config.rootUrl}/hr/leave/requests/${requestId}/comments`, { remarks });
  }

  employeeLeaveSummary(query: EmployeeLeaveQuery): Observable<EmployeeLeaveStats> {
    return this.http.get<EmployeeLeaveStats>(`${this.config.rootUrl}/hr/leave/employees/summary`, {
      params: this.employeeParams(query),
    });
  }

  employeeLeaves(query: EmployeeLeaveListQuery): Observable<EmployeeLeavePage> {
    return this.http.get<EmployeeLeavePage>(`${this.config.rootUrl}/hr/leave/employees`, {
      params: this.employeeParams(query),
    });
  }

  employeeLeaveExport(query: EmployeeLeaveQuery & { sort?: string }): Observable<EmployeeLeavePage> {
    return this.http.get<EmployeeLeavePage>(`${this.config.rootUrl}/hr/leave/employees/export`, {
      params: this.employeeParams(query),
    });
  }

  employeeLeave(employeeId: number, financialYear: number): Observable<EmployeeLeaveDetail> {
    return this.http.get<EmployeeLeaveDetail>(`${this.config.rootUrl}/hr/leave/employees/${employeeId}`, {
      params: { financialYear: String(financialYear) },
    });
  }

  leaveCalendar(query: LeaveCalendarQuery): Observable<LeaveCalendarBoard> {
    return this.http.get<LeaveCalendarBoard>(`${this.config.rootUrl}/hr/leave/calendar`, {
      params: this.calendarParams(query),
    });
  }

  private calendarParams(query: LeaveCalendarQuery): Record<string, string> {
    const params: Record<string, string> = { year: String(query.year), month: String(query.month) };
    if (query.departmentId != null) params['departmentId'] = String(query.departmentId);
    if (query.designationId != null) params['designationId'] = String(query.designationId);
    if (query.branchId != null) params['branchId'] = String(query.branchId);
    if (query.leaveTypeId != null) params['leaveTypeId'] = String(query.leaveTypeId);
    if (query.search) params['search'] = query.search;
    return params;
  }

  private employeeParams(query: EmployeeLeaveListQuery): Record<string, string> {
    const params: Record<string, string> = { financialYear: String(query.financialYear) };
    if (query.departmentId != null) params['departmentId'] = String(query.departmentId);
    if (query.designationId != null) params['designationId'] = String(query.designationId);
    if (query.branchId != null) params['branchId'] = String(query.branchId);
    if (query.search) params['search'] = query.search;
    if (query.page != null) params['page'] = String(query.page);
    if (query.pageSize != null) params['pageSize'] = String(query.pageSize);
    if (query.sort) params['sort'] = query.sort;
    return params;
  }

  private requestParams(query: LeaveRequestListQuery): Record<string, string> {
    const params: Record<string, string> = {};
    if (query.status) params['status'] = query.status;
    if (query.departmentId != null) params['departmentId'] = String(query.departmentId);
    if (query.leaveTypeId != null) params['leaveTypeId'] = String(query.leaveTypeId);
    if (query.fromDate) params['fromDate'] = query.fromDate;
    if (query.toDate) params['toDate'] = query.toDate;
    if (query.search) params['search'] = query.search;
    if (query.page != null) params['page'] = String(query.page);
    if (query.pageSize != null) params['pageSize'] = String(query.pageSize);
    return params;
  }

  holidayFilters(): Observable<HolidayFilters> {
    return this.http.get<HolidayFilters>(`${this.config.rootUrl}/hr/leave/holidays/filters`);
  }

  holidaySummary(query: HolidayQuery): Observable<HolidaySummary> {
    return this.http.get<HolidaySummary>(`${this.config.rootUrl}/hr/leave/holidays/summary`, {
      params: this.holidayParams(query),
    });
  }

  holidays(query: HolidayListQuery): Observable<HolidayPage> {
    return this.http.get<HolidayPage>(`${this.config.rootUrl}/hr/leave/holidays`, {
      params: this.holidayParams(query),
    });
  }

  holidayCalendar(query: HolidayCalendarQuery): Observable<HolidayItem[]> {
    return this.http.get<HolidayItem[]>(`${this.config.rootUrl}/hr/leave/holidays/calendar`, {
      params: this.holidayParams(query),
    });
  }

  createHoliday(body: HolidayWrite): Observable<HolidayItem> {
    return this.http.post<HolidayItem>(`${this.config.rootUrl}/hr/leave/holidays`, body);
  }

  updateHoliday(holidayId: number, rowVersion: string, body: HolidayWrite): Observable<HolidayItem> {
    return this.http.patch<HolidayItem>(`${this.config.rootUrl}/hr/leave/holidays/${holidayId}`, body, {
      context: withRowVersion(rowVersion),
    });
  }

  deleteHoliday(holidayId: number, rowVersion: string): Observable<void> {
    return this.http.delete<void>(`${this.config.rootUrl}/hr/leave/holidays/${holidayId}`, {
      context: withRowVersion(rowVersion),
    });
  }

  private holidayParams(query: HolidayQuery): Record<string, string> {
    const params: Record<string, string> = {};
    if (query.financialYear != null) params['financialYear'] = String(query.financialYear);
    if (query.calendarYear != null) params['calendarYear'] = String(query.calendarYear);
    if (query.holidayCategory) params['holidayCategory'] = query.holidayCategory;
    if (query.stateId != null) params['stateId'] = String(query.stateId);
    if (query.locationId != null) params['locationId'] = String(query.locationId);
    if (query.search) params['search'] = query.search;
    if (query.page != null) params['page'] = String(query.page);
    if (query.pageSize != null) params['pageSize'] = String(query.pageSize);
    if (query.sort) params['sort'] = query.sort;
    if (query.startDate) params['startDate'] = query.startDate;
    if (query.endDate) params['endDate'] = query.endDate;
    return params;
  }
}

export interface MineProfile {
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  department: string | null;
  designation: string | null;
  location: string | null;
  dateOfJoining: string | null;
  confirmationDate: string | null;
  employmentStatus: string;
}

export interface MineBalance {
  leaveTypeId: number;
  code: string;
  name: string;
  opening: string;
  credited: string;
  availed: string;
  pending: string;
  available: string;
  expired: string | null;
  maxBackdateDays?: number | null;
  backdateRequiresAuthorization?: boolean;
}

export interface MineBalances {
  financialYear: number;
  items: MineBalance[];
}

export interface MineCompOffLine {
  earnedOn: string;
  days: string;
  note: string;
  expires: string;
  status: string;
}

export interface MineCompOff {
  earned: string;
  available: string;
  used: string;
  expiring: string | null;
  expiryTracked: boolean;
  lines: MineCompOffLine[];
}

export interface CompOffReport {
  employeeId: number;
  employeeCode: string;
  employeeName: string;
}

export interface CompOffAuthorizationItem {
  id: number;
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  workDate: string;
  dayKind: string;
  status: string;
  remarks: string | null;
}

export interface MineHoliday {
  holidayDate: string;
  name: string;
  holidayType: string;
}

export interface MineRequestItem {
  requestId: number;
  displayId: string;
  leaveTypeId: number;
  leaveType: string;
  fromDate: string;
  toDate: string;
  days: string;
  reason: string | null;
  appliedAt: string;
  status: 'Pending' | 'Approved' | 'Rejected' | 'Cancelled';
  isHalfDay: boolean;
  approverUserId: number | null;
  actedAt: string | null;
  currentApprovalLevel: string | null;
  pendingWithName: string | null;
  pendingWithRole: string | null;
  needsHrAttention: boolean;
}

export interface MineRequestPage {
  items: MineRequestItem[];
  total: number;
  page: number;
  pageSize: number;
}

export interface MineApprovalStep {
  title: string;
  approverName: string | null;
  approverRole: string | null;
  level: string | null;
  status: 'Submitted' | 'Pending' | 'Approved' | 'Rejected' | 'Upcoming' | 'Cancelled';
  actedAt: string | null;
  comments: string | null;
}

export interface MineRequestDetail extends MineRequestItem {
  history: { fromStatus: string | null; toStatus: string; changedAt: string; remarks: string | null }[];
  approvalSteps: MineApprovalStep[];
}

export interface MineApply {
  leaveTypeId: number;
  fromDate: string;
  toDate: string;
  isHalfDay: boolean;
  halfDayPart?: 'First half' | 'Second half' | null;
  reason: string;
  contact?: string | null;
}

export interface LeaveOption {
  id: number;
  name: string;
}

export interface LeaveRequestFilterQuery {
  departmentId?: number | null;
  leaveTypeId?: number | null;
  fromDate?: string | null;
  toDate?: string | null;
  search?: string | null;
}

export interface LeaveRequestListQuery extends LeaveRequestFilterQuery {
  status?: 'Pending' | 'Approved' | 'Rejected';
  page?: number;
  pageSize?: number;
}

export interface LeaveRequestSummary {
  pending: number;
  approved: number;
  rejected: number;
  total: number;
  departments: LeaveOption[];
  leaveTypes: LeaveOption[];
}

export interface LeaveRequestEmployee {
  code: string;
  name: string;
  department: string | null;
  designation: string | null;
  location: string | null;
  manager: string | null;
}

export interface LeaveRequestRow {
  requestId: number;
  displayId: string;
  employee: LeaveRequestEmployee;
  leaveTypeId: number;
  leaveType: string;
  leaveCode: string;
  fromDate: string;
  toDate: string;
  isHalfDay: boolean;
  days: string;
  reason: string | null;
  appliedOn: string;
  status: string;
  balance: string | null;
  canApprove: boolean;
}

export interface LeaveHistoryEvent {
  id: number;
  action: string;
  actor: string;
  at: string;
  remarks: string;
}

export interface LeaveRequestDetail extends LeaveRequestRow {
  approverUserId: number | null;
  actedAt: string | null;
  history: LeaveHistoryEvent[];
  comments: string[];
}

export interface LeaveRequestPage {
  items: LeaveRequestRow[];
  total: number;
  page: number;
  pageSize: number;
}

export interface EmployeeLeaveQuery {
  financialYear: number;
  departmentId?: number | null;
  designationId?: number | null;
  branchId?: number | null;
  search?: string | null;
  sort?: string;
}

export interface EmployeeLeaveListQuery extends EmployeeLeaveQuery {
  page?: number;
  pageSize?: number;
}

export interface EmployeeLeaveOption {
  id: number;
  name: string;
}

export interface EmployeeLeaveStats {
  employees: number;
  onLeave: number;
  upcoming: number;
  taken: string;
  departments: EmployeeLeaveOption[];
  designations: EmployeeLeaveOption[];
  locations: EmployeeLeaveOption[];
}

export interface EmployeeLeaveSpan {
  requestId: number;
  displayId: string;
  leaveCode: string;
  fromDate: string;
  toDate: string;
  days: string;
}

export interface EmployeeLeaveBalanceView {
  opening: string;
  credited: string;
  consumed: string;
  adjustments: string;
  expired: string;
  closing: string;
  nextExpiry?: string | null;
}

export interface EmployeeLeaveRow {
  employeeId: number;
  code: string;
  name: string;
  department: string | null;
  designation: string | null;
  location: string | null;
  status: string;
  dateOfJoining: string | null;
  cl: string;
  el: string;
  sl: string;
  co: string;
  taken: string;
  upcoming: EmployeeLeaveSpan | null;
  onLeaveToday: boolean;
}

export interface EmployeeLeaveHistoryItem {
  requestId: number;
  displayId: string;
  leaveCode: string;
  leaveType: string;
  fromDate: string;
  toDate: string;
  days: string;
  status: string;
  approvedBy: string | null;
}

export interface EmployeeLeaveDetail extends EmployeeLeaveRow {
  lastLeave: EmployeeLeaveSpan | null;
  balances: Record<string, EmployeeLeaveBalanceView>;
  history: EmployeeLeaveHistoryItem[];
}

export interface EmployeeLeavePage {
  items: EmployeeLeaveRow[];
  total: number;
  page: number;
  pageSize: number;
}

export interface LeaveCalendarQuery {
  year: number;
  month: number;
  departmentId?: number | null;
  designationId?: number | null;
  branchId?: number | null;
  leaveTypeId?: number | null;
  search?: string;
}

export interface LeaveCalendarSummary {
  totalEmployees: number;
  onLeaveToday: number;
  onLeavePercent: string;
  pendingApproval: number;
  approvedMtd: number;
  rejectedMtd: number;
  upcomingLeaves: number;
}

export interface LeaveCalendarEmployee {
  employeeId: number;
  code: string;
  name: string;
  department: string | null;
  designation: string | null;
  location: string | null;
  status: string;
}

export interface LeaveCalendarTypeOption {
  id: number;
  code: string;
  name: string;
}

export interface LeaveCalendarEntry {
  requestId: number;
  displayId: string;
  employee: LeaveCalendarEmployee;
  leaveCode: string;
  leaveType: string;
  fromDate: string;
  toDate: string;
  days: string;
  status: string;
  reason: string | null;
  approvedBy: string | null;
}

export interface LeaveCalendarHoliday {
  holidayDate: string;
  name: string;
}

export type HolidayCategory = 'National' | 'Festival' | 'Regional' | 'Optional';

export interface HolidayQuery {
  financialYear?: number | null;
  calendarYear?: number | null;
  holidayCategory?: HolidayCategory | null;
  stateId?: number | null;
  locationId?: number | null;
  search?: string;
  page?: number;
  pageSize?: number;
  sort?: string;
  startDate?: string;
  endDate?: string;
}

export interface HolidayListQuery extends HolidayQuery {
  page: number;
  pageSize: number;
}

export interface HolidayCalendarQuery extends HolidayQuery {
  startDate: string;
  endDate: string;
}

export interface HolidayWrite {
  name: string;
  holidayDate: string;
  category: HolidayCategory;
  stateId?: number | null;
  locationId?: number | null;
  description?: string | null;
  isActive: boolean;
}

export interface HolidayItem {
  id: number;
  name: string;
  holidayDate: string;
  day: string;
  category: HolidayCategory;
  stateId: number | null;
  stateName: string | null;
  locationId: number | null;
  locationName: string;
  description: string | null;
  optional: boolean;
  isActive: boolean;
  sourceNotificationNo: string | null;
  sourceNotificationDate: string | null;
  rowVersion: string;
}

export interface HolidaySummary {
  total: number;
  upcoming: number;
  national: number;
  festival: number;
  regional: number;
  optional: number;
}

export interface HolidayPage {
  items: HolidayItem[];
  total: number;
  page: number;
  pageSize: number;
}

export interface HolidayOption {
  id: number;
  name: string;
  stateId?: number | null;
}

export interface HolidayFilters {
  categories: { id: HolidayCategory; name: string }[];
  states: HolidayOption[];
  locations: HolidayOption[];
  financialYears: number[];
  policyFestivals: string[];
}

export interface LeaveCalendarBoard {
  summary: LeaveCalendarSummary;
  entries: LeaveCalendarEntry[];
  holidays: LeaveCalendarHoliday[];
  departments: EmployeeLeaveOption[];
  designations: EmployeeLeaveOption[];
  locations: EmployeeLeaveOption[];
  leaveTypes: LeaveCalendarTypeOption[];
}
