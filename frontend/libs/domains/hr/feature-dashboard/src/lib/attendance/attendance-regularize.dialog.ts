import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatDatepicker, MatDatepickerInput, MatDatepickerToggle } from '@angular/material/datepicker';
import {
  MAT_DIALOG_DATA,
  MatDialogClose,
  MatDialogRef,
} from '@angular/material/dialog';
import { MatFormField, MatLabel, MatPrefix, MatSuffix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { DailyAttendanceRow, RegularizationRequestType } from './attendance.models';

export type RegularizeRequestType = RegularizationRequestType;

export interface RegularizeEmployeeOption {
  id: number;
  employeeCode: string;
  employeeName: string;
  department: string;
  avatarTone: string;
  firstIn?: string | null;
  lastOut?: string | null;
  status?: string;
  /** When provided (DailyAttendanceRow), preferred over `id` for API create. */
  employeeId?: number;
}

export interface AttendanceRegularizeData {
  employee?: RegularizeEmployeeOption | DailyAttendanceRow | null;
  attendanceDate?: Date | null;
  employees?: readonly (RegularizeEmployeeOption | DailyAttendanceRow)[];
}

export interface RegularizeSubmitResult {
  employeeId: number;
  attendanceDate: string;
  requestType: RegularizeRequestType;
  requestedIn: string;
  requestedOut: string;
  reason: string;
  attachmentName: string | null;
}

const REQUEST_TYPES: RegularizeRequestType[] = [
  'Missed Punch',
  'Wrong Attendance',
  'Early Exit',
  'WFH Correction',
  'Late Arrival',
];

/** Regularize Attendance popup — returns submit payload for the caller to POST. */
@Component({
  selector: 'trishul-attendance-regularize-dialog',
  imports: [
    FormsModule,
    MatButton,
    MatDatepicker,
    MatDatepickerInput,
    MatDatepickerToggle,
    MatDialogClose,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatInput,
    MatLabel,
    MatOption,
    MatPrefix,
    MatSelect,
    MatSuffix,
    StatusBadge,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-regularize.dialog.html',
  styleUrl: './attendance-regularize.dialog.scss',
})
export class AttendanceRegularizeDialog {
  private readonly dialogRef = inject(
    MatDialogRef<AttendanceRegularizeDialog, RegularizeSubmitResult | null>,
  );
  protected readonly data = inject<AttendanceRegularizeData>(MAT_DIALOG_DATA);

  protected readonly requestTypes = REQUEST_TYPES;
  protected readonly employees = [...(this.data.employees ?? [])];

  protected readonly severities: Partial<Record<string, StatusSeverity>> = {
    Present: 'success',
    Late: 'warn',
    Absent: 'danger',
    'On Leave': 'info',
    WFH: 'info',
    'Missing Punch': 'warn',
  };

  protected readonly employeeId = signal<number | null>(
    resolveEmployeeId(this.data.employee),
  );
  protected readonly requestType = signal<RegularizeRequestType>('Missed Punch');
  protected readonly attendanceDate = signal<Date>(
    this.data.attendanceDate ? new Date(this.data.attendanceDate) : new Date(),
  );
  protected readonly currentIn = signal(this.data.employee?.firstIn ?? null);
  protected readonly currentOut = signal(this.data.employee?.lastOut ?? null);
  protected readonly requestedIn = signal(this.data.employee?.firstIn ?? '09:30 AM');
  protected readonly requestedOut = signal(this.data.employee?.lastOut ?? '06:30 PM');
  protected readonly reason = signal('');
  protected readonly attachmentName = signal<string | null>(null);
  protected readonly attachmentSize = signal<string | null>(null);

  protected readonly selectedEmployee = computed(() => {
    const id = this.employeeId();
    return (
      this.employees.find((row) => resolveEmployeeId(row) === id) ??
      this.data.employee ??
      null
    );
  });

  protected readonly canSubmit = computed(() => {
    const reason = this.reason().trim();
    return (
      !!this.selectedEmployee() &&
      !!this.requestedIn().trim() &&
      !!this.requestedOut().trim() &&
      reason.length > 0 &&
      reason.length <= 250
    );
  });

  protected readonly reasonCount = computed(() => this.reason().length);

  protected readonly lockEmployee = !!this.data.employee;

  protected initials(name: string): string {
    return name
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('');
  }

  protected optionId(row: RegularizeEmployeeOption | DailyAttendanceRow): number {
    return resolveEmployeeId(row) ?? row.id;
  }

  protected onEmployeeChange(id: number): void {
    this.employeeId.set(id);
    const employee = this.employees.find((row) => resolveEmployeeId(row) === id);
    if (!employee) return;
    this.currentIn.set(employee.firstIn ?? null);
    this.currentOut.set(employee.lastOut ?? null);
    this.requestedIn.set(employee.firstIn ?? '09:30 AM');
    this.requestedOut.set(employee.lastOut ?? '06:30 PM');
  }

  protected onReason(value: string): void {
    this.reason.set(value.slice(0, 250));
  }

  protected onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    this.attachmentName.set(file.name);
    this.attachmentSize.set(formatBytes(file.size));
    input.value = '';
  }

  protected clearAttachment(): void {
    this.attachmentName.set(null);
    this.attachmentSize.set(null);
  }

  protected submit(): void {
    if (!this.canSubmit()) return;
    const employeeId = resolveEmployeeId(this.selectedEmployee());
    if (employeeId == null) return;
    this.dialogRef.close({
      employeeId,
      attendanceDate: toIsoDate(this.attendanceDate()),
      requestType: this.requestType(),
      requestedIn: this.requestedIn().trim(),
      requestedOut: this.requestedOut().trim(),
      reason: this.reason().trim(),
      attachmentName: this.attachmentName(),
    });
  }
}

function resolveEmployeeId(
  employee: RegularizeEmployeeOption | DailyAttendanceRow | null | undefined,
): number | null {
  if (!employee) return null;
  if ('employeeId' in employee && typeof employee.employeeId === 'number') {
    return employee.employeeId;
  }
  return employee.id;
}

function toIsoDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
