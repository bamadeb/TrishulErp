import { DecimalPipe } from '@angular/common';
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
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { provideNativeDateAdapter } from '@angular/material/core';
import {
  MatDatepickerToggle,
  MatDateRangeInput,
  MatDateRangePicker,
  MatEndDate,
  MatStartDate,
} from '@angular/material/datepicker';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatLabel, MatPrefix, MatSuffix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltip } from '@angular/material/tooltip';
import { ActivatedRoute } from '@angular/router';
import {
  AttendanceApi,
  RegularizationKpi as ApiRegularizationKpi,
  RegularizationPage,
  RegularizationRow as ApiRegularizationRow,
} from '@trishul/hr-data-access';
import { PageHeader } from '@trishul/shared-ui';
import {
  Subject,
  catchError,
  debounceTime,
  distinctUntilChanged,
  filter,
  finalize,
  forkJoin,
  map,
  of,
  switchMap,
  tap,
} from 'rxjs';
import {
  AttendanceRegularizationDecisionDialog,
  RegularizationDecisionResult,
} from './attendance-regularization-decision.dialog';
import { AttendanceRegularizationDetailDialog } from './attendance-regularization-detail.dialog';
import {
  ATTENDANCE_REGULARIZE_DIALOG_OPTIONS,
  AttendanceRegularizeDialog,
  RegularizeEmployeeOption,
  RegularizeSubmitResult,
} from './attendance-regularize.dialog';
import {
  REGULARIZATION_REQUEST_TYPES,
  RegularizationKpi,
  RegularizationListRow,
  RegularizationRequestType,
  RegularizationTab,
} from './attendance.models';

const AVATAR_TONES = [
  '#2563eb',
  '#db2777',
  '#ea580c',
  '#7c3aed',
  '#0891b2',
  '#059669',
  '#c2410c',
  '#4f46e5',
  '#be123c',
  '#0d9488',
];

const EMPTY_KPI: RegularizationKpi = {
  total: 0,
  pending: 0,
  approved: 0,
  rejected: 0,
};

const PAGE_SIZE = 200;

