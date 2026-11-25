import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { RouterLink } from '@angular/router';
import {
  AttendanceApi,
  EmployeeCounts,
  EmployeeListItem,
  AttendanceDashboard,
  AttendanceExceptionRow,
  EmployeesApi,
  HolidayItem,
  LeaveApi,
  LeaveRequestRow,
  PayrollRunItem,
  PayrollRunsApi,
  RegularizationRow,
  ApprovalRequest,
  ApprovalStatus,
  approvalStatusFilters,
  approvalStatusSeverity,
} from '@trishul/hr-data-access';
import { PageHeader, StatusBadge, confirmAction } from '@trishul/shared-ui';
import { Observable, catchError, forkJoin, map, of, switchMap } from 'rxjs';
import { HrApprovalDetailDialog } from './hr-approval-detail.dialog';

type SortKey = 'employeeName' | 'requestType' | 'submittedOn' | 'status';
type SortDir = 'asc' | 'desc';
type ViewState = 'ready' | 'loading' | 'error';

interface DashboardApproval extends ApprovalRequest {
  source: 'leave' | 'regularization';
  recordId: number;
}

interface PayrollCard {
  period: string;
  from: string;
  to: string;
  status: string;
  note: string;
  tasks: { label: string; state: string }[];
}

interface GapRow {
  id: number;
  employeeName: string;
  gap: string;
  department: string;
  branch: string;
}

interface CelebrationRow {
  employeeName: string;
  kind: 'Birthday' | 'Work anniversary';
  detail: string;
  dateLabel: string;
  branch: string;
  department: string;
}

interface ActivityRow {
  id: string;
  description: string;
  whenLabel: string;
}

const STATUS_RANK: Record<string, number> = { Pending: 0, Approved: 1, Rejected: 2 };
const EMPTY_PAYROLL: PayrollCard = {
  period: '—',
  from: '—',
  to: '—',
  status: 'No payroll run',
  note: 'No processed payroll month is stored.',
  tasks: [],
};

