import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatLabel, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSort, MatSortHeader, Sort } from '@angular/material/sort';
import { MatTableModule } from '@angular/material/table';
import { RouterLink } from '@angular/router';
import { Subject, debounceTime, distinctUntilChanged, filter } from 'rxjs';
import { AuthStore, HasPermission } from '@trishul/core-auth';
import {
  DepartmentOption,
  DesignationOption,
  EMPLOYEE_MANAGE_PERMISSION,
  EMPLOYEE_TYPES,
  EmployeeCounts,
  EmployeeListStore,
  EmployeeRow,
  EmployeeType,
  EmployeesApi,
} from '@trishul/hr-data-access';
import { PageHeader, StatusBadge, StatusSeverity, confirmAction } from '@trishul/shared-ui';
import { EmployeeActions } from '../employee-actions';
import { EmployeeColumnsDrawer } from './employee-columns.drawer';
import { DIRECTORY_OVERVIEW } from './employee-directory.mock';
import {
  EmployeeDirectoryPrefs,
  EmployeeSavedView,
  EmployeeViewFilters,
  yearsInService,
} from './employee-directory.prefs';
import { EmployeeHistoryDialog } from './employee-history.dialog';
import { EmployeeViewNameDialog } from './employee-view-name.dialog';

const STATUS_SEVERITY: Record<string, StatusSeverity> = {
  Active: 'success',
  Probation: 'warn',
  'Notice Period': 'info',
  Exited: 'danger',
  Archived: 'neutral',
};

type CardId = (typeof DIRECTORY_OVERVIEW)[number]['id'];

/** Employee directory. The rows and card totals come from GET /core/employees. */
@Component({
  selector: 'trishul-employee-list-page',
  imports: [
    DatePipe,
    RouterLink,
    MatTableModule,
    MatSort,
    MatSortHeader,
    MatPaginator,
    MatProgressBar,
    MatFormField,
    MatLabel,
    MatPrefix,
    MatInput,
    MatSelect,
    MatOption,
    MatButton,
    MatIconButton,
    MatIcon,
    MatMenu,
    MatMenuItem,
    MatMenuTrigger,
    HasPermission,
    PageHeader,
    StatusBadge,
    EmployeeColumnsDrawer,
  ],
  providers: [EmployeeListStore],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './employee-list.page.html',
  styleUrl: './employee-list.page.scss',
})
export class EmployeeListPage {
  protected readonly store = inject(EmployeeListStore);
  protected readonly prefs = inject(EmployeeDirectoryPrefs);
  private readonly actions = inject(EmployeeActions);
  private readonly api = inject(EmployeesApi);
  private readonly dialog = inject(MatDialog);
  private readonly auth = inject(AuthStore);
  protected readonly canManage = this.auth.hasPermission(EMPLOYEE_MANAGE_PERMISSION);

