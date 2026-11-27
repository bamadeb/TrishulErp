import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, DestroyRef, inject, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { MatFormField, MatLabel, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatDrawer, MatDrawerContainer, MatDrawerContent } from '@angular/material/sidenav';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltip } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import {
  EmployeeLeaveBalanceView,
  EmployeeLeaveDetail,
  EmployeeLeaveHistoryItem,
  EmployeeLeaveOption,
  EmployeeLeaveQuery,
  EmployeeLeaveRow,
  EmployeeLeaveSpan,
  LeaveApi,
} from '@trishul/hr-data-access';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';

const COLORS = ['#7C4DFF', '#2E7D32', '#EF6C00', '#C2185B', '#1565C0', '#00838F', '#6A1B9A', '#455A64'];
type SortKey = 'code' | 'name' | 'department' | 'designation' | 'cl' | 'el' | 'sl' | 'co' | 'taken' | 'upcoming';
type DetailTab = 'overview' | 'history' | 'balance';

interface LeaveSpan {
  fromDate: string;
  toDate: string;
  days: number;
  leaveCode: string;
}

interface HistoryView {
  id: string;
  leaveCode: string;
  fromDate: string;
  toDate: string;
  days: number;
  status: string;
  approvedBy: string | null;
}

interface BalanceView {
  opening: number;
  credited: number;
  consumed: number;
  adjustments: number;
  expired: number;
  closing: number;
  nextExpiry: string | null;
}

interface EmployeeView {
  employeeId: number;
  code: string;
  name: string;
  initials: string;
  color: string;
  department: string;
  designation: string;
  location: string;
  status: string;
  dateOfJoining: string | null;
  cl: number;
  el: number;
  sl: number;
  co: number;
  taken: number;
  upcoming: LeaveSpan | null;
  lastLeave: LeaveSpan | null;
  balances: Record<string, BalanceView>;
  history: HistoryView[];
}