/** HR command center. Figures come from the employee, attendance, leave, holiday and payroll APIs. */
@Component({
  selector: 'trishul-hr-dashboard-page',
  imports: [
    RouterLink,
    MatButton,
    MatFormField,
    MatLabel,
    MatSelect,
    MatOption,
    MatIcon,
    MatProgressBar,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './hr-dashboard.page.html',
  styleUrl: './hr-dashboard.page.scss',
})
export class HrDashboardPage implements OnInit {
  private readonly attendanceApi = inject(AttendanceApi);
  private readonly employeesApi = inject(EmployeesApi);
  private readonly leaveApi = inject(LeaveApi);
  private readonly payrollApi = inject(PayrollRunsApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly approvalStatuses = approvalStatusFilters;
  protected readonly severity = {
    ...approvalStatusSeverity,
    Draft: 'neutral' as const,
    Processed: 'success' as const,
    Paid: 'success' as const,
    Locked: 'neutral' as const,
    'No payroll run': 'neutral' as const,
  };
  protected readonly dates = recentDates(14);

  protected readonly viewState = signal<ViewState>('loading');
  protected readonly loadError = signal<string | null>(null);
  protected readonly selectedDate = signal(indiaToday());
  protected readonly sampleBranch = signal('All');
  protected readonly department = signal('All');
  protected readonly approvalStatus = signal<(typeof approvalStatusFilters)[number]>('All');
  protected readonly requestType = signal('All');
  protected readonly sortKey = signal<SortKey>('submittedOn');
  protected readonly sortDir = signal<SortDir>('desc');

  private readonly employees = signal<EmployeeListItem[]>([]);
  private readonly employeeCounts = signal<EmployeeCounts | null>(null);
  private readonly attendancePage = signal<AttendanceDashboard | null>(null);
  protected readonly approvals = signal<DashboardApproval[]>([]);
  protected readonly gaps = signal<GapRow[]>([]);
  protected readonly holidays = signal<{ name: string; type: string; dateLabel: string }[]>([]);
  protected readonly activities = signal<ActivityRow[]>([]);
  protected readonly payroll = signal<PayrollCard>(EMPTY_PAYROLL);
  protected readonly quickActions = signal<{ label: string; icon: string; route: string }[]>([]);

  protected readonly branches = computed(() => [
    'All',
    ...uniqueSorted(this.employees().map((row) => row.branchName || '').filter(Boolean)),
  ]);
  protected readonly departments = computed(() => [
    'All',
    ...uniqueSorted(this.employees().map((row) => row.department || '').filter(Boolean)),
  ]);
  protected readonly requestTypes = computed(() => [
    'All',
    ...uniqueSorted(this.approvals().map((row) => row.requestType)),
  ]);
  protected readonly dateLabel = computed(
    () => this.dates.find((day) => day.date === this.selectedDate())?.label ?? this.selectedDate(),
  );
  protected readonly scopeLabel = computed(() => {
    const branch = this.sampleBranch() === 'All' ? 'all locations' : this.sampleBranch();
    const department = this.department() === 'All' ? 'all departments' : this.department();
    return `${branch} · ${department} · ${this.dateLabel()}`;
  });
  protected readonly scopedEmployees = computed(() =>
    this.employees().filter(
      (row) =>
        (this.sampleBranch() === 'All' || (row.branchName || '') === this.sampleBranch()) &&
        (this.department() === 'All' || (row.department || '') === this.department()),
    ),
  );
  protected readonly headcountTotal = computed(() => {
    if (this.sampleBranch() === 'All' && this.department() === 'All') {
      return this.employeeCounts()?.allEmployees ?? this.employees().length;
    }
    return this.scopedEmployees().length;
  });
  protected readonly attendance = computed(() => {
    const page = this.attendancePage();
    if (!page) return null;
    return {
      headcount: page.kpi.total,
      present: page.kpi.present,
      absent: page.kpi.absent,
      onLeave: page.kpi.onLeave ?? 0,
    };
  });
  protected readonly attendanceShare = computed(() => {
    const day = this.attendance();
    return day ? formatShare(day.present, day.headcount) : '0%';
  });
  protected readonly attendanceTone = computed(() => {
    const day = this.attendance();
    if (!day || day.headcount === 0) return 'Below';
    const ratio = day.present / day.headcount;
    if (ratio >= 0.9) return 'On track';
    if (ratio >= 0.75) return 'Watch';
    return 'Below';
  });
  protected readonly pendingCount = computed(
    () => this.approvals().filter((row) => row.status === 'Pending').length,
  );
  protected readonly summaryCards = computed(() => {
    const day = this.attendance();
    const present = day?.present ?? 0;
    const absent = day?.absent ?? 0;
    const onLeave = day?.onLeave ?? 0;
    const payroll = this.payroll();
    return [
      {
        label: 'Total Employees',
        value: String(this.headcountTotal()),
        description: `Employee records for ${this.scopeLabel()}`,
        icon: 'groups',
        tone: 'Clear',
        route: '/hr/employees',
        fragment: undefined as string | undefined,
      },
      {
        label: 'Present Today',
        value: String(present),
        description: `${this.attendanceShare()} of the roster marked present`,
        icon: 'how_to_reg',
        tone: this.attendanceTone(),
        route: '/hr/attendance/daily',
        fragment: undefined as string | undefined,
      },
      {
        label: 'Absent Today',
        value: String(absent),
        description: absent === 0 ? 'No absences for this selection' : 'Absent on the selected date',
        icon: 'person_off',
        tone: absent > 0 ? 'Watch' : 'Clear',
        route: '/hr/attendance/daily',
        fragment: undefined as string | undefined,
      },
      {
        label: 'On Leave',
        value: String(onLeave),
        description: 'Approved leave covering the selected date',
        icon: 'event_busy',
        tone: onLeave > 0 ? 'Watch' : 'Clear',
        route: '/hr/leave',
        fragment: undefined as string | undefined,
      },
      {
        label: 'Pending Approvals',
        value: String(this.pendingCount()),
        description: 'Leave requests and attendance regularizations waiting for a decision',
        icon: 'pending_actions',
        tone: this.pendingCount() > 0 ? 'Open' : 'Clear',
        route: '/hr/dashboard',
        fragment: 'approvals',
      },
      {
        label: 'Payroll Status',
        value: payroll.status,
        description: payroll.note,
        icon: 'payments',
        tone: payroll.status === 'No payroll run' ? 'Not started' : payroll.status,
        route: '/hr/payroll',
        fragment: undefined as string | undefined,
      },
    ];
  });
  protected readonly departmentRows = computed(() => {
    const branch = this.sampleBranch();
    const rows = this.employees().filter(
      (row) => branch === 'All' || (row.branchName || '') === branch,
    );
    return shareRows(
      countBy(rows, (row) => row.department || '—'),
      this.department(),
    );
  });
  protected readonly locationRows = computed(() => {
    const department = this.department();
    const rows = this.employees().filter(
      (row) => department === 'All' || (row.department || '') === department,
    );
    return shareRows(
      countBy(rows, (row) => row.branchName || '—'),
      this.sampleBranch(),
    );
  });
  protected readonly employmentRows = computed(() => {
    const counts = this.employeeCounts();
    const unfiltered = this.sampleBranch() === 'All' && this.department() === 'All' && counts;
    const active = unfiltered
      ? counts.active
      : this.scopedEmployees().filter((row) => row.isActive && row.status === 'Active' && isConfirmed(row)).length;
    const probation = unfiltered
      ? counts.probation
      : this.scopedEmployees().filter((row) => row.isActive && row.status === 'Active' && !isConfirmed(row)).length;
    const onNotice = unfiltered
      ? counts.notice
      : this.scopedEmployees().filter((row) => row.status === 'Notice').length;
    const whole = active + probation + onNotice;
    return [
      { label: 'Active', count: active },
      { label: 'Probation', count: probation },
      { label: 'On notice', count: onNotice },
    ].map((row) => ({
      ...row,
      percentLabel: formatShare(row.count, whole),
      percent: whole === 0 ? 0 : (row.count / whole) * 100,
    }));
  });
  protected readonly trend = computed(() => {
    const rows = (this.attendancePage()?.trend ?? []).map((day) => ({
      date: day.date,
      label: day.label,
      present: day.present ?? 0,
      absent: day.absent ?? 0,
      onLeave: day.onLeave ?? 0,
    }));
    const peak = Math.max(1, ...rows.flatMap((row) => [row.present, row.absent, row.onLeave]));
    return rows.map((row) => ({
      ...row,
      presentHeight: barHeight(row.present, peak),
      absentHeight: barHeight(row.absent, peak),
      leaveHeight: barHeight(row.onLeave, peak),
    }));
  });
  protected readonly visibleCelebrations = computed(() => celebrationsFor(this.scopedEmployees()));
  protected readonly visibleActivities = computed(() => this.activities());
  protected readonly approvalRows = computed(() => {
    const status = this.approvalStatus();
    const type = this.requestType();
    const rows = this.approvals().filter((row) => {
      const statusOk = status === 'All' || row.status === status;
      const typeOk = type === 'All' || row.requestType === type;
      const scopeOk =
        (this.sampleBranch() === 'All' || row.branch === this.sampleBranch()) &&
        (this.department() === 'All' || row.department === this.department());
      return statusOk && typeOk && scopeOk;
    });
    const dir = this.sortDir() === 'asc' ? 1 : -1;
    const key = this.sortKey();
    return [...rows].sort((a, b) => dir * compareApprovals(a, b, key));
  });

  ngOnInit(): void {
    this.reload();
  }

  protected setSampleBranch(branch: string): void {
    this.sampleBranch.set(branch);
    this.reload();
  }

  protected setDepartment(department: string): void {
    this.department.set(department);
    this.reload();
  }

  protected setDate(date: string): void {
    this.selectedDate.set(date);
    this.reload();
  }

  protected sort(key: SortKey): void {
    if (this.sortKey() === key) {
      this.sortDir.update((dir) => (dir === 'asc' ? 'desc' : 'asc'));
      return;
    }
    this.sortKey.set(key);
    this.sortDir.set(key === 'submittedOn' ? 'desc' : 'asc');
  }

  protected sortMarker(key: SortKey): string {
    if (this.sortKey() !== key) return '';
    return this.sortDir() === 'asc' ? 'ascending' : 'descending';
  }

  protected view(request: ApprovalRequest): void {
    this.dialog.open(HrApprovalDetailDialog, {
      data: request,
      width: '32rem',
      autoFocus: 'dialog',
    });
  }

  protected decide(request: DashboardApproval, status: Extract<ApprovalStatus, 'Approved' | 'Rejected'>): void {
    if (request.status !== 'Pending') return;
    confirmAction(this.dialog, {
      title: status === 'Approved' ? 'Approve this request?' : 'Reject this request?',
      message: `${request.employeeName}'s ${request.requestType.toLowerCase()} will be marked ${status}.`,
      confirmText: status === 'Approved' ? 'Approve' : 'Reject',
      destructive: status === 'Rejected',
    })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((confirmed) => {
        if (!confirmed) return;
        const call: Observable<unknown> =
          request.source === 'leave'
            ? status === 'Approved'
              ? this.leaveApi.approveLeaveRequest(request.recordId)
              : this.leaveApi.rejectLeaveRequest(request.recordId, 'Rejected from the HR dashboard')
            : status === 'Approved'
              ? this.attendanceApi.approveRegularization(request.recordId)
              : this.attendanceApi.rejectRegularization(request.recordId, 'Rejected from the HR dashboard');
        call.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
          next: () => {
            this.snackBar.open(`${request.employeeName} marked ${status}.`, 'OK', { duration: 3000 });
            this.reload();
          },
          error: (err: unknown) =>
            this.snackBar.open(httpMessage(err, 'The request could not be updated.'), 'OK', { duration: 4000 }),
        });
      });
  }

  protected reload(): void {
    const day = this.selectedDate();
    const department = this.department() === 'All' ? undefined : this.department();
    const location = this.sampleBranch() === 'All' ? undefined : this.sampleBranch();
    const from = shiftIso(day, -30);
    this.viewState.set('loading');
    this.loadError.set(null);
    forkJoin({
      employees: this.loadEmployees(),
      attendance: this.attendanceApi.dashboard(day, department, location),
      leave: this.leaveApi.leaveRequests({ status: 'Pending', page: 1, pageSize: 100 }).pipe(
        catchError(() => of({ items: [] as LeaveRequestRow[], total: 0, page: 1, pageSize: 100 })),
      ),
      regs: this.attendanceApi
        .listRegularizations({
          from,
          to: day,
          statusTab: 'pending',
          page: 1,
          pageSize: 100,
          department,
          location,
        })
        .pipe(catchError(() => of(null))),
      gaps: this.attendanceApi
        .listExceptions({
          from: day,
          to: day,
          statusTab: 'pending',
          page: 1,
          pageSize: 50,
          department,
          location,
        })
        .pipe(catchError(() => of(null))),
      holidays: this.leaveApi
        .holidayCalendar({ startDate: day, endDate: shiftIso(day, 120) })
        .pipe(catchError(() => of([] as HolidayItem[]))),
      payroll: this.payrollApi.list().pipe(catchError(() => of([] as PayrollRunItem[]))),
      recentLeave: this.leaveApi
        .leaveRequests({ page: 1, pageSize: 15 })
        .pipe(catchError(() => of({ items: [] as LeaveRequestRow[], total: 0, page: 1, pageSize: 15 }))),
      recentRegs: this.attendanceApi
        .listRegularizations({ from, to: day, statusTab: 'all', page: 1, pageSize: 15 })
        .pipe(catchError(() => of(null))),
    })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result) => {
          this.employees.set(result.employees.items);
          this.employeeCounts.set(result.employees.counts);
          this.attendancePage.set(result.attendance);
          this.approvals.set([
            ...result.leave.items.map(leaveApproval),
            ...(result.regs?.items ?? []).map(regularizationApproval),
          ]);
          this.gaps.set((result.gaps?.items ?? []).map(gapRow));
          this.holidays.set(
            [...result.holidays]
              .sort((a, b) => a.holidayDate.localeCompare(b.holidayDate))
              .slice(0, 8)
              .map((row) => ({
                name: row.name,
                type: row.category,
                dateLabel: formatIso(row.holidayDate),
              })),
          );
          this.payroll.set(payrollCard(result.payroll));
          this.activities.set(activitiesFrom(result.recentLeave.items, result.recentRegs?.items ?? []));
          this.quickActions.set(
            result.attendance.actions.map((action) => ({
              label: action.label,
              icon: action.icon,
              route: action.route,
            })),
          );
          this.viewState.set('ready');
        },
        error: (err: unknown) => {
          this.loadError.set(httpMessage(err, 'The HR dashboard could not be loaded.'));
          this.viewState.set('error');
        },
      });
  }

  private loadEmployees(): Observable<{ items: EmployeeListItem[]; counts: EmployeeCounts }> {
    const query = { page: 1, pageSize: 200, sort: 'firstName', status: 'all' as const };
    return this.employeesApi.list(query).pipe(
      switchMap((first) => {
        const pages = Math.ceil(first.total / Math.max(first.pageSize, 1));
        if (pages <= 1) return of(first);
        return forkJoin(
          Array.from({ length: pages - 1 }, (_, index) =>
            this.employeesApi.list({ ...query, page: index + 2 }),
          ),
        ).pipe(map((rest) => ({ ...first, items: [first.items, ...rest.map((page) => page.items)].flat() })));
      }),
    );
  }
}

