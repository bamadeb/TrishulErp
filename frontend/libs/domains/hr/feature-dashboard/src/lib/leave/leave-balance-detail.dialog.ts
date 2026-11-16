import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogActions, MatDialogContent, MatDialogRef, MatDialogTitle } from '@angular/material/dialog';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { BalanceDetail, LeaveApi } from '@trishul/hr-data-access';

export interface LeaveBalanceDetailData {
  employeeId: number;
  year: number;
  focus: 'details' | 'transactions' | 'history' | 'adjust';
  canManage: boolean;
}

@Component({
  selector: 'trishul-leave-balance-detail-dialog',
  imports: [FormsModule, MatButton, MatDialogActions, MatDialogContent, MatDialogTitle, MatFormField, MatInput, MatLabel, MatOption, MatSelect],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './leave-balance-detail.dialog.html',
  styleUrl: './leave-balance-detail.dialog.scss',
})
export class LeaveBalanceDetailDialog {
  private readonly api = inject(LeaveApi);
  private readonly dialogRef = inject(MatDialogRef<LeaveBalanceDetailDialog, boolean>);
  protected readonly data = inject<LeaveBalanceDetailData>(MAT_DIALOG_DATA);
  protected readonly detail = signal<BalanceDetail | null>(null);
  protected readonly error = signal('');
  protected readonly leaveTypeId = signal<number | null>(null);
  protected readonly days = signal('');
  protected readonly reason = signal('');

  constructor() {
    this.load();
  }

  protected load(): void {
    this.api.balanceDetail(this.data.employeeId, this.data.year).subscribe({
      next: (row) => {
        this.detail.set(row);
        const first = row.types.find((type) => type.leaveTypeId != null);
        if (this.leaveTypeId() == null && first?.leaveTypeId) this.leaveTypeId.set(first.leaveTypeId);
      },
      error: () => this.error.set('The balance could not be loaded.'),
    });
  }

  protected save(): void {
    const typeId = this.leaveTypeId();
    if (typeId == null || this.reason().trim().length < 3) {
      this.error.set('Choose a leave type and enter a reason.');
      return;
    }
    this.api.adjustBalance(this.data.employeeId, {
      leaveTypeId: typeId, year: this.data.year, days: this.days(), reason: this.reason().trim(),
    }).subscribe({
      next: (row) => {
        this.detail.set(row);
        this.reason.set('');
        this.days.set('');
      },
      error: (error: { error?: { detail?: string } }) => this.error.set(this.detailText(error)),
    });
  }

  protected close(): void {
    this.dialogRef.close(true);
  }

  private detailText(error: { error?: { detail?: string } }): string {
    const text = error.error?.detail;
    return typeof text === 'string' && text ? text : 'The adjustment could not be saved.';
  }
}
