import { DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltip } from '@angular/material/tooltip';
import { PageHeader, confirmAction } from '@trishul/shared-ui';
import { filter } from 'rxjs';
import {
  FINALIZATION_CHECKLIST,
  FINALIZATION_DEPARTMENTS,
  FINALIZATION_KPI,
  FINALIZATION_LOCATIONS,
  FINALIZATION_SEED,
  FINALIZATION_SUMMARY,
} from './attendance-finalization.mock';
import {
  FinalizationGroupRow,
  FinalizationRowStatus,
  FinalizationTab,
} from './attendance.models';

const MONTH_LABELS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
] as const;

/** Attendance Finalization screen — UI-only static mock matching the HRMS reference. */
@Component({
  selector: 'trishul-attendance-finalization-page',
  imports: [
    DecimalPipe,
    FormsModule,
    MatButton,
    MatCheckbox,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatInput,
    MatMenu,
    MatMenuItem,
    MatMenuTrigger,
    MatOption,
    MatPrefix,
    MatSelect,
    MatTooltip,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attendance-finalization.page.html',
  styleUrl: './attendance-finalization.page.scss',
})
export class AttendanceFinalizationPage {
  private readonly snackBar = inject(MatSnackBar);
  private readonly dialog = inject(MatDialog);

  protected readonly kpi = FINALIZATION_KPI;
  protected readonly summary = FINALIZATION_SUMMARY;
  protected readonly checklist = signal(FINALIZATION_CHECKLIST.map((item) => ({ ...item })));
  protected readonly year = signal(FINALIZATION_SEED.year);
  protected readonly monthIndex = signal(FINALIZATION_SEED.monthIndex);

  protected readonly contentTab = signal<FinalizationTab>('department');
  protected readonly search = signal('');
  protected readonly groupFilter = signal('');
  protected readonly statusFilter = signal<FinalizationRowStatus | ''>('');
  protected readonly selectedIds = signal<Set<number>>(new Set());
  protected readonly menuRow = signal<FinalizationGroupRow | null>(null);

  protected readonly monthLabel = computed(
    () => `${MONTH_LABELS[this.monthIndex()]!} ${this.year()}`,
  );

  protected readonly groupLabel = computed(() =>
    this.contentTab() === 'department' ? 'Department' : 'Location',
  );

  protected readonly sourceRows = computed(() =>
    this.contentTab() === 'department' ? FINALIZATION_DEPARTMENTS : FINALIZATION_LOCATIONS,
  );

  protected readonly groupOptions = computed(() =>
    [...new Set(this.sourceRows().map((row) => row.name))].sort((a, b) => a.localeCompare(b)),
  );

  protected readonly filteredRows = computed(() => {
    const q = this.search().trim().toLowerCase();
    const group = this.groupFilter();
    const status = this.statusFilter();
    return this.sourceRows().filter((row) => {
      if (group && row.name !== group) return false;
      if (status && row.status !== status) return false;
      if (!q) return true;
      return row.name.toLowerCase().includes(q);
    });
  });

  protected readonly allSelected = computed(() => {
    const rows = this.filteredRows();
    return rows.length > 0 && rows.every((row) => this.selectedIds().has(row.id));
  });

  protected readonly someSelected = computed(() => {
    const rows = this.filteredRows();
    const selected = rows.filter((row) => this.selectedIds().has(row.id)).length;
    return selected > 0 && selected < rows.length;
  });

  protected readonly checklistDoneCount = computed(
    () => this.checklist().filter((item) => item.done).length,
  );

  protected setTab(tab: FinalizationTab): void {
    this.contentTab.set(tab);
    this.search.set('');
    this.groupFilter.set('');
    this.statusFilter.set('');
    this.selectedIds.set(new Set());
  }

  protected shiftMonth(delta: number): void {
    const date = new Date(this.year(), this.monthIndex() + delta, 1);
    this.year.set(date.getFullYear());
    this.monthIndex.set(date.getMonth());
    this.snackBar.open(
      `Showing finalization for ${MONTH_LABELS[date.getMonth()]} ${date.getFullYear()} (sample data).`,
      'OK',
      { duration: 2200 },
    );
  }

  protected onSearch(value: string): void {
    this.search.set(value);
  }

  protected onGroupFilter(value: string): void {
    this.groupFilter.set(value);
  }

  protected onStatusFilter(value: FinalizationRowStatus | ''): void {
    this.statusFilter.set(value);
  }

  protected isSelected(id: number): boolean {
    return this.selectedIds().has(id);
  }

  protected toggleRow(id: number, checked: boolean): void {
    this.selectedIds.update((set) => {
      const next = new Set(set);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  protected toggleAll(checked: boolean): void {
    this.selectedIds.update((set) => {
      const next = new Set(set);
      for (const row of this.filteredRows()) {
        if (checked) next.add(row.id);
        else next.delete(row.id);
      }
      return next;
    });
  }

  protected toggleChecklist(id: string, checked: boolean): void {
    this.checklist.update((items) =>
      items.map((item) => (item.id === id ? { ...item, done: checked } : item)),
    );
  }

  protected refresh(): void {
    this.snackBar.open('Finalization data refreshed (sample).', 'OK', { duration: 2000 });
  }

  protected exportExcel(): void {
    this.snackBar.open(`Exported ${this.filteredRows().length} row(s) (sample).`, 'OK', {
      duration: 2200,
    });
  }

  protected viewDetails(row?: FinalizationGroupRow | null): void {
    const target = row ?? this.menuRow();
    if (!target) return;
    this.snackBar.open(
      `${target.name}: ${target.readiness}% ready · ${target.exceptions} exception(s)`,
      'OK',
      { duration: 2800 },
    );
  }

  protected finalizeAttendance(): void {
    confirmAction(this.dialog, {
      title: 'Finalize & lock attendance?',
      message: `Once finalized, attendance for ${this.monthLabel()} will be locked and sent to Payroll for processing. This UI demo does not change live data.`,
      confirmText: 'Finalize & Lock',
      destructive: true,
    })
      .pipe(filter(Boolean))
      .subscribe(() => {
        this.snackBar.open(`Attendance for ${this.monthLabel()} finalized (UI only).`, 'OK', {
          duration: 2800,
        });
      });
  }

  protected statusClass(status: FinalizationRowStatus): string {
    switch (status) {
      case 'Ready':
        return 'status ready';
      case 'Review':
        return 'status review';
      case 'Pending':
        return 'status pending';
    }
  }

  protected statusIcon(status: FinalizationRowStatus): string {
    switch (status) {
      case 'Ready':
        return 'check_circle';
      case 'Review':
        return 'schedule';
      case 'Pending':
        return 'hourglass_empty';
    }
  }

  protected readinessTone(value: number): string {
    if (value >= 90) return 'high';
    if (value >= 80) return 'mid';
    return 'low';
  }
}