function leaveApproval(row: LeaveRequestRow): DashboardApproval {
  return {
    id: `leave-${row.requestId}`,
    recordId: row.requestId,
    source: 'leave',
    employeeName: row.employee.name,
    requestType: row.leaveType || 'Leave',
    submittedOn: row.appliedOn,
    submittedLabel: formatIso(row.appliedOn.slice(0, 10)),
    status: approvalStatus(row.status),
    priority: 'Medium',
    branch: row.employee.location || '—',
    department: row.employee.department || '—',
    detail: `${row.fromDate} to ${row.toDate} · ${row.days} day(s). ${row.reason || ''}`.trim(),
  };
}

function regularizationApproval(row: RegularizationRow): DashboardApproval {
  return {
    id: `reg-${row.id}`,
    recordId: row.id,
    source: 'regularization',
    employeeName: row.employeeName,
    requestType: row.requestType,
    submittedOn: row.submittedOn,
    submittedLabel: formatIso(row.submittedOn.slice(0, 10)),
    status: row.status,
    priority: 'Medium',
    branch: row.location || '—',
    department: row.department || '—',
    detail: row.reason,
  };
}

function gapRow(row: AttendanceExceptionRow): GapRow {
  return {
    id: row.id,
    employeeName: row.employeeName,
    gap: row.exceptionType,
    department: row.department,
    branch: row.location,
  };
}