/** Attendance Regularization — wired to /hr/attendance/regularizations (UI unchanged). */
@Component({
  selector: 'trishul-attendance-regularization-page',
  imports: [
    DecimalPipe,
    FormsModule,
    MatButton,
    MatCheckbox,
    MatDateRangeInput,
    MatDateRangePicker,
    MatDatepickerToggle,
    MatEndDate,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatInput,
    MatLabel,
    MatOption,
    MatPaginator,
    MatPrefix,
    MatSelect,
    MatStartDate,
    MatSuffix,
    MatTooltip,
    PageHeader,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-regularization.page.html',
  styleUrl: './attendance-regularization.page.scss',
})
export class AttendanceRegularizationPage implements OnInit {
  private readonly api = inject(AttendanceApi);
  private readonly snackBar = inject(MatSnackBar);
  private readonly dialog = inject(MatDialog);
  private readonly destroyRef = inject(DestroyRef);
  private readonly route = inject(ActivatedRoute);
  private readonly reload$ = new Subject<void>();
  private readonly search$ = new Subject<string>();

  protected readonly requestTypes = REGULARIZATION_REQUEST_TYPES;
  protected readonly loading = signal(false);
  protected readonly allRows = signal<RegularizationListRow[]>([]);
  protected readonly departments = signal<string[]>([]);
  protected readonly locations = signal<string[]>([]);
  protected readonly kpi = signal<RegularizationKpi>(EMPTY_KPI);

  private readonly now = new Date();
  protected readonly contentTab = signal<RegularizationTab>('all');
  protected readonly search = signal('');
  protected readonly department = signal('');
  protected readonly location = signal('');
  protected readonly requestType = signal<RegularizationRequestType | ''>('');
  protected readonly rangeStart = signal<Date | null>(
    new Date(this.now.getFullYear(), this.now.getMonth(), 1),
  );
  protected readonly rangeEnd = signal<Date | null>(
    new Date(this.now.getFullYear(), this.now.getMonth(), this.now.getDate()),
  );
  protected readonly page = signal(0);
  protected readonly pageSize = signal(10);
  protected readonly selectedIds = signal<Set<number>>(new Set());

  protected readonly tabCounts = computed(() => this.kpi());

  protected readonly filtered = computed(() => this.allRows());

  protected readonly total = computed(() => this.filtered().length);

  protected readonly pageRows = computed(() => {
    const start = this.page() * this.pageSize();
    return this.filtered().slice(start, start + this.pageSize());
  });

  protected readonly allPageSelected = computed(() => {
    const rows = this.pageRows();
    return rows.length > 0 && rows.every((row) => this.selectedIds().has(row.id));
  });

  protected readonly somePageSelected = computed(() => {
    const rows = this.pageRows();
    const selected = rows.filter((row) => this.selectedIds().has(row.id)).length;
    return selected > 0 && selected < rows.length;
  });

  ngOnInit(): void {
    this.search$
      .pipe(debounceTime(250), distinctUntilChanged(), takeUntilDestroyed(this.destroyRef))
      .subscribe((value) => {
        this.search.set(value);
        this.page.set(0);
        this.reload$.next();
      });

    this.reload$
      .pipe(
        tap(() => this.loading.set(true)),
        switchMap(() => this.loadRange$()),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe();

    this.applyRouteRange();
    this.reload$.next();
  }

  private applyRouteRange(): void {
    const from = this.route.snapshot.queryParamMap.get('from');
    const to = this.route.snapshot.queryParamMap.get('to');
    if (from) this.rangeStart.set(parseIsoDate(from));
    if (to) this.rangeEnd.set(parseIsoDate(to));
  }

  protected setTab(tab: RegularizationTab): void {
    this.contentTab.set(tab);
    this.page.set(0);
    this.selectedIds.set(new Set());
    this.reload$.next();
  }

  protected onSearch(value: string): void {
    this.search$.next(value);
  }

  protected onDepartment(value: string): void {
    this.department.set(value);
    this.page.set(0);
    this.reload$.next();
  }

  protected onLocation(value: string): void {
    this.location.set(value);
    this.page.set(0);
    this.reload$.next();
  }

  protected onRequestType(value: RegularizationRequestType | ''): void {
    this.requestType.set(value);
    this.page.set(0);
    this.reload$.next();
  }

  protected setRangeStart(value: Date | null): void {
    this.rangeStart.set(value);
    this.page.set(0);
    if (value && this.rangeEnd()) this.reload$.next();
  }

  protected setRangeEnd(value: Date | null): void {
    this.rangeEnd.set(value);
    this.page.set(0);
    if (value && this.rangeStart()) this.reload$.next();
  }

  protected onPage(event: PageEvent): void {
    this.page.set(event.pageIndex);
    this.pageSize.set(event.pageSize);
  }

  protected isSelected(id: number): boolean {
    return this.selectedIds().has(id);
  }

  protected toggleRow(id: number, checked: boolean): void {
    this.selectedIds.update((set) => {
      const next = new Set(set);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  protected togglePage(checked: boolean): void {
    this.selectedIds.update((set) => {
      const next = new Set(set);
      for (const row of this.pageRows()) {
        if (checked) next.add(row.id);
        else next.delete(row.id);
      }
      return next;
    });
  }

  protected refresh(): void {
    this.reload$.next();
  }

  protected openRegularize(): void {
    const selected = this.allRows().find((row) => this.selectedIds().has(row.id)) ?? null;
    const today = toIsoDate(new Date());
    const loadDate = selected?.attendanceDateIso || today;
    this.api
      .listDaily({
        date: loadDate,
        page: 1,
        pageSize: 200,
        statusTab: 'all',
        includePunches: false,
      })
      .pipe(
        catchError((err: unknown) => {
          this.snackBar.open(extractHttpError(err, 'Failed to load employees.'), 'OK', {
            duration: 4000,
          });
          return of(null);
        }),
      )
      .subscribe((page) => {
        if (!page) return;
        const employees: RegularizeEmployeeOption[] = page.items.map((row) => ({
          id: row.employeeId,
          employeeId: row.employeeId,
          employeeCode: row.employeeCode,
          employeeName: row.employeeName,
          department: row.department,
          avatarTone: AVATAR_TONES[Math.abs(row.employeeId) % AVATAR_TONES.length]!,
          firstIn: formatTime(row.firstIn),
          lastOut: formatTime(row.lastOut),
          status: row.status,
        }));

        let prefill: RegularizeEmployeeOption | null = null;
        if (selected) {
          prefill =
            employees.find((row) => row.id === selected.employeeId) ??
            ({
              id: selected.employeeId,
              employeeId: selected.employeeId,
              employeeCode: selected.employeeCode,
              employeeName: selected.employeeName,
              department: selected.department,
              avatarTone: selected.avatarTone,
              firstIn: selected.originalIn,
              lastOut: selected.originalOut,
            } satisfies RegularizeEmployeeOption);
          if (!employees.some((row) => row.id === prefill!.id)) {
            employees.unshift(prefill);
          }
        }

        this.dialog
          .open(AttendanceRegularizeDialog, {
            ...ATTENDANCE_REGULARIZE_DIALOG_OPTIONS,
            data: {
              employees,
              employee: prefill,
              attendanceDate: selected ? parseIsoDate(selected.attendanceDateIso) : new Date(),
              lockEmployee: false,
            },
          })
          .afterClosed()
          .pipe(filter((result): result is RegularizeSubmitResult => !!result))
          .subscribe((result) => this.submitRegularization(result));
      });
  }

  protected viewDetails(row: RegularizationListRow): void {
    this.dialog
      .open(AttendanceRegularizationDetailDialog, {
        ...ATTENDANCE_REGULARIZE_DIALOG_OPTIONS,
        data: { row },
      })
      .afterClosed()
      .subscribe((action: 'approve' | 'reject' | null | undefined) => {
        if (action === 'approve') this.approve(row);
        if (action === 'reject') this.reject(row);
      });
  }

  protected approve(row: RegularizationListRow): void {
    this.dialog
      .open(AttendanceRegularizationDecisionDialog, {
        ...ATTENDANCE_REGULARIZE_DIALOG_OPTIONS,
        data: { row, decision: 'approve' },
      })
      .afterClosed()
      .pipe(filter((result): result is RegularizationDecisionResult => !!result))
      .subscribe((result) => {
        const remark = result.reason?.trim();
        if (!remark) return;
        this.api
          .approveRegularization(row.id, remark)
          .pipe(
            catchError((err: unknown) => {
              this.snackBar.open(extractHttpError(err, 'Failed to approve request.'), 'OK', {
                duration: 4000,
              });
              return of(null);
            }),
          )
          .subscribe((saved) => {
            if (!saved) return;
            this.snackBar.open(`Approved request for ${row.employeeName}.`, 'OK', {
              duration: 2600,
            });
            this.reload$.next();
          });
      });
  }

  protected reject(row: RegularizationListRow): void {
    this.dialog
      .open(AttendanceRegularizationDecisionDialog, {
        ...ATTENDANCE_REGULARIZE_DIALOG_OPTIONS,
        data: { row, decision: 'reject' },
      })
      .afterClosed()
      .pipe(filter((result): result is RegularizationDecisionResult => !!result))
      .subscribe((result) => {
        const remark = result.reason?.trim();
        if (!remark) return;
        this.api
          .rejectRegularization(row.id, remark)
          .pipe(
            catchError((err: unknown) => {
              this.snackBar.open(extractHttpError(err, 'Failed to reject request.'), 'OK', {
                duration: 4000,
              });
              return of(null);
            }),
          )
          .subscribe((saved) => {
            if (!saved) return;
            this.snackBar.open(`Rejected request for ${row.employeeName}.`, 'OK', {
              duration: 2600,
            });
            this.reload$.next();
          });
      });
  }

  protected initials(name: string): string {
    return name
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('');
  }

  protected typeClass(type: RegularizationRequestType): string {
    switch (type) {
      case 'Missed Punch':
        return 'type missed';
      case 'Wrong Attendance':
        return 'type wrong';
      case 'Early Exit':
        return 'type early';
      case 'WFH Correction':
        return 'type wfh';
      case 'Late Arrival':
        return 'type late';
    }
  }

  protected statusClass(status: RegularizationListRow['status']): string {
    switch (status) {
      case 'Pending':
        return 'status pending';
      case 'Approved':
        return 'status approved';
      case 'Rejected':
        return 'status rejected';
    }
  }

  private submitRegularization(result: RegularizeSubmitResult): void {
    this.api
      .createRegularization({
        employeeId: result.employeeId,
        attendanceDate: result.attendanceDate,
        requestType: result.requestType,
        requestedIn: result.requestedIn,
        requestedOut: result.requestedOut,
        reason: result.reason,
        attachmentName: result.attachmentName,
      })
      .pipe(
        catchError((err: unknown) => {
          this.snackBar.open(extractHttpError(err, 'Failed to submit regularization.'), 'OK', {
            duration: 4000,
          });
          return of(null);
        }),
      )
      .subscribe((saved) => {
        if (!saved) return;
        this.contentTab.set('pending');
        this.page.set(0);
        this.snackBar.open(`Regularization submitted for ${saved.employeeName}.`, 'OK', {
          duration: 2800,
        });
        this.reload$.next();
      });
  }

  private loadRange$() {
    const start = this.rangeStart();
    const end = this.rangeEnd();
    if (!start || !end) {
      this.loading.set(false);
      return of(null);
    }

    const base = {
      from: toIsoDate(start),
      to: toIsoDate(end),
      pageSize: PAGE_SIZE,
      statusTab: this.contentTab(),
      search: this.search() || undefined,
      department: this.department() || undefined,
      location: this.location() || undefined,
      requestType: this.requestType() || undefined,
    };

    return this.api.listRegularizations({ ...base, page: 1 }).pipe(
      switchMap((first) => {
        const pages = Math.max(1, Math.ceil(first.total / Math.max(first.pageSize, 1)));
        if (pages <= 1) return of(first);
        const rest = Array.from({ length: pages - 1 }, (_, index) =>
          this.api.listRegularizations({ ...base, page: index + 2 }),
        );
        return forkJoin(rest).pipe(
          map((extra) => ({
            ...first,
            items: [...first.items, ...extra.flatMap((page) => page.items)],
          })),
        );
      }),
      tap((page) => this.applyPage(page)),
      catchError((err: unknown) => {
        this.allRows.set([]);
        this.kpi.set(EMPTY_KPI);
        this.departments.set([]);
        this.locations.set([]);
        this.snackBar.open(extractHttpError(err, 'Failed to load regularization requests.'), 'OK', {
          duration: 4000,
        });
        return of(null);
      }),
      finalize(() => this.loading.set(false)),
    );
  }

  private applyPage(result: RegularizationPage): void {
    this.kpi.set(mapKpi(result.summary));
    this.departments.set(result.filterOptions.departments);
    this.locations.set(result.filterOptions.locations);
    this.allRows.set(result.items.map(normalizeRow));
  }
}

function mapKpi(summary: ApiRegularizationKpi): RegularizationKpi {
  return {
    total: summary.total,
    pending: summary.pending,
    approved: summary.approved,
    rejected: summary.rejected,
  };
}

function normalizeRow(row: ApiRegularizationRow): RegularizationListRow {
  return {
    id: row.id,
    employeeId: row.employeeId,
    employeeCode: row.employeeCode,
    employeeName: row.employeeName,
    department: row.department,
    location: row.location,
    attendanceDate: formatDisplayDate(row.attendanceDate),
    attendanceDateIso: row.attendanceDate.slice(0, 10),
    requestType: row.requestType,
    originalIn: formatTime(row.originalIn),
    originalOut: formatTime(row.originalOut),
    requestedIn: row.requestedIn,
    requestedOut: row.requestedOut,
    reason: row.reason,
    submittedOn: formatSubmitted(row.submittedOn),
    status: row.status,
    avatarTone: AVATAR_TONES[Math.abs(row.employeeId || row.id) % AVATAR_TONES.length]!,
    attachmentName: row.attachmentName,
    rejectionReason: row.rejectionReason,
  };
}

function formatTime(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).format(date);
}

function formatDisplayDate(value: string): string {
  const date = parseIsoDate(value);
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(date);
}

function formatSubmitted(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).format(date);
}

function parseIsoDate(value: string): Date {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year!, (month ?? 1) - 1, day ?? 1);
}

function toIsoDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function extractHttpError(err: unknown, fallback: string): string {
  if (!(err instanceof HttpErrorResponse)) return fallback;
  const detail = (err.error as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (err.status === 0) return 'Unable to reach the API server.';
  if (err.status === 401 || err.status === 403) {
    return 'You do not have permission for attendance regularization.';
  }
  return err.message || fallback;
}
