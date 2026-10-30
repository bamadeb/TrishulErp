import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  effect,
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
import { AuthStore } from '@trishul/core-auth';
import { PageHeader, StatusBadge, confirmAction } from '@trishul/shared-ui';
import { HrApprovalDetailDialog } from './hr-approval-detail.dialog';
import {
  DEMO_AS_OF,
  DEMO_BRANCHES,
  DEMO_DEPARTMENTS,
  ApprovalRequest,
  ApprovalStatus,
  HrActivity,
  approvalStatusFilters,
  approvalStatusSeverity,
  attendanceDates,
  attendanceForScope,
  celebrations,
  formatShare,
  headcount,
  holidays,
  matchesScope,
  missingAttendance,
  payrollOverview,
  pendingApprovals,
  quickActions,
  recentActivities,
  scopeHeadcount,
  validateSample,
} from './hr-dashboard.mock-data';

type SortKey = 'employeeName' | 'requestType' | 'submittedOn' | 'status' | 'priority';
type SortDir = 'asc' | 'desc';
type ViewState = 'ready' | 'loading' | 'error';

const PRIORITY_RANK: Record<string, number> = { High: 0, Medium: 1, Low: 2 };
const STATUS_RANK: Record<string, number> = { Pending: 0, Approved: 1, Rejected: 2 };