function payrollCard(runs: PayrollRunItem[]): PayrollCard {
  const latest = [...runs].sort((a, b) => b.periodMonth.localeCompare(a.periodMonth))[0];
  if (!latest) return EMPTY_PAYROLL;
  return {
    period: latest.periodMonth,
    from: latest.runDate,
    to: latest.status,
    status: latest.status,
    note: `${latest.employees} employees · net ${latest.netPay}`,
    tasks: [
      { label: 'Gross', state: latest.gross },
      { label: 'Deductions', state: latest.deductions },
      { label: 'Net pay', state: latest.netPay },
    ],
  };
}

function activitiesFrom(leave: LeaveRequestRow[], regs: RegularizationRow[]): ActivityRow[] {
  const rows: (ActivityRow & { sort: string })[] = [
    ...leave.map((row) => ({
      id: `leave-${row.requestId}`,
      description: `${row.employee.name}'s ${row.leaveType} is ${row.status}.`,
      whenLabel: formatIso(row.appliedOn.slice(0, 10)),
      sort: row.appliedOn,
    })),
    ...regs.map((row) => ({
      id: `reg-${row.id}`,
      description: `${row.employeeName}'s ${row.requestType} is ${row.status}.`,
      whenLabel: formatIso(row.submittedOn.slice(0, 10)),
      sort: row.submittedOn,
    })),
  ];
  return rows
    .sort((a, b) => b.sort.localeCompare(a.sort))
    .slice(0, 8)
    .map(({ id, description, whenLabel }) => ({ id, description, whenLabel }));
}

