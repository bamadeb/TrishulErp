import { DecimalPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  DestroyRef,
  NgZone,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { MatFormField, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltip } from '@angular/material/tooltip';
import {
  AttendanceApi,
  MonthlyMusterPage,
  MusterEmployeeRow as ApiMusterEmployeeRow,
  MusterKpi,
} from '@trishul/hr-data-access';
import { PageHeader } from '@trishul/shared-ui';
import {
  Subject,
  catchError,
  debounceTime,
  distinctUntilChanged,
  finalize,
  forkJoin,
  map,
  of,
  switchMap,
  tap,
} from 'rxjs';
import {
  AttendanceKpi,
  MusterDayCode,
  MusterDayColumn,
  MusterEmployeeRow,
} from './attendance.models';

const MONTH_LABELS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
] as const;

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

const MUSTER_PAGE_SIZE = 200;

/** Monthly Muster — wired to GET /hr/attendance/muster (UI structure unchanged). */
@Component({
  selector: 'trishul-attendance-muster-page',
  imports: [
    DecimalPipe,
    FormsModule,
    MatButton,
    MatCheckbox,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatInput,
    MatOption,
    MatPaginator,
    MatPrefix,
    MatSelect,
    MatTooltip,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-muster.page.html',
  styleUrl: './attendance-muster.page.scss',
})
export class AttendanceMusterPage implements OnInit {
  private readonly api = inject(AttendanceApi);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);
  private readonly route = inject(ActivatedRoute);
  private readonly zone = inject(NgZone);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly reload$ = new Subject<void>();
  private readonly search$ = new Subject<string>();

  protected readonly kpi = signal<AttendanceKpi>(EMPTY_KPI);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly allRows = signal<MusterEmployeeRow[]>([]);
  protected readonly departments = signal<string[]>([]);
  protected readonly locations = signal<string[]>([]);

  private readonly now = new Date();
  protected readonly year = signal(this.now.getFullYear());
  protected readonly monthIndex = signal(this.now.getMonth());
  protected readonly search = signal('');
  protected readonly department = signal('');
  protected readonly location = signal('');
  protected readonly employmentStatus = signal<'Active' | 'Inactive' | ''>('Active');
  protected readonly page = signal(0);
  protected readonly pageSize = signal(10);
  protected readonly selectedIds = signal<Set<number>>(new Set());

  protected readonly monthLabel = computed(
    () => `${MONTH_LABELS[this.monthIndex()]!} ${this.year()}`,
  );

  protected readonly dayColumns = computed((): MusterDayColumn[] => {
    const year = this.year();
    const monthIndex = this.monthIndex();
    const count = new Date(year, monthIndex + 1, 0).getDate();
    return Array.from({ length: count }, (_, index) => {
      const day = index + 1;
      const weekday = weekdayLabel(year, monthIndex, day);
      return {
        day,
        weekday,
        isWeekend: weekday === 'Sun',
      };
    });
  });

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
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
        }),
        switchMap(() => this.loadMonth$()),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe();

    this.applyRouteMonth();
    this.reload$.next();
  }

  private applyRouteMonth(): void {
    const params = this.route.snapshot.queryParamMap;
    const year = Number(params.get('year'));
    const month = Number(params.get('month'));
    if (year >= 2000 && month >= 1 && month <= 12) {
      this.year.set(year);
      this.monthIndex.set(month - 1);
    }
    const department = params.get('department');
    const location = params.get('location');
    if (department) this.department.set(department);
    if (location) this.location.set(location);
  }

  protected shiftMonth(delta: number): void {
    const date = new Date(this.year(), this.monthIndex() + delta, 1);
    this.year.set(date.getFullYear());
    this.monthIndex.set(date.getMonth());
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

  protected onEmploymentStatus(value: 'Active' | 'Inactive' | ''): void {
    this.employmentStatus.set(value);
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
      this.snackBar.open('No muster rows to export.', 'OK', { duration: 2200 });
      return;
    }
    const columns = this.dayColumns();
    downloadCsv(
      `monthly-muster-${this.year()}-${String(this.monthIndex() + 1).padStart(2, '0')}.csv`,
      rows,
      columns,
    );
    this.snackBar.open(`Exported ${rows.length} muster row(s).`, 'OK', { duration: 2200 });
  }

  protected initials(name: string): string {
    return name
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('');
  }

  protected dayCode(row: MusterEmployeeRow, dayIndex: number): MusterDayCode {
    return row.days[dayIndex] ?? 'OFF';
  }

  protected dayLabel(code: MusterDayCode): string {
    return code === 'OFF' || code === 'H' ? '—' : code;
  }

  protected dayClass(code: MusterDayCode): string {
    switch (code) {
      case 'P':
        return 'mark present';
      case 'L':
        return 'mark late';
      case 'A':
        return 'mark absent';
      case 'PL':
        return 'mark leave';
      case 'WFH':
        return 'mark wfh';
      case 'H':
        return 'mark holiday';
      default:
        return 'mark off';
    }
  }

  private loadMonth$() {
    const year = this.year();
    const month = this.monthIndex() + 1;
    const base = {
      year,
      month,
      pageSize: MUSTER_PAGE_SIZE,
      search: this.search() || undefined,
      department: this.department() || undefined,
      location: this.location() || undefined,
      employmentStatus: this.employmentStatus() || undefined,
    };

    return this.api.listMuster({ ...base, page: 1 }).pipe(
      switchMap((first) => {
        const pages = Math.max(1, Math.ceil(first.total / Math.max(first.pageSize, 1)));
        if (pages <= 1) return of(first);
        const rest = Array.from({ length: pages - 1 }, (_, index) =>
          this.api.listMuster({ ...base, page: index + 2 }),
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
            : 'Failed to load monthly muster.';
        this.zone.run(() => {
          this.error.set(message);
          this.allRows.set([]);
          this.kpi.set(EMPTY_KPI);
          this.departments.set([]);
          this.locations.set([]);
          this.snackBar.open(message, 'OK', { duration: 4000 });
          this.cdr.markForCheck();
        });
        return of(null);
      }),
      finalize(() => {
        this.zone.run(() => {
          this.loading.set(false);
          this.cdr.markForCheck();
        });
      }),
    );
  }

  private applyPage(page: MonthlyMusterPage): void {
    this.zone.run(() => {
      this.kpi.set(mapKpi(page.summary));
      this.departments.set(page.filterOptions?.departments ?? []);
      this.locations.set(page.filterOptions?.locations ?? []);
      this.allRows.set((page.items ?? []).map(normalizeRow));
      this.error.set(null);
      this.cdr.markForCheck();
    });
  }
}