  protected readonly employeeTypes = EMPLOYEE_TYPES;
  protected readonly statusSeverity = STATUS_SEVERITY;
  protected readonly yearsInService = yearsInService;
  protected readonly displayedColumns = computed(() => [...this.prefs.columns(), 'actions']);
  protected readonly showDepartment = computed(() => this.prefs.columns().includes('department'));
  protected readonly columnsOpen = signal(false);
  protected readonly searchText = signal(this.prefs.filters().search);
  protected readonly departments = signal<DepartmentOption[]>([]);
  protected readonly designations = signal<DesignationOption[]>([]);
  protected readonly branches = computed(() => this.auth.user()?.branches ?? []);
  protected readonly activeView = computed(
    () => this.prefs.views().find((view) => view.id === this.prefs.activeViewId()) ?? null,
  );
  protected readonly cards = computed(() =>
    DIRECTORY_OVERVIEW.map((card) => ({ ...card, count: countFor(this.store.counts(), card.id) })),
  );
  protected readonly updatedLabel = new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date());

  private readonly search$ = new Subject<string>();

  constructor() {
    this.store.start(this.prefs.query());
    this.api.departments().subscribe((rows) => this.departments.set(rows));
    this.api.designations().subscribe((rows) => this.designations.set(rows));
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) => this.applyFilters({ search }));
  }

  protected selectCard(id: CardId): void {
    this.applyFilters({ lifecycle: id, status: 'all' });
  }

  protected onSearch(value: string): void {
    this.searchText.set(value);
    this.search$.next(value.trim());
  }

  protected onBranch(branchId: number | null): void {
    this.applyFilters({ branchId });
  }

  protected onDepartment(departmentId: number | null): void {
    this.applyFilters({ departmentId });
  }

  protected onDesignation(designationId: number | null): void {
    this.applyFilters({ designationId });
  }

  protected onType(employeeType: EmployeeType | null): void {
    this.applyFilters({ employeeType });
  }

  protected clearFilters(): void {
    this.searchText.set('');
    this.applyFilters({
      status: 'all',
      lifecycle: 'all',
      search: '',
      branchId: null,
      departmentId: null,
      designationId: null,
      employeeType: null,
    });
  }

  protected onSort(sort: Sort): void {
    const value = sort.direction ? `${sort.direction === 'desc' ? '-' : ''}${sort.active}` : 'fullName';
    this.prefs.rememberList({ sort: value });
    this.store.updateQuery({ sort: value });
  }

  protected onPage(event: PageEvent): void {
    this.prefs.rememberList({ pageSize: event.pageSize });
    this.store.updateQuery({ page: event.pageIndex + 1, pageSize: event.pageSize });
  }

  protected selectView(id: string): void {
    const filtersChanged = this.prefs.selectView(id);
    this.searchText.set(this.prefs.filters().search);
    if (filtersChanged) {
      this.store.updateQuery(this.prefs.query());
    }
  }

  protected saveCurrentView(): void {
    const active = this.activeView();
    if (active && !active.builtin) {
      this.prefs.overwriteActive();
      return;
    }
    this.askName('Save current view', '').subscribe((name) => this.prefs.saveCurrentView(name));
  }

  protected createView(): void {
    this.askName('Create view', '').subscribe((name) => this.prefs.saveCurrentView(name));
  }

  protected renameView(view: EmployeeSavedView): void {
    this.askName('Rename view', view.name).subscribe((name) => this.prefs.rename(view.id, name));
  }

  protected deleteView(view: EmployeeSavedView): void {
    confirmAction(this.dialog, {
      title: 'Delete saved view?',
      message: `"${view.name}" will be removed from your saved views. Employee records are not changed.`,
      confirmText: 'Delete',
      destructive: true,
    })
      .pipe(filter(Boolean))
      .subscribe(() => {
        const wasActive = this.prefs.activeViewId() === view.id;
        this.prefs.remove(view.id);
        this.searchText.set(this.prefs.filters().search);
        if (wasActive) this.store.updateQuery(this.prefs.query());
      });
  }

  protected setDefault(id: string): void {
    this.prefs.setDefault(id);
  }

  protected applyColumns(columnIds: string[]): void {
    this.prefs.applyColumns(columnIds);
    this.columnsOpen.set(false);
  }

  protected deactivate(employee: EmployeeRow): void {
    this.actions.deactivate(employee).subscribe(() => this.store.reload());
  }

  protected activate(employee: EmployeeRow): void {
    this.actions.activate(employee).subscribe(() => this.store.reload());
  }

  protected showHistory(employee: EmployeeRow): void {
    this.dialog.open(EmployeeHistoryDialog, {
      data: {
        employeeId: employee.id,
        fullName: employee.fullName,
        employeeCode: employee.employeeCode,
      },
      width: '28rem',
    });
  }

  protected statusLabel(employee: EmployeeRow): string {
    if (!employee.isActive) return 'Archived';
    if (employee.status === 'Notice') return 'Notice Period';
    if (employee.status === 'Exited') return 'Exited';
    return 'Active';
  }

  protected text(value: string | null | undefined): string {
    const trimmed = value?.trim();
    return trimmed ? trimmed : '—';
  }

  private applyFilters(change: Partial<EmployeeViewFilters>): void {
    this.prefs.patchFilters(change);
    this.store.updateQuery(this.prefs.query());
  }

  private askName(title: string, name: string) {
    return this.dialog
      .open<EmployeeViewNameDialog, { title: string; name: string }, string>(EmployeeViewNameDialog, {
        data: { title, name },
        width: '24rem',
      })
      .afterClosed()
      .pipe(filter((value): value is string => !!value?.trim()));
  }
}

function countFor(counts: EmployeeCounts, id: CardId): number {
  switch (id) {
    case 'all':
      return counts.allEmployees;
    case 'active':
      return counts.active;
    case 'probation':
      return counts.probation;
    case 'notice':
      return counts.notice;
    case 'exited':
      return counts.exited;
    case 'archived':
      return counts.archived;
  }
}
