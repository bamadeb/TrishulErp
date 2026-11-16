import { DatePipe, DecimalPipe, PercentPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatTab, MatTabGroup } from '@angular/material/tabs';
import { RouterLink } from '@angular/router';
import { LeaveApi, LeaveDashboard, LeaveDashboardQuery, LeaveRequestRow } from '@trishul/hr-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';

interface MonthChoice {
  key: string;
  year: number;
  month: number;
  label: string;
}

@Component({
  selector: 'trishul-leave-dashboard-page',
  imports: [
    DatePipe,
    DecimalPipe,
    PercentPipe,
    FormsModule,
    MatButton,
    MatFormField,
    MatIcon,
    MatInput,
    MatLabel,
    MatOption,
    MatPaginator,
    MatProgressBar,
    MatSelect,
    MatTab,
    MatTabGroup,
    PageHeader,
    RouterLink,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './leave-dashboard.page.html',
  styleUrl: './leave-dashboard.page.scss',
})
export class LeaveDashboardPage {
  private readonly api = inject(LeaveApi);

  protected readonly months = recentMonths();
  protected readonly severities: Partial<Record<string, StatusSeverity>> = {
    Approved: 'success',
    Pending: 'warn',
    Rejected: 'danger',
    Cancelled: 'neutral',
  };
  protected readonly actions = [
    { label: 'My leave', route: '/hr/leave/mine', icon: 'person' },
    { label: 'Employee leaves', route: '/hr/leave/employees', icon: 'groups' },
    { label: 'Leave requests', route: '/hr/leave/requests', icon: 'inbox' },
    { label: 'Leave balance', route: '/hr/leave/balances', icon: 'account_balance_wallet' },
    { label: 'Leave reports', route: '/hr/leave/reports', icon: 'summarize' },
    { label: 'Leave types', route: '/hr/leave/types', icon: 'category' },
    { label: 'Leave policies', route: '/hr/leave/policies', icon: 'policy' },
  ];

  protected readonly loading = signal(true);
  protected readonly error = signal('');
  protected readonly data = signal<LeaveDashboard | null>(null);
  protected readonly monthKey = signal(this.months[0].key);
  protected readonly departmentId = signal<number | null>(null);
  protected readonly leaveTypeId = signal<number | null>(null);
  protected readonly status = signal<string | null>(null);
  protected readonly upcoming = signal(false);
  protected readonly search = signal('');
  protected readonly page = signal(1);
  protected readonly pageSize = signal(10);
  protected readonly sort = signal('-fromDate');

  protected readonly slices = computed(() => donut(this.data()));
  protected readonly trendLine = computed(() => trend(this.data()?.trend ?? []));

  constructor() {
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.error.set('');
    this.api.dashboard(this.params()).subscribe({
      next: (board) => {
        this.data.set(board);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.error.set('The leave dashboard could not be loaded.');
      },
    });
  }

  protected selectMonth(key: string): void {
    this.monthKey.set(key);
    this.page.set(1);
    this.load();
  }

  protected filterStatus(status: string | null, upcoming = false): void {
    this.status.set(status);
    this.upcoming.set(upcoming);
    this.page.set(1);
    this.load();
  }

  protected applyFilters(): void {
    this.page.set(1);
    this.load();
  }

  protected onPage(event: PageEvent): void {
    this.page.set(event.pageIndex + 1);
    this.pageSize.set(event.pageSize);
    this.load();
  }

  protected toggleSort(field: string): void {
    this.sort.set(this.sort() === field ? `-${field}` : field);
    this.load();
  }

  protected exportList(): void {
    this.api.dashboard({ ...this.params(), page: 1, pageSize: 200 }).subscribe({
      next: (board) => downloadCsv(board.requests.items),
      error: () => this.error.set('The leave list could not be exported.'),
    });
  }

  private params(): LeaveDashboardQuery {
    const selected = this.months.find((item) => item.key === this.monthKey()) ?? this.months[0];
    return {
      year: selected.year,
      month: selected.month,
      departmentId: this.departmentId(),
      leaveTypeId: this.leaveTypeId(),
      status: this.status(),
      upcoming: this.upcoming(),
      search: this.search(),
      page: this.page(),
      pageSize: this.pageSize(),
      sort: this.sort(),
    };
  }
}

function recentMonths(): MonthChoice[] {
  const today = new Date();
  return Array.from({ length: 12 }, (_, offset) => {
    const day = new Date(today.getFullYear(), today.getMonth() - offset, 1);
    const year = day.getFullYear();
    const month = day.getMonth() + 1;
    const label = day.toLocaleString('en', { month: 'long', year: 'numeric' });
    return { key: `${year}-${month}`, year, month, label };
  });
}

function donut(board: LeaveDashboard | null): { label: string; count: number; percent: number; dash: string; offset: number; color: string }[] {
  const parts = [
    { label: 'Working', count: board?.overview.working ?? 0, color: 'var(--trishul-success)' },
    { label: 'On leave', count: board?.overview.onLeave ?? 0, color: 'var(--mat-sys-primary)' },
    { label: 'Pending', count: board?.overview.pending ?? 0, color: 'var(--trishul-warn)' },
  ];
  const total = parts.reduce((sum, part) => sum + part.count, 0);
  const circumference = 2 * Math.PI * 42;
  let cursor = 0;
  return parts.map((part) => {
    const length = total === 0 ? 0 : (part.count / total) * circumference;
    const slice = {
      ...part,
      percent: total === 0 ? 0 : part.count / total,
      dash: `${length} ${circumference - length}`,
      offset: -cursor,
    };
    cursor += length;
    return slice;
  });
}

function trend(points: { days: string }[]): string {
  if (points.length === 0) return '';
  const max = Math.max(...points.map((point) => Number(point.days)), 1);
  const width = 280;
  const height = 88;
  return points
    .map((point, index) => {
      const x = points.length === 1 ? width / 2 : (index / (points.length - 1)) * width;
      const y = height - (Number(point.days) / max) * (height - 8) - 4;
      return `${x},${y}`;
    })
    .join(' ');
}

function downloadCsv(rows: LeaveRequestRow[]): void {
  const header = ['Employee ID', 'Employee', 'Department', 'Leave type', 'From', 'To', 'Days', 'Reason', 'Status'];
  const body = rows.map((row) => [
    row.employeeCode,
    row.employeeName,
    row.department ?? '',
    row.leaveType,
    row.fromDate,
    row.toDate,
    row.days,
    row.reason ?? '',
    row.status,
  ]);
  const csv = [header, ...body].map((line) => line.map(csvCell).join(',')).join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'leave-requests.csv';
  link.click();
  URL.revokeObjectURL(url);
}

function csvCell(value: string): string {
  return `"${value.replaceAll('"', '""')}"`;
}