function celebrationsFor(rows: EmployeeListItem[]): CelebrationRow[] {
  const today = indiaToday();
  const upcoming: CelebrationRow[] = [];
  for (const row of rows) {
    const birthday = nextAnnual(row.dateOfBirth, today);
    if (birthday) {
      upcoming.push({
        employeeName: row.fullName,
        kind: 'Birthday',
        detail: 'Birthday',
        dateLabel: formatIso(birthday),
        branch: row.branchName || '—',
        department: row.department || '—',
      });
    }
    const anniversary = nextAnnual(row.dateOfJoining, today);
    if (anniversary && anniversary !== row.dateOfJoining) {
      upcoming.push({
        employeeName: row.fullName,
        kind: 'Work anniversary',
        detail: 'Work anniversary',
        dateLabel: formatIso(anniversary),
        branch: row.branchName || '—',
        department: row.department || '—',
      });
    }
  }
  return upcoming.sort((a, b) => a.dateLabel.localeCompare(b.dateLabel)).slice(0, 8);
}

function nextAnnual(isoDate: string | null, today: string): string | null {
  if (!isoDate) return null;
  const [, month, day] = isoDate.split('-');
  if (!month || !day) return null;
  const year = Number(today.slice(0, 4));
  let next = `${year}-${month}-${day}`;
  if (next < today) next = `${year + 1}-${month}-${day}`;
  const limit = shiftIso(today, 45);
  return next <= limit ? next : null;
}

