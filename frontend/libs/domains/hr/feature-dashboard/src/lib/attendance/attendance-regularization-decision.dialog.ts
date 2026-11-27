import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogClose, MatDialogRef } from '@angular/material/dialog';
import { MatFormField, MatLabel, MatSuffix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { RegularizationListRow } from './attendance.models';

export type RegularizationDecision = 'approve' | 'reject';

export interface RegularizationDecisionData {
  row: RegularizationListRow;
  decision: RegularizationDecision;
}

export interface RegularizationDecisionResult {
  decision: RegularizationDecision;
  reason?: string;
}

/** Approve or Reject with mandatory manager remarks (backend requires them for managers). */
@Component({
  selector: 'trishul-attendance-regularization-decision-dialog',
  imports: [
    FormsModule,
    MatButton,
    MatDialogClose,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatInput,
    MatLabel,
    MatSuffix,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-regularization-decision.dialog.html',
  styleUrl: './attendance-regularization-decision.dialog.scss',
})
export class AttendanceRegularizationDecisionDialog {
  private readonly dialogRef = inject(
    MatDialogRef<AttendanceRegularizationDecisionDialog, RegularizationDecisionResult | null>,
  );
  protected readonly data = inject<RegularizationDecisionData>(MAT_DIALOG_DATA);

  protected readonly reason = signal('');
  protected readonly reasonCount = computed(() => this.reason().length);
  protected readonly isReject = this.data.decision === 'reject';
  protected readonly submitting = signal(false);

  protected readonly canConfirm = computed(() => {
    if (this.submitting()) return false;
    const value = this.reason().trim();
    return value.length > 0 && value.length <= 250;
  });

  protected onReason(value: string): void {
    this.reason.set(value.slice(0, 250));
  }

  protected confirm(): void {
    if (!this.canConfirm()) return;
    this.submitting.set(true);
    this.dialogRef.close({
      decision: this.data.decision,
      reason: this.reason().trim(),
    });
  }
}
