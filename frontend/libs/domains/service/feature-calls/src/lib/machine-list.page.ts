import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  untracked,
} from '@angular/core';
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
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { AuthStore, HasPermission } from '@trishul/core-auth';
import {
  MACHINE_MANAGE_PERMISSION,
  MACHINE_STATUS_FILTERS,
  MachineListStore,
  MachineRow,
} from '@trishul/service-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { MachineActions } from './machine-actions';

const STATUS_LABELS = { active: 'Active', inactive: 'Inactive', all: 'All' };
const ACTIVE_SEVERITY: Record<string, StatusSeverity> = {
  Active: 'success',
  Inactive: 'neutral',
};

/** Machines of the selected brand with their owner; add, edit, deactivate and reactivate. */
@Component({
  selector: 'trishul-machine-list-page',
  imports: [
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
    MatIconButton,
    MatIcon,
    MatMenu,
    MatMenuItem,
    MatMenuTrigger,
    HasPermission,
    PageHeader,
    StatusBadge,
  ],
  providers: [MachineListStore],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './machine-list.page.html',
  styleUrl: './machine-list.page.scss',
})
export class MachineListPage {
  protected readonly store = inject(MachineListStore);
  private readonly actions = inject(MachineActions);
  private readonly auth = inject(AuthStore);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  protected readonly canManage = this.auth.hasPermission(
    MACHINE_MANAGE_PERMISSION,
  );

  protected readonly columns = [
    'serialNumber',
    'modelName',
    'customerName',
    'warrantyEndDate',
    'hmr',
    'status',
    'actions',
  ];
  protected readonly statusFilters = MACHINE_STATUS_FILTERS;
  protected readonly statusLabels = STATUS_LABELS;
  protected readonly activeSeverity = ACTIVE_SEVERITY;

  private readonly search$ = new Subject<string>();

  /** Set when opened from a customer's machine count (/service/machines?customerId=…). */
  readonly customerId = input<string>();

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) => this.store.updateQuery({ search }));
    effect(() => {
      const id = this.customerId();
      untracked(() => {
        const customerId = id ? Number(id) : undefined;
        if (customerId !== this.store.query().customerId)
          this.store.updateQuery({ customerId });
      });
    });
  }

  /** The customer the list is narrowed to, named from the first row. */
  protected readonly customerFilterName = computed(() =>
    this.store.query().customerId
      ? (this.store.items()[0]?.customerName ?? 'one customer')
      : null,
  );

  protected clearCustomer(): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { customerId: null },
      queryParamsHandling: 'merge',
    });
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

  protected deactivate(machine: MachineRow): void {
    this.actions.deactivate(machine).subscribe(() => this.store.reload());
  }

  protected activate(machine: MachineRow): void {
    this.actions.activate(machine).subscribe(() => this.store.reload());
  }
}