function isConfirmed(row: EmployeeListItem): boolean {
  return !!row.confirmationDate && row.confirmationDate <= indiaToday();
}

function shareRows(counts: Map<string, number>, selected: string) {
  const whole = [...counts.values()].reduce((sum, value) => sum + value, 0);
  return [...counts.entries()]
    .map(([label, employees]) => ({
      department: label,
      employees,
      percentLabel: formatShare(employees, whole),
      percent: whole === 0 ? 0 : (employees / whole) * 100,
      selected: selected !== 'All' && selected === label,
    }))
    .sort((a, b) => b.employees - a.employees || a.department.localeCompare(b.department));
}

function countBy(rows: EmployeeListItem[], key: (row: EmployeeListItem) => string): Map<string, number> {
  const counts = new Map<string, number>();
  for (const row of rows) counts.set(key(row), (counts.get(key(row)) ?? 0) + 1);
  return counts;
}

function approvalStatus(status: string): ApprovalStatus {
  if (status === 'Approved' || status === 'Rejected' || status === 'Pending') return status;
  return 'Pending';
}

function formatShare(part: number, whole: number): string {
  if (!whole) return '0%';
  return `${Math.round((part / whole) * 1000) / 10}%`;
}

function barHeight(value: number, peak: number): number {
  if (value <= 0) return 0;
  return Math.max(8, Math.round((value / peak) * 100));
}

function compareApprovals(a: ApprovalRequest, b: ApprovalRequest, key: SortKey): number {
  if (key === 'status') return STATUS_RANK[a.status] - STATUS_RANK[b.status];
  return String(a[key]).localeCompare(String(b[key]));
}

function uniqueSorted(values: string[]): string[] {
  return [...new Set(values)].sort((a, b) => a.localeCompare(b));
}

function indiaToday(): string {
  return new Date(Date.now() + 5.5 * 3600 * 1000).toISOString().slice(0, 10);
}

function shiftIso(isoDate: string, days: number): string {
  const date = new Date(`${isoDate}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function recentDates(count: number): { date: string; label: string }[] {
  const today = indiaToday();
  return Array.from({ length: count }, (_, index) => {
    const date = shiftIso(today, -(count - 1 - index));
    return { date, label: formatIso(date) };
  });
}

function formatIso(isoDate: string): string {
  const date = new Date(`${isoDate.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return isoDate;
  return new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(date);
}

function httpMessage(err: unknown, fallback: string): string {
  if (err instanceof HttpErrorResponse) {
    const detail = err.error?.detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (err.status === 401) return 'Sign in required.';
    if (err.status === 403) return 'You do not have permission to view the HR dashboard.';
    if (err.status === 0) return 'Cannot reach the API server.';
  }
  return fallback;
}
