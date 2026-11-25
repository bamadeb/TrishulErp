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
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatDatepicker, MatDatepickerInput } from '@angular/material/datepicker';
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
  AttendanceSummary,
  DailyAttendancePage,
  DailyAttendanceRow as ApiDailyAttendanceRow,
  FaceAttendanceApi,
  FacePunch,
  RegularizationRow,
} from '@trishul/hr-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
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
import { AttendanceDailyDrawer } from './attendance-daily.drawer';
import {
  ATTENDANCE_REGULARIZE_DIALOG_OPTIONS,
  AttendanceRegularizeData,
  AttendanceRegularizeDialog,
  RegularizeSubmitResult,
} from './attendance-regularize.dialog';
import {
  AttendanceKpi,
  AttendanceStatus,
  ContentTab,
  DailyAttendanceRow,
  RegularizationRequest,
} from './attendance.models';

const STATUS_ICON: Record<AttendanceStatus, string> = {
  Present: 'check_circle',
  Late: 'schedule',
  'Missing Punch': 'fingerprint',
  Absent: 'cancel',
  'On Leave': 'flight_takeoff',
  'Off Day': 'event_busy',
  Holiday: 'celebration',
  WFH: 'home',
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

const EMPTY_KPI: AttendanceKpi = {
  total: 0,
  present: 0,
  late: 0,
  absent: 0,
  onLeave: 0,
  wfh: 0,
};

const DAY_PAGE_SIZE = 200;

/** Daily Attendance — wired to GET /hr/attendance/daily (UI structure unchanged). */
@Component({
  selector: 'trishul-attendance-daily-page',
  imports: [
    DecimalPipe,
    FormsModule,
    MatButton,
    MatCheckbox,
    MatDatepicker,
    MatDatepickerInput,
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
    StatusBadge,
    AttendanceDailyDrawer,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-daily.page.html',
  styleUrl: './attendance-daily.page.scss',
})
export class AttendanceDailyPage implements OnInit {
  private readonly api = inject(AttendanceApi);
  private readonly faces = inject(FaceAttendanceApi);
  private readonly snackBar = inject(MatSnackBar);
  private readonly dialog = inject(MatDialog);
  private readonly destroyRef = inject(DestroyRef);
  private readonly picker = viewChild(MatDatepicker);
  private readonly reload$ = new Subject<void>();
  private readonly search$ = new Subject<string>();

  protected readonly severities: Partial<Record<string, StatusSeverity>> = {
    Present: 'success',
    Late: 'warn',
    'Missing Punch': 'warn',
    Absent: 'danger',
    'On Leave': 'info',
    'Off Day': 'info',
    Holiday: 'neutral',
    WFH: 'info',
    Pending: 'warn',
    Approved: 'success',
    Rejected: 'danger',
  };

  protected readonly regularization = signal<RegularizationRequest[]>([]);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  /** Plain object so existing template bindings (`kpi.total`) stay unchanged. */
  protected kpi: AttendanceKpi = EMPTY_KPI;
  protected readonly dayRows = signal<DailyAttendanceRow[]>([]);
  protected readonly departments = signal<string[]>([]);
  protected readonly locations = signal<string[]>([]);
  protected readonly shifts = signal<string[]>([]);

  protected readonly selectedDate = signal(new Date());
  protected readonly contentTab = signal<ContentTab>('records');
  protected readonly search = signal('');
  protected readonly department = signal('');
  protected readonly location = signal('');
  protected readonly shift = signal('');
  protected readonly page = signal(0);
  protected readonly pageSize = signal(10);
  protected readonly selectedIds = signal<Set<number>>(new Set());
  protected readonly punchRows = signal<FacePunch[]>([]);
  protected readonly punchLoading = signal(false);
  protected readonly punchError = signal<string | null>(null);
  protected readonly selected = signal<DailyAttendanceRow | null>(null);
  protected readonly menuRow = signal<DailyAttendanceRow | null>(null);

  protected readonly dateLabel = computed(() =>
    new Intl.DateTimeFormat('en-GB', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(this.selectedDate()),
  );

  protected readonly filteredRows = computed(() => {
    const tab = this.contentTab();
    return this.dayRows().filter((row) => {
      if (tab === 'exceptions') {
        return row.status === 'Late' || row.status === 'Absent' || row.status === 'Missing Punch';
      }
      return true;
    });
  });

  protected readonly filteredPunches = computed(() => {
    const q = this.search().trim().toLowerCase();
    const department = this.department();
    const location = this.location();
    return this.punchRows()
      .filter((row) => {
        if (department && (row.departmentName || '') !== department) return false;
        if (location && (row.branchName || '') !== location) return false;
        if (!q) return true;
        return `${row.employeeCode ?? ''} ${row.employeeName ?? ''}`.toLowerCase().includes(q);
      })
      .sort((a, b) => a.effectiveAt.localeCompare(b.effectiveAt) || a.id - b.id);
  });

  protected readonly punchDepartments = computed(() =>
    uniqueSorted(this.punchRows().map((row) => row.departmentName || '').filter(Boolean)),
  );

  protected readonly punchLocations = computed(() =>
    uniqueSorted(this.punchRows().map((row) => row.branchName || '').filter(Boolean)),
  );

  protected readonly punchPageRows = computed(() => {
    const start = this.page() * this.pageSize();
    return this.filteredPunches().slice(start, start + this.pageSize());
  });

  protected readonly total = computed(() => {
    if (this.contentTab() === 'punches') return this.filteredPunches().length;
    if (this.contentTab() === 'regularization') return this.regularization().length;
    return this.filteredRows().length;
  });

  protected readonly pageRows = computed(() => {
    const start = this.page() * this.pageSize();
    return this.filteredRows().slice(start, start + this.pageSize());
  });

  protected readonly pageRequests = computed(() => {
    const start = this.page() * this.pageSize();
    return this.regularization().slice(start, start + this.pageSize());
  });

  protected readonly allPageSelected = computed(() => {
    const rows = this.pageRows();
    return rows.length > 0 && rows.every((row) => this.selectedIds().has(row.id));
  });

  protected readonly somePageSelected = computed(() => {
    const rows = this.pageRows();
    const count = rows.filter((row) => this.selectedIds().has(row.id)).length;
    return count > 0 && count < rows.length;
  });

  ngOnInit(): void {
    this.reload$
      .pipe(
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
        }),
        switchMap(() => this.loadDay$()),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe();

    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed(this.destroyRef))
      .subscribe((value) => {
        this.search.set(value);
        this.page.set(0);
        if (this.contentTab() !== 'punches') this.reload$.next();
      });

    this.reload$.next();
  }

  protected statusIcon(status: AttendanceStatus): string {
    return STATUS_ICON[status] ?? 'info';
  }

  protected avatarColor(id: number): string {
    return avatarTone(id);
  }

  protected initials(name: string): string {
    return name
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('');
  }

  protected shiftDate(delta: number): void {
    const next = new Date(this.selectedDate());
    next.setDate(next.getDate() + delta);
    this.selectedDate.set(next);
    this.page.set(0);
    this.selectedIds.set(new Set());
    this.selected.set(null);
    this.reload$.next();
    this.loadPunches();
  }

  protected openPicker(): void {
    this.picker()?.open();
  }

  protected onDatePicked(value: Date | null): void {
    if (!value) return;
    this.selectedDate.set(value);
    this.page.set(0);
    this.selectedIds.set(new Set());
    this.selected.set(null);
    this.reload$.next();
    this.loadPunches();
  }

  protected setTab(tab: ContentTab): void {
    this.contentTab.set(tab);
    this.page.set(0);
    this.selectedIds.set(new Set());
    if (tab === 'punches') this.loadPunches();
  }

  protected onSearch(value: string): void {
    this.search$.next(value.trim());
  }

  protected onDepartment(value: string): void {
    this.department.set(value);
    this.page.set(0);
    if (this.contentTab() !== 'punches') this.reload$.next();
  }

  protected onLocation(value: string): void {
    this.location.set(value);
    this.page.set(0);
    if (this.contentTab() !== 'punches') this.reload$.next();
  }

  protected onShift(value: string): void {
    this.shift.set(value);
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
    const next = new Set(this.selectedIds());
    if (checked) next.add(id);
    else next.delete(id);
    this.selectedIds.set(next);
  }

  protected togglePage(checked: boolean): void {
    const next = new Set(this.selectedIds());
    for (const row of this.pageRows()) {
      if (checked) next.add(row.id);
      else next.delete(row.id);
    }
    this.selectedIds.set(next);
  }

  protected openDetails(row: DailyAttendanceRow): void {
    this.selected.set(row);
  }

  protected closeDetails(): void {
    this.selected.set(null);
  }

  protected refresh(): void {
    if (this.contentTab() === 'punches') {
      this.loadPunches();
      return;
    }
    this.reload$.next();
  }

  protected punchKind(row: FacePunch): 'IN' | 'OUT' {
    return row.punchType === 'Out' ? 'OUT' : 'IN';
  }

  protected punchClock(row: FacePunch): string {
    const date = new Date(row.effectiveAt);
    if (Number.isNaN(date.getTime())) return row.effectiveAt;
    return new Intl.DateTimeFormat('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    }).format(date);
  }

  protected punchDevice(row: FacePunch): string {
    const platform = (row.platform || '').toLowerCase();
    if (platform.includes('ios')) return 'iOS';
    if (platform.includes('android')) return 'Android';
    return row.platform || 'Mobile';
  }

  protected punchVerified(row: FacePunch): string {
    if (row.status === 'Present') return 'Verified';
    return row.status;
  }

  protected punchMap(row: FacePunch): string | null {
    if (row.latitude == null || row.longitude == null) return null;
    return `https://www.google.com/maps?q=${row.latitude},${row.longitude}`;
  }

  protected openPunchDetails(row: FacePunch): void {
    const history = this.punchRows()
      .filter((item) => item.employeeId === row.employeeId && item.attendanceDate === row.attendanceDate)
      .sort((a, b) => a.effectiveAt.localeCompare(b.effectiveAt));
    const firstIn = history.find((item) => item.punchType === 'In');
    const lastOut = [...history].reverse().find((item) => item.punchType === 'Out');
    this.selected.set({
      id: row.employeeId,
      employeeId: row.employeeId,
      employeeCode: row.employeeCode || '',
      employeeName: row.employeeName || '',
      department: row.departmentName || '—',
      location: row.branchName || row.workLocationName || '—',
      shift: '—',
      employeeType: '',
      reportingManager: '',
      firstIn: firstIn ? this.punchClock(firstIn) : null,
      lastOut: lastOut ? this.punchClock(lastOut) : null,
      firstInLate: false,
      workingHours: null,
      status: 'Present',
      remarks: this.punchVerified(row),
      avatarTone: avatarTone(row.employeeId),
      punches: history.map((item) => ({
        kind: this.punchKind(item),
        at: item.effectiveAt,
        device: `${this.punchDevice(item)} · ${this.punchVerified(item)}`,
        location:
          item.latitude != null && item.longitude != null
            ? {
                latitude: Number(item.latitude),
                longitude: Number(item.longitude),
                accuracyM: item.gpsAccuracyM != null ? Number(item.gpsAccuracyM) : null,
                place: item.workLocationName,
                insideOffice: item.insideGeofence,
                distanceM: item.distanceM != null ? Number(item.distanceM) : null,
                fakeGps: item.isMockLocation,
              }
            : null,
      })),
      history: [],
    });
  }

  private punchRequest = 0;

  private loadPunches(): void {
    const day = toIsoDate(this.selectedDate());
    const request = ++this.punchRequest;
    this.punchLoading.set(true);
    this.punchError.set(null);
    this.faces
      .listPunches({ fromDate: day, toDate: day, limit: 1000 })
      .pipe(
        catchError((err: unknown) => {
          if (request !== this.punchRequest) return of([] as FacePunch[]);
          const message =
            err instanceof HttpErrorResponse
              ? extractHttpError(err)
              : 'Failed to load punch logs.';
          this.punchRows.set([]);
          this.punchError.set(message);
          this.snackBar.open(message, 'OK', { duration: 4000 });
          return of([] as FacePunch[]);
        }),
        finalize(() => {
          if (request === this.punchRequest) this.punchLoading.set(false);
        }),
      )
      .subscribe((rows) => {
        if (request === this.punchRequest && !this.punchError()) this.punchRows.set(rows);
      });
  }

  protected exportExcel(): void {
    if (this.contentTab() === 'punches') {
      const punches = this.filteredPunches();
      if (!punches.length) {
        this.snackBar.open('No punch logs to export.', 'OK', { duration: 2200 });
        return;
      }
      downloadPunchCsv(`punch-logs-${toIsoDate(this.selectedDate())}.csv`, punches);
      this.snackBar.open(`Exported ${punches.length} punch log(s).`, 'OK', { duration: 2500 });
      return;
    }
    const rows = this.filteredRows();
    if (!rows.length) {
      this.snackBar.open('No attendance rows to export.', 'OK', { duration: 2200 });
      return;
    }
    downloadCsv(`daily-attendance-${toIsoDate(this.selectedDate())}.csv`, rows);
    this.snackBar.open(`Exported ${rows.length} attendance row(s).`, 'OK', { duration: 2500 });
  }

  protected regularize(row?: DailyAttendanceRow | null): void {
    const target = this.resolveRegularizeEmployee(row);
    const data: AttendanceRegularizeData = {
      employee: target,
      attendanceDate: this.selectedDate(),
      employees: this.dayRows(),
    };

    this.dialog
      .open(AttendanceRegularizeDialog, {
        ...ATTENDANCE_REGULARIZE_DIALOG_OPTIONS,
        data,
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
              { duration: 2800 },
            );
            this.reload$.next();
          });
      });
  }

  protected menuView(): void {
    const row = this.menuRow();
    if (row) this.openDetails(row);
  }

  protected menuRegularize(): void {
    this.regularize(this.menuRow());
  }

  private resolveRegularizeEmployee(
    row?: DailyAttendanceRow | null,
  ): DailyAttendanceRow | null {
    if (row) return row;
    const selectedIds = [...this.selectedIds()];
    if (selectedIds.length === 1) {
      return this.dayRows().find((item) => item.id === selectedIds[0]) ?? null;
    }
    return this.selected();
  }

  private loadDay$() {
    const date = toIsoDate(this.selectedDate());
    const base = {
      date,
      pageSize: DAY_PAGE_SIZE,
      statusTab: 'all' as const,
      includePunches: true,
      includeHistory: false,
      search: this.search() || undefined,
      department: this.department() || undefined,
      location: this.location() || undefined,
      shift: this.shift() || undefined,
    };

    const regs$ = this.api
      .listRegularizations({
        from: date,
        to: date,
        page: 1,
        pageSize: 200,
        statusTab: 'all',
      })
      .pipe(
        catchError(() =>
          of({
            items: [] as RegularizationRow[],
            total: 0,
            page: 1,
            pageSize: 200,
            pendingCount: 0,
            approvedCount: 0,
            rejectedCount: 0,
            dateFrom: date,
            dateTo: date,
            summary: { total: 0, pending: 0, approved: 0, rejected: 0 },
            filterOptions: { departments: [], locations: [], requestTypes: [] },
          }),
        ),
      );

    return forkJoin({
      daily: this.api.listDaily({ ...base, page: 1 }).pipe(
        switchMap((first) => {
          const pages = Math.max(1, Math.ceil(first.total / Math.max(first.pageSize, 1)));
          if (pages <= 1) return of(first);
          const rest = Array.from({ length: pages - 1 }, (_, index) =>
            this.api.listDaily({ ...base, page: index + 2 }),
          );
          return forkJoin(rest).pipe(
            map((extra) => ({
              ...first,
              items: [...first.items, ...extra.flatMap((page) => page.items)],
            })),
          );
        }),
      ),
      regs: regs$,
    }).pipe(
      tap(({ daily, regs }) => {
        this.applyPage(daily);
        this.regularization.set(
          regs.items.map((row) => ({
            id: row.id,
            employeeCode: row.employeeCode,
            employeeName: row.employeeName,
            date: formatDisplayDate(row.attendanceDate),
            reason: row.reason,
            status: row.status,
            avatarTone: avatarTone(row.employeeId || row.id),
          })),
        );
      }),
      catchError((err: unknown) => {
        const message =
          err instanceof HttpErrorResponse
            ? extractHttpError(err)
            : 'Failed to load daily attendance.';
        this.error.set(message);
        this.dayRows.set([]);
        this.regularization.set([]);
        this.kpi = EMPTY_KPI;
        this.snackBar.open(message, 'OK', { duration: 4000 });
        return of(null);
      }),
      finalize(() => this.loading.set(false)),
    );
  }

  private applyPage(page: DailyAttendancePage): void {
    this.kpi = mapKpi(page.summary);
    this.departments.set(page.filterOptions.departments);
    this.locations.set(page.filterOptions.locations);
    this.shifts.set(page.filterOptions.shifts);
    this.dayRows.set(page.items.map(normalizeRow));
    this.error.set(null);

    const selected = this.selected();
    if (selected) {
      const refreshed = this.dayRows().find((row) => row.id === selected.id) ?? null;
      this.selected.set(refreshed);
    }
  }
}

