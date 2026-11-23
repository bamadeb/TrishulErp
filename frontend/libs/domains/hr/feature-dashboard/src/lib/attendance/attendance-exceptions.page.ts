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
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltip } from '@angular/material/tooltip';
import {
  AttendanceApi,
  AttendanceExceptionRow as ApiExceptionRow,
  AttendanceExceptionsList,
  ExceptionKpi as ApiExceptionKpi,
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
  AttendanceRegularizeDialog,
  RegularizeSubmitResult,
} from './attendance-regularize.dialog';
import {
  AttendanceExceptionRow,
  EXCEPTION_TYPES,
  ExceptionKpi,
  ExceptionReviewStatus,
  ExceptionTab,
  ExceptionType,
} from './attendance.models';

const TYPE_ICON: Record<ExceptionType, string> = {
  'Missing Punch': 'fingerprint',
  'Late Arrival': 'schedule',
  'Early Exit': 'logout',
  'Short Hours': 'timer',
  Absent: 'person_off',
};

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

const EMPTY_KPI: ExceptionKpi = {
  total: 0,
  missingPunch: 0,
  lateArrival: 0,
  earlyExit: 0,
  shortHours: 0,
  absent: 0,
};

const PAGE_SIZE = 200;

/** Attendance Exceptions — wired to GET /hr/attendance/exceptions (UI structure unchanged). */
@Component({
  selector: 'trishul-attendance-exceptions-page',
  imports: [
    DecimalPipe,
    FormsModule,
    MatButton,
    MatCheckbox,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatInput,
    MatMenu,
    MatMenuItem,
    MatMenuTrigger,
    MatOption,
    MatPaginator,
    MatPrefix,
    MatSelect,
    MatTooltip,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-exceptions.page.html',
  styleUrl: './attendance-exceptions.page.scss',
})
export class AttendanceExceptionsPage implements OnInit {
  private readonly api = inject(AttendanceApi);
  private readonly snackBar = inject(MatSnackBar);
  private readonly dialog = inject(MatDialog);
  private readonly destroyRef = inject(DestroyRef);
  private readonly reload$ = new Subject<void>();
  private readonly search$ = new Subject<string>();

  protected kpi: ExceptionKpi = EMPTY_KPI;
  protected rangeLabel = '';
  protected readonly exceptionTypes = EXCEPTION_TYPES;
  protected readonly loading = signal(false);
  protected readonly allRows = signal<AttendanceExceptionRow[]>([]);
  protected readonly departments = signal<string[]>([]);
  protected readonly locations = signal<string[]>([]);
  protected readonly pendingCount = signal(0);
  protected readonly resolvedCount = signal(0);

  private readonly now = new Date();
  protected readonly rangeStart = signal(new Date(this.now.getFullYear(), this.now.getMonth(), 1));
  protected readonly rangeEnd = signal(
    new Date(this.now.getFullYear(), this.now.getMonth(), this.now.getDate()),
  );

  protected readonly contentTab = signal<ExceptionTab>('all');
  protected readonly search = signal('');
  protected readonly department = signal('');
  protected readonly location = signal('');
  protected readonly exceptionType = signal<ExceptionType | ''>('');
  protected readonly status = signal<ExceptionReviewStatus | ''>('');
  protected readonly page = signal(0);
  protected readonly pageSize = signal(10);
  protected readonly selectedIds = signal<Set<number>>(new Set());
  protected readonly menuRow = signal<AttendanceExceptionRow | null>(null);

  protected readonly tabCounts = computed(() => ({
    all: this.kpi.total,
    pending: this.pendingCount(),
    resolved: this.resolvedCount(),
  }));

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

    this.reload$.next();
  }

  protected setTab(tab: ExceptionTab): void {
    this.contentTab.set(tab);
    this.page.set(0);
    this.reload$.next();
  }

  protected shiftRange(delta: number): void {
    const start = this.rangeStart();
    const next = new Date(start.getFullYear(), start.getMonth() + delta, 1);
    const endOfMonth = new Date(next.getFullYear(), next.getMonth() + 1, 0);
    const today = new Date();
    const end =
      next.getFullYear() === today.getFullYear() && next.getMonth() === today.getMonth()
        ? today
        : endOfMonth;
    this.rangeStart.set(next);
    this.rangeEnd.set(end);
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

  protected onExceptionType(value: ExceptionType | ''): void {
    this.exceptionType.set(value);
    this.page.set(0);
    this.reload$.next();
  }

  protected onStatus(value: ExceptionReviewStatus | ''): void {
    this.status.set(value);
    this.page.set(0);
    this.reload$.next();
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

  protected exportExcel(): void {
    const rows = this.filtered();
    if (!rows.length) {
      this.snackBar.open('No exceptions to export.', 'OK', { duration: 2200 });
      return;
    }
    downloadCsv(
      `attendance-exceptions-${toIsoDate(this.rangeStart())}_${toIsoDate(this.rangeEnd())}.csv`,
      rows,
    );
    this.snackBar.open(`Exported ${rows.length} exception(s).`, 'OK', { duration: 2200 });
  }

  protected regularize(row?: AttendanceExceptionRow | null): void {
    const target = row ?? this.menuRow();
    this.dialog
      .open(AttendanceRegularizeDialog, {
        data: {
          employee: target
            ? {
                id: target.employeeId,
                employeeCode: target.employeeCode,
                employeeName: target.employeeName,
                department: target.department,
                avatarTone: target.avatarTone,
                firstIn: target.firstIn,
                lastOut: target.lastOut,
                status: target.exceptionType,
              }
            : null,
          employees: uniqueEmployees(this.allRows()).map((item) => ({
            id: item.employeeId,
            employeeCode: item.employeeCode,
            employeeName: item.employeeName,
            department: item.department,
            avatarTone: item.avatarTone,
            firstIn: item.firstIn,
            lastOut: item.lastOut,
            status: item.exceptionType,
          })),
          attendanceDate: target ? parseDisplayDate(target.date) : this.rangeEnd(),
        },
        width: '36rem',
        maxWidth: '95vw',
        autoFocus: 'dialog',
        panelClass: 'attendance-regularize-panel',
      })
      .afterClosed()
      .pipe(filter((result): result is RegularizeSubmitResult => !!result))
      .subscribe((result) => {
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
              const message =
                err instanceof HttpErrorResponse
                  ? extractHttpError(err)
                  : 'Failed to submit regularization.';
              this.snackBar.open(message, 'OK', { duration: 4000 });
              return of(null);
            }),
          )
          .subscribe((saved) => {
            if (!saved) return;
            this.snackBar.open(
              `Regularization submitted for ${saved.employeeName}.`,
              'OK',
              { duration: 2500 },
            );
          });
      });
  }

  protected viewDetails(row?: AttendanceExceptionRow | null): void {
    const target = row ?? this.menuRow();
    if (!target) return;
    this.snackBar.open(
      `${target.employeeName}: ${target.exceptionType} · ${target.remark || 'No remark'}`,
      'OK',
      { duration: 4000 },
    );
  }

  protected resolve(row?: AttendanceExceptionRow | null): void {
    const target = row ?? this.menuRow();
    if (!target || target.status === 'Resolved') return;
    this.api
      .resolveException(target.id, 'Resolved from Attendance Exceptions')
      .pipe(
        catchError((err: unknown) => {
          const message =
            err instanceof HttpErrorResponse
              ? extractHttpError(err)
              : 'Failed to resolve exception.';
          this.snackBar.open(message, 'OK', { duration: 4000 });
          return of(null);
        }),
      )
      .subscribe((result) => {
        if (!result) return;
        this.snackBar.open(`Resolved exception for ${target.employeeName}.`, 'OK', {
          duration: 2600,
        });
        this.reload$.next();
      });
  }

  protected initials(name: string): string {
    return name
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('');
  }

  protected typeIcon(type: ExceptionType): string {
    return TYPE_ICON[type];
  }

  protected typeClass(type: ExceptionType): string {
    switch (type) {
      case 'Missing Punch':
        return 'type missing';
      case 'Late Arrival':
        return 'type late';
      case 'Early Exit':
        return 'type early';
      case 'Short Hours':
        return 'type short';
      case 'Absent':
        return 'type absent';
    }
  }

  protected statusClass(status: ExceptionReviewStatus): string {
    return status === 'Pending' ? 'status pending' : 'status resolved';
  }

  protected statusIcon(status: ExceptionReviewStatus): string {
    return status === 'Pending' ? 'hourglass_empty' : 'check_circle';
  }

  private loadRange$() {
    const base = {
      from: toIsoDate(this.rangeStart()),
      to: toIsoDate(this.rangeEnd()),
      pageSize: PAGE_SIZE,
      statusTab: this.contentTab(),
      search: this.search() || undefined,
      department: this.department() || undefined,
      location: this.location() || undefined,
      exceptionType: this.exceptionType() || undefined,
      status: this.status() || undefined,
    };

    return this.api.listExceptions({ ...base, page: 1 }).pipe(
      switchMap((first) => {
        const pages = Math.max(1, Math.ceil(first.total / Math.max(first.pageSize, 1)));
        if (pages <= 1) return of(first);
        const rest = Array.from({ length: pages - 1 }, (_, index) =>
          this.api.listExceptions({ ...base, page: index + 2 }),
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
        const message =
          err instanceof HttpErrorResponse
            ? extractHttpError(err)
            : 'Failed to load attendance exceptions.';
        this.allRows.set([]);
        this.kpi = EMPTY_KPI;
        this.pendingCount.set(0);
        this.resolvedCount.set(0);
        this.departments.set([]);
        this.locations.set([]);
        this.snackBar.open(message, 'OK', { duration: 4000 });
        return of(null);
      }),
      finalize(() => this.loading.set(false)),
    );
  }

  private applyPage(result: AttendanceExceptionsList): void {
    this.kpi = mapKpi(result.summary);
    this.pendingCount.set(result.pendingCount);
    this.resolvedCount.set(result.resolvedCount);
    this.departments.set(result.filterOptions.departments);
    this.locations.set(result.filterOptions.locations);
    this.rangeLabel = `${formatDisplayDate(result.dateFrom)} – ${formatDisplayDate(result.dateTo)}`;
    this.allRows.set(result.items.map(normalizeRow));
  }
}

