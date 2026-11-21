import { DecimalPipe } from '@angular/common';
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
import { MatChip, MatChipRemove, MatChipSet } from '@angular/material/chips';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatDatepicker, MatDatepickerInput } from '@angular/material/datepicker';
import { MatFormField, MatLabel, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltip } from '@angular/material/tooltip';
import {
  AttendanceApi,
  DailyAttendancePage,
  DailyAttendanceRow as ApiDailyAttendanceRow,
} from '@trishul/hr-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import {
  Subject,
  catchError,
  debounceTime,
  distinctUntilChanged,
  finalize,
  map,
  of,
  switchMap,
  tap,
} from 'rxjs';
import { AttendanceDailyDrawer } from './attendance-daily.drawer';
import {
  ATTENDANCE_STATUSES,
  AttendanceHistoryItem,
  AttendanceKpi,
  AttendancePunch,
  AttendanceStatus,
  DailyAttendanceRow,
  StatusTab,
} from './attendance.models';

interface AdvancedFilters {
  department: string;
  location: string;
  shift: string;
  status: AttendanceStatus | '';
  employeeType: string;
  reportingManager: string;
}

interface FilterChip {
  key: keyof AdvancedFilters;
  label: string;
  value: string;
}

interface QueryState {
  date: string;
  page: number;
  pageSize: number;
  search: string;
  statusTab: StatusTab;
  filters: AdvancedFilters;
}

const EMPTY_FILTERS: AdvancedFilters = {
  department: '',
  location: '',
  shift: '',
  status: '',
  employeeType: '',
  reportingManager: '',
};

const EMPTY_KPI: AttendanceKpi = {
  total: 0,
  present: 0,
  absent: 0,
  onLeave: 0,
  offDay: 0,
  holiday: 0,
  late: 0,
  missingPunch: 0,
};

