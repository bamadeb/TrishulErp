import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatChip, MatChipSet } from '@angular/material/chips';
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
import {
  Subject,
  catchError,
  debounceTime,
  distinctUntilChanged,
  of,
} from 'rxjs';
import {
  USER_MANAGE_PERMISSION,
  USER_STATUS_FILTERS,
  UserListStore,
  UserRow,
  UsersApi,
  roleLabel,
} from '@trishul/admin-data-access';
import { AuthStore, HasPermission } from '@trishul/core-auth';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { UserActions } from './user-actions';

const STATUS_LABELS = { active: 'Active', inactive: 'Inactive', all: 'All' };
const ACTIVE_SEVERITY: Record<string, StatusSeverity> = {
  Active: 'success',
  Inactive: 'neutral',
};

/** Users of the ERP, with their roles; add, edit, deactivate and reset passwords. */
@Component({
  selector: 'trishul-user-list-page',
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
    MatChipSet,
    MatChip,
    HasPermission,
    PageHeader,
    StatusBadge,
  ],
  providers: [UserListStore],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './user-list.page.html',
  styleUrl: './user-list.page.scss',
})
export class UserListPage {
  protected readonly store = inject(UserListStore);
  private readonly actions = inject(UserActions);
  protected readonly canManage = inject(AuthStore).hasPermission(
    USER_MANAGE_PERMISSION,
  );

  protected readonly columns = [
    'employeeCode',
    'firstName',
    'lastName',
    'username',
    'phone',
    'designation',
    'roles',
    'status',
    'actions',
  ];
  protected readonly statusFilters = USER_STATUS_FILTERS;
  protected readonly statusLabels = STATUS_LABELS;
  protected readonly activeSeverity = ACTIVE_SEVERITY;
  protected readonly roleLabel = roleLabel;
  protected readonly roles = toSignal(
    inject(UsersApi)
      .roles()
      .pipe(catchError(() => of([]))),
    { initialValue: [] },
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

  protected deactivate(user: UserRow): void {
    this.actions.deactivate(user).subscribe(() => this.store.reload());
  }

  protected activate(user: UserRow): void {
    this.actions.activate(user).subscribe(() => this.store.reload());
  }

  protected resetPassword(user: UserRow): void {
    this.actions.resetPassword(user).subscribe();
  }
}
