import { DatePipe } from '@angular/common';
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
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatSort, MatSortHeader, Sort } from '@angular/material/sort';
import { MatTableModule } from '@angular/material/table';
import { RouterLink } from '@angular/router';
import {
  EMPTY,
  Subject,
  catchError,
  debounceTime,
  distinctUntilChanged,
} from 'rxjs';
import {
  ALERT_RULE_MANAGE_PERMISSION,
  ALERT_RULE_STATUS_FILTERS,
  AlertRuleListStore,
  AlertRuleRow,
  AlertRulesApi,
} from '@trishul/admin-data-access';
import { AuthStore, HasPermission } from '@trishul/core-auth';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';

const STATUS_LABELS = { all: 'All', active: 'Active', inactive: 'Inactive' };
export const ACTIVE_SEVERITY: Record<string, StatusSeverity> = {
  Active: 'success',
  Inactive: 'neutral',
};
export const ALERT_SEVERITY: Record<string, StatusSeverity> = {
  Critical: 'danger',
  Warning: 'warn',
  Info: 'info',
};

/** Alert Master: the configured alert rules; add, edit, switch on and off. */
@Component({
  selector: 'trishul-alert-rule-list-page',
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
  ],
  providers: [AlertRuleListStore],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './alert-rule-list.page.html',
  styleUrl: './customer-list.page.scss',
})
export class AlertRuleListPage {
  protected readonly store = inject(AlertRuleListStore);
  private readonly api = inject(AlertRulesApi);
  private readonly snackBar = inject(MatSnackBar);
  protected readonly canManage = inject(AuthStore).hasPermission(
    ALERT_RULE_MANAGE_PERMISSION,
  );

  protected readonly columns = [
    'name',
    'alertType',
    'severity',
    'scope',
    'recipients',
    'openAlerts',
    'lastRunAt',
    'status',
    'actions',
  ];
  protected readonly statusFilters = ALERT_RULE_STATUS_FILTERS;
  protected readonly statusLabels = STATUS_LABELS;
  protected readonly activeSeverity = ACTIVE_SEVERITY;
  protected readonly alertSeverity = ALERT_SEVERITY;
  protected triggerLabel(trigger: AlertRuleRow['trigger']): string {
    return trigger === 'Event' ? 'When it happens' : 'Checked every minute';
  }

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

  protected setActive(rule: AlertRuleRow, active: boolean): void {
    (active ? this.api.activate(rule.id) : this.api.deactivate(rule.id))
      .pipe(catchError(() => EMPTY))
      .subscribe(() => {
        this.snackBar.open(
          `${rule.name} ${active ? 'switched on' : 'switched off'}`,
          'OK',
          { duration: 4000 },
        );
        this.store.reload();
      });
  }
}
