import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import {
  AttendanceApi,
  AttendanceStatus,
  MineAttendanceDay,
  RegularizationRequestType,
  RegularizationRow,
} from '@trishul/hr-data-access';
import { StatusBadge, StatusSeverity } from '@trishul/shared-ui';

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

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

const REQUEST_TYPES: { value: RegularizationRequestType; label: string }[] = [
  { value: 'Late Arrival', label: 'Correct Punch-In (Late Arrival)' },
  { value: 'Missed Punch', label: 'Missed Punch' },
  { value: 'Early Exit', label: 'Early Exit' },
  { value: 'Wrong Attendance', label: 'Wrong Attendance' },
  { value: 'WFH Correction', label: 'WFH Correction' },
];

type DrawerStep = 1 | 2 | 3;
export type RegularizeDrawerMode = 'regularize' | 'compOff';

/** Employee already loaded on Daily Attendance. The drawer does not fetch a second employee list. */
export interface RegularizeEmployeeChoice {
  employeeId: number;
  employeeCode: string;
  employeeName: string;
}

interface CalendarCell {
  iso: string;
  day: number;
  tone: string;
  eligible: boolean;
}

/**
 * Employee regularization drawer from My Attendance.
 * Shared by My Attendance, My Regularization, and My Punch Logs.
 * Dates and punches come from GET /hr/attendance/mine for the signed-in employee.
 */
