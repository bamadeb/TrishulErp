import { ChangeDetectionStrategy, Component, Injectable, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { DateAdapter, MAT_DATE_FORMATS, MAT_NATIVE_DATE_FORMATS, NativeDateAdapter } from '@angular/material/core';
import { MatDatepicker, MatDatepickerInput, MatDatepickerToggle } from '@angular/material/datepicker';
import {
  MAT_DIALOG_DATA,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatFormField, MatHint, MatLabel, MatSuffix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { LeaveApi, MineApply } from '@trishul/hr-data-access';
import { MineDayPart, MineLeaveRequest } from './leave-mine.models';

export interface LeaveTypeChoice {
  id: number;
  label: string;
  maxBackdateDays: number | null;
  backdateRequiresAuthorization: boolean;
}

export interface LeaveApplyDialogData {
  mode: 'create' | 'edit' | 'view';
  request: MineLeaveRequest | null;
  leaveTypes: LeaveTypeChoice[];
  canAuthorizeBackdate: boolean;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const LEAVE_DATE_FORMATS = {
  ...MAT_NATIVE_DATE_FORMATS,
  parse: { ...MAT_NATIVE_DATE_FORMATS.parse, dateInput: 'DD-MMM-YYYY' },
  display: {
    ...MAT_NATIVE_DATE_FORMATS.display,
    dateInput: { day: '2-digit', month: 'short', year: 'numeric' },
  },
};

/** Calendar that shows 01-Jan-2027, matching the other leave screens. */
@Injectable()
class LeaveDateAdapter extends NativeDateAdapter {
  override format(date: Date, displayFormat: object): string {
    if (displayFormat === LEAVE_DATE_FORMATS.display.dateInput) {
      const day = String(date.getDate()).padStart(2, '0');
      return `${day}-${MONTHS[date.getMonth()]}-${date.getFullYear()}`;
    }
    return super.format(date, displayFormat);
  }

  override parse(value: unknown): Date | null {
    if (typeof value !== 'string') return value ? super.parse(value) : null;
    const match = /^(\d{1,2})-([A-Za-z]{3})-(\d{4})$/.exec(value.trim());
    if (!match) return super.parse(value);
    const month = MONTHS.findIndex((item) => item.toLowerCase() === match[2].toLowerCase());
    if (month < 0) return null;
    const parsed = new Date(Number(match[3]), month, Number(match[1]));
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }
}

@Component({
  selector: 'trishul-leave-apply-dialog',
  imports: [
    FormsModule,
    MatButton,
    MatDatepicker,
    MatDatepickerInput,
    MatDatepickerToggle,
    MatDialogActions,
    MatDialogClose,
    MatDialogContent,
    MatDialogTitle,
    MatFormField,
    MatHint,
    MatIcon,
    MatIconButton,
    MatInput,
    MatLabel,
    MatOption,
    MatSelect,
    MatSuffix,
  ],
  providers: [
    { provide: DateAdapter, useClass: LeaveDateAdapter },
    { provide: MAT_DATE_FORMATS, useValue: LEAVE_DATE_FORMATS },
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './leave-apply.dialog.html',
  styleUrl: './leave-apply.dialog.scss',
})
export class LeaveApplyDialog {
  private readonly dialogRef = inject(MatDialogRef<LeaveApplyDialog, boolean>);
  private readonly api = inject(LeaveApi);
  private readonly snackBar = inject(MatSnackBar);
  private previewToken = 0;
  protected readonly data = inject<LeaveApplyDialogData>(MAT_DIALOG_DATA);

  protected readonly types = this.data.leaveTypes;
  protected readonly parts: MineDayPart[] = ['Full day', 'First half', 'Second half'];
  protected readonly leaveType = signal(this.data.request?.leaveTypeId ?? this.types[0]?.id ?? null);
  protected readonly from = signal<Date | null>(parse(this.data.request?.from));
  protected readonly to = signal<Date | null>(parse(this.data.request?.to));
  protected readonly part = signal<MineDayPart>(this.data.request?.part ?? 'Full day');
  protected readonly reason = signal(this.data.request?.reason ?? '');
  protected readonly contact = signal(this.data.request?.contact ?? '');
  protected readonly fileName = signal(this.data.request?.fileName ?? '');
  protected readonly error = signal('');
  protected readonly dayCount = signal<string | null>(null);
  protected readonly counting = signal(false);
  protected readonly saving = signal(false);
  protected readonly viewing = this.data.mode === 'view';

  constructor() {
    this.dialogRef.updateSize('680px');
    this.dialogRef.disableClose = false;
    this.refreshDays();
  }

  protected title(): string {
    if (this.data.mode === 'edit') return 'Edit leave';
    if (this.data.mode === 'view') return this.data.request?.id ?? 'Leave request';
    return 'Apply leave';
  }

  protected dayLabel(): string {
    if (this.counting()) return '';
    return this.dayCount() ?? '';
  }

  protected openDate(picker: MatDatepicker<Date>): void {
    if (!this.viewing) picker.open();
  }

  protected onType(value: number): void {
    this.leaveType.set(value);
    this.refreshDays();
  }

  protected onPart(value: MineDayPart): void {
    this.part.set(value);
    if (value !== 'Full day' && this.from()) this.to.set(this.from());
    this.refreshDays();
  }

  protected onFrom(value: Date | null): void {
    this.from.set(value);
    const currentTo = this.to();
    if (this.part() !== 'Full day') {
      this.to.set(value);
    } else if (value && currentTo && strip(currentTo) < strip(value)) {
      this.to.set(null);
    }
    this.refreshDays();
  }

  protected onTo(value: Date | null): void {
    this.to.set(value);
    this.refreshDays();
  }

  protected chooseFile(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.fileName.set(input.files?.[0]?.name ?? '');
  }

  protected canSubmit(): boolean {
    if (this.viewing || this.saving() || this.counting() || this.error()) return false;
    const count = Number(this.dayCount());
    return this.dayBody() !== null && this.reason().trim().length > 0 && count > 0;
  }

  protected submit(): void {
    const body = this.payload();
    if (!body || this.saving()) return;
    this.saving.set(true);
    this.dialogRef.disableClose = true;
    const requestId = this.data.request?.requestId;
    const call = this.data.mode === 'edit' && requestId
      ? this.api.updateMineRequest(requestId, body)
      : this.api.applyLeave(body);
    call.subscribe({
      next: () => {
        this.snackBar.open('Leave request saved.', 'Close', { duration: 2500 });
        this.dialogRef.close(true);
      },
      error: (error: unknown) => {
        this.saving.set(false);
        this.dialogRef.disableClose = false;
        this.error.set(problemDetail(error, 'The leave request could not be saved.'));
      },
    });
  }

  private refreshDays(): void {
    const token = ++this.previewToken;
    const problem = this.rangeProblem();
    if (problem) {
      this.counting.set(false);
      this.dayCount.set(null);
      this.error.set(problem);
      return;
    }
    const body = this.dayBody();
    if (!body) {
      this.counting.set(false);
      this.dayCount.set(null);
      if (!this.saving()) this.error.set('');
      return;
    }
    this.counting.set(true);
    this.api.previewLeaveDays(body).subscribe({
      next: (row) => {
        if (token !== this.previewToken) return;
        this.counting.set(false);
        this.dayCount.set(row.days);
        if (Number(row.days) <= 0) this.error.set('The selected dates are weekly offs or holidays.');
        else if (!this.saving()) this.error.set('');
      },
      error: (error: unknown) => {
        if (token !== this.previewToken) return;
        this.counting.set(false);
        this.dayCount.set(null);
        this.error.set(problemDetail(error, 'The leave days could not be calculated.'));
      },
    });
  }

  protected earliest(): Date | null {
    return earliestLeaveDate(this.selectedType(), this.data.canAuthorizeBackdate);
  }

  protected toEarliest(): Date | null {
    const from = this.from();
    const earliest = this.earliest();
    if (!from) return earliest;
    if (!earliest) return strip(from);
    return strip(from) > earliest ? strip(from) : earliest;
  }

  protected backdateHint(): string {
    if (this.viewing) return '';
    const type = this.selectedType();
    if (!type || (type.backdateRequiresAuthorization && this.data.canAuthorizeBackdate)) return '';
    if (type.backdateRequiresAuthorization) return 'Past dates require HR authorization.';
    if (type.maxBackdateDays == null) return '';
    if (type.maxBackdateDays === 0) return 'Past dates are not allowed.';
    return `Past dates are allowed up to ${type.maxBackdateDays} calendar days.`;
  }

  private selectedType(): LeaveTypeChoice | undefined {
    return this.types.find((item) => item.id === this.leaveType());
  }

  private rangeProblem(): string {
    const from = this.from();
    const to = this.to();
    if (!this.viewing) {
      const blocked = backdateProblem(this.selectedType(), from, to, this.data.canAuthorizeBackdate);
      if (blocked) return blocked;
    }
    if (!from || !to) return '';
    if (strip(to) < strip(from)) return 'The to date is before the from date.';
    if (this.part() !== 'Full day' && strip(from).getTime() !== strip(to).getTime()) {
      return 'A half day applies to a single date.';
    }
    return '';
  }

  private dayBody(): Omit<MineApply, 'reason' | 'contact'> | null {
    const from = this.from();
    const to = this.to();
    const leaveTypeId = this.leaveType();
    if (!from || !to || leaveTypeId == null || this.rangeProblem()) return null;
    const part = this.part();
    return {
      leaveTypeId,
      fromDate: iso(from),
      toDate: iso(to),
      isHalfDay: part !== 'Full day',
      halfDayPart: part === 'Full day' ? null : part,
    };
  }

  private payload(): MineApply | null {
    const days = this.dayBody();
    if (!days || !this.reason().trim() || this.dayCount() == null || Number(this.dayCount()) <= 0) return null;
    const contact = this.contact().trim();
    return { ...days, reason: this.reason().trim(), contact: contact || null };
  }
}

function earliestLeaveDate(type: LeaveTypeChoice | undefined, canAuthorize: boolean): Date | null {
  if (!type || (type.backdateRequiresAuthorization && canAuthorize)) return null;
  const today = strip(new Date());
  if (type.backdateRequiresAuthorization) return today;
  if (type.maxBackdateDays == null) return null;
  today.setDate(today.getDate() - type.maxBackdateDays);
  return today;
}

function backdateProblem(
  type: LeaveTypeChoice | undefined,
  from: Date | null,
  to: Date | null,
  canAuthorize: boolean,
): string {
  const earliest = earliestLeaveDate(type, canAuthorize);
  if (!type || !earliest) return '';
  const tooEarly = (value: Date | null) => value != null && strip(value) < earliest;
  if (!tooEarly(from) && !tooEarly(to)) return '';
  if (type.backdateRequiresAuthorization) return 'Past dates for this leave type require HR authorization.';
  if (type.maxBackdateDays === 0) return 'This leave type cannot start before today.';
  const day = String(earliest.getDate()).padStart(2, '0');
  const label = `${day}-${MONTHS[earliest.getMonth()]}-${earliest.getFullYear()}`;
  return `This leave type can start at most ${type.maxBackdateDays} calendar days before today (${label}).`;
}

function parse(value: string | undefined): Date | null {
  return value ? new Date(`${value}T00:00:00`) : null;
}

function strip(value: Date): Date {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

function iso(value: Date): string {
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${value.getFullYear()}-${month}-${day}`;
}

function problemDetail(error: unknown, fallback: string): string {
  const detail = (error as { error?: { detail?: string } }).error?.detail;
  return typeof detail === 'string' && detail ? detail : fallback;
}

@Component({
  selector: 'trishul-leave-confirm-dialog',
  imports: [MatButton, MatDialogActions, MatDialogClose, MatDialogContent, MatDialogTitle],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Cancel request</h2>
    <mat-dialog-content>Cancel leave request {{ data }}? A pending request is not deducted from the balance.</mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" mat-dialog-close>Cancel</button>
      <button mat-flat-button color="primary" type="button" [mat-dialog-close]="true">Cancel request</button>
    </mat-dialog-actions>
  `,
})
export class LeaveConfirmDialog {
  protected readonly data = inject<string>(MAT_DIALOG_DATA);
}
