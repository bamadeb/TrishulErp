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
import { MatFormField, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltip } from '@angular/material/tooltip';
import { PageHeader } from '@trishul/shared-ui';
import {
  ATTENDANCE_RULE_BLOCKS,
  HOLIDAY_ROWS,
  SHIFT_ASSIGNMENTS,
  SHIFT_KPI,
  SHIFT_ROWS,
} from './attendance-rules.mock';
import {
  RulesTab,
  ShiftRow,
  ShiftStatus,
} from './attendance.models';

/** Shift & Attendance Rules screen — UI-only static mock matching the HRMS reference. */
@Component({
  selector: 'trishul-attendance-rules-page',
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
  templateUrl: './attendance-rules.page.html',
  styleUrl: './attendance-rules.page.scss',
})
export class AttendanceRulesPage {
  private readonly snackBar = inject(MatSnackBar);

  protected readonly kpi = SHIFT_KPI;
  protected readonly ruleBlocks = ATTENDANCE_RULE_BLOCKS;
  protected readonly assignments = SHIFT_ASSIGNMENTS;
  protected readonly holidays = HOLIDAY_ROWS;
  protected readonly allShifts = signal<ShiftRow[]>(SHIFT_ROWS);

  protected readonly contentTab = signal<RulesTab>('shifts');
  protected readonly search = signal('');
  protected readonly status = signal<ShiftStatus | ''>('');
  protected readonly selectedIds = signal<Set<number>>(new Set());
  protected readonly menuRow = signal<ShiftRow | null>(null);

  protected readonly filteredShifts = computed(() => {
    const q = this.search().trim().toLowerCase();
    const status = this.status();
    return this.allShifts().filter((row) => {
      if (status && row.status !== status) return false;
      if (!q) return true;
      return `${row.code} ${row.name}`.toLowerCase().includes(q);
    });
  });

  protected readonly allSelected = computed(() => {
    const rows = this.filteredShifts();
    return rows.length > 0 && rows.every((row) => this.selectedIds().has(row.id));
  });

  protected readonly someSelected = computed(() => {
    const rows = this.filteredShifts();
    const selected = rows.filter((row) => this.selectedIds().has(row.id)).length;
    return selected > 0 && selected < rows.length;
  });

  protected setTab(tab: RulesTab): void {
    this.contentTab.set(tab);
  }

  protected onSearch(value: string): void {
    this.search.set(value);
  }

  protected onStatus(value: ShiftStatus | ''): void {
    this.status.set(value);
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
      for (const row of this.filteredShifts()) {
        if (checked) next.add(row.id);
        else next.delete(row.id);
      }
      return next;
    });
  }

  protected refresh(): void {
    this.snackBar.open('Shifts refreshed (sample data).', 'OK', { duration: 2000 });
  }

  protected exportExcel(): void {
    this.snackBar.open(`Exported ${this.filteredShifts().length} shift(s) (sample).`, 'OK', {
      duration: 2200,
    });
  }

  protected addShift(): void {
    this.snackBar.open('Add Shift is UI-only for now.', 'OK', { duration: 2200 });
  }

  protected editShift(row?: ShiftRow | null): void {
    const target = row ?? this.menuRow();
    if (!target) return;
    this.snackBar.open(`Edit ${target.name} (UI only).`, 'OK', { duration: 2200 });
  }

  protected deleteShift(row?: ShiftRow | null): void {
    const target = row ?? this.menuRow();
    if (!target) return;
    this.snackBar.open(`Delete ${target.name} (UI only).`, 'OK', { duration: 2200 });
  }

  protected editRules(): void {
    this.snackBar.open('Edit Rules is UI-only for now.', 'OK', { duration: 2200 });
  }

  protected typeClass(type: string): string {
    return type === 'Flexible' ? 'type flexible' : 'type regular';
  }

  protected statusClass(status: ShiftStatus): string {
    return status === 'Active' ? 'status active' : 'status inactive';
  }

  protected initials(name: string): string {
    return name
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('');
  }
}