function mapKpi(summary: MusterKpi): AttendanceKpi {
  return {
    total: summary.total,
    present: summary.present,
    late: summary.late,
    absent: summary.absent,
    onLeave: summary.onLeave,
    wfh: summary.wfh,
  };
}

function normalizeRow(row: ApiMusterEmployeeRow): MusterEmployeeRow {
  return {
    id: row.id,
    employeeCode: row.employeeCode,
    employeeName: row.employeeName,
    department: row.department,
    location: row.location,
    employmentStatus: row.employmentStatus,
    avatarTone: AVATAR_TONES[Math.abs(row.employeeId || row.id) % AVATAR_TONES.length]!,
    days: row.days,
    present: row.present,
    late: row.late,
    absent: row.absent,
    leave: row.leave,
    wfh: row.wfh,
    hours: row.hours,
  };
}

function weekdayLabel(year: number, monthIndex: number, day: number): string {
  return new Intl.DateTimeFormat('en-US', { weekday: 'short' }).format(
    new Date(year, monthIndex, day),
  );
}

function extractHttpError(err: HttpErrorResponse): string {
  const detail = (err.error as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (err.status === 0) return 'Unable to reach the API server.';
  if (err.status === 401 || err.status === 403) return 'You do not have permission to view attendance.';
  return err.message || 'Failed to load monthly muster.';
}

function downloadCsv(
  filename: string,
  rows: MusterEmployeeRow[],
  columns: MusterDayColumn[],
): void {
  const header = [
    'Emp ID',
    'Employee Name',
    'Department',
    'Location',
    'Status',
    ...columns.map((col) => `${String(col.day).padStart(2, '0')} ${col.weekday}`),
    'P',
    'L',
    'A',
    'PL',
    'WFH',
    'Hrs',
  ];
  const lines = [
    header.join(','),
    ...rows.map((row) =>
      [
        csv(row.employeeCode),
        csv(row.employeeName),
        csv(row.department),
        csv(row.location),
        csv(row.employmentStatus),
        ...row.days.map((code) => csv(code)),
        row.present,
        row.late,
        row.absent,
        row.leave,
        row.wfh,
        row.hours,
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
