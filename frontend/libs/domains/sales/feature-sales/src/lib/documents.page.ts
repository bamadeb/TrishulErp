import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
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
  DeliveryListItem,
  ReceiptListItem,
  SalesInvoiceListItem,
  getCustomerAccount,
  listDeliveries,
  listReceipts,
  listSalesInvoices,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import { isoDate, n0 } from '@trishul/inventory-data-access';
import {
  CustomerPicker,
  PickedCustomer,
  SAL_DELIVERY_MANAGE,
  SAL_INVOICE_CREATE_PERMISSIONS,
  SAL_RECEIPT_MANAGE,
} from '@trishul/sales-data-access';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import {
  EMPTY,
  Observable,
  Subject,
  catchError,
  debounceTime,
  distinctUntilChanged,
  of,
} from 'rxjs';
import { DELIVERY_STATUS, INVOICE_STATE, rupees } from './sales.shared';

export type SalesDocKind = 'delivery' | 'invoice' | 'receipt';
type Row = DeliveryListItem | SalesInvoiceListItem | ReceiptListItem;
interface Query {
  page: number;
  pageSize: number;
  search?: string | null;
  customerId?: number | null;
  fromDate?: string | null;
  toDate?: string | null;
  state?: SalesInvoiceListItem['state'] | null;
  flag?: boolean;
}

const TEXT: Record<SalesDocKind, { title: string; subtitle: string; add: string; search: string; flag: string;
  permissions: readonly string[] }> = {
  delivery: { title: 'Deliveries', subtitle: 'Goods sent to customers, against orders or direct',
    add: 'Direct delivery', search: 'Delivery no, order no, customer or vehicle', flag: 'Not fully invoiced',
    permissions: [SAL_DELIVERY_MANAGE] },
  invoice: { title: 'Sales invoices', subtitle: 'Customer invoices, what is outstanding and when it is due',
    add: 'New invoice', search: 'Invoice no, order no or customer', flag: 'Direct only',
    permissions: SAL_INVOICE_CREATE_PERMISSIONS },
  receipt: { title: 'Customer receipts', subtitle: 'Money received, order advances and what is still unallocated',
    add: 'Record receipt', search: 'Receipt no, reference or customer', flag: 'With unallocated amount',
    permissions: [SAL_RECEIPT_MANAGE] },
}; // prettier-ignore

