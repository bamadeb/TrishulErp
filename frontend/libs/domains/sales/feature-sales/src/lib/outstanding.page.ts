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
import { RouterLink } from '@angular/router';
import {
  ApiClient,
  ListOutstandingOrderLines$Params,
  listOutstandingOrderLines,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import { pagedList } from '@trishul/inventory-data-access';
import {
  CustomerPicker,
  NO_SALES_OPTIONS,
  PickedCustomer,
  SAL_DELIVERY_MANAGE,
  SalesLookups,
} from '@trishul/sales-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { rupees } from './sales.shared';

/** Order lines still to be delivered, oldest first, with what they are worth. */
@Component({
  selector: 'trishul-sales-outstanding-page',
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
    MatInput,
    MatSelect,
    MatOption,
    MatPaginator,
    MatProgressBar,
    CustomerPicker,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  template: `
    <trishul-page-header
      title="Orders to deliver"
      subtitle="Approved order lines with quantity still to go out"
    >
      <a mat-stroked-button routerLink="../orders"
        ><mat-icon>list</mat-icon>All orders</a
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
          placeholder="Order no, item or customer"
          aria-label="Search"
          (input)="search$.next($any($event.target).value)"
        />
      </mat-form-field>
      <trishul-customer-picker
        [formControl]="customer"
        style="flex: 1 1 16rem"
      />
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
      <mat-checkbox
        [checked]="!!query().overdueOnly"
        (change)="update({ overdueOnly: $event.checked })"
        >Past expected date</mat-checkbox
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
              <th>Customer</th>
              <th>Item</th>
              <th class="num">Ordered</th>
              <th class="num">Delivered</th>
              <th class="num">To deliver</th>
              <th class="num">Value</th>
              <th class="num">Days open</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (l of list.items(); track l.lineId) {
              <tr>
                <td>
                  <a
                    class="name"
                    [routerLink]="['/sales/orders', l.salesOrderId]"
                    >{{ l.orderNo }}</a
                  >
                  <div class="muted">
                    {{ l.orderDate | date: 'dd MMM'
                    }}{{
                      l.expectedDeliveryDate
                        ? ' · due ' + (l.expectedDeliveryDate | date: 'dd MMM')
                        : ''
                    }}
                  </div>
                </td>
                <td>
                  {{ l.customerName }}
                  <div class="muted">{{ l.branchName }}</div>
                </td>
                <td>
                  {{ l.itemCode }}
                  <div class="muted">{{ l.description }}</div>
                </td>
                <td class="num">
                  {{ l.qtyOrdered | number: '1.0-3' }} {{ l.uomCode ?? '' }}
                </td>
                <td class="num">{{ l.qtyDelivered | number: '1.0-3' }}</td>
                <td class="num negative">
                  {{ l.qtyToDeliver | number: '1.0-3' }}
                </td>
                <td class="num">{{ money(l.pendingValue) }}</td>
                <td class="num">{{ l.daysOpen }}</td>
                <td>
                  @if (canDeliver) {
                    <a
                      mat-button
                      routerLink="/sales/deliveries/new"
                      [queryParams]="{ orderId: l.salesOrderId }"
                      >Deliver</a
                    >
                  }
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="9" class="empty">
                  {{
                    list.loading()
                      ? 'Loading…'
                      : 'Nothing is waiting to be delivered.'
                  }}
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
        aria-label="Pages"
        (page)="onPage($event)"
      />
    </div>
  `,
})
export class SalesOutstandingPage {
  private readonly api = inject(ApiClient);
  protected readonly canDeliver =
    inject(AuthStore).hasPermission(SAL_DELIVERY_MANAGE);
  protected readonly money = rupees;
  protected readonly options = toSignal(inject(SalesLookups).options(), {
    initialValue: NO_SALES_OPTIONS,
  });
  protected readonly customer = new FormControl<PickedCustomer | null>(null);
  protected readonly query = signal<ListOutstandingOrderLines$Params>({
    page: 1,
    pageSize: 50,
  });
  protected readonly list = pagedList(this.query, (q) =>
    this.api.call(listOutstandingOrderLines, q),
  );
  protected readonly search$ = new Subject<string>();

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) => this.update({ search: search.trim() || null }));
    this.customer.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe((c) => this.update({ customerId: c?.id ?? null }));
  }

  protected update(change: Partial<ListOutstandingOrderLines$Params>): void {
    this.query.update((q) => ({ ...q, ...change, page: change.page ?? 1 }));
  }

  protected onPage(event: PageEvent): void {
    this.update({ page: event.pageIndex + 1, pageSize: event.pageSize });
  }
}
