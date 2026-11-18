import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogTitle,
} from '@angular/material/dialog';
import { ReportingApi, ReportingHistoryItem } from '@trishul/hr-data-access';

export interface ReportingHistoryData {
  employeeId: number;
  name: string;
}

@Component({
  selector: 'trishul-reporting-history-dialog',
  imports: [MatButton, MatDialogTitle, MatDialogContent, MatDialogActions, MatDialogClose],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './reporting-history.dialog.html',
  styleUrl: './reporting-history.dialog.scss',
})
export class ReportingHistoryDialog {
  private readonly api = inject(ReportingApi);
  protected readonly data = inject<ReportingHistoryData>(MAT_DIALOG_DATA);
  protected readonly rows = signal<ReportingHistoryItem[] | null>(null);
  protected readonly error = signal('');

  constructor() {
    this.api.history(this.data.employeeId).subscribe({
      next: (rows) => this.rows.set(rows),
      error: () => {
        this.rows.set([]);
        this.error.set('The reporting history could not be loaded.');
      },
    });
  }

  protected day(value: string): string {
    const [year, month, day] = value.split('-');
    return `${day}-${month}-${year}`;
  }
}
