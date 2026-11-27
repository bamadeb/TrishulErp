import { DecimalPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  DestroyRef,
  HostListener,
  NgZone,
  OnInit,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatDateRangeInput, MatDateRangePicker, MatEndDate, MatStartDate } from '@angular/material/datepicker';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltip } from '@angular/material/tooltip';
import { ActivatedRoute } from '@angular/router';
import {
  AttendanceApi,
  AttendanceExceptionRow as ApiExceptionRow,
  AttendanceExceptionsList,
  DailyAttendanceRow as ApiDailyAttendanceRow,
  ExceptionKpi as ApiExceptionKpi,
  RegularizationRow,
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
  AttendanceExceptionResolveDialog,
  ExceptionResolveResult,
} from './attendance-exception-resolve.dialog';
import { AttendanceDailyDrawer } from './attendance-daily.drawer';
import { AttendanceRegularizeDrawer } from './attendance-regularize-drawer';
import { AttendanceShiftDrawer } from './attendance-shift.drawer';
import {
  AttendanceExceptionRow,
  AttendanceStatus,
  DailyAttendanceRow,
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

/** Attendance Exceptions — wired to GET /hr/attendance/exceptions (UI structure unchanged). */
@Component({
  selector: 'trishul-attendance-exceptions-page',
  imports: [
    DecimalPipe,
    FormsModule,
    MatButton,
    MatCheckbox,
    MatDateRangeInput,
    MatDateRangePicker,
    MatEndDate,
    MatFormField,
    MatStartDate,
    MatIcon,
    MatIconButton,
    MatInput,
    MatMenu,
    MatMenuItem,
    MatMenuTrigger,
    MatOption,
    MatPaginator,
    MatPrefix,
    MatProgressBar,
    MatSelect,
    MatTooltip,
    PageHeader,
    AttendanceDailyDrawer,
    AttendanceShiftDrawer,
    AttendanceRegularizeDrawer,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-exceptions.page.html',
  styleUrl: './attendance-exceptions.page.scss',
  providers: [provideNativeDateAdapter()],
})
export class AttendanceExceptionsPage implements OnInit {
  private readonly api = inject(AttendanceApi);
  private readonly rangePicker = viewChild(MatDateRangePicker);
  private readonly snackBar = inject(MatSnackBar);
  private readonly dialog = inject(MatDialog);
  private readonly destroyRef = inject(DestroyRef);
  private readonly route = inject(ActivatedRoute);
  private readonly zone = inject(NgZone);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly reload$ = new Subject<void>();
  private readonly search$ = new Subject<string>();
  private readonly detail$ = new Subject<AttendanceExceptionRow>();
  private ignoreOutsideClick = false;
  /** Cache regularizations by date range so tab/page changes don't refetch them. */
  private regsCacheKey: string | null = null;

  protected readonly kpi = signal<ExceptionKpi>(EMPTY_KPI);
  protected readonly rangeLabel = signal('');
  protected readonly error = signal<string | null>(null);
  protected readonly exceptionTypes = EXCEPTION_TYPES;
  protected readonly loading = signal(false);
  protected readonly allRows = signal<AttendanceExceptionRow[]>([]);
  protected readonly departments = signal<string[]>([]);
  protected readonly locations = signal<string[]>([]);
  protected readonly pendingCount = signal(0);
  protected readonly resolvedCount = signal(0);
  protected readonly serverTotal = signal(0);

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
  protected readonly regularizations = signal<RegularizationRow[]>([]);
  protected readonly regDrawerKeys = signal<number[]>([]);
  protected readonly regEmployeeId = signal<number | null>(null);
  protected readonly regDate = signal<string | null>(null);
  protected readonly regEmployees = computed(() =>
    uniqueEmployees(this.allRows()).map((row) => ({
      employeeId: row.employeeId,
      employeeCode: row.employeeCode,
      employeeName: row.employeeName,
    })),
  );
  protected readonly shiftFocus = signal<{
    name: string;
    employeeId: number;
    employeeName: string;
  } | null>(null);
  protected readonly detail = signal<DailyAttendanceRow | null>(null);
  protected readonly detailDate = signal<Date | null>(null);
  protected readonly detailException = signal<AttendanceExceptionRow | null>(null);

  protected readonly tabCounts = computed(() => ({
    all: this.kpi().total,
    pending: this.pendingCount(),
    resolved: this.resolvedCount(),
  }));

  protected readonly total = computed(() => this.serverTotal());

  /** The API already returns one page. Do not slice it again. */
  protected readonly pageRows = computed(() => this.allRows());

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
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
          // Keep prior rows visible until the new page arrives (avoids empty-table flash).
        }),
        switchMap(() => this.loadRange$()),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe();

    this.applyRouteRange();
    this.reload$.next();
    this.syncRangeLabel();

    this.detail$
      .pipe(
        switchMap((row) =>
          this.api
            .listDaily({
              date: row.dateIso,
              search: row.employeeCode,
              page: 1,
              pageSize: 20,
              statusTab: 'all',
              includePunches: true,
              includeHistory: false,
            })
            .pipe(
              map((page) => ({
                id: row.id,
                item: page.items.find((item) => item.employeeId === row.employeeId) ?? null,
              })),
              catchError(() => of({ id: row.id, item: null as ApiDailyAttendanceRow | null })),
            ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(({ id, item }) => {
        const current = this.detailException();
        if (!current || current.id !== id || !item) return;
        this.detail.set(toAttendanceRow(item, current));
        this.cdr.markForCheck();
      });
  }

  @HostListener('document:click', ['$event'])
  protected onDocumentClick(event: MouseEvent): void {
    if (!this.detail()) return;
    if (this.ignoreOutsideClick) {
      this.ignoreOutsideClick = false;
      return;
    }
    const target = event.target as HTMLElement | null;
    if (
      target?.closest(
        'trishul-attendance-daily-drawer, trishul-attendance-regularize-drawer, .name, [aria-label="View details"], .cdk-overlay-container',
      )
    ) {
      return;
    }
    this.closeDetails();
  }

  protected setTab(tab: ExceptionTab): void {
    const status: ExceptionReviewStatus | '' =
      tab === 'pending' ? 'Pending' : tab === 'resolved' ? 'Resolved' : '';
    if (tab === this.contentTab() && status === this.status()) return;
    this.contentTab.set(tab);
    this.status.set(status);
    this.page.set(0);
    this.selectedIds.set(new Set());
    this.reload$.next();
  }

  private applyRouteRange(): void {
    const from = this.route.snapshot.queryParamMap.get('from');
    const to = this.route.snapshot.queryParamMap.get('to');
    if (from) this.rangeStart.set(parseIsoDate(from));
    if (to) this.rangeEnd.set(parseIsoDate(to));
  }

  protected openRangePicker(): void {
    this.rangePicker()?.open();
  }

  protected onRangeStart(value: Date | null): void {
    if (!value || toIsoDate(value) === toIsoDate(this.rangeStart())) return;
    this.rangeStart.set(value);
    const end = this.rangeEnd();
    if (end && toIsoDate(value) <= toIsoDate(end)) this.applyPickedRange();
  }

  protected onRangeEnd(value: Date | null): void {
    if (!value || toIsoDate(value) === toIsoDate(this.rangeEnd())) return;
    this.rangeEnd.set(value);
    const start = this.rangeStart();
    if (start && toIsoDate(start) <= toIsoDate(value)) this.applyPickedRange();
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
    this.syncRangeLabel();
    this.page.set(0);
    this.selectedIds.set(new Set());
    this.reload$.next();
  }

  protected onSearch(value: string): void {
    this.search$.next(value);
  }

  protected onDepartment(value: string): void {
    const next = value ?? '';
    if (next === this.department()) return;
    this.department.set(next);
    this.page.set(0);
    this.reload$.next();
  }

  protected onLocation(value: string): void {
    const next = value ?? '';
    if (next === this.location()) return;
    this.location.set(next);
    this.page.set(0);
    this.reload$.next();
  }

  protected onExceptionType(value: ExceptionType | ''): void {
    const next = value ?? '';
    if (next === this.exceptionType()) return;
    this.exceptionType.set(next);
    this.page.set(0);
    this.reload$.next();
  }

  protected onStatus(value: ExceptionReviewStatus | ''): void {
    const next = value ?? '';
    if (next === this.status()) return;
    this.status.set(next);
    const tab: ExceptionTab =
      next === 'Pending' ? 'pending' : next === 'Resolved' ? 'resolved' : 'all';
    this.contentTab.set(tab);
    this.page.set(0);
    this.selectedIds.set(new Set());
    this.reload$.next();
  }

  protected onPage(event: PageEvent): void {
    if (event.pageIndex === this.page() && event.pageSize === this.pageSize()) return;
    this.page.set(event.pageIndex);
    this.pageSize.set(event.pageSize);
    this.selectedIds.set(new Set());
    this.reload$.next();
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
    const pageSize = 200;
    this.api
      .listExceptions(this.listQuery(1, pageSize))
      .pipe(
        switchMap((first) => {
          const items = Array.isArray(first?.items) ? first.items : [];
          const size = Math.max(first?.pageSize || pageSize, 1);
          const pages = Math.max(1, Math.ceil((first?.total || items.length) / size));
          if (pages <= 1) return of(items);
          const rest = Array.from({ length: pages - 1 }, (_, index) =>
            this.api.listExceptions(this.listQuery(index + 2, pageSize)),
          );
          return forkJoin(rest).pipe(
            map((extra) => [...items, ...extra.flatMap((page) => page.items ?? [])]),
          );
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (items) => {
          const rows = items
            .filter((row) => row.exceptionType !== ('Present' as ExceptionType))
            .map(normalizeRow);
          if (!rows.length) {
            this.snackBar.open('No exceptions to export.', 'OK', { duration: 2200 });
            return;
          }
          downloadCsv(
            `attendance-exceptions-${toIsoDate(this.rangeStart())}_${toIsoDate(this.rangeEnd())}.csv`,
            rows,
          );
          this.snackBar.open(`Exported ${rows.length} exception(s).`, 'OK', { duration: 2200 });
        },
        error: () => this.snackBar.open('Failed to export exceptions.', 'OK', { duration: 3000 }),
      });
  }

  /** Pending opens the regularization drawer. Resolved opens the daily attendance details. */
  protected openFromName(row: AttendanceExceptionRow): void {
    if (row.status === 'Resolved') {
      this.closeRegularize();
      this.viewDetails(row);
      return;
    }
    this.closeDetails();
    this.regEmployeeId.set(row.employeeId);
    this.regDate.set(row.dateIso);
    this.regDrawerKeys.set([Date.now()]);
  }

  protected regularize(row?: AttendanceExceptionRow | null): void {
    const selected = [...this.selectedIds()];
    const checked =
      selected.length === 1 ? this.allRows().find((item) => item.id === selected[0]) ?? null : null;
    const target = row ?? checked;
    if (target && this.regFor(target)) {
      this.viewDetails(target);
      return;
    }
    this.regEmployeeId.set(target?.employeeId ?? null);
    this.regDate.set(target?.dateIso ?? toIsoDate(this.rangeEnd()));
    this.regDrawerKeys.set([Date.now()]);
  }

  protected closeRegularize(): void {
    this.regDrawerKeys.set([]);
  }

  protected onRegularized(): void {
    this.regDrawerKeys.set([]);
    this.regsCacheKey = null;
    this.reload$.next();
  }

  protected regFor(row: AttendanceExceptionRow | null): RegularizationRow | null {
    if (!row) return null;
    const day = row.dateIso.slice(0, 10);
    const matches = this.regularizations().filter(
      (item) => item.employeeId === row.employeeId && item.attendanceDate.slice(0, 10) === day,
    );
    return (
      matches.find((item) => item.status === 'Approved') ??
      matches.find((item) => item.status === 'Pending') ??
      matches[0] ??
      null
    );
  }

  protected viewDetails(row?: AttendanceExceptionRow | null): void {
    const target = row ?? this.menuRow();
    if (!target) return;
    this.ignoreOutsideClick = true;
    this.shiftFocus.set(null);
    this.detailException.set(target);
    this.detailDate.set(parseIsoDate(target.dateIso));
    this.detail.set(attendanceFromException(target));
    this.detail$.next(target);
    queueMicrotask(() => {
      this.ignoreOutsideClick = false;
    });
  }

  protected closeDetails(): void {
    this.detail.set(null);
    this.detailDate.set(null);
    this.detailException.set(null);
  }

  protected openShift(row: AttendanceExceptionRow): void {
    const name = shiftDisplayName(row.shift);
    if (!name) return;
    this.closeDetails();
    this.shiftFocus.set({
      name,
      employeeId: row.employeeId,
      employeeName: row.employeeName,
    });
  }

  protected openShiftFromDetail(): void {
    const row = this.detailException();
    if (row) this.openShift(row);
  }

  protected closeShift(): void {
    this.shiftFocus.set(null);
  }

  protected shiftLabel(value: string): string {
    return shiftDisplayName(value);
  }

  protected resolve(row?: AttendanceExceptionRow | null): void {
    const target = row ?? this.menuRow();
    if (!target || target.status === 'Resolved') return;
    const requireStatus =
      target.exceptionType === 'Missing Punch' || target.exceptionType === 'Absent';
    this.dialog
      .open(AttendanceExceptionResolveDialog, {
        data: {
          employeeName: target.employeeName,
          exceptionType: target.exceptionType,
          date: target.date,
          requireStatus,
        },
        width: '28rem',
        maxWidth: '95vw',
        autoFocus: 'dialog',
      })
      .afterClosed()
      .pipe(filter((result): result is ExceptionResolveResult => !!result))
      .subscribe((choice) => {
        this.api
          .resolveException(target.id, choice.remark, choice.resolvedStatus)
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
            this.regsCacheKey = null;
            this.reload$.next();
          });
      });
  }

  protected initials(name: string | null | undefined): string {
    return (name || '')
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

  /** UI label for exception review status; API/DB value stays Pending | Resolved. */
  protected reviewLabel(status: ExceptionReviewStatus | string | null | undefined): string {
    if (status === 'Pending') return 'Unresolved';
    return status || '—';
  }

  protected statusClass(status: ExceptionReviewStatus): string {
    return status === 'Pending' ? 'status pending' : 'status resolved';
  }

  protected statusIcon(status: ExceptionReviewStatus): string {
    return status === 'Pending' ? 'hourglass_empty' : 'check_circle';
  }

  private loadRange$() {
    const from = toIsoDate(this.rangeStart());
    const to = toIsoDate(this.rangeEnd());
    const regsKey = `${from}|${to}`;
    const regs$ =
      this.regsCacheKey === regsKey && this.regularizations().length
        ? of({ items: this.regularizations() })
        : this.api.listRegularizations({ from, to, page: 1, pageSize: 200, statusTab: 'all' }).pipe(
            tap(() => {
              this.regsCacheKey = regsKey;
            }),
            catchError(() => {
              this.regsCacheKey = null;
              return of(null);
            }),
          );
    return forkJoin({
      page: this.api.listExceptions(this.listQuery(this.page() + 1, this.pageSize())),
      regs: regs$,
    }).pipe(
      tap(({ page, regs }) => {
        this.applyPage(page);
        if (regs?.items) this.regularizations.set(regs.items);
      }),
      catchError((err: unknown) => {
        const message =
          err instanceof HttpErrorResponse
            ? extractHttpError(err)
            : 'Failed to load attendance exceptions.';
        this.zone.run(() => {
          this.allRows.set([]);
          this.regularizations.set([]);
          this.serverTotal.set(0);
          this.kpi.set(EMPTY_KPI);
          this.pendingCount.set(0);
          this.resolvedCount.set(0);
          this.departments.set([]);
          this.locations.set([]);
          this.error.set(message);
          this.cdr.markForCheck();
        });
        this.snackBar.open(message, 'OK', { duration: 4000 });
        return of(null);
      }),
      finalize(() => {
        this.zone.run(() => this.loading.set(false));
      }),
    );
  }

  private listQuery(page: number, pageSize: number) {
    return {
      from: toIsoDate(this.rangeStart()),
      to: toIsoDate(this.rangeEnd()),
      page,
      pageSize,
      statusTab: this.contentTab(),
      search: this.search() || undefined,
      department: this.department() || undefined,
      location: this.location() || undefined,
      exceptionType: this.exceptionType() || undefined,
      status: this.status() || undefined,
    };
  }

  private applyPickedRange(): void {
    this.syncRangeLabel();
    this.page.set(0);
    this.selectedIds.set(new Set());
    this.closeDetails();
    this.regsCacheKey = null;
    this.reload$.next();
  }

  private syncRangeLabel(): void {
    const start = this.rangeStart();
    const end = this.rangeEnd();
    this.rangeLabel.set(`${formatDisplayDate(toIsoDate(start))} – ${formatDisplayDate(toIsoDate(end))}`);
  }

  private applyPage(result: AttendanceExceptionsList): void {
    this.zone.run(() => {
      const summary = result?.summary;
      const items = result?.items;
      if (!summary || !Array.isArray(items)) {
        this.error.set('The exceptions response could not be read.');
        this.kpi.set(EMPTY_KPI);
        this.allRows.set([]);
        this.serverTotal.set(0);
        this.cdr.markForCheck();
        return;
      }
      const total = numberOrZero(result.total);
      if (items.length === 0 && total > 0 && this.page() > 0) {
        this.serverTotal.set(total);
        this.page.set(0);
        this.reload$.next();
        return;
      }
      this.error.set(null);
      this.serverTotal.set(total);
      this.kpi.set(mapKpi(summary));
      this.pendingCount.set(numberOrZero(result.pendingCount));
      this.resolvedCount.set(numberOrZero(result.resolvedCount));
      this.departments.set(result.filterOptions?.departments ?? []);
      this.locations.set(result.filterOptions?.locations ?? []);
      if (result.dateFrom && result.dateTo) {
        this.rangeLabel.set(
          `${formatDisplayDate(String(result.dateFrom))} – ${formatDisplayDate(String(result.dateTo))}`,
        );
      }
      this.allRows.set(
        items
          .filter((row) => row.exceptionType !== ('Present' as ExceptionType))
          .map(normalizeRow),
      );
      this.cdr.markForCheck();
    });
  }
}

function shiftDisplayName(value: string | null | undefined): string {
  const name = (value ?? '').split('(')[0]?.trim() ?? '';
  return name === '—' || name === '-' ? '' : name;
}

function mapKpi(summary: ApiExceptionKpi): ExceptionKpi {
  const raw = summary as ApiExceptionKpi & Record<string, unknown>;
  return {
    total: numberOrZero(raw.total),
    missingPunch: numberOrZero(raw.missingPunch ?? raw['missing_punch']),
    lateArrival: numberOrZero(raw.lateArrival ?? raw['late_arrival']),
    earlyExit: numberOrZero(raw.earlyExit ?? raw['early_exit']),
    shortHours: numberOrZero(raw.shortHours ?? raw['short_hours']),
    absent: numberOrZero(raw.absent),
  };
}

function numberOrZero(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
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
    dateIso: String(row.date).slice(0, 10),
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

function attendanceFromException(row: AttendanceExceptionRow): DailyAttendanceRow {
  return {
    id: row.employeeId,
    employeeId: row.employeeId,
    employeeCode: row.employeeCode,
    employeeName: row.employeeName,
    department: row.department,
    location: row.location,
    shift: shiftDisplayName(row.shift) || row.shift,
    employeeType: '',
    reportingManager: '',
    firstIn: row.firstIn,
    lastOut: row.lastOut,
    firstInLate: row.exceptionType === 'Late Arrival',
    workingHours: row.actualHours,
    workingHoursDetail: null,
    currentPunch: null,
    currentPunchSince: null,
    requiredHours: null,
    shortfall: null,
    openInAt: null,
    closedWorkedMinutes: 0,
    status: attendanceStatusFor(row.exceptionType),
    remarks: row.remark,
    lateArrivalMinutes: null,
    earlyExitMinutes: null,
    avatarTone: row.avatarTone,
    punches: [],
    history: [],
  };
}

function toAttendanceRow(row: ApiDailyAttendanceRow, source: AttendanceExceptionRow): DailyAttendanceRow {
  return {
    id: row.id,
    employeeId: row.employeeId,
    employeeCode: row.employeeCode,
    employeeName: row.employeeName,
    department: row.department,
    location: row.location,
    shift: shiftDisplayName(row.shift) || row.shift,
    employeeType: row.employeeType,
    reportingManager: row.reportingManager,
    firstIn: formatTime(row.firstIn),
    lastOut: formatTime(row.lastOut),
    firstInLate: row.firstInLate,
    workingHours: row.workingHours,
    workingHoursDetail: row.workingHoursDetail ?? null,
    currentPunch: row.currentPunch ?? null,
    currentPunchSince: formatTime(row.currentPunchSince ?? null),
    requiredHours: row.requiredHours ?? null,
    shortfall: row.shortfall ?? null,
    openInAt: row.openInAt ?? null,
    closedWorkedMinutes: row.closedWorkedMinutes ?? 0,
    status: row.status,
    remarks: row.remarks,
    lateArrivalMinutes: row.lateArrivalMinutes ?? null,
    earlyExitMinutes: row.earlyExitMinutes ?? null,
    avatarTone: source.avatarTone,
    punches: row.punches ?? [],
    history: [],
  };
}

function attendanceStatusFor(type: ExceptionType): AttendanceStatus {
  switch (type) {
    case 'Absent':
      return 'Absent';
    case 'Late Arrival':
      return 'Late';
    case 'Missing Punch':
      return 'Missing Punch';
    default:
      return 'Present';
  }
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
        csv(row.status === 'Pending' ? 'Unresolved' : row.status),
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
