import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatProgressBar } from '@angular/material/progress-bar';
import { PayrollEmployeeDetail, PayrollLine, PayrollPreview, PayrollRunItem, PayrollRunsApi } from '@trishul/hr-data-access';
import { inr } from '../payroll.format';

export interface PayrollRunDialogData {
  run: PayrollRunItem;
  monthLabel: string;
  startWithPreview: boolean;
}

const EARNINGS: ReadonlyArray<readonly [string, string]> = [
  ['BASIC', 'Basic'],
  ['HRA', 'HRA'],
  ['CONV', 'Conveyance'],
  ['SPL', 'Special Allowance'],
  ['OTH_ALLOW', 'Other Allowance'],
  ['FIX_INC', 'Fixed Incentive'],
  ['TADA', 'TA/DA Reimbursement'],
];

const DEDUCTIONS: ReadonlyArray<readonly [string, string]> = [
  ['PF', 'PF'],
  ['ESI', 'ESI'],
  ['PT', 'Professional Tax'],
  ['IT', 'TDS'],
  ['LOAN', 'Loan'],
  ['SAL_ADV', 'Salary Advance'],
  ['OTH_DED', 'Other deductions'],
];

const KNOWN = new Set([...EARNINGS, ...DEDUCTIONS].map(([code]) => code));

/** Employee-wise payroll snapshot, with a preview before recalculation. */
@Component({
  selector: 'trishul-payroll-run-dialog',
  imports: [MatButton, MatDialogModule, MatProgressBar],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './payroll-run.dialog.html',
  styleUrl: './payroll-run.dialog.scss',
})
export class PayrollRunDialog {
  private readonly api = inject(PayrollRunsApi);
  private readonly dialogRef = inject(MatDialogRef<PayrollRunDialog, boolean>);
  protected readonly data = inject<PayrollRunDialogData>(MAT_DIALOG_DATA);
  protected readonly inr = inr;
  protected readonly earnings = EARNINGS;
  protected readonly deductions = DEDUCTIONS;
  protected readonly employees = signal<PayrollEmployeeDetail[]>([]);
  protected readonly preview = signal<PayrollPreview | null>(null);
  protected readonly loading = signal(true);
  protected readonly applying = signal(false);
  protected readonly error = signal('');
  protected readonly changed = signal(false);

  constructor() {
    this.loadDetails();
    if (this.data.startWithPreview) this.loadPreview();
  }

  protected money(value: string | null): string {
    return value == null ? '—' : inr(Number(value), 2);
  }

  protected line(employee: PayrollEmployeeDetail, code: string): PayrollLine | undefined {
    return employee.lines.find((item) => item.code === code);
  }

  protected otherLines(employee: PayrollEmployeeDetail): PayrollLine[] {
    return employee.lines.filter((item) => !KNOWN.has(item.code));
  }

  protected amount(employee: PayrollEmployeeDetail, code: string): string {
    const item = this.line(employee, code);
    return item ? inr(Number(item.amount), 2) : 'Not in this payslip';
  }

  protected canRecalculate(): boolean {
    return this.data.run.status === 'Draft' || this.data.run.status === 'Processed';
  }

  protected showPreview(): void {
    this.error.set('');
    this.loadPreview();
  }

  protected apply(): void {
    this.applying.set(true);
    this.error.set('');
    this.api.recalculate(this.data.run.id).subscribe({
      next: (run) => {
        this.data.run.employees = run.employees;
        this.data.run.gross = run.gross;
        this.data.run.deductions = run.deductions;
        this.data.run.netPay = run.netPay;
        this.data.run.status = run.status;
        this.changed.set(true);
        this.preview.set(null);
        this.applying.set(false);
        this.loadDetails();
      },
      error: (error: { error?: { detail?: string } }) => {
        this.applying.set(false);
        this.error.set(this.detail(error, 'Payroll could not be recalculated.'));
      },
    });
  }

  protected close(): void {
    this.dialogRef.close(this.changed());
  }

  private loadDetails(): void {
    this.loading.set(true);
    this.api.details(this.data.run.id).subscribe({
      next: (rows) => {
        this.employees.set(rows);
        this.loading.set(false);
      },
      error: (error: { error?: { detail?: string } }) => {
        this.loading.set(false);
        this.error.set(this.detail(error, 'Payroll details could not be loaded.'));
      },
    });
  }

  private loadPreview(): void {
    this.api.preview(this.data.run.id).subscribe({
      next: (row) => this.preview.set(row),
      error: (error: { error?: { detail?: string } }) => {
        this.error.set(this.detail(error, 'The recalculation preview could not be loaded.'));
      },
    });
  }

  private detail(error: { error?: { detail?: string } }, fallback: string): string {
    return typeof error.error?.detail === 'string' && error.error.detail ? error.error.detail : fallback;
  }
}