@Component({
  selector: 'trishul-leave-employees-page',
  imports: [
    FormsModule, MatButton, MatCheckbox, MatDrawer, MatDrawerContainer, MatDrawerContent, MatFormField, MatIcon,
    MatIconButton, MatInput, MatLabel, MatMenu, MatMenuItem, MatMenuTrigger, MatOption, MatPrefix, MatProgressBar, MatSelect,
    MatTooltip, PageHeader, RouterLink, StatusBadge,
  ],
  providers: [DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './leave-employees.page.html',
  styleUrl: './leave-employees.page.scss',
})
export class LeaveEmployeesPage {
  private readonly api = inject(LeaveApi);
  private readonly dates = inject(DatePipe);
  private readonly snack = inject(MatSnackBar);
  private readonly drawer = viewChild.required<MatDrawer>('drawer');
  private readonly destroyRef = inject(DestroyRef);
  private loadToken = 0;

  protected readonly years = yearChoices();
  protected readonly severities = { Active: 'success', Notice: 'warn', Approved: 'success', Pending: 'warn', Rejected: 'danger' } as const;
  protected readonly balanceCodes = ['CL', 'AL', 'CO'] as const;

  protected readonly year = signal(this.years[0].id);
  protected readonly department = signal<number | null>(null);
  protected readonly designation = signal<number | null>(null);
  protected readonly location = signal<number | null>(null);
  protected readonly search = signal('');
  protected readonly pageIndex = signal(0);
  protected readonly pageSize = signal(5);
  protected readonly sortKey = signal<SortKey>('code');
  protected readonly sortAsc = signal(true);
  protected readonly selected = signal<number[]>([]);
  protected readonly openEmployee = signal<EmployeeView | null>(null);
  protected readonly tab = signal<DetailTab>('overview');
  protected readonly rows = signal<EmployeeView[]>([]);
  protected readonly total = signal(0);
  protected readonly counts = signal({ employees: 0, onLeave: 0, upcoming: 0, taken: '0' });
  protected readonly departments = signal<EmployeeLeaveOption[]>([]);
  protected readonly designations = signal<EmployeeLeaveOption[]>([]);
  protected readonly locations = signal<EmployeeLeaveOption[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal('');

  protected readonly pageCount = computed(() => Math.max(1, Math.ceil(this.total() / this.pageSize())));
  protected readonly pageRows = computed(() => this.rows());
  protected readonly pageNumbers = computed(() => {
    const count = this.pageCount();
    const current = this.pageIndex();
    const start = Math.max(0, Math.min(current - 2, count - 5));
    return Array.from({ length: Math.min(5, count) }, (_, index) => start + index);
  });
  protected readonly pageAllSelected = computed(() => {
    const page = this.pageRows();
    return page.length > 0 && page.every((row) => this.selected().includes(row.employeeId));
  });
  protected readonly pagePartSelected = computed(() => {
    const page = this.pageRows();
    const count = page.filter((row) => this.selected().includes(row.employeeId)).length;
    return count > 0 && count < page.length;
  });

  constructor() {
    this.reload();
    this.destroyRef.onDestroy(() => this.loadToken++);
  }

  protected setYear(value: number): void {
    this.year.set(value);
    this.pageIndex.set(0);
    this.selected.set([]);
    this.reload();
  }

  protected setDepartment(value: number | null): void {
    this.department.set(value);
    this.pageIndex.set(0);
    this.reload();
  }

  protected setDesignation(value: number | null): void {
    this.designation.set(value);
    this.pageIndex.set(0);
    this.reload();
  }

  protected setLocation(value: number | null): void {
    this.location.set(value);
    this.pageIndex.set(0);
    this.reload();
  }

  protected setSearch(value: string): void {
    this.search.set(value);
    this.pageIndex.set(0);
    this.reload();
  }

  protected reset(): void {
    this.department.set(null);
    this.designation.set(null);
    this.location.set(null);
    this.search.set('');
    this.pageIndex.set(0);
    this.selected.set([]);
    this.reload();
  }

  protected sortBy(key: SortKey): void {
    if (this.sortKey() === key) this.sortAsc.update((value) => !value);
    else {
      this.sortKey.set(key);
      this.sortAsc.set(true);
    }
    this.reload();
  }

  protected setPageSize(value: number): void {
    this.pageSize.set(value);
    this.pageIndex.set(0);
    this.reload();
  }

  protected togglePage(checked: boolean): void {
    const pageIds = this.pageRows().map((row) => row.employeeId);
    this.selected.update((ids) => (checked ? [...new Set([...ids, ...pageIds])] : ids.filter((id) => !pageIds.includes(id))));
  }

  protected toggleRow(id: number, checked: boolean): void {
    this.selected.update((ids) => (checked ? [...ids, id] : ids.filter((item) => item !== id)));
  }

  protected isSelected(id: number): boolean {
    return this.selected().includes(id);
  }

  protected view(row: EmployeeView): void {
    this.tab.set('overview');
    this.openEmployee.set(row);
    this.drawer().open();
    this.api.employeeLeave(row.employeeId, this.year()).subscribe({
      next: (detail) => this.openEmployee.set(toView(detail)),
      error: (error: unknown) => this.snack.open(problemDetail(error, 'The employee leave record could not be opened.'), 'Dismiss', { duration: 3000 }),
    });
  }

  protected closeDrawer(): void {
    this.drawer().close();
  }

  protected expiryLabel(value: string | null): string {
    if (!value) return '';
    return this.dates.transform(value, 'dd MMM y') ?? value;
  }

  protected copyCode(code: string): void {
    void navigator.clipboard?.writeText(code);
    this.snack.open(`${code} copied.`, 'Dismiss', { duration: 2000 });
  }

  protected exportRows(): void {
    this.api.employeeLeaveExport({ ...this.filters(), sort: this.sortParam() }).subscribe({
      next: (page) => download(page.items.map((row) => toView(row))),
      error: (error: unknown) => this.snack.open(problemDetail(error, 'The list could not be exported.'), 'Dismiss', { duration: 3000 }),
    });
  }

  protected showing(): string {
    const total = this.total();
    if (!total) return 'Showing 0 employees';
    const start = this.pageIndex() * this.pageSize() + 1;
    const end = Math.min(total, start + this.pageSize() - 1);
    return `Showing ${start} – ${end} of ${total} employees`;
  }

  protected when(value: string | null): string {
    return value ? (this.dates.transform(value, 'dd-MMM-yyyy') ?? value) : '—';
  }

  protected short(value: string): string {
    return this.dates.transform(value, 'dd MMM') ?? value;
  }

  protected range(item: LeaveSpan): string {
    const days = `${item.days}d`;
    if (item.fromDate === item.toDate) return `${this.short(item.fromDate)} (${days})`;
    return `${this.short(item.fromDate)} – ${this.short(item.toDate)} (${days})`;
  }

  protected goTo(page: number): void {
    this.pageIndex.set(Math.min(Math.max(page, 0), this.pageCount() - 1));
    this.reload();
  }

  private reload(): void {
    const token = ++this.loadToken;
    this.loading.set(true);
    this.error.set('');
    const filters = this.filters();
    forkJoin({
      summary: this.api.employeeLeaveSummary(filters),
      page: this.api.employeeLeaves({
        ...filters,
        sort: this.sortParam(),
        page: this.pageIndex() + 1,
        pageSize: this.pageSize(),
      }),
    }).subscribe({
      next: (result) => {
        if (token !== this.loadToken) return;
        this.counts.set({
          employees: result.summary.employees,
          onLeave: result.summary.onLeave,
          upcoming: result.summary.upcoming,
          taken: amount(result.summary.taken),
        });
        this.departments.set(result.summary.departments);
        this.designations.set(result.summary.designations);
        this.locations.set(result.summary.locations);
        this.rows.set(result.page.items.map((row) => toView(row)));
        this.total.set(result.page.total);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        if (token !== this.loadToken) return;
        this.rows.set([]);
        this.total.set(0);
        this.error.set(problemDetail(error, 'Employee leaves could not be loaded.'));
        this.loading.set(false);
      },
    });
  }

  private filters(): EmployeeLeaveQuery {
    return {
      financialYear: this.year(),
      departmentId: this.department(),
      designationId: this.designation(),
      branchId: this.location(),
      search: this.search().trim() || null,
    };
  }

  private sortParam(): string {
    return `${this.sortAsc() ? '' : '-'}${this.sortKey()}`;
  }
}

function toView(row: EmployeeLeaveRow | EmployeeLeaveDetail): EmployeeView {
  const detail = 'history' in row ? row : null;
  const balances = detail?.balances ?? balancesFrom(row);
  return {
    employeeId: row.employeeId,
    code: row.code,
    name: row.name,
    initials: initials(row.name),
    color: colorFor(row.code),
    department: row.department ?? '—',
    designation: row.designation ?? '—',
    location: row.location ?? '—',
    status: row.status,
    dateOfJoining: row.dateOfJoining,
    cl: Number(row.cl),
    el: Number(row.el),
    sl: Number(row.sl),
    co: Number(row.co),
    taken: Number(row.taken),
    upcoming: span(row.upcoming),
    lastLeave: detail ? span(detail.lastLeave) : null,
    balances: {
      CL: balance(balances['CL']),
      AL: balance(balances['AL'] ?? balances['EL']),
      CO: balance(balances['CO']),
    },
    history: detail?.history.map(historyItem) ?? [],
  };
}

function balancesFrom(row: EmployeeLeaveRow): Record<string, EmployeeLeaveBalanceView> {
  return {
    CL: blank(row.cl),
    AL: blank(row.el),
    CO: blank(row.co),
  };
}

function blank(closing: string): EmployeeLeaveBalanceView {
  return { opening: '0', credited: '0', consumed: '0', adjustments: '0', expired: '0', closing };
}

function balance(row: EmployeeLeaveBalanceView | undefined): BalanceView {
  return {
    opening: Number(row?.opening ?? 0),
    credited: Number(row?.credited ?? 0),
    consumed: Number(row?.consumed ?? 0),
    adjustments: Number(row?.adjustments ?? 0),
    expired: Number(row?.expired ?? 0),
    closing: Number(row?.closing ?? 0),
    nextExpiry: row?.nextExpiry ?? null,
  };
}

function span(row: EmployeeLeaveSpan | null): LeaveSpan | null {
  if (!row) return null;
  return { fromDate: row.fromDate, toDate: row.toDate, days: Number(row.days), leaveCode: row.leaveCode };
}

function historyItem(row: EmployeeLeaveHistoryItem): HistoryView {
  return {
    id: row.displayId,
    leaveCode: row.leaveCode,
    fromDate: row.fromDate,
    toDate: row.toDate,
    days: Number(row.days),
    status: row.status,
    approvedBy: row.approvedBy,
  };
}

function amount(value: string): string {
  const number = Number(value);
  return Number.isInteger(number) ? String(number) : number.toFixed(1);
}

function initials(name: string): string {
  const parts = name.split(' ').filter(Boolean);
  return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase();
}

function colorFor(code: string): string {
  const total = [...code].reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return COLORS[total % COLORS.length];
}

function yearChoices(): { id: number; label: string }[] {
  const now = new Date();
  const start = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
  return [0, 1].map((offset) => {
    const year = start - offset;
    return { id: year, label: `FY ${year} – ${year + 1}` };
  });
}

function download(rows: EmployeeView[]): void {
  const header = ['Employee ID', 'Employee', 'Department', 'Designation', 'Location', 'CL', 'AL', 'CO', 'Leave Taken', 'Upcoming Leave', 'Status'];
  const lines = rows.map((row) => [
    row.code, row.name, row.department, row.designation, row.location,
    String(row.cl), String(row.el), String(row.co), String(row.taken),
    row.upcoming ? `${row.upcoming.fromDate} to ${row.upcoming.toDate}` : '', row.status,
  ].map((value) => `"${value.replaceAll('"', '""')}"`).join(','));
  const blob = new Blob([[header.join(','), ...lines].join('\n')], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'employee-leaves.csv';
  link.click();
  URL.revokeObjectURL(url);
}

function problemDetail(error: unknown, fallback: string): string {
  const detail = (error as { error?: { detail?: string } }).error?.detail;
  return typeof detail === 'string' && detail ? detail : fallback;
}
