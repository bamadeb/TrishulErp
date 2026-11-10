import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { provideNativeDateAdapter } from '@angular/material/core';
import {
  MatDatepicker,
  MatDatepickerInput,
  MatDatepickerToggle,
} from '@angular/material/datepicker';
import {
  MatFormField,
  MatLabel,
  MatPrefix,
  MatSuffix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { RouterLink } from '@angular/router';
import {
  ApiClient,
  ItemListItem,
  ListPurchaseOrders$Params,
  listPurchaseOrders,
} from '@trishul/core-api';
import { HasPermission } from '@trishul/core-auth';
import {
  InventoryLookups,
  ItemPicker,
  isoDate,
  pagedList,
} from '@trishul/inventory-data-access';
import { PUR_PO_MANAGE } from '@trishul/purchases-data-access';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { PO_STATUS, PO_STATUSES, rupees } from './purchases.shared';

/** Purchase orders inquiry: by number, supplier, branch, item, date, status, outstanding. */
@Component({
  selector: 'trishul-po-list-page',
  imports: [
    DatePipe,
    DecimalPipe,
    ReactiveFormsModule,
    RouterLink,
    MatButton,
    MatIcon,
    MatCheckbox,
    MatFormField,
    MatLabel,
    MatPrefix,
    MatSuffix,
    MatInput,
    MatSelect,
    MatOption,
    MatDatepicker,
    MatDatepickerInput,
    MatDatepickerToggle,
    MatPaginator,
    MatProgressBar,
    HasPermission,
    ItemPicker,
    PageHeader,
    StatusBadge,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  template: `
    <trishul-page-header
      title="Purchase orders"
      subtitle="Ordered, received and pending quantities of every order"
    >
      <a mat-stroked-button routerLink="../outstanding"
        ><mat-icon>pending_actions</mat-icon>Outstanding</a
      >
      <a mat-flat-button routerLink="new" *trishulHasPermission="manage"
        ><mat-icon>add</mat-icon>New order</a
      >
    </trishul-page-header>

    <div class="filters">
      <mat-form-field
        class="search"
        appearance="outline"
        subscriptSizing="dynamic"
      >
        <mat-icon matPrefix>search</mat-icon>
        <input
          matInput
          type="search"
          placeholder="PO no, supplier or OEM ref"
          aria-label="Search orders"
          (input)="search$.next($any($event.target).value)"
        />
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Status</mat-label>
        <mat-select
          [value]="query().status ?? null"
          (valueChange)="update({ status: $event })"
        >
          <mat-option [value]="null">All</mat-option>
          @for (s of statuses; track s) {
            <mat-option [value]="s">{{ s }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Supplier</mat-label>
        <mat-select
          [value]="query().supplierId ?? null"
          (valueChange)="update({ supplierId: $event })"
        >
          <mat-option [value]="null">All</mat-option>
          @for (s of suppliers(); track s.id) {
            <mat-option [value]="s.id">{{ s.name }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Branch</mat-label>
        <mat-select
          [value]="query().branchId ?? null"
          (valueChange)="update({ branchId: $event })"
        >
          <mat-option [value]="null">All</mat-option>
          @for (b of branches(); track b.id) {
            <mat-option [value]="b.id">{{ b.name }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
    </div>
    <div class="filters">
      <trishul-item-picker
        label="Item"
        [stockOnly]="false"
        [formControl]="item"
        style="flex: 1 1 18rem"
      />
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>From</mat-label>
        <input
          matInput
          [matDatepicker]="fromPicker"
          (dateChange)="
            update({ fromDate: $event.value ? iso($event.value) : null })
          "
        />
        <mat-datepicker-toggle matSuffix [for]="fromPicker" /><mat-datepicker
          #fromPicker
        />
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>To</mat-label>
        <input
          matInput
          [matDatepicker]="toPicker"
          (dateChange)="
            update({ toDate: $event.value ? iso($event.value) : null })
          "
        />
        <mat-datepicker-toggle matSuffix [for]="toPicker" /><mat-datepicker
          #toPicker
        />
      </mat-form-field>
      <mat-checkbox
        [checked]="!!query().outstandingOnly"
        (change)="update({ outstandingOnly: $event.checked })"
      >
        Still to receive
      </mat-checkbox>
    </div>

    <div class="table-card">
      <div class="progress">
        @if (list.loading()) {
          <mat-progress-bar mode="indeterminate" />
        }
      </div>
      <div class="table-scroll">
        <table class="plain wide">
          <thead>
            <tr>
              <th>PO no</th>
              <th>Date</th>
              <th>Supplier</th>
              <th>Deliver to</th>
              <th>Status</th>
              <th class="num">Ordered</th>
              <th class="num">Received</th>
              <th class="num">Pending</th>
              <th class="num">Total</th>
            </tr>
          </thead>
          <tbody>
            @for (po of list.items(); track po.id) {
              <tr>
                <td>
                  <a class="name" [routerLink]="[po.id]">{{ po.poNo }}</a>
                </td>
                <td class="nowrap">
                  {{ po.poDate | date: 'dd MMM yyyy' }}
                  @if (po.expectedDate) {
                    <div class="muted">
                      due {{ po.expectedDate | date: 'dd MMM' }}
                    </div>
                  }
                </td>
                <td>{{ po.supplierName }}</td>
                <td>
                  {{ po.branchName }}
                  <div class="muted">{{ po.locationName }}</div>
                </td>
                <td>
                  <trishul-status-badge
                    [status]="po.status"
                    [severities]="statusSeverity"
                  />
                </td>
                <td class="num">{{ po.qtyOrdered | number: '1.0-3' }}</td>
                <td class="num">{{ po.qtyReceived | number: '1.0-3' }}</td>
                <td class="num" [class.negative]="+po.qtyPending > 0">
                  {{ po.qtyPending | number: '1.0-3' }}
                </td>
                <td class="num">{{ money(po.total) }}</td>
              </tr>
            } @empty {
              <tr>
                <td colspan="9" class="empty">
                  {{ list.loading() ? 'Loading…' : 'No orders match.' }}
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
      <mat-paginator
        [length]="list.total()"
        [pageIndex]="(query().page ?? 1) - 1"
        [pageSize]="query().pageSize"
        [pageSizeOptions]="[20, 50, 100]"
        aria-label="Pages of orders"
        (page)="onPage($event)"
      />
    </div>
  `,
})
export class PoListPage {
  private readonly api = inject(ApiClient);
  private readonly lookups = inject(InventoryLookups);
  protected readonly manage = PUR_PO_MANAGE;
  protected readonly statuses = PO_STATUSES;
  protected readonly statusSeverity = PO_STATUS;
  protected readonly money = rupees;
  protected readonly iso = isoDate;

  protected readonly suppliers = toSignal(this.lookups.suppliers(), {
    initialValue: [],
  });
  protected readonly branches = toSignal(this.lookups.branches(), {
    initialValue: [],
  });
  protected readonly item = new FormControl<ItemListItem | null>(null);
  protected readonly query = signal<ListPurchaseOrders$Params>({
    page: 1,
    pageSize: 20,
  });
  protected readonly list = pagedList(this.query, (q) =>
    this.api.call(listPurchaseOrders, q),
  );
  protected readonly search$ = new Subject<string>();

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) => this.update({ search: search.trim() || null }));
    this.item.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe((item) => this.update({ itemId: item?.id ?? null }));
  }

  protected update(change: Partial<ListPurchaseOrders$Params>): void {
    this.query.update((q) => ({ ...q, ...change, page: change.page ?? 1 }));
  }

  protected onPage(event: PageEvent): void {
    this.update({ page: event.pageIndex + 1, pageSize: event.pageSize });
  }
}
