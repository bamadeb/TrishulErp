import { DatePipe } from '@angular/common';
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
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatFormField } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { AuthStore } from '@trishul/core-auth';
import {
  AttendanceApi,
  AttendanceHistoryItem,
  RegularizationKpi,
  RegularizationRow,
} from '@trishul/hr-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { Subject, catchError, finalize, of, switchMap } from 'rxjs';

type StatusFilter = 'pending' | 'approved' | 'rejected' | 'all';

interface MonthOption {
  key: string;
  year: number;
  month: number;
  label: string;
}

const EMPTY_KPI: RegularizationKpi = { total: 0, pending: 0, approved: 0, rejected: 0 };

/** Manager review of regularization requests from direct reports. */
@Component({
  selector: 'trishul-attendance-regularization-approvals-page',
  imports: [
    DatePipe,
    FormsModule,
    MatButton,
    MatFormField,
    MatIcon,
    MatOption,
    MatSelect,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-regularization-approvals.page.html',
  styleUrl: './attendance-regularization-approvals.page.scss',
})
export class AttendanceRegularizationApprovalsPage implements OnInit {
  private readonly api = inject(AttendanceApi);
  private readonly auth = inject(AuthStore);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);
  private readonly load$ = new Subject<void>();

  protected readonly months = buildMonths();
  protected readonly monthKey = signal(this.months[0]!.key);
  protected readonly statusFilter = signal<StatusFilter>('pending');
  protected readonly search = signal('');
  protected readonly loading = signal(false);
  protected readonly deciding = signal(false);
  protected readonly kpi = signal<RegularizationKpi>(EMPTY_KPI);
  protected readonly rows = signal<RegularizationRow[]>([]);
  protected readonly selectedId = signal<number | null>(null);
  protected readonly comment = signal('');
  protected readonly history = signal<AttendanceHistoryItem[]>([]);
  protected readonly historyLoading = signal(false);

  protected readonly filtered = computed(() => {
    const tab = this.statusFilter();
    const q = this.search().trim().toLowerCase();
    return this.rows().filter((row) => {
      if (tab === 'pending' && row.status !== 'Pending') return false;
      if (tab === 'approved' && row.status !== 'Approved') return false;
      if (tab === 'rejected' && row.status !== 'Rejected') return false;
      if (!q) return true;
      return `${row.employeeCode} ${row.employeeName}`.toLowerCase().includes(q);
    });
  });

  protected readonly selected = computed(
    () => this.rows().find((row) => row.id === this.selectedId()) ?? this.filtered()[0] ?? null,
  );

  protected readonly commentCount = computed(() => this.comment().length);
  protected readonly canDecide = computed(() => {
    const row = this.selected();
    const text = this.comment().trim();
    return !!row && row.status === 'Pending' && text.length > 0 && text.length <= 250 && !this.deciding();
  });

  ngOnInit(): void {
    this.load$
      .pipe(
        switchMap(() => {
          this.loading.set(true);
          const month = this.months.find((item) => item.key === this.monthKey()) ?? this.months[0]!;
          const from = `${month.year}-${String(month.month).padStart(2, '0')}-01`;
          const last = new Date(month.year, month.month, 0).getDate();
          const to = `${month.year}-${String(month.month).padStart(2, '0')}-${String(last).padStart(2, '0')}`;
          return this.api
            .listRegularizations({
              from,
              to,
              page: 1,
              pageSize: 200,
              statusTab: 'all',
              scope: this.auth.hasPermission('core.employee.manage') ? 'all' : 'team',
            })
            .pipe(
              catchError((err: unknown) => {
                this.rows.set([]);
                this.kpi.set(EMPTY_KPI);
                this.snackBar.open(extractHttpError(err, 'Failed to load regularization requests.'), 'OK', {
                  duration: 4000,
                });
                return of(null);
              }),
              finalize(() => this.loading.set(false)),
            );
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((page) => {
        if (!page) return;
        this.kpi.set(page.summary);
        this.rows.set(page.items);
        const current = this.selectedId();
        const still = page.items.some((row) => row.id === current);
        if (!still) this.selectedId.set(page.items.find((row) => row.status === 'Pending')?.id ?? page.items[0]?.id ?? null);
        this.comment.set('');
        this.loadHistory();
      });
    this.load$.next();
  }

  protected setMonth(key: string): void {
    this.monthKey.set(key);
    this.load$.next();
  }

  protected setFilter(filter: StatusFilter): void {
    this.statusFilter.set(filter);
    const first = this.filtered()[0];
    if (first && !this.filtered().some((row) => row.id === this.selectedId())) {
      this.select(first);
    }
  }

  protected onSearch(value: string): void {
    this.search.set(value);
  }

  protected select(row: RegularizationRow): void {
    if (this.selectedId() === row.id) return;
    this.selectedId.set(row.id);
    this.comment.set('');
    this.loadHistory();
  }

  protected onComment(value: string): void {
    this.comment.set(value.slice(0, 250));
  }

  protected approve(): void {
    this.decide(true);
  }

  protected reject(): void {
    this.decide(false);
  }

  protected showAttachment(name: string): void {
    this.snackBar.open(`Attachment recorded with the request: ${name}`, 'OK', { duration: 4000 });
  }

  protected initials(name: string): string {
    const parts = name.trim().split(/\s+/).filter(Boolean);
    return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase() || '—';
  }

  protected requestLabel(row: RegularizationRow): string {
    if (row.requestType === 'Missed Punch' && !row.originalOut) return 'Missed Punch Out';
    if (row.requestType === 'Missed Punch' && !row.originalIn) return 'Missed Punch In';
    return row.requestType;
  }

  protected clock(value: string | null | undefined): string {
    return formatTime(value) ?? 'Not Recorded';
  }

  protected statusClass(status: string | null | undefined): string {
    if (status === 'Present' || status === 'Approved') return 'ok';
    if (status === 'Pending' || status === 'Late' || status === 'Missing Punch' || status === 'In Progress') return 'warn';
    if (status === 'Rejected' || status === 'Absent') return 'bad';
    return 'muted';
  }

  private decide(approve: boolean): void {
    const row = this.selected();
    const remark = this.comment().trim();
    if (!row || !this.canDecide()) return;
    this.deciding.set(true);
    const call = approve
      ? this.api.approveRegularization(row.id, remark)
      : this.api.rejectRegularization(row.id, remark);
    call
      .pipe(
        finalize(() => this.deciding.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: () => {
          this.snackBar.open(
            approve
              ? 'Request approved. Attendance was recalculated from the requested punches.'
              : 'Request rejected. The employee has been notified.',
            'OK',
            { duration: 4000 },
          );
          this.load$.next();
        },
        error: (err: unknown) => {
          this.snackBar.open(extractHttpError(err, 'Could not update this request.'), 'OK', { duration: 4000 });
        },
      });
  }

  private loadHistory(): void {
    const row = this.rows().find((item) => item.id === this.selectedId());
    if (!row) {
      this.history.set([]);
      return;
    }
    this.historyLoading.set(true);
    this.api
      .employeeHistory(row.employeeId, row.attendanceDate.slice(0, 10), 10)
      .pipe(
        catchError(() => of([] as AttendanceHistoryItem[])),
        finalize(() => this.historyLoading.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((items) => this.history.set(items.slice(0, 5)));
  }
}

function buildMonths(): MonthOption[] {
  const today = new Date();
  const items: MonthOption[] = [];
  for (let i = 0; i < 12; i++) {
    const date = new Date(today.getFullYear(), today.getMonth() - i, 1);
    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    items.push({
      key: `${year}-${month}`,
      year,
      month,
      label: new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' }).format(date),
    });
  }
  return items;
}

function formatTime(value: string | null | undefined): string | null {
  if (!value) return null;
  if (/am|pm/i.test(value) && !value.includes('T')) return value;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-US', { hour: '2-digit', minute: '2-digit', hour12: true }).format(date);
}

function extractHttpError(err: unknown, fallback: string): string {
  if (err instanceof HttpErrorResponse) {
    const detail = err.error?.detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
  }
  return fallback;
}
