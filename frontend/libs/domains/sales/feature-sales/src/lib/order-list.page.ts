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
  ListSalesOrders$Params,
  listSalesOrders,
} from '@trishul/core-api';
import { HasPermission } from '@trishul/core-auth';
import {
  ItemPicker,
  isoDate,
  n0,
  pagedList,
} from '@trishul/inventory-data-access';
import {
  CustomerPicker,
  NO_SALES_OPTIONS,
  PickedCustomer,
  SAL_ORDER_MANAGE,
  SalesLookups,
} from '@trishul/sales-data-access';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { ORDER_STATUS, ORDER_STATUSES, rupees } from './sales.shared';

/** Sales orders inquiry: number, customer, branch, item, date, status, outstanding, prepaid. */
@Component({
  selector: 'trishul-order-list-page',
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
    CustomerPicker,
    ItemPicker,
    PageHeader,
    StatusBadge,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  template: `
    <trishul-page-header
      title="Sales orders"
      subtitle="Ordered, delivered and invoiced quantities of every order"
    >
      <a mat-stroked-button routerLink="../outstanding"
        ><mat-icon>pending_actions</mat-icon>To deliver</a
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
          placeholder="Order no, customer or customer PO"
          aria-label="Search orders"
          (input)="search$.next($any($event.target).value)"
        />
      </mat-form-field>
      <trishul-customer-picker
        [formControl]="customer"
        style="flex: 1 1 16rem"
      />
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
        <mat-label>Branch</mat-label>
        <mat-select
          [value]="query().branchId ?? null"
          (valueChange)="update({ branchId: $event })"
        >
          <mat-option [value]="null">All</mat-option>
          @for (b of options().branches; track b.id) {
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
        >Still to deliver</mat-checkbox
      >
      <mat-checkbox
        [checked]="!!query().prepaidOnly"
        (change)="update({ prepaidOnly: $event.checked })"
        >Prepaid</mat-checkbox
      >
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
              <th>Order</th>
              <th>Date</th>
              <th>Customer</th>
              <th>Brand · branch</th>
              <th>Status</th>
              <th class="num">Ordered</th>
              <th class="num">Delivered</th>
              <th class="num">Invoiced</th>
              <th class="num">Advance</th>
              <th class="num">Total</th>
            </tr>
          </thead>
          <tbody>
            @for (o of list.items(); track o.id) {
              <tr>
                <td>
                  <a class="name" [routerLink]="[o.id]">{{ o.orderNo }}</a>
                  @if (o.customerPoNo) {
                    <div class="muted">PO {{ o.customerPoNo }}</div>
                  }
                </td>
                <td class="nowrap">
                  {{ o.orderDate | date: 'dd MMM yyyy' }}
                  @if (o.expectedDeliveryDate) {
                    <div class="muted">
                      due {{ o.expectedDeliveryDate | date: 'dd MMM' }}
                    </div>
                  }
                </td>
                <td>
                  {{ o.customerName }}
                  @if (o.customerSiteName) {
                    <div class="muted">{{ o.customerSiteName }}</div>
                  }
                </td>
                <td>
                  {{ o.principalName }}
                  <div class="muted">{{ o.branchName }}</div>
                </td>
                <td>
                  <trishul-status-badge
                    [status]="o.status"
                    [severities]="severity"
                  />
                  @if (o.isPrepaid) {
                    <div class="muted">Prepaid</div>
                  }
                </td>
                <td class="num">{{ o.qtyOrdered | number: '1.0-3' }}</td>
                <td class="num">{{ o.qtyDelivered | number: '1.0-3' }}</td>
                <td class="num">{{ o.qtyInvoiced | number: '1.0-3' }}</td>
                <td class="num">
                  {{ n0(o.advanceReceived) ? money(o.advanceReceived) : '—' }}
                </td>
                <td class="num">{{ money(o.total) }}</td>
              </tr>
            } @empty {
              <tr>
                <td colspan="10" class="empty">
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
export class OrderListPage {
  private readonly api = inject(ApiClient);
  protected readonly manage = SAL_ORDER_MANAGE;
  protected readonly statuses = ORDER_STATUSES;
  protected readonly severity = ORDER_STATUS;
  protected readonly money = rupees;
  protected readonly n0 = n0;
  protected readonly iso = isoDate;
  protected readonly options = toSignal(inject(SalesLookups).options(), {
    initialValue: NO_SALES_OPTIONS,
  });
  protected readonly customer = new FormControl<PickedCustomer | null>(null);
  protected readonly item = new FormControl<ItemListItem | null>(null);
  protected readonly query = signal<ListSalesOrders$Params>({
    page: 1,
    pageSize: 20,
  });
  protected readonly list = pagedList(this.query, (q) =>
    this.api.call(listSalesOrders, q),
  );
  protected readonly search$ = new Subject<string>();

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) => this.update({ search: search.trim() || null }));
    this.customer.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe((c) => this.update({ customerId: c?.id ?? null }));
    this.item.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe((i) => this.update({ itemId: i?.id ?? null }));
  }

  protected update(change: Partial<ListSalesOrders$Params>): void {
    this.query.update((q) => ({ ...q, ...change, page: change.page ?? 1 }));
  }

  protected onPage(event: PageEvent): void {
    this.update({ page: event.pageIndex + 1, pageSize: event.pageSize });
  }
}
