import { DecimalPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatFormField } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { RouterLink } from '@angular/router';
import {
  AttendanceApi,
  AttendanceReportsSummary,
  MusterEmployeeRow,
} from '@trishul/hr-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

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

/** Attendance Reports — summary + CSV exports from existing muster/exception APIs. */
@Component({
  selector: 'trishul-attendance-reports-page',
  imports: [
    DecimalPipe,
    FormsModule,
    MatButton,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatOption,
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

  protected exportMuster(): void {
    this.exporting.set(true);
    const year = this.year();
    const month = this.monthIndex() + 1;
    this.api
      .listMuster({ year, month, page: 1, pageSize: 200, employmentStatus: 'Active' })
      .pipe(catchError((err) => {
        this.snackBar.open(messageFrom(err), 'OK', { duration: 4000 });
        return of(null);
      }))
      .subscribe((page) => {
        this.exporting.set(false);
        if (!page) return;
        downloadMusterCsv(`attendance-muster-${year}-${String(month).padStart(2, '0')}.csv`, page.items);
        this.snackBar.open(`Exported ${page.items.length} muster row(s).`, 'OK', { duration: 2500 });
      });
  }

  protected exportExceptions(): void {
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
        const header = [
          'Emp ID',
          'Employee',
          'Department',
          'Date',
          'Exception',
          'Status',
          'In',
          'Out',
          'Remark',
        ];
        const body = page.items.map((row) =>
          [
            row.employeeCode,
            row.employeeName,
            row.department,
            row.date,
            row.exceptionType,
            row.status,
            row.firstIn ?? '',
            row.lastOut ?? '',
            row.remark,
          ]
            .map(csvEscape)
            .join(','),
        );
        triggerDownload(
          `attendance-exceptions-${year}-${String(month).padStart(2, '0')}.csv`,
          [header.join(','), ...body].join('\n'),
        );
        this.snackBar.open(`Exported ${page.items.length} exception row(s).`, 'OK', {
          duration: 2500,
        });
      });
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
        downloadMusterCsv(
          `attendance-muster-${year}-${String(month).padStart(2, '0')}.csv`,
          bundle.muster.items,
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

function downloadMusterCsv(filename: string, rows: MusterEmployeeRow[]): void {
  const header = [
    'Emp ID',
    'Employee',
    'Department',
    'Location',
    'Present',
    'Late',
    'Absent',
    'Leave',
    'Hours',
  ];
  const body = rows.map((row) =>
    [
      row.employeeCode,
      row.employeeName,
      row.department,
      row.location,
      row.present,
      row.late,
      row.absent,
      row.leave,
      row.hours,
    ]
      .map(csvEscape)
      .join(','),
  );
  triggerDownload(filename, [header.join(','), ...body].join('\n'));
}

function csvEscape(value: string | number): string {
  const text = String(value ?? '');
  if (/[",\n]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

function triggerDownload(filename: string, content: string): void {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function messageFrom(err: unknown): string {
  if (err instanceof HttpErrorResponse) {
    const detail = err.error?.detail ?? err.error?.message;
    if (typeof detail === 'string') return detail;
  }
  return err instanceof Error ? err.message : 'Failed to load attendance reports.';
}
