import { DatePipe, DecimalPipe } from '@angular/common';
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
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import {
  AttendanceApi,
  AttendanceStatus,
  MineAttendanceDay,
  RegularizationRow,
} from '@trishul/hr-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { catchError, filter, of } from 'rxjs';
import {
  AttendanceRegularizeDialog,
  RegularizeSubmitResult,
  ATTENDANCE_REGULARIZE_DIALOG_OPTIONS,
} from './attendance-regularize.dialog';

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

/** ESS — logged-in employee's monthly attendance from GET /hr/attendance/mine. */
@Component({
  selector: 'trishul-attendance-mine-page',
  imports: [
    DatePipe,
    DecimalPipe,
    FormsModule,
    MatButton,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatInput,
    MatOption,
    MatPrefix,
    MatSelect,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-mine.page.html',
  styleUrl: './attendance-mine.page.scss',
})
export class AttendanceMinePage implements OnInit {
  private readonly api = inject(AttendanceApi);
  private readonly snackBar = inject(MatSnackBar);
  private readonly dialog = inject(MatDialog);

  protected readonly months = MONTHS;
  protected readonly years = [2026, 2025, 2024];
  protected readonly year = signal(new Date().getFullYear());
  protected readonly monthIndex = signal(new Date().getMonth());
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly employeeId = signal(0);
  protected readonly employeeName = signal('');
  protected readonly employeeCode = signal('');
  protected readonly monthLabel = signal('');
  protected readonly isFinalized = signal(false);
  protected readonly canRegularize = signal(false);
  protected readonly search = signal('');
  protected readonly items = signal<MineAttendanceDay[]>([]);
  protected readonly regularizations = signal<RegularizationRow[]>([]);
  protected readonly summary = signal({
    present: 0,
    late: 0,
    absent: 0,
    onLeave: 0,
    offDay: 0,
    holiday: 0,
    missingPunch: 0,
  });

  protected readonly severities: Partial<Record<string, StatusSeverity>> = {
    Present: 'success',
    Late: 'warn',
    'Missing Punch': 'warn',
    Absent: 'danger',
    'On Leave': 'info',
    'Off Day': 'neutral',
    Holiday: 'neutral',
    Pending: 'warn',
    Approved: 'success',
    Rejected: 'danger',
  };

  protected readonly filtered = computed(() => {
    const q = this.search().trim().toLowerCase();
    if (!q) return this.items();
    return this.items().filter(
      (row) =>
        row.status.toLowerCase().includes(q) ||
        row.shift.toLowerCase().includes(q) ||
        row.remarks.toLowerCase().includes(q) ||
        row.date.includes(q),
    );
  });

  protected readonly regByDate = computed(() => {
    const map = new Map<string, RegularizationRow>();
    for (const row of this.regularizations()) {
      map.set(row.attendanceDate, row);
    }
    return map;
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
    this.api.mine(this.year(), this.monthIndex() + 1).subscribe({
      next: (page) => {
        this.employeeId.set(page.employeeId);
        this.employeeName.set(page.employeeName);
        this.employeeCode.set(page.employeeCode);
        this.monthLabel.set(page.monthLabel);
        this.isFinalized.set(page.isMonthFinalized);
        this.canRegularize.set(page.canRegularize !== false && !page.isMonthFinalized);
        this.summary.set(page.summary);
        this.items.set(page.items);
        this.regularizations.set(page.regularizations ?? []);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.items.set([]);
        this.regularizations.set([]);
        const message = messageFrom(err);
        this.error.set(message);
        this.snackBar.open(message, 'OK', { duration: 4500 });
      },
    });
  }

  protected requestFor(date: string): RegularizationRow | undefined {
    return this.regByDate().get(date);
  }

  protected openRegularize(row?: MineAttendanceDay): void {
    if (!this.canRegularize()) {
      this.snackBar.open('This month is finalized; regularization is locked.', 'OK', {
        duration: 3500,
      });
      return;
    }
    const employee = {
      id: this.employeeId(),
      employeeId: this.employeeId(),
      employeeCode: this.employeeCode(),
      employeeName: this.employeeName(),
      department: '—',
      avatarTone: 'blue',
      firstIn: row?.firstIn ?? null,
      lastOut: row?.lastOut ?? null,
      status: row?.status,
    };
    this.dialog
      .open(AttendanceRegularizeDialog, {
        ...ATTENDANCE_REGULARIZE_DIALOG_OPTIONS,
        data: {
          employee,
          employees: [employee],
          attendanceDate: row ? parseIsoDate(row.date) : new Date(),
        },
      })
      .afterClosed()
      .pipe(filter((result): result is RegularizeSubmitResult => !!result))
      .subscribe((result) => {
        this.api
          .createMineRegularization({
            employeeId: this.employeeId(),
            attendanceDate: result.attendanceDate,
            requestType: result.requestType,
            requestedIn: result.requestedIn,
            requestedOut: result.requestedOut,
            reason: result.reason,
            attachmentName: result.attachmentName,
          })
          .pipe(
            catchError((err: unknown) => {
              this.snackBar.open(messageFrom(err), 'OK', { duration: 4000 });
              return of(null);
            }),
          )
          .subscribe((saved) => {
            if (!saved) return;
            this.snackBar.open('Regularization request submitted.', 'OK', { duration: 2500 });
            this.reload();
          });
      });
  }

  protected statusIcon(status: AttendanceStatus): string {
    switch (status) {
      case 'Present':
        return 'check_circle';
      case 'Late':
        return 'schedule';
      case 'Missing Punch':
        return 'fingerprint';
      case 'Absent':
        return 'cancel';
      case 'On Leave':
        return 'flight_takeoff';
      case 'Holiday':
        return 'celebration';
      default:
        return 'event_busy';
    }
  }
}

function parseIsoDate(value: string): Date {
  const [y, m, d] = value.split('-').map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
}

function messageFrom(err: unknown): string {
  if (err instanceof HttpErrorResponse) {
    const detail = err.error?.detail ?? err.error?.message;
    if (typeof detail === 'string') return detail;
  }
  return err instanceof Error ? err.message : 'Failed to load my attendance.';
}