/** Delivery / invoice / receipt lists (the route's data.kind). */
@Component({
  selector: 'trishul-sales-documents-page',
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
    CustomerPicker,
    PageHeader,
    StatusBadge,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  template: `
    <trishul-page-header [title]="text().title" [subtitle]="text().subtitle">
      @if (canAdd()) {
        <a mat-flat-button routerLink="new"
          ><mat-icon>add</mat-icon>{{ text().add }}</a
        >
      }
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
          [placeholder]="text().search"
          aria-label="Search"
          (input)="search$.next($any($event.target).value)"
        />
      </mat-form-field>
      <trishul-customer-picker
        [formControl]="customer"
        style="flex: 1 1 16rem"
      />
      @if (kind() === 'invoice') {
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>State</mat-label>
          <mat-select
            [value]="query().state ?? null"
            (valueChange)="update({ state: $event })"
          >
            <mat-option [value]="null">All</mat-option>
            <mat-option value="Unpaid">Not fully paid</mat-option>
            <mat-option value="Overdue">Overdue</mat-option>
            <mat-option value="Partially paid">Partially paid</mat-option>
            <mat-option value="Paid">Paid</mat-option>
            <mat-option value="Cancelled">Cancelled</mat-option>
          </mat-select>
        </mat-form-field>
      }
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
        [checked]="!!query().flag"
        (change)="update({ flag: $event.checked })"
        >{{ text().flag }}</mat-checkbox
      >
    </div>

    <div class="table-card">
      <div class="progress">
        @if (loading()) {
          <mat-progress-bar mode="indeterminate" />
        }
      </div>
      <div class="table-scroll">
        <table class="plain wide">
          @switch (kind()) {
            @case ('delivery') {
              <thead>
                <tr>
                  <th>Delivery</th>
                  <th>Date</th>
                  <th>Customer</th>
                  <th>Order</th>
                  <th>From</th>
                  <th>Status</th>
                  <th class="num">Qty</th>
                  <th class="num">Invoiced</th>
                </tr>
              </thead>
              <tbody>
                @for (d of deliveries(); track d.id) {
                  <tr>
                    <td>
                      <a class="name" [routerLink]="[d.id]">{{
                        d.deliveryNo
                      }}</a>
                    </td>
                    <td class="nowrap">
                      {{ d.deliveryDate | date: 'dd MMM yyyy' }}
                    </td>
                    <td>
                      {{ d.customerName }}
                      @if (d.customerSiteName) {
                        <div class="muted">{{ d.customerSiteName }}</div>
                      }
                    </td>
                    <td>{{ d.orderNo ?? 'Direct' }}</td>
                    <td>
                      {{ d.locationName }}
                      <div class="muted">{{ d.branchName }}</div>
                    </td>
                    <td>
                      <trishul-status-badge
                        [status]="d.status"
                        [severities]="deliveryStatus"
                      />
                    </td>
                    <td class="num">{{ d.totalQty | number: '1.0-3' }}</td>
                    <td class="num">{{ d.qtyInvoiced | number: '1.0-3' }}</td>
                  </tr>
                } @empty {
                  <tr>
                    <td colspan="8" class="empty">
                      {{ loading() ? 'Loading…' : 'Nothing matches.' }}
                    </td>
                  </tr>
                }
              </tbody>
            }
            @case ('invoice') {
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Date</th>
                  <th>Customer</th>
                  <th>Due</th>
                  <th>Against</th>
                  <th>State</th>
                  <th class="num">Total</th>
                  <th class="num">Outstanding</th>
                </tr>
              </thead>
              <tbody>
                @for (i of invoices(); track i.id) {
                  <tr>
                    <td>
                      <a class="name" [routerLink]="[i.id]">{{
                        i.invoiceNo
                      }}</a>
                    </td>
                    <td class="nowrap">
                      {{ i.invoiceDate | date: 'dd MMM yyyy' }}
                    </td>
                    <td>
                      {{ i.customerName }}
                      <div class="muted">
                        {{ i.principalName }} · {{ i.branchName }}
                      </div>
                    </td>
                    <td class="nowrap" [class.negative]="i.overdueDays > 0">
                      {{ i.dueDate ? (i.dueDate | date: 'dd MMM yyyy') : '—' }}
                      @if (i.overdueDays > 0) {
                        <div class="muted">{{ i.overdueDays }} days late</div>
                      }
                    </td>
                    <td>
                      {{
                        i.deliveryNo ??
                          i.orderNo ??
                          (i.isDirect ? 'Direct' : 'Deliveries')
                      }}
                    </td>
                    <td>
                      <trishul-status-badge
                        [status]="i.state"
                        [severities]="invoiceState"
                      />
                    </td>
                    <td class="num">{{ money(i.total) }}</td>
                    <td class="num">{{ money(i.outstanding) }}</td>
                  </tr>
                } @empty {
                  <tr>
                    <td colspan="8" class="empty">
                      {{ loading() ? 'Loading…' : 'Nothing matches.' }}
                    </td>
                  </tr>
                }
              </tbody>
            }
            @case ('receipt') {
              <thead>
                <tr>
                  <th>Receipt</th>
                  <th>Date</th>
                  <th>Customer</th>
                  <th>Type</th>
                  <th>Mode · reference</th>
                  <th class="num">Amount</th>
                  <th class="num">Unallocated</th>
                </tr>
              </thead>
              <tbody>
                @for (r of receipts(); track r.id) {
                  <tr>
                    <td>
                      <a class="name" [routerLink]="[r.id]">{{
                        r.receiptNo
                      }}</a>
                    </td>
                    <td class="nowrap">
                      {{ r.receiptDate | date: 'dd MMM yyyy' }}
                    </td>
                    <td>
                      {{ r.customerName }}
                      <div class="muted">{{ r.branchName }}</div>
                    </td>
                    <td>
                      {{ r.receiptType
                      }}{{ r.orderNo ? ' · ' + r.orderNo : '' }}
                    </td>
                    <td>
                      {{ r.paymentMode }}
                      <div class="muted">{{ r.referenceNo ?? '' }}</div>
                    </td>
                    <td class="num">{{ money(r.amount) }}</td>
                    <td class="num" [class.positive]="n0(r.unallocated) > 0">
                      {{ n0(r.unallocated) ? money(r.unallocated) : '—' }}
                    </td>
                  </tr>
                } @empty {
                  <tr>
                    <td colspan="7" class="empty">
                      {{ loading() ? 'Loading…' : 'Nothing matches.' }}
                    </td>
                  </tr>
                }
              </tbody>
            }
          }
        </table>
      </div>
      <mat-paginator
        [length]="total()"
        [pageIndex]="query().page - 1"
        [pageSize]="query().pageSize"
        [pageSizeOptions]="[20, 50, 100]"
        aria-label="Pages"
        (page)="onPage($event)"
      />
    </div>
  `,
})
export class SalesDocumentsPage {
  private readonly api = inject(ApiClient);
  private readonly auth = inject(AuthStore);