function mapKpi(summary: ApiExceptionKpi): ExceptionKpi {
  return {
    total: summary.total,
    missingPunch: summary.missingPunch,
    lateArrival: summary.lateArrival,
    earlyExit: summary.earlyExit,
    shortHours: summary.shortHours,
    absent: summary.absent,
  };
}

function normalizeRow(row: ApiExceptionRow): AttendanceExceptionRow {
  return {
    id: row.id,
    employeeId: row.employeeId,
    employeeCode: row.employeeCode,
    employeeName: row.employeeName,
    department: row.department,
    location: row.location,
    date: formatDisplayDate(row.date),
    shift: row.shift,
    firstIn: formatTime(row.firstIn),
    lastOut: formatTime(row.lastOut),
    exceptionType: row.exceptionType,
    expectedHours: row.expectedHours,
    actualHours: row.actualHours,
    status: row.status,
    avatarTone: AVATAR_TONES[Math.abs(row.employeeId || row.id) % AVATAR_TONES.length]!,
    remark: row.remark,
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

function parseIsoDate(value: string): Date {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year!, (month ?? 1) - 1, day ?? 1);
}

function parseDisplayDate(value: string): Date {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? new Date() : parsed;
}

function toIsoDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function extractHttpError(err: HttpErrorResponse): string {
  const detail = (err.error as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (err.status === 0) return 'Unable to reach the API server.';
  if (err.status === 401 || err.status === 403) {
    return 'You do not have permission to view attendance exceptions.';
  }
  if (err.status === 404) return 'No attendance record found to resolve this exception.';
  return err.message || 'Failed to load attendance exceptions.';
}

function downloadCsv(filename: string, rows: AttendanceExceptionRow[]): void {
  const header = [
    'Emp ID',
    'Employee Name',
    'Department',
    'Location',
    'Date',
    'Shift',
    'In Time',
    'Out Time',
    'Exception Type',
    'Expected Hours',
    'Actual Hours',
    'Status',
    'Remark',
  ];
  const lines = [
    header.join(','),
    ...rows.map((row) =>
      [
        csv(row.employeeCode),
        csv(row.employeeName),
        csv(row.department),
        csv(row.location),
        csv(row.date),
        csv(row.shift),
        csv(row.firstIn ?? ''),
        csv(row.lastOut ?? ''),
        csv(row.exceptionType),
        csv(row.expectedHours),
        csv(row.actualHours ?? ''),
        csv(row.status),
        csv(row.remark),
      ].join(','),
    ),
  ];
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function csv(value: string): string {
  if (/[",\n]/.test(value)) return `"${value.replace(/"/g, '""')}"`;
  return value;
}

function uniqueEmployees(rows: AttendanceExceptionRow[]): AttendanceExceptionRow[] {
  const seen = new Set<number>();
  const result: AttendanceExceptionRow[] = [];
  for (const row of rows) {
    if (seen.has(row.employeeId)) continue;
    seen.add(row.employeeId);
    result.push(row);
  }
  return result;
}
