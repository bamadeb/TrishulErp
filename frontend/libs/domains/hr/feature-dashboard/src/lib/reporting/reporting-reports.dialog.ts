import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import { ReportingPerson } from '@trishul/hr-data-access';

export interface DirectReportsData {
  managerName: string;
  reports: readonly ReportingPerson[];
}

@Component({
  selector: 'trishul-reporting-reports-dialog',
  imports: [MatButton, MatDialogTitle, MatDialogContent, MatDialogActions, MatDialogClose],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './reporting-reports.dialog.html',
  styleUrl: './reporting-reports.dialog.scss',
})
export class ReportingReportsDialog {
  private readonly dialogRef = inject(MatDialogRef<ReportingReportsDialog, number>);
  protected readonly data = inject<DirectReportsData>(MAT_DIALOG_DATA);
  protected readonly query = signal('');
  protected readonly department = signal('All');
  protected readonly status = signal<'All' | 'Active' | 'Inactive'>('All');
  protected readonly page = signal(0);
  protected readonly pageSize = 8;
  protected readonly departments = [...new Set(this.data.reports.map((row) => row.department))].sort((a, b) =>
    a.localeCompare(b),
  );

  protected readonly filtered = computed(() => {
    const term = this.query().trim().toLowerCase();
    return this.data.reports.filter((row) => {
      if (this.department() !== 'All' && row.department !== this.department()) return false;
      if (this.status() !== 'All' && row.status !== this.status()) return false;
      if (!term) return true;
      return `${row.code} ${row.name}`.toLowerCase().includes(term);
    });
  });

  protected readonly rows = computed(() => {
    const start = this.page() * this.pageSize;
    return this.filtered().slice(start, start + this.pageSize);
  });

  protected readonly range = computed(() => {
    const total = this.filtered().length;
    if (!total) return { start: 0, end: 0, total: 0 };
    const start = this.page() * this.pageSize + 1;
    return { start, end: Math.min(total, start + this.pageSize - 1), total };
  });

  constructor() {
    effect(() => {
      this.query();
      this.department();
      this.status();
      this.page.set(0);
    });
  }

  protected shown(name: string): string {
    const trimmed = name.trim();
    if (trimmed !== trimmed.toUpperCase()) return trimmed;
    return trimmed.toLowerCase().replace(/(^|[\s'-])([a-z])/g, (_, lead: string, letter: string) => `${lead}${letter.toUpperCase()}`);
  }

  protected initials(name: string): string {
    const parts = this.shown(name).split(' ').filter(Boolean);
    return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase();
  }

  protected onQuery(event: Event): void {
    this.query.set((event.target as HTMLInputElement).value);
  }

  protected onDepartment(event: Event): void {
    this.department.set((event.target as HTMLSelectElement).value);
  }

  protected onStatus(event: Event): void {
    this.status.set((event.target as HTMLSelectElement).value as 'All' | 'Active' | 'Inactive');
  }

  protected shift(step: number): void {
    const last = Math.max(0, Math.ceil(this.filtered().length / this.pageSize) - 1);
    this.page.set(Math.min(last, Math.max(0, this.page() + step)));
  }

  protected choose(id: number): void {
    this.dialogRef.close(id);
  }

  /** Closes the popup without a selected employee. */
  protected close(): void {
    this.dialogRef.close();
  }
}
