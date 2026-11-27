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
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { MatSnackBar } from '@angular/material/snack-bar';
import { AttendanceApi, RegularizationRow, RegularizationStatus } from '@trishul/hr-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { catchError, forkJoin, of } from 'rxjs';
import { AttendanceRegularizeDrawer } from './attendance-regularize-drawer';

type Tab = 'all' | 'pending' | 'approved' | 'rejected';

/** The signed-in employee's own regularization requests and the request-details view. */
@Component({
  selector: 'trishul-attendance-my-regularization-page',
  imports: [DatePipe, MatButton, MatIcon, MatIconButton, PageHeader, AttendanceRegularizeDrawer],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-my-regularization.page.html',
  styleUrl: './attendance-my-regularization.page.scss',
})
export class AttendanceMyRegularizationPage implements OnInit {
  private readonly api = inject(AttendanceApi);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly loading = signal(false);
  protected readonly rows = signal<RegularizationRow[]>([]);
  protected readonly tab = signal<Tab>('all');
  protected readonly selectedId = signal<number | null>(null);
  protected readonly selfEmployeeId = signal<number | null>(null);
  protected readonly drawerKeys = signal<number[]>([]);
  protected readonly drawerDate = signal<string | null>(null);

  protected readonly filtered = computed(() => {
    const tab = this.tab();
    return this.rows().filter((row) => {
      if (tab === 'pending') return row.status === 'Pending';
      if (tab === 'approved') return row.status === 'Approved';
      if (tab === 'rejected') return row.status === 'Rejected';
      return true;
    });
  });

  protected readonly selected = computed(
    () => this.rows().find((row) => row.id === this.selectedId()) ?? null,
  );

  protected readonly counts = computed(() => ({
    all: this.rows().length,
    pending: this.rows().filter((row) => row.status === 'Pending').length,
    approved: this.rows().filter((row) => row.status === 'Approved').length,
    rejected: this.rows().filter((row) => row.status === 'Rejected').length,
  }));

  ngOnInit(): void {
    this.reload();
  }

  protected reload(): void {
    const today = new Date();
    const from = `${today.getFullYear()}-01-01`;
    const to = `${today.getFullYear()}-12-31`;
    this.loading.set(true);
    forkJoin({
      page: this.api
        .listRegularizations({ from, to, page: 1, pageSize: 200, statusTab: 'all', scope: 'self' })
        .pipe(
          catchError((err: unknown) => {
            this.snackBar.open(message(err, 'Could not load your regularization requests.'), 'OK', { duration: 4000 });
            return of(null);
          }),
        ),
      mine: this.api.mine(today.getFullYear(), today.getMonth() + 1).pipe(catchError(() => of(null))),
    })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(({ page, mine }) => {
        this.loading.set(false);
        const selfId = mine?.employeeId ?? null;
        this.selfEmployeeId.set(selfId);
        const items = page?.items ?? [];
        this.rows.set(selfId == null ? items : items.filter((row) => row.employeeId === selfId));
      });
  }

  protected openRequest(date: string | null = null): void {
    this.drawerDate.set(date);
    this.drawerKeys.set([Date.now()]);
  }

  protected closeDrawer(): void {
    this.drawerKeys.set([]);
  }

  protected onRegularized(): void {
    this.drawerKeys.set([]);
    this.reload();
  }

  protected open(row: RegularizationRow): void {
    this.selectedId.set(row.id);
  }

  protected back(): void {
    this.selectedId.set(null);
  }

  protected requestId(row: RegularizationRow): string {
    return `REG-${String(row.id).padStart(4, '0')}`;
  }

  protected statusText(status: RegularizationStatus): string {
    if (status === 'Pending') return 'Pending with Reporting Manager';
    return status;
  }

  protected requestLabel(row: RegularizationRow): string {
    if (row.requestType === 'Missed Punch' && !row.originalOut) return 'Missed Punch Out';
    if (row.requestType === 'Missed Punch' && !row.originalIn) return 'Missed Punch In';
    return row.requestType;
  }

  protected clock(value: string | null | undefined): string {
    if (!value) return '—';
    if (/am|pm/i.test(value) && !value.includes('T')) return value;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat('en-US', { hour: '2-digit', minute: '2-digit', hour12: true }).format(date);
  }

  protected initials(name: string): string {
    const parts = name.trim().split(/\s+/).filter(Boolean);
    return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase() || '—';
  }
}

function message(err: unknown, fallback: string): string {
  if (err instanceof HttpErrorResponse && typeof err.error?.detail === 'string') return err.error.detail;
  return fallback;
}