@Component({
  selector: 'trishul-attendance-regularize-drawer',
  imports: [
    FormsModule,
    MatButton,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatLabel,
    MatOption,
    MatSelect,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-regularize-drawer.html',
  styleUrl: './attendance-regularize-drawer.scss',
  host: { '[class.embedded]': 'embedded()' },
})
export class AttendanceRegularizeDrawer implements OnInit {
  private readonly api = inject(AttendanceApi);
  private readonly snackBar = inject(MatSnackBar);

  /** YYYY-MM-DD to preselect after that month's attendance loads. */
  readonly initialDate = input<string | null>(null);
  /** Regular punch correction, or Comp Off for a worked holiday / weekly off. */
  readonly mode = input<RegularizeDrawerMode>('regularize');
  /** Daily Attendance: pick an employee, then load that person's punches into this same drawer. */
  readonly onBehalf = input(false);
  readonly employees = input<RegularizeEmployeeChoice[]>([]);
  readonly forEmployeeId = input<number | null>(null);
  /** Sit in the Daily Attendance column instead of covering the page. */
  readonly embedded = input(false);
  readonly closed = output<void>();
  readonly submitted = output<void>();

  protected readonly months = MONTHS;
  protected readonly weekdays = WEEKDAYS;
  protected readonly requestTypes = REQUEST_TYPES;
  protected readonly isCompOff = computed(() => this.mode() === 'compOff');
  protected readonly year = signal(new Date().getFullYear());
  protected readonly monthIndex = signal(new Date().getMonth());
  protected readonly loading = signal(false);
  protected readonly submitting = signal(false);
  protected readonly formError = signal('');
  protected readonly employeeId = signal(0);
  protected readonly employeeName = signal('');
  protected readonly employeeCode = signal('');
  protected readonly chosenEmployeeId = signal<number | null>(null);
  protected readonly canRegularize = signal(false);
  protected readonly items = signal<MineAttendanceDay[]>([]);
  protected readonly regularizations = signal<RegularizationRow[]>([]);
  protected readonly step = signal<DrawerStep>(1);
  protected readonly selectedIso = signal<string | null>(null);
  protected readonly requestType = signal<RegularizationRequestType>('Late Arrival');
  protected readonly requestedIn = signal('09:30');
  protected readonly requestedOut = signal('17:30');
  protected readonly reason = signal('');
  protected readonly attachmentName = signal<string | null>(null);
  protected readonly attachmentSize = signal<string | null>(null);

  protected readonly severities: Partial<Record<string, StatusSeverity>> = {
    Present: 'success',
    Late: 'warn',
    'In Progress': 'info',
    'Missing Punch': 'warn',
    Absent: 'danger',
    'On Leave': 'info',
    'Off Day': 'neutral',
    Holiday: 'neutral',
    Pending: 'warn',
    Approved: 'success',
    Rejected: 'danger',
  };

  private pendingIso: string | null = null;

  protected readonly regByDate = computed(() => {
    const map = new Map<string, RegularizationRow>();
    for (const row of this.regularizations()) map.set(row.attendanceDate.slice(0, 10), row);
    return map;
  });

  protected readonly dayByIso = computed(() => {
    const map = new Map<string, MineAttendanceDay>();
    for (const row of this.items()) map.set(row.date.slice(0, 10), row);
    return map;
  });

  protected readonly cells = computed(() =>
    buildMonth(
      this.year(),
      this.monthIndex(),
      this.items(),
      this.regByDate(),
      this.canRegularize(),
      this.mode(),
    ),
  );

  protected readonly selectedDay = computed(() => {
    const iso = this.selectedIso();
    return iso ? this.dayByIso().get(iso) ?? null : null;
  });

  protected readonly selectedLabel = computed(() => formatLong(this.selectedIso()));
  protected readonly requestLabel = computed(() =>
    this.isCompOff()
      ? 'Holiday Work (Comp Off)'
      : (REQUEST_TYPES.find((item) => item.value === this.requestType())?.label ?? this.requestType()),
  );
  protected readonly title = computed(() =>
    this.isCompOff() ? 'Request Comp Off' : 'Request Regularization',
  );
  protected readonly reasonCount = computed(() => this.reason().length);
  protected readonly requestedInLabel = computed(() => clockLabel(this.requestedIn()));
  protected readonly requestedOutLabel = computed(() => clockLabel(this.requestedOut()));

  ngOnInit(): void {
    const seed = this.initialDate();
    if (seed && /^\d{4}-\d{2}-\d{2}$/.test(seed)) {
      const [year, month] = seed.split('-').map(Number);
      this.year.set(year);
      this.monthIndex.set(month - 1);
      this.pendingIso = seed;
    }
    const preset = this.forEmployeeId();
    if (preset) this.chosenEmployeeId.set(preset);
    if (!this.onBehalf() || preset) this.load();
  }

  protected chooseEmployee(employeeId: number | null): void {
    if (!employeeId || employeeId === this.chosenEmployeeId()) return;
    this.chosenEmployeeId.set(employeeId);
    this.selectedIso.set(null);
    this.step.set(1);
    this.reason.set('');
    this.attachmentName.set(null);
    this.attachmentSize.set(null);
    this.formError.set('');
    this.load();
  }

  protected shiftMonth(delta: number): void {
    const cursor = new Date(this.year(), this.monthIndex() + delta, 1);
    this.year.set(cursor.getFullYear());
    this.monthIndex.set(cursor.getMonth());
    this.selectedIso.set(null);
    this.pendingIso = null;
    this.load();
  }

  protected close(): void {
    if (this.submitting()) return;
    this.closed.emit();
  }

  protected selectDate(iso: string): void {
    const row = this.dayByIso().get(iso);
    if (!row || !this.canPick(row)) return;
    this.selectedIso.set(iso);
    this.requestType.set(this.isCompOff() ? 'Holiday Work' : defaultRequestType(row.status));
    const window = shiftWindow(row.shift);
    this.requestedIn.set(toTimeValue(row.firstIn) ?? window.start);
    this.requestedOut.set(toTimeValue(row.lastOut) ?? window.end);
    this.formError.set('');
  }

  protected next(): void {
    if (this.step() === 1) {
      if (!this.selectedDay()) {
        this.formError.set('Select an eligible attendance date.');
        return;
      }
      this.formError.set('');
      this.step.set(2);
      return;
    }
    if (!this.detailsValid()) {
      this.formError.set(
        this.isCompOff()
          ? 'Punch-in, punch-out and a reason for working are required.'
          : 'Request type, punch-in time and a reason are required.',
      );
      return;
    }
    this.formError.set('');
    this.step.set(3);
  }

  protected back(): void {
    this.formError.set('');
    this.step.set(this.step() === 3 ? 2 : 1);
  }

  protected onReason(value: string): void {
    this.reason.set(value.slice(0, 250));
  }

  protected onFile(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    const allowed = ['application/pdf', 'image/jpeg', 'image/png'];
    if (!allowed.includes(file.type) && !/\.(pdf|jpe?g|png)$/i.test(file.name)) {
      this.formError.set('Attach a PDF, JPG or PNG file.');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      this.formError.set('Attachment must be 5 MB or smaller.');
      return;
    }
    this.formError.set('');
    this.attachmentName.set(file.name);
    this.attachmentSize.set(formatBytes(file.size));
  }

  protected clearAttachment(): void {
    this.attachmentName.set(null);
    this.attachmentSize.set(null);
  }

  protected submit(): void {
    const day = this.selectedDay();
    if (!day || !this.detailsValid() || this.submitting()) return;
    this.submitting.set(true);
    this.formError.set('');
    const reason = this.isCompOff()
      ? `Compensation: Compensatory Off (Comp Off)\n${this.reason().trim()}`.slice(0, 250)
      : this.reason().trim();
    const body = {
      employeeId: this.employeeId(),
      attendanceDate: day.date.slice(0, 10),
      requestType: this.isCompOff() ? ('Holiday Work' as RegularizationRequestType) : this.requestType(),
      requestedIn: clockLabel(this.requestedIn()),
      requestedOut: this.requestedOut() ? clockLabel(this.requestedOut()) : null,
      reason,
      attachmentName: this.attachmentName(),
    };
    const request = this.onBehalf()
      ? this.api.createRegularization(body)
      : this.api.createMineRegularization(body);
    request
      .subscribe({
        next: () => {
          this.submitting.set(false);
          this.snackBar.open(
            this.isCompOff() ? 'Comp Off request submitted.' : 'Regularization request submitted.',
            'OK',
            { duration: 2500 },
          );
          this.submitted.emit();
        },
        error: (err: unknown) => {
          this.submitting.set(false);
          this.formError.set(messageFrom(err));
        },
      });
  }

  private load(): void {
    if (this.onBehalf() && !this.chosenEmployeeId()) return;
    this.loading.set(true);
    this.formError.set('');
    const employeeId = this.onBehalf() ? this.chosenEmployeeId() ?? undefined : undefined;
    this.api.mine(this.year(), this.monthIndex() + 1, employeeId).subscribe({
      next: (page) => {
        this.employeeId.set(page.employeeId);
        this.employeeName.set(page.employeeName);
        this.employeeCode.set(page.employeeCode);
        this.canRegularize.set(page.canRegularize !== false && !page.isMonthFinalized);
        this.items.set(page.items);
        this.regularizations.set(page.regularizations ?? []);
        this.loading.set(false);
        if (!this.canRegularize()) {
          this.formError.set(
            this.isCompOff()
              ? 'This month is finalized. New Comp Off requests are locked.'
              : 'This month is finalized. New regularization requests are locked.',
          );
        }
        const iso = this.pendingIso;
        this.pendingIso = null;
        if (iso) this.selectDate(iso);
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.items.set([]);
        this.regularizations.set([]);
        this.formError.set(messageFrom(err));
      },
    });
  }

  private canPick(row: MineAttendanceDay): boolean {
    if (!this.canRegularize()) return false;
    if (row.resolved) return false;
    if (this.regByDate().has(row.date.slice(0, 10))) return false;
    if (this.isCompOff()) {
      return (row.status === 'Holiday' || row.status === 'Off Day') && !!row.firstIn && !!row.lastOut;
    }
    if (row.status === 'In Progress' || row.status === 'Holiday' || row.status === 'Off Day' || row.status === 'On Leave') {
      return false;
    }
    return row.status === 'Present' || row.status === 'Late' || row.status === 'Missing Punch' || row.status === 'Absent';
  }

  private detailsValid(): boolean {
    if (!this.requestedIn() || this.reason().trim().length === 0 || this.reason().trim().length > 250) {
      return false;
    }
    if (this.isCompOff() && !this.requestedOut()) return false;
    return true;
  }
}

function buildMonth(
  year: number,
  monthIndex: number,
  items: MineAttendanceDay[],
  requests: Map<string, RegularizationRow>,
  canRegularize: boolean,
  mode: RegularizeDrawerMode,
): CalendarCell[] {
  const byDate = new Map(items.map((row) => [row.date.slice(0, 10), row]));
  const first = new Date(year, monthIndex, 1);
  const count = new Date(year, monthIndex + 1, 0).getDate();
  const cells: CalendarCell[] = Array.from({ length: first.getDay() }, () => ({
    iso: '',
    day: 0,
    tone: 'empty',
    eligible: false,
  }));
  for (let day = 1; day <= count; day += 1) {
    const iso = `${year}-${String(monthIndex + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const row = byDate.get(iso);
    const tone = row ? toneFor(row.status) : 'plain';
    const open =
      canRegularize &&
      !!row &&
      !row.resolved &&
      !requests.has(iso) &&
      (mode === 'compOff'
        ? (row.status === 'Holiday' || row.status === 'Off Day') && !!row.firstIn && !!row.lastOut
        : tone === 'present' || tone === 'exception');
    cells.push({
      iso,
      day,
      tone: mode === 'compOff' && open ? 'exception' : tone,
      eligible: open,
    });
  }
  return cells;
}

function toneFor(status: AttendanceStatus): string {
  if (status === 'Present') return 'present';
  if (status === 'Late' || status === 'Missing Punch' || status === 'Absent') return 'exception';
  if (status === 'In Progress') return 'progress';
  if (status === 'Holiday' || status === 'Off Day' || status === 'On Leave') return 'off';
  return 'plain';
}

function defaultRequestType(status: AttendanceStatus): RegularizationRequestType {
  if (status === 'Late') return 'Late Arrival';
  if (status === 'Absent' || status === 'Missing Punch') return 'Missed Punch';
  return 'Wrong Attendance';
}

function shiftWindow(shift: string): { start: string; end: string } {
  const match = shift.match(/(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})/);
  if (!match) return { start: '09:30', end: '17:30' };
  return {
    start: `${match[1].padStart(2, '0')}:${match[2]}`,
    end: `${match[3].padStart(2, '0')}:${match[4]}`,
  };
}

function toTimeValue(value: string | null): string | null {
  if (!value || value === '—') return null;
  const match = value.trim().match(/^(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM)?$/i);
  if (!match) return null;
  let hours = Number(match[1]);
  const minutes = match[2];
  const meridiem = match[3]?.toUpperCase();
  if (meridiem === 'PM' && hours < 12) hours += 12;
  if (meridiem === 'AM' && hours === 12) hours = 0;
  return `${String(hours).padStart(2, '0')}:${minutes}`;
}

function clockLabel(value: string): string {
  const match = value.match(/^(\d{2}):(\d{2})$/);
  if (!match) return value;
  const date = new Date();
  date.setHours(Number(match[1]), Number(match[2]), 0, 0);
  return new Intl.DateTimeFormat('en-US', { hour: '2-digit', minute: '2-digit', hour12: true }).format(date);
}

function formatLong(iso: string | null): string {
  if (!iso) return '';
  const [year, month, day] = iso.split('-').map(Number);
  return new Date(year, month - 1, day).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function messageFrom(err: unknown): string {
  if (err instanceof HttpErrorResponse) {
    const detail = err.error?.detail ?? err.error?.message;
    if (typeof detail === 'string') return detail;
  }
  return err instanceof Error ? err.message : 'Failed to load attendance for this date.';
}
