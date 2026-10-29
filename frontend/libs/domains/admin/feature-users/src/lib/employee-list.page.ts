import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButton, MatIconButton } from '@angular/material/button';
import {
  MatFormField,
  MatLabel,
  MatPrefix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSort, MatSortHeader, Sort } from '@angular/material/sort';
import { MatTableModule } from '@angular/material/table';
import { RouterLink } from '@angular/router';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import {
  EMPLOYEE_MANAGE_PERMISSION,
  EMPLOYEE_STATUS_FILTERS,
  EMPLOYEE_TYPES,
  EmployeeListStore,
  EmployeeRow,
} from '@trishul/admin-data-access';
import { AuthStore, HasPermission } from '@trishul/core-auth';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { EmployeeActions } from './employee-actions';

const STATUS_LABELS = { active: 'Active', inactive: 'Inactive', all: 'All' };
const ACTIVE_SEVERITY: Record<string, StatusSeverity> = {
  Active: 'success',
  Inactive: 'neutral',
};

/** Employees of the company; add, edit, deactivate and reactivate. */
@Component({
  selector: 'trishul-employee-list-page',
  imports: [
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
  ],
  providers: [EmployeeListStore],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './employee-list.page.html',
  styleUrl: './employee-list.page.scss',
})
export class EmployeeListPage {
  protected readonly store = inject(EmployeeListStore);
  private readonly actions = inject(EmployeeActions);
  private readonly auth = inject(AuthStore);
  protected readonly canManage = this.auth.hasPermission(
    EMPLOYEE_MANAGE_PERMISSION,
  );

  protected readonly columns = [
    'employeeCode',
    'fullName',
    'mobile',
    'branch',
    'designation',
    'type',
    'status',
    'login',
    'actions',
  ];
  protected readonly statusFilters = EMPLOYEE_STATUS_FILTERS;
  protected readonly statusLabels = STATUS_LABELS;
  protected readonly employeeTypes = EMPLOYEE_TYPES;
  protected readonly activeSeverity = ACTIVE_SEVERITY;
  protected readonly branches = computed(
    () => this.auth.user()?.branches ?? [],
  );

  private readonly search$ = new Subject<string>();

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) => this.store.updateQuery({ search }));
  }

  protected onSearch(value: string): void {
    this.search$.next(value.trim());
  }

  protected onSort(sort: Sort): void {
    this.store.updateQuery({
      sort: sort.direction
        ? `${sort.direction === 'desc' ? '-' : ''}${sort.active}`
        : undefined,
    });
  }

  protected onPage(event: PageEvent): void {
    this.store.updateQuery({
      page: event.pageIndex + 1,
      pageSize: event.pageSize,
    });
  }

  protected deactivate(employee: EmployeeRow): void {
    this.actions.deactivate(employee).subscribe(() => this.store.reload());
  }

  protected activate(employee: EmployeeRow): void {
    this.actions.activate(employee).subscribe(() => this.store.reload());
  }
}
