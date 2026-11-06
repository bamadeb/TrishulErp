import { MatOptgroup } from '@angular/material/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import { MatFormField, MatLabel, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSort, MatSortHeader, Sort } from '@angular/material/sort';
import { MatTableModule } from '@angular/material/table';
import { RouterLink } from '@angular/router';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { AuthStore, BranchGroupsPipe, HasPermission } from '@trishul/core-auth';
import {
  ASC_IMPORT_PERMISSION,
  ASC_MANAGE_PERMISSION,
  ASC_STATUS_FILTERS,
  ASC_STATUS_LABELS,
  AscListStore,
} from '@trishul/service-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';

export const ASC_STATE_SEVERITY: Record<string, StatusSeverity> = {
  Active: 'success',
  Upcoming: 'info',
  Expired: 'warn',
  Cancelled: 'neutral',
};

/** ASC contracts in the user's branches: live, expiring, expired (renewal due) or cancelled. */
@Component({
  selector: 'trishul-asc-list-page',
  imports: [
    BranchGroupsPipe,
    MatOptgroup,
    DatePipe,
    DecimalPipe,
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
    MatIcon,
    HasPermission,
    PageHeader,
    StatusBadge,
  ],
  providers: [AscListStore],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './asc-list.page.html',
  styleUrl: './machine-list.page.scss',
})
export class AscListPage {
  protected readonly store = inject(AscListStore);
  private readonly auth = inject(AuthStore);

  protected readonly columns = [
    'contractNo',
    'machineSerialNo',
    'customerName',
    'branch',
    'endDate',
    'visits',
    'value',
    'state',
  ];
  protected readonly statusFilters = ASC_STATUS_FILTERS;
  protected readonly statusLabels = ASC_STATUS_LABELS;
  protected readonly stateSeverity = ASC_STATE_SEVERITY;
  protected readonly managePermission = ASC_MANAGE_PERMISSION;
  protected readonly importPermission = ASC_IMPORT_PERMISSION;
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
}
