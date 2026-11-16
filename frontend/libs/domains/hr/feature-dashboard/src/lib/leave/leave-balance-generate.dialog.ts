import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogActions, MatDialogContent, MatDialogRef, MatDialogTitle } from '@angular/material/dialog';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatOption, MatSelect } from '@angular/material/select';
import { EntitlementPreviewBoard, LeaveApi, LeavePolicyItem } from '@trishul/hr-data-access';

export interface LeaveBalanceGenerateData {
  policies: LeavePolicyItem[];
  policyId: number | null;
  year: number;
}

@Component({
  selector: 'trishul-leave-balance-generate-dialog',
  imports: [FormsModule, MatButton, MatDialogActions, MatDialogContent, MatDialogTitle, MatFormField, MatLabel, MatOption, MatSelect],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './leave-balance-generate.dialog.html',
  styleUrl: './leave-balance-detail.dialog.scss',
})
export class LeaveBalanceGenerateDialog {
  private readonly api = inject(LeaveApi);
  private readonly dialogRef = inject(MatDialogRef<LeaveBalanceGenerateDialog, boolean>);
  protected readonly data = inject<LeaveBalanceGenerateData>(MAT_DIALOG_DATA);
  protected readonly step = signal(1);
  protected readonly policyId = signal(this.data.policyId);
  protected readonly year = signal(this.data.year);
  protected readonly preview = signal<EntitlementPreviewBoard | null>(null);
  protected readonly error = signal('');
  protected readonly result = signal('');

  protected years(): number[] {
    const policy = this.data.policies.find((row) => row.id === this.policyId());
    const start = policy ? Number(policy.effectiveFrom.slice(0, 4)) : this.year();
    const end = Math.max(start, new Date().getFullYear()) + 1;
    return Array.from({ length: end - Math.min(start, this.year()) + 1 }, (_, index) => Math.min(start, this.year()) + index);
  }

  protected next(): void {
    const policyId = this.policyId();
    if (policyId == null) return;
    this.api.previewEntitlement({ policyId, year: this.year(), generationType: 'Annual' }).subscribe({
      next: (board) => {
        this.preview.set(board);
        this.step.set(2);
      },
      error: (error: { error?: { detail?: string } }) => this.error.set(this.detail(error)),
    });
  }

  protected generate(): void {
    const policyId = this.policyId();
    if (policyId == null) return;
    this.api.generateEntitlements({ policyId, year: this.year(), generationType: 'Annual' }).subscribe({
      next: (row) => {
        this.result.set(`${row.creditedEmployees} employees credited. ${row.skippedDuplicates} already generated. ${row.blocked} blocked.`);
        this.step.set(3);
      },
      error: (error: { error?: { detail?: string } }) => this.error.set(this.detail(error)),
    });
  }

  protected close(): void {
    this.dialogRef.close(this.step() === 3);
  }

  private detail(error: { error?: { detail?: string } }): string {
    const text = error.error?.detail;
    return typeof text === 'string' && text ? text : 'Entitlement generation could not continue.';
  }
}
