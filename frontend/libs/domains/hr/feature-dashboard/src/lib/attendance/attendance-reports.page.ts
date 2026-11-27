import { DecimalPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatIconButton } from '@angular/material/button';
import { MatFormField, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { RouterLink } from '@angular/router';
import {
  AttendanceApi,
  AttendanceExceptionRow,
  AttendanceReportsSummary,
  DailyAttendanceRow,
  MusterEmployeeRow,
  RegularizationRow,
} from '@trishul/hr-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { forkJoin, of } from 'rxjs';
import { catchError, map, switchMap } from 'rxjs/operators';

const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];

type ReportType = 'Daily' | 'Monthly' | 'Exceptions' | 'Payroll';
type ExportFormat = 'csv' | 'xlsx';
type SheetCell = string | number;
interface ReportSheet {
  headers: string[];
  rows: SheetCell[][];
}
type ReportExport = 'summary' | 'muster' | 'absent' | 'hours' | 'daily' | 'shift' | 'late' | 'missing' | 'exceptions' | 'regularization';

interface AttendanceReport {
  id: string;
  name: string;
  description: string;
  type: ReportType;
  icon: string;
  tone: string;
  route: string;
  export: ReportExport;
}

const REPORTS: AttendanceReport[] = [
  {
    id: 'muster',
    name: 'Monthly Attendance Muster',
    description: 'Employee-wise monthly attendance (P, A, L, WO, H).',
    type: 'Monthly',
    icon: 'calendar_month',
    tone: 'violet',
    route: '/hr/attendance/monthly-muster',
    export: 'muster',
  },
  {
    id: 'summary',
    name: 'Attendance Summary',
    description: 'Consolidated attendance for the selected period.',
    type: 'Monthly',
    icon: 'summarize',
    tone: 'blue',
    route: '/hr/attendance/monthly-muster',
    export: 'summary',
  },
  {
    id: 'daily',
    name: 'Daily Attendance Report',
    description: 'Daily IN/OUT, working hours and attendance status.',
    type: 'Daily',
    icon: 'event_available',
    tone: 'blue',
    route: '/hr/attendance/daily',
    export: 'daily',
  },
  {
    id: 'late',
    name: 'Late In & Early Out Report',
    description: 'Employees who arrived late or left early.',
    type: 'Daily',
    icon: 'schedule',
    tone: 'orange',
    route: '/hr/attendance/exceptions',
    export: 'late',
  },
  {
    id: 'missing',
    name: 'Missing Punch Report',
    description: 'Employees with incomplete punch records (IN or OUT missing).',
    type: 'Daily',
    icon: 'error',
    tone: 'red',
    route: '/hr/attendance/exceptions',
    export: 'missing',
  },
  {
    id: 'absent',
    name: 'Absent Report',
    description: 'Employee-wise absence details for the selected period.',
    type: 'Monthly',
    icon: 'person_off',
    tone: 'pink',
    route: '/hr/attendance/monthly-muster',
    export: 'absent',
  },
  {
    id: 'regularization',
    name: 'Attendance Regularization Report',
    description: 'Pending, approved and rejected regularization requests.',
    type: 'Exceptions',
    icon: 'fact_check',
    tone: 'green',
    route: '/hr/attendance/regularization',
    export: 'regularization',
  },
  {
    id: 'exceptions',
    name: 'Attendance Exception Report',
    description: 'Open and resolved attendance exceptions.',
    type: 'Exceptions',
    icon: 'warning',
    tone: 'amber',
    route: '/hr/attendance/exceptions',
    export: 'exceptions',
  },
  {
    id: 'hours',
    name: 'Work Hours Report',
    description: 'Actual working hours, shortfall and overtime details.',
    type: 'Payroll',
    icon: 'schedule',
    tone: 'green',
    route: '/hr/attendance/monthly-muster',
    export: 'hours',
  },
  {
    id: 'shift',
    name: 'Shift-wise Attendance Report',
    description: 'Attendance grouped by shift with Present, Absent and Leave.',
    type: 'Monthly',
    icon: 'more_time',
    tone: 'violet',
    route: '/hr/attendance/daily',
    export: 'shift',
  },
];

