import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatFormField, MatLabel, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { ReportingApi, ReportingPerson } from '@trishul/hr-data-access';
import { ReportingAssignDialog } from './reporting-assign.dialog';
import { ReportingDemoStore } from './reporting.store';
import { ReportingTree } from './reporting-tree';

type ListTab = 'employees' | 'managers' | 'tree';

const STATUS_SEVERITY: Record<string, StatusSeverity> = {
  Active: 'success',
  Inactive: 'neutral',
};

@Component({
  selector: 'trishul-reporting-structure-page',
  imports: [
    PageHeader,
    StatusBadge,
    MatButton,
    MatCheckbox,
    MatFormField,
    MatLabel,
    MatPrefix,
    MatIcon,
    MatInput,
    MatSelect,
    MatOption,
    ReportingTree,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './reporting-structure.page.html',
  styleUrl: './reporting-structure.page.scss',
})
export class ReportingStructurePage {
  private readonly snackBar = inject(MatSnackBar);
  private readonly dialog = inject(MatDialog);
  private readonly store = inject(ReportingDemoStore);
  private readonly reporting = inject(ReportingApi);
  protected readonly severities = STATUS_SEVERITY;
  protected readonly tab = signal<ListTab>('employees');
  protected readonly search = signal('');
  protected readonly department = signal('All');
  protected readonly designation = signal('All');
  protected readonly location = signal('All');
  protected readonly status = signal<'All' | 'Active' | 'Inactive'>('All');
  protected readonly selected = signal<number[]>([]);

  protected readonly people = this.store.people;
  protected readonly departments = computed(() => unique(this.people().map((person) => person.department)));
  protected readonly designations = computed(() => unique(this.people().map((person) => person.designation)));
  protected readonly locations = computed(() => unique(this.people().map((person) => person.location)));

  constructor() {
    this.reload();
  }

  protected readonly cards = computed(() => {
    const rows = this.people();
    const assigned = rows.filter((person) => person.managerId !== null).length;
    const managers = rows.filter((person) => this.directReports(person.id) > 0).length;
    const unassigned = rows.filter((person) => person.managerId === null && this.directReports(person.id) === 0).length;
    return [
      { label: 'Total Employees', count: rows.length, icon: 'groups', tone: 'blue' },
      { label: 'Assigned', count: assigned, icon: 'how_to_reg', tone: 'green' },
      { label: 'Unassigned', count: unassigned, icon: 'person_off', tone: 'orange' },
      { label: 'Levels', count: unique(rows.map((person) => person.level)).length, icon: 'account_tree', tone: 'violet' },
      { label: 'Active Managers', count: managers, icon: 'supervisor_account', tone: 'cyan' },
    ];
  });

  protected readonly employeeRows = computed(() => this.applyFilters(this.people()));

  protected readonly managerRows = computed(() =>
    this.applyFilters(this.people().filter((person) => this.directReports(person.id) > 0)),
  );

  protected readonly visibleRows = computed(() =>
    this.tab() === 'employees' ? this.employeeRows() : this.managerRows(),
  );

  protected readonly allSelected = computed(() => {
    const rows = this.employeeRows();
    return rows.length > 0 && rows.every((row) => this.selected().includes(row.id));
  });

  protected managerName(id: number | null): string {
    if (id === null) return 'Not assigned';
    return this.people().find((person) => person.id === id)?.name ?? 'Not assigned';
  }

  protected directReports(id: number): number {
    return this.people().filter((person) => person.managerId === id).length;
  }

  protected isSelected(id: number): boolean {
    return this.selected().includes(id);
  }

  protected setTab(tab: ListTab): void {
    this.tab.set(tab);
  }

  protected onSearch(value: string): void {
    this.search.set(value);
  }

  protected toggle(id: number, checked: boolean): void {
    this.selected.update((ids) => (checked ? [...ids, id] : ids.filter((item) => item !== id)));
  }

  protected toggleAll(checked: boolean): void {
    this.selected.set(checked ? this.employeeRows().map((row) => row.id) : []);
  }

  protected clearSelection(): void {
    this.selected.set([]);
  }

  protected clearFilters(): void {
    this.search.set('');
    this.department.set('All');
    this.designation.set('All');
    this.location.set('All');
    this.status.set('All');
  }

  protected assignOne(): void {
    const count = this.selected().length;
    if (count !== 1) {
      this.snackBar.open('Select one employee to assign a manager.', 'Close', { duration: 2500 });
      return;
    }
    const employeeId = this.selected()[0];
    this.dialog
      .open(ReportingAssignDialog, { data: { employeeId }, width: '34rem', panelClass: 'reporting-assign-dialog' })
      .afterClosed()
      .subscribe((saved) => {
        if (!saved) return;
        this.selected.set([]);
        this.reload();
        this.snackBar.open('Reporting manager assigned.', 'Close', { duration: 2500 });
      });
  }

  private reload(): void {
    this.reporting.list().subscribe((rows) => this.store.replace(rows));
  }

  protected assignBulk(): void {
    const employeeIds = this.selected();
    if (employeeIds.length < 2) {
      this.snackBar.open('Select at least two employees for a bulk assign.', 'Close', { duration: 2500 });
      return;
    }
    this.dialog
      .open(ReportingAssignDialog, { data: { employeeIds }, width: '34rem', panelClass: 'reporting-assign-dialog' })
      .afterClosed()
      .subscribe((saved) => {
        if (!saved) return;
        this.selected.set([]);
        this.reload();
        this.snackBar.open('Reporting managers updated.', 'Close', { duration: 2500 });
      });
  }

  protected exportRows(): void {
    const header = ['Employee ID', 'Name', 'Designation', 'Department', 'Location', 'Reporting Manager', 'Level', 'Status'];
    const lines = this.visibleRows().map((row) =>
      [row.code, row.name, row.designation, row.department, row.location, this.managerName(row.managerId), row.level, row.status]
        .map((value) => `"${value.replaceAll('"', '""')}"`)
        .join(','),
    );
    const blob = new Blob([[header.join(','), ...lines].join('\n')], { type: 'text/csv' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'reporting-structure.csv';
    link.click();
    URL.revokeObjectURL(link.href);
  }

  private applyFilters(rows: readonly ReportingPerson[]): ReportingPerson[] {
    const term = this.search().trim().toLowerCase();
    return rows.filter((row) => {
      if (this.department() !== 'All' && row.department !== this.department()) return false;
      if (this.designation() !== 'All' && row.designation !== this.designation()) return false;
      if (this.location() !== 'All' && row.location !== this.location()) return false;
      if (this.status() !== 'All' && row.status !== this.status()) return false;
      if (!term) return true;
      return `${row.code} ${row.name}`.toLowerCase().includes(term);
    });
  }
}

function unique(values: string[]): string[] {
  return [...new Set(values)].sort((left, right) => left.localeCompare(right));
}