/** HR command center. Every figure is derived from the local sample. */
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
export class HrDashboardPage {
  private readonly auth = inject(AuthStore);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);
  private resetTimer = 0;

  protected readonly dates = attendanceDates;
  protected readonly branches = ['All', ...DEMO_BRANCHES];
  protected readonly departments = ['All', ...DEMO_DEPARTMENTS];
  protected readonly approvalStatuses = approvalStatusFilters;
  protected readonly severity = approvalStatusSeverity;
  protected readonly holidays = holidays;
  protected readonly payroll = payrollOverview;
  protected readonly quickActions = quickActions;
  protected readonly requestTypes = [
    'All',
    ...new Set(pendingApprovals.map((row) => row.requestType)),
  ];

  protected readonly viewState = signal<ViewState>('ready');
  protected readonly loadError = signal<string | null>(null);
  protected readonly selectedDate = signal(DEMO_AS_OF);
  protected readonly sampleBranch = signal('All');
  /** After a manual choice, the header branch no longer overwrites the sample filter. */
  private readonly branchPinned = signal(false);
  protected readonly department = signal('All');
  protected readonly approvalStatus = signal<(typeof approvalStatusFilters)[number]>('All');
  protected readonly requestType = signal('All');
  protected readonly sortKey = signal<SortKey>('submittedOn');
  protected readonly sortDir = signal<SortDir>('desc');
  protected readonly approvals = signal<ApprovalRequest[]>(
    pendingApprovals.map((row) => ({ ...row })),
  );
  protected readonly activities = signal<HrActivity[]>(
    recentActivities.map((row) => ({ ...row })),
  );

  protected readonly signedInBranchName = computed(
    () => this.auth.currentBranch()?.name ?? '',
  );
  protected readonly signedInMatchesSample = computed(() =>
    DEMO_BRANCHES.some(
      (branch) => branch.toLowerCase() === this.signedInBranchName().toLowerCase(),
    ),
  );
  protected readonly dateLabel = computed(
    () => this.dates.find((day) => day.date === this.selectedDate())?.label ?? '',
  );
  protected readonly scopeLabel = computed(() => {
    const branch = this.sampleBranch() === 'All' ? 'all sample branches' : this.sampleBranch();
    const department = this.department() === 'All' ? 'all departments' : this.department();
    return `${branch} · ${department} · ${this.dateLabel()}`;
  });
  protected readonly attendance = computed(() =>
    attendanceForScope(this.selectedDate(), this.sampleBranch(), this.department()),
  );
  protected readonly headcountTotal = computed(() =>
    scopeHeadcount(this.sampleBranch(), this.department()),
  );
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
    () => this.scopedApprovals().filter((row) => row.status === 'Pending').length,
  );
  protected readonly summaryCards = computed(() => {
    const day = this.attendance();
    const present = day?.present ?? 0;
    const absent = day?.absent ?? 0;
    const onLeave = day?.onLeave ?? 0;
    const people = this.headcountTotal();
    return [
      {
        label: 'Total Employees',
        value: String(people),
        description: `Sample headcount for ${this.scopeLabel()}`,
        icon: 'groups',
        tone: 'Sample',
        route: '/admin/employees',
        fragment: undefined as string | undefined,
      },
      {
        label: 'Present Today',
        value: String(present),
        description: `${this.attendanceShare()} of this sample marked present`,
        icon: 'how_to_reg',
        tone: this.attendanceTone(),
        route: '/hr/attendance',
        fragment: undefined as string | undefined,
      },
      {
        label: 'Absent Today',
        value: String(absent),
        description: absent === 0 ? 'No absences in this sample selection' : 'Included in the sample absent count',
        icon: 'person_off',
        tone: absent > 0 ? 'Watch' : 'Clear',
        route: '/hr/attendance',
        fragment: undefined as string | undefined,
      },
      {
        label: 'On Leave',
        value: String(onLeave),
        description: 'Sample leave for the selected date',
        icon: 'event_busy',
        tone: onLeave > 0 ? 'Watch' : 'Clear',
        route: '/hr/leave',
        fragment: undefined as string | undefined,
      },
      {
        label: 'Pending Approvals',
        value: String(this.pendingCount()),
        description: 'Awaiting a decision in this demo only',
        icon: 'pending_actions',
        tone: this.pendingCount() > 0 ? 'Open' : 'Clear',
        route: '/hr/dashboard',
        fragment: 'approvals',
      },
      {
        label: 'Payroll Status',
        value: this.payroll.status,
        description: `${this.payroll.period} has not been started`,
        icon: 'payments',
        tone: 'Not started',
        route: '/hr/payroll',
        fragment: undefined as string | undefined,
      },
    ];
  });
  protected readonly departmentRows = computed(() => {
    const branch = this.sampleBranch();
    const whole = scopeHeadcount(branch, 'All');
    return DEMO_DEPARTMENTS.map((department) => {
      const employees = scopeHeadcount(branch, department);
      return {
        department,
        employees,
        percentLabel: formatShare(employees, whole),
        percent: whole === 0 ? 0 : (employees / whole) * 100,
        selected: this.department() !== 'All' && this.department() === department,
      };
    }).filter((row) => row.employees > 0);
  });
  protected readonly employmentRows = computed(() => {
    const cells = headcount.filter((cell) =>
      matchesScope(cell.branch, cell.department, this.sampleBranch(), this.department()),
    );
    const active = cells.reduce((sum, cell) => sum + cell.active, 0);
    const probation = cells.reduce((sum, cell) => sum + cell.probation, 0);
    const onNotice = cells.reduce((sum, cell) => sum + cell.onNotice, 0);
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
    const rows = this.dates.map((day) => {
      const totals = attendanceForScope(day.date, this.sampleBranch(), this.department());
      return {
        date: day.date,
        label: day.label.slice(0, 6),
        present: totals?.present ?? 0,
        absent: totals?.absent ?? 0,
        onLeave: totals?.onLeave ?? 0,
      };
    });
    const peak = Math.max(1, ...rows.flatMap((row) => [row.present, row.absent, row.onLeave]));
    return rows.map((row) => ({
      ...row,
      presentHeight: barHeight(row.present, peak),
      absentHeight: barHeight(row.absent, peak),
      leaveHeight: barHeight(row.onLeave, peak),
    }));
  });
  protected readonly gaps = computed(() =>
    missingAttendance.filter(
      (row) =>
        row.date === this.selectedDate() &&
        matchesScope(row.branch, row.department, this.sampleBranch(), this.department()),
    ),
  );
  protected readonly visibleCelebrations = computed(() =>
    celebrations.filter((row) =>
      matchesScope(row.branch, row.department, this.sampleBranch(), this.department()),
    ),
  );
  protected readonly visibleActivities = computed(() =>
    this.activities().filter((row) =>
      row.branch
        ? matchesScope(
            row.branch,
            row.department ?? '',
            this.sampleBranch(),
            this.department(),
          )
        : true,
    ),
  );
  protected readonly approvalRows = computed(() => {
    const status = this.approvalStatus();
    const type = this.requestType();
    const rows = this.scopedApprovals().filter((row) => {
      const statusOk = status === 'All' || row.status === status;
      const typeOk = type === 'All' || row.requestType === type;
      return statusOk && typeOk;
    });
    const dir = this.sortDir() === 'asc' ? 1 : -1;
    const key = this.sortKey();
    return [...rows].sort((a, b) => dir * compareApprovals(a, b, key));
  });

  constructor() {
    this.destroyRef.onDestroy(() => window.clearTimeout(this.resetTimer));
    const problem = validateSample();
    if (problem) {
      this.loadError.set(problem);
      this.viewState.set('error');
    }
    effect(() => {
      const name = this.auth.currentBranch()?.name ?? '';
      if (this.branchPinned()) return;
      const match = DEMO_BRANCHES.find(
        (branch) => branch.toLowerCase() === name.toLowerCase(),
      );
      this.sampleBranch.set(match ?? 'All');
    });
  }

  protected setSampleBranch(branch: string): void {
    this.branchPinned.set(true);
    this.sampleBranch.set(branch);
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

  protected decide(request: ApprovalRequest, status: Extract<ApprovalStatus, 'Approved' | 'Rejected'>): void {
    if (request.status !== 'Pending') return;
    confirmAction(this.dialog, {
      title: status === 'Approved' ? 'Approve this sample request?' : 'Reject this sample request?',
      message: `${request.employeeName}'s ${request.requestType.toLowerCase()} will be marked ${status} on this page only. No server record is changed.`,
      confirmText: status === 'Approved' ? 'Approve' : 'Reject',
      destructive: status === 'Rejected',
    })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((confirmed) => {
        if (!confirmed) return;
        this.approvals.update((rows) =>
          rows.map((row) => (row.id === request.id ? { ...row, status } : row)),
        );
        this.activities.update((rows) => [
          {
            id: `demo-${request.id}-${status}`,
            whenLabel: 'Just now · this page',
            description: `${request.employeeName}'s ${request.requestType} was marked ${status} in the demo.`,
            branch: request.branch,
            department: request.department,
          },
          ...rows,
        ]);
        this.snackBar.open(
          `${request.employeeName} marked ${status} in this demo. The server was not updated.`,
          'OK',
          { duration: 5000 },
        );
      });
  }

  protected resetSample(): void {
    window.clearTimeout(this.resetTimer);
    this.viewState.set('loading');
    this.loadError.set(null);
    this.resetTimer = window.setTimeout(() => {
      const problem = validateSample();
      if (problem) {
        this.loadError.set(problem);
        this.viewState.set('error');
        return;
      }
      this.approvals.set(pendingApprovals.map((row) => ({ ...row })));
      this.activities.set(recentActivities.map((row) => ({ ...row })));
      this.approvalStatus.set('All');
      this.requestType.set('All');
      this.viewState.set('ready');
      this.snackBar.open(
        'Sample data restored on this page. The server was not contacted.',
        'OK',
        { duration: 4000 },
      );
    }, 400);
  }

  private scopedApprovals(): ApprovalRequest[] {
    return this.approvals().filter((row) =>
      matchesScope(row.branch, row.department, this.sampleBranch(), this.department()),
    );
  }
}

function barHeight(value: number, peak: number): number {
  if (value <= 0) return 0;
  return Math.max(8, Math.round((value / peak) * 100));
}

function compareApprovals(a: ApprovalRequest, b: ApprovalRequest, key: SortKey): number {
  if (key === 'priority') return PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority];
  if (key === 'status') return STATUS_RANK[a.status] - STATUS_RANK[b.status];
  return a[key].localeCompare(b[key]);
}