const QUICK_LINKS = [
  { label: 'Daily Attendance', route: '/hr/attendance/daily' },
  { label: 'Exceptions', route: '/hr/attendance/exceptions' },
  { label: 'Regularization', route: '/hr/attendance/regularization' },
  { label: 'Monthly Muster', route: '/hr/attendance/monthly-muster' },
  { label: 'Attendance Finalization', route: '/hr/attendance/finalization' },
];

/** Attendance Reports — summary + CSV exports from existing muster/exception APIs. */
@Component({
  selector: 'trishul-attendance-reports-page',
  imports: [
    DecimalPipe,
    FormsModule,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatInput,
    MatMenu,
    MatMenuItem,
    MatMenuTrigger,
    MatOption,
    MatPrefix,
    MatSelect,
    PageHeader,
    RouterLink,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-reports.page.html',
  styleUrl: './attendance-reports.page.scss',
})
export class AttendanceReportsPage implements OnInit {
  private readonly api = inject(AttendanceApi);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly months = MONTHS;
  protected readonly years = [2026, 2025, 2024];
  protected readonly year = signal(new Date().getFullYear());
  protected readonly monthIndex = signal(new Date().getMonth());
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly summary = signal<AttendanceReportsSummary | null>(null);
  protected readonly exporting = signal(false);
  protected readonly reports = REPORTS;
  protected readonly quickLinks = QUICK_LINKS;
  protected readonly reportTab = signal<ReportType | 'All'>('All');
  protected readonly reportSearch = signal('');
  protected readonly reportTabs = computed(() => {
    const counts = { All: REPORTS.length, Daily: 0, Monthly: 0, Exceptions: 0, Payroll: 0 };
    for (const report of REPORTS) counts[report.type] += 1;
    return (['All', 'Daily', 'Monthly', 'Exceptions', 'Payroll'] as const).map((id) => ({
      id,
      label: id === 'All' ? 'All Reports' : id,
      count: counts[id],
    }));
  });
  protected readonly visibleReports = computed(() => {
    const tab = this.reportTab();
    const query = this.reportSearch().trim().toLowerCase();
    return REPORTS.filter((report) => {
      if (tab !== 'All' && report.type !== tab) return false;
      if (!query) return true;
      return `${report.name} ${report.description}`.toLowerCase().includes(query);
    });
  });

  ngOnInit(): void {
    this.reload();
  }

  protected onYear(value: number): void {
    this.year.set(value);
    this.reload();
  }

  protected onMonth(value: number): void {
    this.monthIndex.set(value);
    this.reload();
  }

  protected reload(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.reportsSummary(this.year(), this.monthIndex() + 1).subscribe({
      next: (page) => {
        this.summary.set(page);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.summary.set(null);
        const message = messageFrom(err);
        this.error.set(message);
        this.snackBar.open(message, 'OK', { duration: 4000 });
      },
    });
  }

  protected exportMuster(kind: 'muster' | 'absent' | 'hours' = 'muster', format: ExportFormat = 'csv'): void {
    this.exporting.set(true);
    const year = this.year();
    const month = this.monthIndex() + 1;
    const query = { year, month, pageSize: 200, employmentStatus: 'Active' as const };
    this.api
      .listMuster({ ...query, page: 1 })
      .pipe(
        switchMap((first) => {
          const pages = Math.max(1, Math.ceil(first.total / Math.max(first.pageSize, 1)));
          if (pages <= 1) return of(first);
          const rest = Array.from({ length: pages - 1 }, (_, index) =>
            this.api.listMuster({ ...query, page: index + 2 }),
          );
          return forkJoin(rest).pipe(
            map((extra) => ({
              ...first,
              items: [...first.items, ...extra.flatMap((page) => page.items)],
            })),
          );
        }),
        catchError((err) => {
          this.snackBar.open(messageFrom(err), 'OK', { duration: 4000 });
          return of(null);
        }),
      )
      .subscribe((page) => {
        this.exporting.set(false);
        if (!page) return;
        const rows = kind === 'absent' ? page.items.filter((row) => row.absent > 0) : page.items;
        const stamp = `${year}-${String(month).padStart(2, '0')}`;
        if (kind === 'muster') {
          this.downloadMusterWithLegend(rows, year, month, format);
          return;
        }
        const sheet = kind === 'hours' ? hoursSheet(rows) : absentSheet(rows);
        const base = kind === 'hours' ? `work-hours-${stamp}` : `absent-report-${stamp}`;
        downloadSheet(base, sheet, format);
        this.snackBar.open(`Exported ${rows.length} row(s).`, 'OK', { duration: 2500 });
      });
  }

  protected exportExceptions(kind: 'exceptions' | 'late' | 'missing' = 'exceptions', format: ExportFormat = 'csv'): void {
    this.exporting.set(true);
    const year = this.year();
    const month = this.monthIndex() + 1;
    const from = `${year}-${String(month).padStart(2, '0')}-01`;
    const last = new Date(year, month, 0).getDate();
    const to = `${year}-${String(month).padStart(2, '0')}-${String(last).padStart(2, '0')}`;
    this.api
      .listExceptions({ from, to, page: 1, pageSize: 200, statusTab: 'all' })
      .pipe(catchError((err) => {
        this.snackBar.open(messageFrom(err), 'OK', { duration: 4000 });
        return of(null);
      }))
      .subscribe((page) => {
        this.exporting.set(false);
        if (!page) return;
        const items = page.items.filter((row) => {
          if (kind === 'late') return row.exceptionType === 'Late Arrival' || row.exceptionType === 'Early Exit';
          if (kind === 'missing') return row.exceptionType === 'Missing Punch';
          return true;
        });
        const name =
          kind === 'late' ? 'late-early-report' : kind === 'missing' ? 'missing-punch-report' : 'attendance-exceptions';
        downloadSheet(`${name}-${year}-${String(month).padStart(2, '0')}`, exceptionSheet(items), format);
        this.snackBar.open(`Exported ${items.length} exception row(s).`, 'OK', {
          duration: 2500,
        });
      });
  }

  private exportRegularizations(format: ExportFormat): void {
    this.exporting.set(true);
    const { from, to } = this.monthRange();
    this.api
      .listRegularizations({ from, to, page: 1, pageSize: 200, statusTab: 'all' })
      .pipe(
        catchError((err) => {
          this.snackBar.open(messageFrom(err), 'OK', { duration: 4000 });
          return of(null);
        }),
      )
      .subscribe((page) => {
        this.exporting.set(false);
        if (!page) return;
        downloadSheet(`attendance-regularization-${this.fileStamp()}`, regularizationSheet(page.items), format);
        this.snackBar.open(`Exported ${page.items.length} regularization row(s).`, 'OK', { duration: 2500 });
      });
  }

  private exportDaily(kind: 'daily' | 'shift', format: ExportFormat): void {
    this.exporting.set(true);
    const date = this.referenceDay();
    this.api
      .listDaily({ date, page: 1, pageSize: 200, statusTab: 'all', includePunches: false, includeHistory: false })
      .pipe(
        catchError((err) => {
          this.snackBar.open(messageFrom(err), 'OK', { duration: 4000 });
          return of(null);
        }),
      )
      .subscribe((page) => {
        this.exporting.set(false);
        if (!page) return;
        downloadSheet(
          `${kind === 'shift' ? 'shift-attendance' : 'daily-attendance'}-${date}`,
          dailySheet(page.items, kind === 'shift'),
          format,
        );
        this.snackBar.open(`Exported ${page.items.length} row(s) for ${date}.`, 'OK', { duration: 2500 });
      });
  }

  private downloadMusterWithLegend(
    rows: MusterEmployeeRow[],
    year: number,
    month: number,
    format: ExportFormat,
  ): void {
    const range = this.monthRange();
    const query = { from: range.from, to: range.to, pageSize: 200, statusTab: 'all' as const };
    this.api
      .listRegularizations({ ...query, page: 1 })
      .pipe(
        switchMap((first) => {
          const pages = Math.max(1, Math.ceil(first.total / Math.max(first.pageSize, 1)));
          if (pages <= 1) return of(first.items);
          const rest = Array.from({ length: pages - 1 }, (_, index) =>
            this.api.listRegularizations({ ...query, page: index + 2 }),
          );
          return forkJoin(rest).pipe(
            map((extra) => [...first.items, ...extra.flatMap((page) => page.items)]),
          );
        }),
        catchError(() => of([] as RegularizationRow[])),
      )
      .subscribe((regs) => {
        downloadMusterWorkbook(
          `Attendance_Muster__${MONTHS[month - 1]}-${year}`,
          rows,
          year,
          month,
          regs,
          format,
        );
      });
  }

  private monthRange(): { from: string; to: string } {
    const year = this.year();
    const month = this.monthIndex() + 1;
    const last = new Date(year, month, 0).getDate();
    const stamp = `${year}-${String(month).padStart(2, '0')}`;
    return { from: `${stamp}-01`, to: `${stamp}-${String(last).padStart(2, '0')}` };
  }

  private fileStamp(): string {
    return this.monthRange().from.slice(0, 7);
  }

  private referenceDay(): string {
    const { from, to } = this.monthRange();
    const today = new Date();
    const iso = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    if (iso >= from && iso <= to) return iso;
    return to;
  }

  protected reportLink(report: AttendanceReport): { from?: string; to?: string } {
    if (report.route.endsWith('/exceptions') || report.route.endsWith('/regularization')) {
      return this.monthRange();
    }
    return {};
  }

  protected exportReport(report: AttendanceReport, format: ExportFormat): void {
    if (report.export === 'summary') {
      const summary = this.summary();
      if (!summary) return;
      downloadSheet(
        `attendance-summary-${this.fileStamp()}`,
        {
          headers: ['Employees', 'Present days', 'Late days', 'Absent days', 'Leave days', 'Pending exceptions', 'Pending regs', 'Payroll lock'],
          rows: [[
            summary.totalEmployees,
            summary.present,
            summary.late,
            summary.absent,
            summary.onLeave,
            summary.pendingExceptions,
            summary.pendingRegularizations,
            summary.isMonthFinalized ? 'Locked' : 'Open',
          ]],
        },
        format,
      );
      this.snackBar.open('Exported attendance summary.', 'OK', { duration: 2500 });
      return;
    }
    if (report.export === 'muster' || report.export === 'absent' || report.export === 'hours') {
      this.exportMuster(report.export, format);
      return;
    }
    if (report.export === 'exceptions' || report.export === 'late' || report.export === 'missing') {
      this.exportExceptions(report.export, format);
      return;
    }
    if (report.export === 'regularization') {
      this.exportRegularizations(format);
      return;
    }
    this.exportDaily(report.export, format);
  }

  protected exportBoth(): void {
    this.exporting.set(true);
    const year = this.year();
    const month = this.monthIndex() + 1;
    const from = `${year}-${String(month).padStart(2, '0')}-01`;
    const last = new Date(year, month, 0).getDate();
    const to = `${year}-${String(month).padStart(2, '0')}-${String(last).padStart(2, '0')}`;
    forkJoin({
      muster: this.api.listMuster({
        year,
        month,
        page: 1,
        pageSize: 200,
        employmentStatus: 'Active',
      }),
      exceptions: this.api.listExceptions({
        from,
        to,
        page: 1,
        pageSize: 200,
        statusTab: 'all',
      }),
    })
      .pipe(
        catchError((err) => {
          this.snackBar.open(messageFrom(err), 'OK', { duration: 4000 });
          return of(null);
        }),
      )
      .subscribe((bundle) => {
        this.exporting.set(false);
        if (!bundle) return;
        downloadMusterWorkbook(
          `Attendance_Muster__${MONTHS[month - 1]}-${year}`,
          bundle.muster.items,
          year,
          month,
          [],
          'csv',
        );
        const header = [
          'Emp ID',
          'Employee',
          'Department',
          'Date',
          'Exception',
          'Status',
          'Remark',
        ];
        const body = bundle.exceptions.items.map((row) =>
          [
            row.employeeCode,
            row.employeeName,
            row.department,
            row.date,
            row.exceptionType,
            row.status,
            row.remark,
          ]
            .map(csvEscape)
            .join(','),
        );
        triggerDownload(
          `attendance-exceptions-${year}-${String(month).padStart(2, '0')}.csv`,
          [header.join(','), ...body].join('\n'),
        );
        this.snackBar.open('Muster and exceptions CSV files downloaded.', 'OK', {
          duration: 2800,
        });
      });
  }
}

/** Excel style indexes used by the muster legend. */
const STYLE = {
  title: 1,
  header: 2,
  deduction: 3,
  pending: 4,
  ignored: 5,
  grace: 6,
  override: 7,
  regularized: 8,
  off: 9,
} as const;

interface StyledCell {
  value: string | number;
  style?: number;
}

function downloadMusterWorkbook(
  basename: string,
  rows: MusterEmployeeRow[],
  year: number,
  month: number,
  regs: RegularizationRow[],
  format: ExportFormat,
): void {
  const book = musterBook(rows, year, month, regs);
  if (format === 'xlsx') {
    triggerBlob(
      `${basename}.xlsx`,
      buildStyledXlsx(book),
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    );
    return;
  }
  const lines = book.rows.map((row) => row.map((cell) => csvEscape(cell.value)).join(','));
  triggerDownload(`${basename}.csv`, lines.join('\n'));
}

function musterBook(
  rows: MusterEmployeeRow[],
  year: number,
  month: number,
  regs: RegularizationRow[],
): { rows: StyledCell[][]; merges: string[] } {
  const days = new Date(year, month, 0).getDate();
  const marks = regularizationMarks(regs);
  const width = 4 + days;
  const title = `Attendance Muster - ${MONTHS[month - 1]} ${year}`;
  const header: StyledCell[] = [
    { value: 'Employee Name', style: STYLE.header },
    { value: 'Employee No', style: STYLE.header },
    { value: 'Department', style: STYLE.header },
    { value: 'Location', style: STYLE.header },
    ...Array.from({ length: days }, (_, index) => ({ value: index + 1, style: STYLE.header })),
  ];
  const body = rows.map((row) => {
    const identity: StyledCell[] = [
      { value: row.employeeName },
      { value: row.employeeCode },
      { value: row.department },
      { value: row.location },
    ];
    const dayCells = Array.from({ length: days }, (_, index) => {
      const code = row.days[index] ?? '';
      const day = `${year}-${String(month).padStart(2, '0')}-${String(index + 1).padStart(2, '0')}`;
      const reg = marks.get(`${row.employeeId}|${day}`);
      return { value: code === 'OFF' || code === 'H' ? code : code, style: dayStyle(code, reg) };
    });
    return [...identity, ...dayCells];
  });
  const legendTop: StyledCell[] = [
    { value: 'Legend' },
    { value: 'Deduction', style: STYLE.deduction },
    { value: 'Pending', style: STYLE.pending },
    { value: 'Ignored', style: STYLE.ignored },
  ];
  const legendBottom: StyledCell[] = [
    { value: '' },
    { value: 'Grace', style: STYLE.grace },
    { value: 'Override', style: STYLE.override },
    { value: 'Regularized', style: STYLE.regularized },
  ];
  return {
    merges: [`A1:${columnName(width - 1)}1`],
    rows: [
      [{ value: title, style: STYLE.title }],
      [],
      header,
      ...body,
      [],
      legendTop,
      legendBottom,
    ],
  };
}

function regularizationMarks(regs: RegularizationRow[]): Map<string, RegularizationRow['status']> {
  const rank: Record<string, number> = { Rejected: 1, Approved: 2, Pending: 3 };
  const marks = new Map<string, RegularizationRow['status']>();
  for (const reg of regs) {
    const day = reg.attendanceDate.slice(0, 10);
    const key = `${reg.employeeId}|${day}`;
    const current = marks.get(key);
    if (!current || (rank[reg.status] ?? 0) >= (rank[current] ?? 0)) marks.set(key, reg.status);
  }
  return marks;
}

function dayStyle(code: string, reg?: RegularizationRow['status']): number | undefined {
  if (reg === 'Pending') return STYLE.pending;
  if (reg === 'Approved') return STYLE.regularized;
  if (reg === 'Rejected') return STYLE.ignored;
  if (code === 'A') return STYLE.deduction;
  if (code === 'L') return STYLE.grace;
  if (code === 'OFF' || code === 'H') return STYLE.off;
  return undefined;
}

function absentSheet(rows: MusterEmployeeRow[]): ReportSheet {
  return {
    headers: ['Emp ID', 'Employee', 'Department', 'Location', 'Absent days'],
    rows: rows.map((row) => [row.employeeCode, row.employeeName, row.department, row.location, row.absent]),
  };
}

function hoursSheet(rows: MusterEmployeeRow[]): ReportSheet {
  return {
    headers: ['Emp ID', 'Employee', 'Department', 'Location', 'Hours', 'Present', 'Absent', 'Leave'],
    rows: rows.map((row) => [
      row.employeeCode,
      row.employeeName,
      row.department,
      row.location,
      row.hours,
      row.present,
      row.absent,
      row.leave,
    ]),
  };
}

function exceptionSheet(rows: AttendanceExceptionRow[]): ReportSheet {
  return {
    headers: ['Emp ID', 'Employee', 'Department', 'Date', 'Exception', 'Status', 'In', 'Out', 'Remark'],
    rows: rows.map((row) => [
      row.employeeCode,
      row.employeeName,
      row.department,
      row.date,
      row.exceptionType,
      row.status,
      row.firstIn ?? '',
      row.lastOut ?? '',
      row.remark,
    ]),
  };
}

function regularizationSheet(rows: RegularizationRow[]): ReportSheet {
  return {
    headers: ['Emp ID', 'Employee', 'Department', 'Date', 'Type', 'Status', 'Requested In', 'Requested Out', 'Reason'],
    rows: rows.map((row) => [
      row.employeeCode,
      row.employeeName,
      row.department,
      row.attendanceDate,
      row.requestType,
      row.status,
      row.requestedIn ?? '',
      row.requestedOut ?? '',
      row.reason,
    ]),
  };
}

function dailySheet(rows: DailyAttendanceRow[], byShift: boolean): ReportSheet {
  const ordered = byShift
    ? [...rows].sort((a, b) => a.shift.localeCompare(b.shift) || a.employeeName.localeCompare(b.employeeName))
    : rows;
  return {
    headers: ['Emp ID', 'Employee', 'Department', 'Shift', 'In', 'Out', 'Hours', 'Status'],
    rows: ordered.map((row) => [
      row.employeeCode,
      row.employeeName,
      row.department,
      row.shift,
      row.firstIn ?? '',
      row.lastOut ?? '',
      row.workingHours ?? '',
      row.status,
    ]),
  };
}

function downloadSheet(basename: string, sheet: ReportSheet, format: ExportFormat): void {
  if (format === 'xlsx') {
    triggerBlob(`${basename}.xlsx`, buildXlsx(sheet), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    return;
  }
  const lines = [
    sheet.headers.map(csvEscape).join(','),
    ...sheet.rows.map((row) => row.map(csvEscape).join(',')),
  ];
  triggerDownload(`${basename}.csv`, lines.join('\n'));
}

function csvEscape(value: string | number): string {
  const text = String(value ?? '');
  if (/[",\n]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

function triggerDownload(filename: string, content: string): void {
  triggerBlob(filename, new Blob([content], { type: 'text/csv;charset=utf-8;' }), 'text/csv');
}

function triggerBlob(filename: string, blob: Blob, _type: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

/** Minimal OOXML workbook (stored ZIP) so Excel opens a real .xlsx file. */
function buildXlsx(sheet: ReportSheet): Blob {
  const files: Record<string, string> = {
    '[Content_Types].xml': `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>`,
    '_rels/.rels': `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>`,
    'xl/workbook.xml': `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Report" sheetId="1" r:id="rId1"/></sheets>
</workbook>`,
    'xl/_rels/workbook.xml.rels': `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>`,
    'xl/worksheets/sheet1.xml': worksheetXml(sheet),
  };
  const bytes = zipStored(files);
  const buffer = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(buffer).set(bytes);
  return new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
}

function buildStyledXlsx(book: { rows: StyledCell[][]; merges: string[] }): Blob {
  const files: Record<string, string> = {
    '[Content_Types].xml': `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>`,
    '_rels/.rels': `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>`,
    'xl/workbook.xml': `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Attendance Muster" sheetId="1" r:id="rId1"/></sheets>
</workbook>`,
    'xl/_rels/workbook.xml.rels': `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>`,
    'xl/styles.xml': musterStylesXml(),
    'xl/worksheets/sheet1.xml': styledWorksheetXml(book),
  };
  const bytes = zipStored(files);
  const buffer = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(buffer).set(bytes);
  return new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
}

function styledWorksheetXml(book: { rows: StyledCell[][]; merges: string[] }): string {
  const rows = book.rows
    .map((cells, rowIndex) => {
      const cols = cells
        .map((cell, colIndex) => {
          const ref = `${columnName(colIndex)}${rowIndex + 1}`;
          const style = cell.style ? ` s="${cell.style}"` : '';
          if (typeof cell.value === 'number' && Number.isFinite(cell.value)) {
            return `<c r="${ref}"${style}><v>${cell.value}</v></c>`;
          }
          return `<c r="${ref}"${style} t="inlineStr"><is><t>${xmlEscape(String(cell.value ?? ''))}</t></is></c>`;
        })
        .join('');
      return `<row r="${rowIndex + 1}">${cols}</row>`;
    })
    .join('');
  const lastDayCol = Math.max(4, (book.rows[2]?.length ?? 4));
  const merges = book.merges.map((ref) => `<mergeCell ref="${ref}"/>`).join('');
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<cols>
<col min="1" max="1" width="26" customWidth="1"/>
<col min="2" max="2" width="14" customWidth="1"/>
<col min="3" max="4" width="18" customWidth="1"/>
<col min="5" max="${lastDayCol}" width="4.5" customWidth="1"/>
</cols>
<sheetData>${rows}</sheetData>
<mergeCells count="${book.merges.length}">${merges}</mergeCells>
</worksheet>`;
}

function musterStylesXml(): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="4">
<font><sz val="11"/><name val="Calibri"/></font>
<font><b/><sz val="16"/><name val="Calibri"/></font>
<font><b/><sz val="11"/><name val="Calibri"/></font>
<font><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
</fonts>
<fills count="9">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFFFC7CE"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF00B0F0"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF7030A0"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFFFFF00"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFFFC000"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF92D050"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFD9D9D9"/></patternFill></fill>
</fills>
<borders count="1"><border><left/><right/><top/><bottom/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="10">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment horizontal="center"/></xf>
<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment horizontal="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="2" borderId="0" xfId="0" applyFill="1" applyAlignment="1"><alignment horizontal="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="3" borderId="0" xfId="0" applyFill="1" applyAlignment="1"><alignment horizontal="center"/></xf>
<xf numFmtId="0" fontId="3" fillId="4" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment horizontal="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="5" borderId="0" xfId="0" applyFill="1" applyAlignment="1"><alignment horizontal="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="6" borderId="0" xfId="0" applyFill="1" applyAlignment="1"><alignment horizontal="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="7" borderId="0" xfId="0" applyFill="1" applyAlignment="1"><alignment horizontal="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="8" borderId="0" xfId="0" applyFill="1" applyAlignment="1"><alignment horizontal="center"/></xf>
</cellXfs>
</styleSheet>`;
}

function worksheetXml(sheet: ReportSheet): string {
  const all = [sheet.headers, ...sheet.rows];
  const rows = all
    .map((cells, rowIndex) => {
      const cols = cells
        .map((cell, colIndex) => {
          const ref = `${columnName(colIndex)}${rowIndex + 1}`;
          if (typeof cell === 'number' && Number.isFinite(cell)) {
            return `<c r="${ref}"><v>${cell}</v></c>`;
          }
          return `<c r="${ref}" t="inlineStr"><is><t>${xmlEscape(String(cell ?? ''))}</t></is></c>`;
        })
        .join('');
      return `<row r="${rowIndex + 1}">${cols}</row>`;
    })
    .join('');
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${rows}</sheetData></worksheet>`;
}

function columnName(index: number): string {
  let n = index + 1;
  let name = '';
  while (n > 0) {
    const rem = (n - 1) % 26;
    name = String.fromCharCode(65 + rem) + name;
    n = Math.floor((n - 1) / 26);
  }
  return name;
}

function xmlEscape(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function zipStored(files: Record<string, string>): Uint8Array {
  const encoder = new TextEncoder();
  const locals: Uint8Array[] = [];
  const central: Uint8Array[] = [];
  let offset = 0;
  for (const [name, content] of Object.entries(files)) {
    const nameBytes = encoder.encode(name);
    const data = encoder.encode(content);
    const crc = crc32(data);
    const local = new Uint8Array(30 + nameBytes.length + data.length);
    const view = new DataView(local.buffer);
    view.setUint32(0, 0x04034b50, true);
    view.setUint16(4, 20, true);
    view.setUint16(8, 0, true);
    view.setUint16(10, 0, true);
    view.setUint32(14, crc, true);
    view.setUint32(18, data.length, true);
    view.setUint32(22, data.length, true);
    view.setUint16(26, nameBytes.length, true);
    local.set(nameBytes, 30);
    local.set(data, 30 + nameBytes.length);
    locals.push(local);

    const dir = new Uint8Array(46 + nameBytes.length);
    const dirView = new DataView(dir.buffer);
    dirView.setUint32(0, 0x02014b50, true);
    dirView.setUint16(4, 20, true);
    dirView.setUint16(6, 20, true);
    dirView.setUint16(10, 0, true);
    dirView.setUint16(12, 0, true);
    dirView.setUint32(16, crc, true);
    dirView.setUint32(20, data.length, true);
    dirView.setUint32(24, data.length, true);
    dirView.setUint16(28, nameBytes.length, true);
    dirView.setUint32(42, offset, true);
    dir.set(nameBytes, 46);
    central.push(dir);
    offset += local.length;
  }
  const centralSize = central.reduce((sum, part) => sum + part.length, 0);
  const end = new Uint8Array(22);
  const endView = new DataView(end.buffer);
  endView.setUint32(0, 0x06054b50, true);
  endView.setUint16(8, central.length, true);
  endView.setUint16(10, central.length, true);
  endView.setUint32(12, centralSize, true);
  endView.setUint32(16, offset, true);
  const total = offset + centralSize + end.length;
  const out = new Uint8Array(total);
  let cursor = 0;
  for (const part of [...locals, ...central, end]) {
    out.set(part, cursor);
    cursor += part.length;
  }
  return out;
}

const CRC_TABLE = new Uint32Array(256).map((_, index) => {
  let crc = index;
  for (let bit = 0; bit < 8; bit += 1) {
    crc = crc & 1 ? 0xedb88320 ^ (crc >>> 1) : crc >>> 1;
  }
  return crc >>> 0;
});

function crc32(data: Uint8Array): number {
  let crc = 0xffffffff;
  for (const byte of data) crc = CRC_TABLE[(crc ^ byte) & 0xff]! ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

function messageFrom(err: unknown): string {
  if (err instanceof HttpErrorResponse) {
    const detail = err.error?.detail ?? err.error?.message;
    if (typeof detail === 'string') return detail;
  }
  return err instanceof Error ? err.message : 'Failed to load attendance reports.';
}