function mapKpi(summary: AttendanceSummary): AttendanceKpi {
  const presentOnly = Math.max(0, summary.present - summary.late - summary.missingPunch);
  return {
    total: summary.total,
    present: presentOnly,
    late: summary.late,
    absent: summary.absent,
    onLeave: summary.onLeave,
    // API has no WFH yet; keep the existing KPI card at zero.
    wfh: 0,
  };
}

function normalizeRow(row: ApiDailyAttendanceRow): DailyAttendanceRow {
  return {
    id: row.id,
    employeeId: row.employeeId,
    employeeCode: row.employeeCode,
    employeeName: row.employeeName,
    department: row.department,
    location: row.location,
    shift: row.shift,
    employeeType: row.employeeType,
    reportingManager: row.reportingManager,
    firstIn: formatTime(row.firstIn),
    lastOut: formatTime(row.lastOut),
    firstInLate: row.firstInLate,
    workingHours: row.workingHours,
    status: row.status,
    remarks: row.remarks,
    avatarTone: avatarTone(row.employeeId || row.id),
    punches: row.punches ?? [],
    history: (row.history ?? []).map((item) => ({
      date: item.date,
      status: item.status,
      firstIn: formatTime(item.firstIn),
      lastOut: formatTime(item.lastOut),
      workingHours: item.workingHours,
    })),
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

function avatarTone(id: number): string {
  return AVATAR_TONES[Math.abs(id) % AVATAR_TONES.length]!;
}

function toIsoDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function formatDisplayDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(date);
}

function downloadCsv(filename: string, rows: DailyAttendanceRow[]): void {
  const header = [
    'Emp ID',
    'Employee Name',
    'Department',
    'Location',
    'Shift',
    'In Time',
    'Out Time',
    'Worked Hours',
    'Status',
    'Remarks',
  ];
  const body = rows.map((row) =>
    [
      row.employeeCode,
      row.employeeName,
      row.department,
      row.location,
      row.shift,
      row.firstIn ?? '',
      row.lastOut ?? '',
      row.workingHours ?? '',
      row.status,
      row.remarks,
    ]
      .map(csvEscape)
      .join(','),
  );
  const blob = new Blob([[header.join(','), ...body].join('\n')], {
    type: 'text/csv;charset=utf-8',
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function uniqueSorted(values: string[]): string[] {
  return [...new Set(values)].sort((a, b) => a.localeCompare(b));
}

function downloadPunchCsv(filename: string, rows: FacePunch[]): void {
  const header = [
    'Employee ID',
    'Employee Name',
    'Punch Time',
    'IN/OUT',
    'Latitude',
    'Longitude',
    'GPS Accuracy (m)',
  ];
  const lines = [
    header.join(','),
    ...rows.map((row) =>
      [
        row.employeeCode || '',
        row.employeeName || '',
        row.effectiveAt,
        row.punchType === 'Out' ? 'OUT' : 'IN',
        row.latitude ?? '',
        row.longitude ?? '',
        row.gpsAccuracyM ?? '',
      ]
        .map((value) => csvEscape(String(value)))
        .join(','),
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

function csvEscape(value: string): string {
  if (/[",\n]/.test(value)) return `"${value.replaceAll('"', '""')}"`;
  return value;
}

function extractHttpError(err: HttpErrorResponse): string {
  const detail = err.error?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (err.status === 401) return 'Sign in required to load attendance.';
  if (err.status === 403) return 'You do not have permission to view attendance.';
  if (err.status === 0) return 'Cannot reach the API server.';
  return `Failed to load daily attendance (${err.status || 'error'}).`;
}
