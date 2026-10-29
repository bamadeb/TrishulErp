import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButton, MatIconButton } from '@angular/material/button';
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
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import {
  CUSTOMER_MANAGE_PERMISSION,
  CUSTOMER_STATUS_FILTERS,
  CUSTOMER_TYPES,
  CustomerListStore,
  CustomerRow,
} from '@trishul/admin-data-access';
import { AuthStore, HasPermission } from '@trishul/core-auth';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { CustomerActions } from './customer-actions';

const STATUS_LABELS = { active: 'Active', inactive: 'Inactive', all: 'All' };
const ACTIVE_SEVERITY: Record<string, StatusSeverity> = {
  Active: 'success',
  Inactive: 'neutral',
};
const PRIORITY_SEVERITY: Record<string, StatusSeverity> = {
  Key: 'warn',
  Normal: 'info',
  Low: 'neutral',
};

/** Customers of the company; add, edit, deactivate and reactivate. */
@Component({
  selector: 'trishul-customer-list-page',
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
  providers: [CustomerListStore],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './customer-list.page.html',
  styleUrl: './customer-list.page.scss',
})
export class CustomerListPage {
  protected readonly store = inject(CustomerListStore);
  private readonly actions = inject(CustomerActions);
  private readonly auth = inject(AuthStore);
  protected readonly canManage = this.auth.hasPermission(
    CUSTOMER_MANAGE_PERMISSION,
  );

  protected readonly columns = [
    'code',
    'name',
    'type',
    'phone',
    'gstin',
    'priority',
    'status',
    'actions',
  ];
  protected readonly statusFilters = CUSTOMER_STATUS_FILTERS;
  protected readonly statusLabels = STATUS_LABELS;
  protected readonly customerTypes = CUSTOMER_TYPES;
  protected readonly activeSeverity = ACTIVE_SEVERITY;
  protected readonly prioritySeverity = PRIORITY_SEVERITY;

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

  protected deactivate(customer: CustomerRow): void {
    this.actions.deactivate(customer).subscribe(() => this.store.reload());
  }

  protected activate(customer: CustomerRow): void {
    this.actions.activate(customer).subscribe(() => this.store.reload());
  }
}