  readonly kind = input.required<SalesDocKind>();
  /** ?customerId=… from a customer page. */
  readonly customerId = input<string>();

  protected readonly text = computed(() => TEXT[this.kind()]);
  protected readonly canAdd = computed(() =>
    this.auth.hasAnyPermission(TEXT[this.kind()].permissions),
  );
  protected readonly deliveryStatus = DELIVERY_STATUS;
  protected readonly invoiceState = INVOICE_STATE;
  protected readonly money = rupees;
  protected readonly n0 = n0;
  protected readonly iso = isoDate;
  protected readonly customer = new FormControl<PickedCustomer | null>(null);
  protected readonly query = signal<Query>({ page: 1, pageSize: 20 });
  protected readonly search$ = new Subject<string>();

  private readonly rows = signal<Row[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(false);
  protected readonly deliveries = computed(
    () => this.rows() as DeliveryListItem[],
  );
  protected readonly invoices = computed(
    () => this.rows() as SalesInvoiceListItem[],
  );
  protected readonly receipts = computed(
    () => this.rows() as ReceiptListItem[],
  );

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) => this.update({ search: search.trim() || null }));
    this.customer.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe((c) => this.update({ customerId: c?.id ?? null }));
    effect(() => {
      const customer = Number(this.customerId());
      untracked(() => {
        if (customer)
          this.api
            .call(getCustomerAccount, { customerId: customer })
            .pipe(catchError(() => EMPTY))
            .subscribe((c) => this.customer.setValue(c));
        else this.update({});
      });
    });
  }

  protected update(change: Partial<Query>): void {
    this.query.update((q) => ({ ...q, ...change, page: change.page ?? 1 }));
    this.load();
  }

  protected onPage(event: PageEvent): void {
    this.update({ page: event.pageIndex + 1, pageSize: event.pageSize });
  }

  private load(): void {
    const q = this.query();
    const base = {
      page: q.page,
      pageSize: q.pageSize,
      search: q.search ?? null,
      customerId: q.customerId ?? null,
      fromDate: q.fromDate ?? null,
      toDate: q.toDate ?? null,
    };
    const requests: Record<
      SalesDocKind,
      () => Observable<{ items: Row[]; total: number }>
    > = {
      delivery: () =>
        this.api.call(listDeliveries, { ...base, uninvoicedOnly: !!q.flag }),
      invoice: () =>
        this.api.call(listSalesInvoices, {
          ...base,
          state: q.state ?? null,
          directOnly: !!q.flag,
        }),
      receipt: () =>
        this.api.call(listReceipts, { ...base, unallocatedOnly: !!q.flag }),
    };
    this.loading.set(true);
    requests[this.kind()]()
      .pipe(catchError(() => of({ items: [] as Row[], total: 0 })))
      .subscribe((page) => {
        this.rows.set(page.items);
        this.total.set(page.total);
        this.loading.set(false);
      });
  }
}