@Component({
  selector: 'trishul-attendance-daily-page',
  imports: [
    DecimalPipe,
    FormsModule,
    MatButton,
    MatCheckbox,
    MatChip,
    MatChipRemove,
    MatChipSet,
    MatDatepicker,
    MatDatepickerInput,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatInput,
    MatLabel,
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
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);
  private readonly query$ = new Subject<QueryState>();
  private readonly picker = viewChild(MatDatepicker);

  protected readonly statuses = ATTENDANCE_STATUSES;
  protected readonly severities: Partial<Record<string, StatusSeverity>> = {
    Present: 'success',
    Late: 'warn',
    'Missing Punch': 'warn',
    Absent: 'danger',
    'On Leave': 'info',
    'Off Day': 'info',
    Holiday: 'neutral',
  };

  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly rows = signal<DailyAttendanceRow[]>([]);
  protected readonly total = signal(0);
  protected readonly kpi = signal<AttendanceKpi>(EMPTY_KPI);
  protected readonly departments = signal<string[]>([]);
  protected readonly locations = signal<string[]>([]);
  protected readonly shifts = signal<string[]>([]);
  protected readonly employeeTypes = signal<string[]>([]);
  protected readonly managers = signal<string[]>([]);

  protected readonly selectedDate = signal(new Date());
  protected readonly statusTab = signal<StatusTab>('all');
  protected readonly search = signal('');
  protected readonly filtersOpen = signal(false);
  protected readonly draftFilters = signal<AdvancedFilters>({ ...EMPTY_FILTERS });
  protected readonly appliedFilters = signal<AdvancedFilters>({ ...EMPTY_FILTERS });
  protected readonly page = signal(0);
  protected readonly pageSize = signal(10);
  protected readonly selected = signal<DailyAttendanceRow | null>(null);
  protected readonly selectedIds = signal<ReadonlySet<number>>(new Set());
  protected readonly menuRow = signal<DailyAttendanceRow | null>(null);

  protected readonly pageRows = computed(() => this.rows());
  protected readonly filterChips = computed((): FilterChip[] => {
    const filters = this.appliedFilters();
    const chips: FilterChip[] = [];
    if (filters.department) chips.push({ key: 'department', label: 'Department', value: filters.department });
    if (filters.location) chips.push({ key: 'location', label: 'Location', value: filters.location });
    if (filters.shift) chips.push({ key: 'shift', label: 'Shift', value: filters.shift });
    if (filters.status) chips.push({ key: 'status', label: 'Status', value: filters.status });
    if (filters.employeeType) {
      chips.push({ key: 'employeeType', label: 'Employee Type', value: filters.employeeType });
    }
    if (filters.reportingManager) {
      chips.push({ key: 'reportingManager', label: 'Manager', value: filters.reportingManager });
    }
    return chips;
  });
  protected readonly activeFilterCount = computed(() => this.filterChips().length);
  protected readonly allPageSelected = computed(() => {
    const rows = this.pageRows();
    if (!rows.length) return false;
    const selected = this.selectedIds();
    return rows.every((row) => selected.has(row.id));
  });
  protected readonly somePageSelected = computed(() => {
    const rows = this.pageRows();
    const selected = this.selectedIds();
    return rows.some((row) => selected.has(row.id)) && !this.allPageSelected();
  });
  protected readonly dateLabel = computed(() =>
    this.selectedDate().toLocaleDateString('en-GB', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }),
  );
  protected readonly tabCounts = computed(() => {
    const kpi = this.kpi();
    return {
      all: kpi.total,
      present: kpi.present,
      absent: kpi.absent,
      leave: kpi.onLeave,
      offDay: kpi.offDay + kpi.holiday,
    };
  });

  ngOnInit(): void {
    this.query$
      .pipe(
        debounceTime(200),
        distinctUntilChanged((a, b) => JSON.stringify(a) === JSON.stringify(b)),
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
          this.rows.set([]);
        }),
        switchMap((query) =>
          this.api
            .listDaily({
              date: query.date,
              page: query.page + 1,
              pageSize: query.pageSize,
              search: query.search.trim() || undefined,
              statusTab: query.statusTab,
              department: query.filters.department || undefined,
              location: query.filters.location || undefined,
              shift: query.filters.shift || undefined,
              status: query.filters.status || undefined,
              employeeType: query.filters.employeeType || undefined,
              reportingManager: query.filters.reportingManager || undefined,
            })
            .pipe(
              map((page) => this.normalizePage(page)),
              catchError(() => {
                this.error.set('Daily attendance could not be loaded from the server.');
                return of({
                  rows: [] as DailyAttendanceRow[],
                  total: 0,
                  kpi: EMPTY_KPI,
                  departments: [] as string[],
                  locations: [] as string[],
                  shifts: [] as string[],
                  employeeTypes: [] as string[],
                  managers: [] as string[],
                });
              }),
              finalize(() => this.loading.set(false)),
            ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((page) => {
        this.rows.set(page.rows);
        this.total.set(page.total);
        this.kpi.set(page.kpi);
        this.departments.set(page.departments);
        this.locations.set(page.locations);
        this.shifts.set(page.shifts);
        this.employeeTypes.set(page.employeeTypes);
        this.managers.set(page.managers);
        const selected = this.selected();
        if (selected) {
          const next = page.rows.find((row) => row.id === selected.id) ?? null;
          this.selected.set(next);
        }
      });

    this.emitQuery();
  }

  protected shiftDate(days: number): void {
    const next = new Date(this.selectedDate());
    next.setDate(next.getDate() + days);
    this.selectedDate.set(next);
    this.selected.set(null);
    this.selectedIds.set(new Set());
    this.page.set(0);
    this.emitQuery();
  }

  protected onDatePicked(value: Date | null): void {
    if (!value) return;
    this.selectedDate.set(value);
    this.selected.set(null);
    this.selectedIds.set(new Set());
    this.page.set(0);
    this.emitQuery();
  }

  protected openPicker(): void {
    this.picker()?.open();
  }

  protected setStatusTab(tab: StatusTab): void {
    this.statusTab.set(tab);
    this.page.set(0);
    this.emitQuery();
  }

  protected onSearch(value: string): void {
    this.search.set(value);
    this.page.set(0);
    this.emitQuery();
  }

  protected toggleFilters(): void {
    if (!this.filtersOpen()) {
      this.draftFilters.set({ ...this.appliedFilters() });
    }
    this.filtersOpen.update((open) => !open);
  }

  protected closeFilters(): void {
    this.filtersOpen.set(false);
    this.draftFilters.set({ ...this.appliedFilters() });
  }

  protected updateDraft<K extends keyof AdvancedFilters>(key: K, value: AdvancedFilters[K]): void {
    this.draftFilters.update((current) => ({ ...current, [key]: value }));
  }

  protected applyFilters(): void {
    this.appliedFilters.set({ ...this.draftFilters() });
    this.filtersOpen.set(false);
    this.page.set(0);
    this.emitQuery();
  }

  protected resetFilters(): void {
    this.draftFilters.set({ ...EMPTY_FILTERS });
    this.appliedFilters.set({ ...EMPTY_FILTERS });
    this.page.set(0);
    this.emitQuery();
  }

  protected removeChip(key: keyof AdvancedFilters): void {
    this.appliedFilters.update((current) => ({ ...current, [key]: '' }));
    this.draftFilters.update((current) => ({ ...current, [key]: '' }));
    this.page.set(0);
    this.emitQuery();
  }

  protected onPage(event: PageEvent): void {
    this.page.set(event.pageIndex);
    this.pageSize.set(event.pageSize);
    this.emitQuery();
  }

  protected openDetails(row: DailyAttendanceRow): void {
    this.selected.set(row);
  }

  protected closeDetails(): void {
    this.selected.set(null);
  }

  protected isSelected(id: number): boolean {
    return this.selectedIds().has(id);
  }

  protected toggleRow(id: number, checked: boolean): void {
    this.selectedIds.update((current) => {
      const next = new Set(current);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  protected togglePage(checked: boolean): void {
    this.selectedIds.update((current) => {
      const next = new Set(current);
      for (const row of this.pageRows()) {
        if (checked) next.add(row.id);
        else next.delete(row.id);
      }
      return next;
    });
  }

  protected initials(name: string): string {
    return name
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('');
  }

  protected exportExcel(): void {
    const filters = this.appliedFilters();
    this.api
      .listDaily({
        date: toIsoDate(this.selectedDate()),
        page: 1,
        pageSize: 200,
        search: this.search().trim() || undefined,
        statusTab: this.statusTab(),
        department: filters.department || undefined,
        location: filters.location || undefined,
        shift: filters.shift || undefined,
        status: filters.status || undefined,
        employeeType: filters.employeeType || undefined,
        reportingManager: filters.reportingManager || undefined,
      })
      .subscribe({
        next: (page) => {
          const rows = page.items.map((row) => this.normalizeRow(row));
          downloadCsv(`daily-attendance-${toIsoDate(this.selectedDate())}.csv`, rows);
          this.snackBar.open(`Exported ${rows.length} attendance row(s).`, 'OK', { duration: 2500 });
        },
        error: () => {
          this.snackBar.open('Excel export failed. Try again.', 'OK', { duration: 3000 });
        },
      });
  }

  protected refresh(): void {
    this.page.set(0);
    this.emitQuery();
  }

  protected regularize(row: DailyAttendanceRow): void {
    this.snackBar.open(
      `Regularization for ${row.employeeName} is not enabled on this screen yet.`,
      'OK',
      { duration: 3000 },
    );
  }

  protected addRemark(row: DailyAttendanceRow): void {
    this.snackBar.open(
      `Remarks for ${row.employeeName}: ${row.remarks || 'none recorded for this date.'}`,
      'OK',
      { duration: 3500 },
    );
  }

  protected viewPunchLog(row: DailyAttendanceRow): void {
    this.selected.set(row);
  }

  protected menuView(): void {
    const row = this.menuRow();
    if (row) this.openDetails(row);
  }

  protected menuRegularize(): void {
    const row = this.menuRow();
    if (row) this.regularize(row);
  }

  protected menuRemark(): void {
    const row = this.menuRow();
    if (row) this.addRemark(row);
  }

  protected menuPunchLog(): void {
    const row = this.menuRow();
    if (row) this.viewPunchLog(row);
  }

  private emitQuery(): void {
    this.query$.next({
      date: toIsoDate(this.selectedDate()),
      page: this.page(),
      pageSize: this.pageSize(),
      search: this.search(),
      statusTab: this.statusTab(),
      filters: { ...this.appliedFilters() },
    });
  }

  private normalizePage(page: DailyAttendancePage) {
    return {
      rows: page.items.map((row) => this.normalizeRow(row)),
      total: page.total,
      kpi: {
        total: page.summary.total,
        present: page.summary.present,
        absent: page.summary.absent,
        onLeave: page.summary.onLeave,
        offDay: page.summary.offDay,
        holiday: page.summary.holiday,
        late: page.summary.late,
        missingPunch: page.summary.missingPunch,
      },
      departments: page.filterOptions.departments,
      locations: page.filterOptions.locations,
      shifts: page.filterOptions.shifts,
      employeeTypes: page.filterOptions.employeeTypes,
      managers: page.filterOptions.managers,
    };
  }

  private normalizeRow(row: ApiDailyAttendanceRow): DailyAttendanceRow {
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
      status: row.status as AttendanceStatus,
      remarks: row.remarks ?? '',
      punches: (row.punches ?? []).map(
        (punch): AttendancePunch => ({
          kind: punch.kind,
          at: formatTime(punch.at) ?? punch.at,
          device: punch.device,
        }),
      ),
      history: (row.history ?? []).map(
        (item): AttendanceHistoryItem => ({
          date: item.date,
          status: item.status as AttendanceStatus,
          firstIn: formatTime(item.firstIn),
          lastOut: formatTime(item.lastOut),
          workingHours: item.workingHours,
        }),
      ),
    };
  }
}

function toIsoDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function formatTime(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
}

function downloadCsv(filename: string, rows: DailyAttendanceRow[]): void {
  const header = [
    'Emp ID',
    'Employee Name',
    'Department',
    'Location',
    'Shift',
    'Employee Type',
    'Reporting Manager',
    'In Time',
    'Out Time',
    'Work Hours',
    'Status',
    'Remarks',
  ];
  const lines = [
    header.join(','),
    ...rows.map((row) =>
      [
        row.employeeCode,
        row.employeeName,
        row.department,
        row.location,
        row.shift,
        row.employeeType,
        row.reportingManager,
        row.firstIn ?? '',
        row.lastOut ?? '',
        row.workingHours ?? '',
        row.status,
        row.remarks,
      ]
        .map(csvEscape)
        .join(','),
    ),
  ];
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function csvEscape(value: string): string {
  if (/[",\n]/.test(value)) return `"${value.replace(/"/g, '""')}"`;
  return value;
}
