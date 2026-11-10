import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialog,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { Observable } from 'rxjs';

export type PaymentMode = 'Payroll' | 'Bank transfer' | 'Cash';

export interface TadaPaymentData {
  employeeName: string;
  employeeCode: string;
  monthLabel: string;
  amountLabel: string;
}

export interface TadaPaymentResult {
  paymentDate: string;
  paymentMode: PaymentMode;
  paymentReference: string;
  remarks: string;
}

/** Records how an approved service-engineer TA amount was paid. */
@Component({
  selector: 'trishul-tada-payment-dialog',
  imports: [
    MatButton, MatDialogTitle, MatDialogContent, MatDialogActions, MatDialogClose,
    MatFormField, MatLabel, MatInput, MatSelect, MatOption,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Settle payment</h2>
    <mat-dialog-content>
      <dl>
        <div><dt>Employee</dt><dd>{{ data.employeeName }} ({{ data.employeeCode }})</dd></div>
        <div><dt>Payroll month</dt><dd>{{ data.monthLabel }}</dd></div>
        <div><dt>Amount</dt><dd>{{ data.amountLabel }}</dd></div>
      </dl>
      <p class="note">This pays the TA of approved trips only. Pending and rejected trips are not included.</p>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Payment date</mat-label>
        <input matInput type="date" [value]="paymentDate()" (input)="paymentDate.set($any($event.target).value)" />
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Payment mode</mat-label>
        <mat-select [value]="paymentMode()" (selectionChange)="paymentMode.set($event.value)">
          <mat-option value="Payroll">Payroll</mat-option>
          <mat-option value="Bank transfer">Bank transfer</mat-option>
          <mat-option value="Cash">Cash</mat-option>
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Payment reference</mat-label>
        <input matInput maxlength="40" [value]="paymentReference()" (input)="paymentReference.set($any($event.target).value)" placeholder="UTR or voucher number" />
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Remarks</mat-label>
        <textarea matInput rows="2" maxlength="300" [value]="remarks()" (input)="remarks.set($any($event.target).value)"></textarea>
      </mat-form-field>
      @if (attempted() && error()) {
        <p class="hint">{{ error() }}</p>
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" mat-dialog-close>Cancel</button>
      <button mat-flat-button color="primary" type="button" (click)="confirm()">Settle payment</button>
    </mat-dialog-actions>
  `,
  styles: `
    mat-dialog-content { display: grid; gap: 0.75rem; min-width: min(26rem, 78vw); }
    dl { display: grid; gap: 0.45rem; margin: 0; }
    dt { color: var(--mat-sys-on-surface-variant); font: var(--mat-sys-body-small); }
    dd { margin: 0.1rem 0 0; }
    .note, .hint { margin: 0; font: var(--mat-sys-body-small); }
    .note { color: var(--mat-sys-on-surface-variant); }
    .hint { color: var(--mat-sys-error); }
  `,
})
export class TadaPaymentDialog {
  protected readonly data = inject<TadaPaymentData>(MAT_DIALOG_DATA);
  private readonly dialogRef = inject(MatDialogRef<TadaPaymentDialog, TadaPaymentResult>);
  protected readonly paymentDate = signal(new Date().toISOString().slice(0, 10));
  protected readonly paymentMode = signal<PaymentMode>('Payroll');
  protected readonly paymentReference = signal('');
  protected readonly remarks = signal('');
  protected readonly attempted = signal(false);
  protected readonly error = signal('');

  protected confirm(): void {
    const reference = this.paymentReference().trim();
    if (!this.paymentDate()) {
      this.fail('Payment date is required.');
      return;
    }
    if (this.paymentMode() === 'Bank transfer' && !reference) {
      this.fail('A bank transfer needs a payment reference.');
      return;
    }
    this.dialogRef.close({
      paymentDate: this.paymentDate(),
      paymentMode: this.paymentMode(),
      paymentReference: reference,
      remarks: this.remarks().trim(),
    });
  }

  private fail(message: string): void {
    this.attempted.set(true);
    this.error.set(message);
  }
}

export function openTadaPayment(dialog: MatDialog, data: TadaPaymentData): Observable<TadaPaymentResult | undefined> {
  return dialog.open<TadaPaymentDialog, TadaPaymentData, TadaPaymentResult>(TadaPaymentDialog, {
    data,
    width: '28rem',
    autoFocus: 'first-tabbable',
  }).afterClosed();
}
