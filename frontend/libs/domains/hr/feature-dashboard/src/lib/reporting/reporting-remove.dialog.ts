import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { ReportingApi } from '@trishul/hr-data-access';

export interface ReportingRemoveData {
  employeeId: number;
  employeeName: string;
  employeeCode: string;
  managerName: string;
  hasTeam: boolean;
}

@Component({
  selector: 'trishul-reporting-remove-dialog',
  imports: [MatButton, MatDialogTitle, MatDialogContent, MatDialogActions, MatDialogClose, MatIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './reporting-remove.dialog.html',
  styleUrl: './reporting-remove.dialog.scss',
})
export class ReportingRemoveDialog {
  private readonly api = inject(ReportingApi);
  private readonly dialogRef = inject(MatDialogRef<ReportingRemoveDialog, boolean>);
  protected readonly data = inject<ReportingRemoveData>(MAT_DIALOG_DATA);
  protected readonly saving = signal(false);
  protected readonly error = signal('');

  protected confirm(): void {
    if (this.saving()) return;
    this.saving.set(true);
    this.error.set('');
    const today = new Date();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    this.api
      .remove({
        employeeId: this.data.employeeId,
        effectiveFrom: `${today.getFullYear()}-${month}-${day}`,
        remarks: 'Reporting manager removed.',
      })
      .subscribe({
        next: () => this.dialogRef.close(true),
        error: (error: HttpErrorResponse) => {
          this.saving.set(false);
          const problem = (error.error ?? {}) as { detail?: string };
          this.error.set(problem.detail || 'The reporting manager could not be removed.');
        },
      });
  }
}
