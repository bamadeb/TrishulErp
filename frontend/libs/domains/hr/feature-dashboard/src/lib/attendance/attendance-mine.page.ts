import { DatePipe, DecimalPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import {
  Subject,
  catchError,
  finalize,
  interval,
  of,
  switchMap,
  tap,
} from 'rxjs';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatFormField, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { AuthStore } from '@trishul/core-auth';
import {
  AttendanceApi,
  MineAttendanceDay,
  RegularizationRow,
} from '@trishul/hr-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { AttendanceDailyDrawer } from './attendance-daily.drawer';
import { AttendanceRegularizeDrawer, RegularizeDrawerMode } from './attendance-regularize-drawer';
import { DailyAttendanceRow } from './attendance.models';
import { displaySessionWorkingHours, displayWorkingHours } from './live-working-hours';

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

type DayAction = 'request' | 'compOff' | 'unavailable' | 'locked' | 'submitted' | 'resolved';

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
    MatProgressBar,
    MatSelect,
    PageHeader,
    StatusBadge,
    AttendanceDailyDrawer,
    AttendanceRegularizeDrawer,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-mine.page.html',
  styleUrl: './attendance-mine.page.scss',
})
export class AttendanceMinePage implements OnInit {
  private readonly api = inject(AttendanceApi);
  private readonly auth = inject(AuthStore);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);

  /** Bumps every minute so In Progress hours stay live without a page reload. */
  private readonly clockTick = signal(Date.now());
  /** Last auth user id that loaded this page — clears rows when the account switches. */
  private boundUserId: number | null = null;
  private readonly reload$ = new Subject<void>();

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
  protected readonly drawerKeys = signal<number[]>([]);
  protected readonly drawerDate = signal<string | null>(null);
  protected readonly drawerMode = signal<RegularizeDrawerMode>('regularize');
  protected readonly detailDay = signal<MineAttendanceDay | null>(null);

  protected readonly severities: Partial<Record<string, StatusSeverity>> = {
    Present: 'success',
    Late: 'warn',
    'In Progress': 'info',
    'Missing Punch': 'warn',
    Absent: 'danger',
    'On Leave': 'info',
    'Off Day': 'neutral',
    'Weekly Off': 'neutral',
    Holiday: 'neutral',
    Regularized: 'success',
    Pending: 'warn',
    Approved: 'success',
    Rejected: 'danger',
    Resolved: 'success',
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
    for (const row of this.regularizations()) map.set(row.attendanceDate.slice(0, 10), row);
    return map;
  });

  constructor() {
    this.reload$
      .pipe(
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
          this.detailDay.set(null);
        }),
        switchMap(() => {
          const linked = this.auth.user()?.employeeId ?? null;
          if (linked == null) {
            this.loading.set(false);
            return of(null);
          }
          return this.api.mine(this.year(), this.monthIndex() + 1).pipe(
            tap((page) => {
              if (page.employeeId !== linked) {
                this.clearEmployeeState();
                this.error.set('Attendance could not be scoped to your employee profile.');
                return;
              }
              this.employeeId.set(page.employeeId);
              this.employeeName.set(page.employeeName);
              this.employeeCode.set(page.employeeCode);
              this.monthLabel.set(page.monthLabel);
              this.isFinalized.set(page.isMonthFinalized);
              this.canRegularize.set(page.canRegularize !== false && !page.isMonthFinalized);
              this.summary.set(page.summary);
              this.items.set(page.items);
              this.regularizations.set(page.regularizations ?? []);
            }),
            catchError((err: unknown) => {
              this.clearEmployeeState();
              const message = messageFrom(err);
              this.error.set(message);
              this.snackBar.open(message, 'OK', { duration: 4500 });
              return of(null);
            }),
            finalize(() => this.loading.set(false)),
          );
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe();

    effect(() => {
      const user = this.auth.user();
      const userId = user?.id ?? null;
      const linkedEmployeeId = user?.employeeId ?? null;
      if (userId === this.boundUserId) return;
      this.boundUserId = userId;
      this.clearEmployeeState();
      if (userId != null && linkedEmployeeId != null) {
        this.reload$.next();
      }
    });
  }

  ngOnInit(): void {
    interval(60_000)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.clockTick.set(Date.now()));
    // First load is owned by the auth effect (and month/year handlers) via reload$.
  }

  private clearEmployeeState(): void {
    this.employeeId.set(0);
    this.employeeName.set('');
    this.employeeCode.set('');
    this.monthLabel.set('');
    this.items.set([]);
    this.regularizations.set([]);
    this.summary.set({
      present: 0,
      late: 0,
      absent: 0,
      onLeave: 0,
      offDay: 0,
      holiday: 0,
      missingPunch: 0,
    });
    this.detailDay.set(null);
    this.drawerKeys.set([]);
    this.error.set(null);
  }

  /** Session sum + live open IN (same board rules as Daily Attendance). */
  protected hoursFor(row: MineAttendanceDay): string {
    this.clockTick();
    if (row.openInAt || (row.closedWorkedMinutes ?? 0) > 0 || row.workingHoursDetail) {
      return displaySessionWorkingHours({
        closedWorkedMinutes: row.closedWorkedMinutes,
        openInAt: row.openInAt,
        frozenHours: row.workingHours,
        workingHoursDetail: row.workingHoursDetail,
      }).total;
    }
    return displayWorkingHours(row.status, row.date, row.firstIn, row.workingHours, undefined, row.lastOut);
  }

  protected hoursDetail(row: MineAttendanceDay): string | null {
    this.clockTick();
    if (row.openInAt || row.workingHoursDetail) {
      return displaySessionWorkingHours({
        closedWorkedMinutes: row.closedWorkedMinutes,
        openInAt: row.openInAt,
        frozenHours: row.workingHours,
        workingHoursDetail: row.workingHoursDetail,
      }).detail;
    }
    return row.workingHoursDetail ?? null;
  }

  /** Attendance status for the row: Weekly Off / Regularized labels where applicable. */
  protected attendanceStatusLabel(row: MineAttendanceDay): string {
    if (row.resolved) return 'Regularized';
    if (row.status === 'Off Day') return 'Weekly Off';
    if (row.status === 'In Progress' && !row.firstIn) return '—';
    return row.status;
  }

  protected punchStatusLabel(row: MineAttendanceDay): string | null {
    if (row.currentPunch === 'IN') return 'IN – In Progress';
    if (row.currentPunch === 'OUT') return 'OUT – Checked Out';
    return null;
  }

  protected requestStatus(row: MineAttendanceDay): RegularizationRow['status'] | null {
    return this.requestFor(row.date)?.status ?? null;
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
    // Keep prior rows visible while the cancellable mine() request runs.
    this.reload$.next();
  }

  protected requestFor(date: string): RegularizationRow | undefined {
    return this.regByDate().get(date.slice(0, 10));
  }

  protected dayAction(row: MineAttendanceDay): DayAction {
    if (this.requestFor(row.date)) return 'submitted';
    if (row.resolved) return 'resolved';
    if (!this.canRegularize()) return 'locked';
    // Still punched in — regularization waits until checked out / day closes.
    if (row.currentPunch === 'IN' || (row.status === 'In Progress' && !row.lastOut)) return 'unavailable';
    if (row.status === 'On Leave') return 'locked';
    if ((row.status === 'Holiday' || row.status === 'Off Day') && this.hasWorkedPunches(row)) {
      return 'compOff';
    }
    if (row.status === 'Holiday' || row.status === 'Off Day') return 'locked';
    if (row.status === 'Present' || row.status === 'Late' || row.status === 'Missing Punch' || row.status === 'Absent') {
      return 'request';
    }
    return 'locked';
  }

  protected canOpen(row: MineAttendanceDay): boolean {
    const request = this.requestFor(row.date);
    if (request?.status === 'Pending' || request?.status === 'Approved' || request?.status === 'Rejected') {
      return true;
    }
    const action = this.dayAction(row);
    return action === 'request' || action === 'compOff';
  }

  protected canViewDetails(row: MineAttendanceDay): boolean {
    return !!(row.firstIn || row.lastOut || row.punches?.length || row.workingHours);
  }

  /** Punch Status / Hours: Attendance Details with IN–OUT punch logs (same as Daily Attendance). */
  protected openPunchDetails(row: MineAttendanceDay): void {
    if (!this.canViewDetails(row)) return;
    this.drawerKeys.set([]);
    this.detailDay.set(row);
  }

  /** No approval yet opens the request form. Pending and Approved open that status drawer. */
  protected openRow(row: MineAttendanceDay): void {
    const request = this.requestFor(row.date);
    if (request?.status === 'Pending' || request?.status === 'Approved' || request?.status === 'Rejected') {
      this.drawerKeys.set([]);
      this.detailDay.set(row);
      return;
    }
    const action = this.dayAction(row);
    if (action === 'compOff') {
      this.openCompOff(row);
      return;
    }
    if (action !== 'request') return;
    this.detailDay.set(null);
    this.openRegularize(row);
  }

  protected openCompOff(row: MineAttendanceDay): void {
    if (!this.canRegularize()) {
      this.snackBar.open('This month is finalized; Comp Off requests are locked.', 'OK', { duration: 3500 });
      return;
    }
    this.detailDay.set(null);
    this.drawerMode.set('compOff');
    this.drawerDate.set(row.date.slice(0, 10));
    this.drawerKeys.set([Date.now()]);
  }

  private hasWorkedPunches(row: MineAttendanceDay): boolean {
    return !!row.firstIn && !!row.lastOut;
  }

  protected detailAttendance(): DailyAttendanceRow | null {
    const day = this.detailDay();
    if (!day) return null;
    return {
      id: this.employeeId(),
      dateIso: day.date.slice(0, 10),
      employeeId: this.employeeId(),
      employeeCode: this.employeeCode(),
      employeeName: this.employeeName(),
      department: '',
      location: '',
      shift: day.shift,
      employeeType: '',
      reportingManager: '',
      firstIn: day.firstIn,
      lastOut: day.lastOut,
      firstInLate: day.firstInLate ?? false,
      workingHours: day.workingHours,
      workingHoursDetail: day.workingHoursDetail ?? null,
      currentPunch: day.currentPunch ?? null,
      currentPunchSince: day.currentPunchSince ?? null,
      requiredHours: day.requiredHours ?? null,
      shortfall: day.shortfall ?? null,
      openInAt: day.openInAt ?? null,
      closedWorkedMinutes: day.closedWorkedMinutes ?? 0,
      status: day.status,
      remarks: day.remarks,
      lateArrivalMinutes: day.lateArrivalMinutes ?? null,
      earlyExitMinutes: day.earlyExitMinutes ?? null,
      avatarTone: '#0754b8',
      punches: (day.punches ?? []).map((punch) => ({
        kind: punch.kind,
        at: punch.at,
        device: punch.device,
        location: punch.location ?? null,
      })),
      history: [],
    };
  }

  protected detailDate(): Date {
    const iso = this.detailDay()?.date.slice(0, 10) ?? '';
    const [year, month, day] = iso.split('-').map(Number);
    return new Date(year || this.year(), (month || 1) - 1, day || 1);
  }

  protected openRegularize(row?: MineAttendanceDay): void {
    if (!this.canRegularize()) {
      this.snackBar.open('This month is finalized; regularization is locked.', 'OK', { duration: 3500 });
      return;
    }
    const date = row && this.dayAction(row) === 'request' ? row.date.slice(0, 10) : null;
    this.drawerMode.set('regularize');
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

  protected shortRemark(value: string): string {
    const text = value.trim();
    if (!text) return '—';
    const sentence = text.split('. ')[0].replace(/\.$/, '');
    return sentence.length > 72 ? `${sentence.slice(0, 72).trimEnd()}…` : sentence;
  }

  protected statusIcon(status: string): string {
    switch (status) {
      case 'Present':
      case 'Regularized':
        return 'check_circle';
      case 'In Progress':
        return 'more_time';
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
      case 'Weekly Off':
      case 'Off Day':
        return 'event_busy';
      default:
        return 'event_busy';
    }
  }

  protected formatClock(value: string | null | undefined): string {
    if (!value?.trim()) return '—';
    const raw = value.trim();
    if (/am|pm/i.test(raw)) return raw;
    const hm = raw.match(/^(\d{1,2}):(\d{2})/);
    if (!hm) return raw;
    let hour = Number(hm[1]);
    const minute = hm[2];
    const meridiem = hour >= 12 ? 'PM' : 'AM';
    hour = hour % 12 || 12;
    return `${hour}:${minute} ${meridiem}`;
  }

  /** Split `General (09:30 - 17:30)` → name bold, timing muted (not punch times). */
  protected shiftParts(value: string | null | undefined): { name: string; hours: string } | null {
    const raw = value?.trim();
    if (!raw || raw === '—') return null;
    const match = raw.match(/^(.+?)\s*\(([^)]+)\)\s*$/);
    if (match) {
      const name = match[1]!.trim();
      const range = match[2]!
        .split(/\s*[-–—]\s*/)
        .map((part) => this.formatShiftClock(part.trim()));
      return {
        name,
        hours: range.length >= 2 ? `${range[0]} – ${range[1]}` : range[0]!,
      };
    }
    return { name: raw, hours: '' };
  }

  /** Shift window only — always 12h with zero-padded hours (e.g. 09:30 AM). */
  private formatShiftClock(value: string): string {
    if (/am|pm/i.test(value)) {
      const ampm = value.match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
      if (!ampm) return value;
      return `${ampm[1]!.padStart(2, '0')}:${ampm[2]} ${ampm[3]!.toUpperCase()}`;
    }
    const hm = value.match(/^(\d{1,2}):(\d{2})$/);
    if (!hm) return value;
    let hour = Number(hm[1]);
    const minute = hm[2]!;
    const meridiem = hour >= 12 ? 'PM' : 'AM';
    const display = hour % 12 || 12;
    return `${String(display).padStart(2, '0')}:${minute} ${meridiem}`;
  }
}

function messageFrom(err: unknown): string {
  if (err instanceof HttpErrorResponse) {
    const detail = err.error?.detail ?? err.error?.message;
    if (typeof detail === 'string') return detail;
  }
  return err instanceof Error ? err.message : 'Failed to load my attendance.';
}
