import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import {
  MatFormField,
  MatLabel,
  MatPrefix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSort, MatSortHeader, Sort } from '@angular/material/sort';
import { MatTableModule } from '@angular/material/table';
import { MatTooltip } from '@angular/material/tooltip';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { HasPermission } from '@trishul/core-auth';
import {
  CALL_PRIORITIES,
  CALL_STATUSES,
  CallPriority,
  CallStatus,
  ServiceCallListItem,
  ServiceCallListStore,
} from '@trishul/service-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';

const STATUS_SEVERITY: Record<CallStatus, StatusSeverity> = {
  Logged: 'info',
  Assigned: 'info',
  'Call ID linked': 'info',
  'Customer contacted': 'info',
  'Trip started': 'warn',
  'Reached site': 'warn',
  'In progress': 'warn',
  'Report submitted': 'warn',
  'Awaiting parts': 'danger',
  'Parts ready': 'warn',
  'Revisit scheduled': 'warn',
  Closed: 'success',
  'Pending OEM closure': 'neutral',
  Completed: 'success',
  Reopened: 'danger',
  Cancelled: 'contrast',
};

const PRIORITY_SEVERITY: Record<CallPriority, StatusSeverity> = {
  Critical: 'danger',
  High: 'warn',
  Normal: 'info',
  Low: 'neutral',
};

const FINISHED: ReadonlySet<CallStatus> = new Set([
  'Closed',
  'Pending OEM closure',
  'Completed',
  'Cancelled',
]);

/** Service call register: every call in the selected branch and brand, newest first. */
@Component({
  selector: 'trishul-call-list-page',
  imports: [
    DatePipe,
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
    MatTooltip,
    HasPermission,
    PageHeader,
    StatusBadge,
  ],
  providers: [ServiceCallListStore],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './call-list.page.html',
  styleUrl: './call-list.page.scss',
})
export class CallListPage {
  protected readonly store = inject(ServiceCallListStore);

  protected readonly columns = [
    'callNo',
    'customerName',
    'machine',
    'complaint',
    'priority',
    'status',
    'engineer',
    'slaDueAt',
  ];
  protected readonly statuses = CALL_STATUSES;
  protected readonly priorities = CALL_PRIORITIES;
  protected readonly statusSeverity = STATUS_SEVERITY;
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

  protected isSlaBreached(call: ServiceCallListItem): boolean {
    return (
      !!call.slaDueAt &&
      !FINISHED.has(call.currentStatus) &&
      new Date(call.slaDueAt) < new Date()
    );
  }
}
