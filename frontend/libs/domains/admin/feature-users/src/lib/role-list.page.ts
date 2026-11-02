import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
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
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';
import { MatTooltip } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import {
  ROLE_MANAGE_PERMISSION,
  ROLE_STATUS_FILTERS,
  RoleListStore,
  RoleRow,
  USER_VIEW_PERMISSIONS,
} from '@trishul/admin-data-access';
import { AuthStore, HasPermission } from '@trishul/core-auth';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { ACTIVE_SEVERITY } from './alert-rule-list.page';
import { RoleActions } from './role-actions';

const STATUS_LABELS = { active: 'Active', inactive: 'Inactive', all: 'All' };

/** Roles: what each one may do (its permissions) and how many users hold it; add, edit, deactivate. */
@Component({
  selector: 'trishul-role-list-page',
  imports: [
    RouterLink,
    MatTableModule,
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
    MatTooltip,
    HasPermission,
    PageHeader,
    StatusBadge,
  ],
  providers: [RoleListStore],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './role-list.page.html',
  styleUrl: './customer-list.page.scss',
})
export class RoleListPage {
  protected readonly store = inject(RoleListStore);
  private readonly actions = inject(RoleActions);
  private readonly auth = inject(AuthStore);
  protected readonly canManage = this.auth.hasPermission(
    ROLE_MANAGE_PERMISSION,
  );
  protected readonly canSeeUsers = this.auth.hasAnyPermission([
    ...USER_VIEW_PERMISSIONS,
  ]);

  protected readonly columns = [
    'name',
    'description',
    'permissions',
    'users',
    'status',
    'actions',
  ];
  protected readonly statusFilters = ROLE_STATUS_FILTERS;
  protected readonly statusLabels = STATUS_LABELS;
  protected readonly activeSeverity = ACTIVE_SEVERITY;

  private readonly search$ = new Subject<string>();

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) =>
        this.store.updateQuery({ search: search || undefined }),
      );
  }

  protected onSearch(value: string): void {
    this.search$.next(value.trim());
  }

  protected deactivate(role: RoleRow): void {
    this.actions.deactivate(role).subscribe(() => this.store.reload());
  }

  protected activate(role: RoleRow): void {
    this.actions.activate(role).subscribe(() => this.store.reload());
  }
}
