import { MatOptgroup } from '@angular/material/core';
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
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';
import { RouterLink } from '@angular/router';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import {
  TEAM_MANAGE_PERMISSION,
  TEAM_STATUS_FILTERS,
  TeamListStore,
  TeamRow,
} from '@trishul/admin-data-access';
import { AuthStore, BranchGroupsPipe, HasPermission } from '@trishul/core-auth';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { ACTIVE_SEVERITY } from './alert-rule-list.page';
import { TeamActions } from './team-actions';

const STATUS_LABELS = { active: 'Active', inactive: 'Inactive', all: 'All' };

/** Teams: who leads which engineers. A team lead sees the service calls of their team. */
@Component({
  selector: 'trishul-team-list-page',
  imports: [
    BranchGroupsPipe,
    MatOptgroup,
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
    HasPermission,
    PageHeader,
    StatusBadge,
  ],
  providers: [TeamListStore],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './team-list.page.html',
  styleUrl: './customer-list.page.scss',
})
export class TeamListPage {
  protected readonly store = inject(TeamListStore);
  private readonly actions = inject(TeamActions);
  private readonly auth = inject(AuthStore);
  protected readonly canManage = this.auth.hasPermission(
    TEAM_MANAGE_PERMISSION,
  );
  protected readonly branches = computed(
    () => this.auth.user()?.branches ?? [],
  );

  protected readonly columns = [
    'name',
    'type',
    'lead',
    'members',
    'status',
    'actions',
  ];
  protected readonly statusFilters = TEAM_STATUS_FILTERS;
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

  protected deactivate(team: TeamRow): void {
    this.actions.deactivate(team).subscribe(() => this.store.reload());
  }

  protected activate(team: TeamRow): void {
    this.actions.activate(team).subscribe(() => this.store.reload());
  }
}
