import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import {
  MatFormField,
  MatLabel,
  MatPrefix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import {
  MatMenu,
  MatMenuContent,
  MatMenuItem,
  MatMenuTrigger,
} from '@angular/material/menu';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatSort, MatSortHeader, Sort } from '@angular/material/sort';
import { MatTableModule } from '@angular/material/table';
import { MatTooltip } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';
import {
  EMPTY,
  Subject,
  catchError,
  debounceTime,
  distinctUntilChanged,
  finalize,
  of,
} from 'rxjs';
import { AuthStore, HasPermission } from '@trishul/core-auth';
import {
  CALL_PRIORITIES,
  CALL_STATUSES,
  CallPriority,
  CallStatus,
  EngineerOption,
  SERVICE_CALL_ASSIGN_PERMISSION,
  ServiceCallApi,
  ServiceCallListItem,
  ServiceCallListStore,
  ServiceCallTriageUpdate,
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
    MatTooltip,
    MatMenu,
    MatMenuContent,
    MatMenuItem,
    MatMenuTrigger,
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
  private readonly api = inject(ServiceCallApi);
  private readonly auth = inject(AuthStore);
  private readonly snackBar = inject(MatSnackBar);

  /** A team lead can assign engineers and set priority inline. */
  protected readonly canAssign = this.auth.hasPermission(
    SERVICE_CALL_ASSIGN_PERMISSION,
  );
  /** Engineers of the selected branch, loaded once for the assign menu. */
  protected readonly engineers = toSignal(
    this.canAssign
      ? this.api.engineerOptions().pipe(catchError(() => of([])))
      : of<EngineerOption[]>([]),
    { initialValue: [] as EngineerOption[] },
  );
  /** The call currently being saved, so its controls disable while in flight. */
  protected readonly busyId = signal<number | null>(null);

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

  protected setPriority(call: ServiceCallListItem, priority: CallPriority): void {
    if (call.priority !== priority) this.apply(call, { priority });
  }

  protected setEngineer(
    call: ServiceCallListItem,
    engineerId: number | null,
  ): void {
    this.apply(call, { engineerId });
  }

  private apply(
    call: ServiceCallListItem,
    body: ServiceCallTriageUpdate,
  ): void {
    this.busyId.set(call.id);
    this.api
      .updateTriage(call.id, call.rowVersion, body)
      .pipe(
        finalize(() => this.busyId.set(null)),
        catchError(() => {
          this.store.reload(); // e.g. 409: refresh so the row shows the current state
          return EMPTY;
        }),
      )
      .subscribe((updated) => {
        this.store.applyUpdate(updated);
        this.snackBar.open(`${updated.callNo} updated`, 'OK', {
          duration: 3000,
        });
      });
  }
}
