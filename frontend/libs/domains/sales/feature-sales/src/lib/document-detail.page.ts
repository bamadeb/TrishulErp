import { DatePipe, DecimalPipe, NgTemplateOutlet } from '@angular/common';
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
import { MatButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { RouterLink } from '@angular/router';
import {
  ApiClient,
  CustomerAllocationOut,
  DeliveryDetail,
  ReceiptDetail,
  SalesInvoiceDetail,
  cancelDelivery,
  cancelSalesInvoice,
  confirmDelivery,
  getDelivery,
  getReceipt,
  getSalesInvoice,
  reverseCustomerAllocation,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import { n0, openFieldsDialog } from '@trishul/inventory-data-access';
import {
  SAL_ALLOCATION_MANAGE,
  SAL_ALLOCATION_REVERSE,
  SAL_DELIVERY_MANAGE,
  SAL_INVOICE_CANCEL,
  SAL_INVOICE_MANAGE,
  SAL_RECEIPT_MANAGE,
} from '@trishul/sales-data-access';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { EMPTY, catchError, filter } from 'rxjs';
import { DELIVERY_STATUS, INVOICE_STATE, rupees } from './sales.shared';
import { SalesDocKind } from './documents.page';

/** One delivery note, sales invoice or receipt (the route's data.kind), with its actions. */
@Component({
  selector: 'trishul-sales-document-detail-page',
  imports: [
    DatePipe,
    DecimalPipe,
    NgTemplateOutlet,
    RouterLink,
    MatButton,
    MatIcon,
    MatProgressBar,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  template: `
    @switch (kind()) {
      @case ('delivery') {
        @if (delivery(); as d) {
          <trishul-page-header
            [title]="'Delivery ' + d.deliveryNo"
            [subtitle]="
              d.customerName + ' · ' + (d.deliveryDate | date: 'dd MMM yyyy')
            "
          >
            <a mat-stroked-button routerLink="/sales/deliveries"
              ><mat-icon>arrow_back</mat-icon>Deliveries</a
            >
            <a
              mat-stroked-button
              [routerLink]="['/print/sales/deliveries', d.id]"
              target="_blank"
              ><mat-icon>print</mat-icon>Delivery challan</a
            >
            @if (d.status === 'Dispatched' && can.deliver) {
              <button mat-stroked-button (click)="confirmReceived(d)">
                <mat-icon>task_alt</mat-icon>Mark received
              </button>
            }
            @if (
              live(d.status) &&
              n0(d.totalQty) > n0(d.qtyInvoiced) &&
              can.invoice
            ) {
              <a
                mat-flat-button
                routerLink="/sales/invoices/new"
                [queryParams]="{ customerId: d.customerId, deliveryId: d.id }"
                ><mat-icon>receipt_long</mat-icon>Invoice</a
              >
            }
            @if (live(d.status) && n0(d.qtyInvoiced) === 0 && can.deliver) {
              <button mat-stroked-button (click)="cancelNote(d)">
                <mat-icon>undo</mat-icon>Cancel delivery
              </button>
            }
          </trishul-page-header>
          <section class="card">
            <dl class="facts">
              <div>
                <dt>Status</dt>
                <dd>
                  <trishul-status-badge
                    [status]="d.status"
                    [severities]="deliveryStatus"
                  />
                </dd>
              </div>
              <div>
                <dt>Customer</dt>
                <dd>
                  <a
                    class="name"
                    [routerLink]="['/sales/customers', d.customerId]"
                    >{{ d.customerName }}</a
                  >
                  @if (d.customerSiteName) {
                    <div class="muted">{{ d.customerSiteName }}</div>
                  }
                </dd>
              </div>
              <div>
                <dt>Order</dt>
                <dd>
                  @if (d.salesOrderId) {
                    <a
                      class="name"
                      [routerLink]="['/sales/orders', d.salesOrderId]"
                      >{{ d.orderNo }}</a
                    >
                  } @else {
                    Direct delivery
                  }
                </dd>
              </div>
              <div>
                <dt>Dispatched from</dt>
                <dd>{{ d.locationName }} · {{ d.branchName }}</dd>
              </div>
              <div>
                <dt>Vehicle · transporter</dt>
                <dd>
                  {{ d.vehicleNo ?? '—'
                  }}{{ d.transporter ? ' · ' + d.transporter : '' }}
                </dd>
              </div>
              <div>
                <dt>LR / reference</dt>
                <dd>
                  {{ d.lrNo ?? '—'
                  }}{{ d.deliveryReference ? ' · ' + d.deliveryReference : '' }}
                </dd>
              </div>
              <div>
                <dt>Recipient</dt>
                <dd>
                  {{ d.receivedByName ?? '—'
                  }}{{ d.recipientPhone ? ' · ' + d.recipientPhone : '' }}
                  @if (d.deliveredAt) {
                    <div class="muted">
                      received {{ d.deliveredAt | date: 'dd MMM, HH:mm' }}
                    </div>
                  }
                </dd>
              </div>
              <div>
                <dt>Posted by</dt>
                <dd>
                  {{ d.postedBy ?? '—'
                  }}{{
                    d.dispatchedAt
                      ? ' · ' + (d.dispatchedAt | date: 'dd MMM, HH:mm')
                      : ''
                  }}
                </dd>
              </div>
              @if (d.cancelledAt) {
                <div>
                  <dt>Cancelled</dt>
                  <dd>{{ d.cancelledBy }} · {{ d.cancelReason }}</dd>
                </div>
              }
              <div style="grid-column: span 2">
                <dt>Delivery address</dt>
                <dd>{{ d.shipToAddress ?? '—' }}</dd>
              </div>
            </dl>
          </section>
          <div class="table-card">
            <div class="table-scroll">
              <table class="plain wide">
                <thead>
                  <tr>
                    <th>Item</th>
                    <th class="num">Qty</th>
                    <th class="num">Invoiced</th>
                    <th>GRN batches taken</th>
                    <th class="num">Cost</th>
                    <th class="num">Price</th>
                  </tr>
                </thead>
                <tbody>
                  @for (l of d.lines; track l.id) {
                    <tr>
                      <td>
                        {{ l.itemCode }}
                        <div class="muted">{{ l.description }}</div>
                      </td>
                      <td class="num">
                        {{ l.quantity | number: '1.0-3' }} {{ l.uomCode ?? '' }}
                      </td>
                      <td class="num">{{ l.qtyInvoiced | number: '1.0-3' }}</td>
                      <td>
                        @for (b of l.batches; track $index) {
                          <div>
                            {{ b.grnNo }} ({{
                              b.grnDate | date: 'dd MMM yyyy'
                            }}) · {{ b.quantity | number: '1.0-3' }}
                            {{ b.binCode ? '· rack ' + b.binCode : '' }}
                          </div>
                        } @empty {
                          <span class="muted"
                            >No stock taken (not a stock item)</span
                          >
                        }
                      </td>
                      <td class="num">{{ money(l.unitCost) }}</td>
                      <td class="num">{{ money(l.unitPrice) }}</td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          </div>
          @if (d.invoices.length) {
            <section class="card" style="margin-top: 1rem">
              <h2>Invoiced on</h2>
              @for (i of d.invoices; track i.id) {
                <div>
                  <a class="name" [routerLink]="['/sales/invoices', i.id]">{{
                    i.invoiceNo
                  }}</a>
                  · {{ i.invoiceDate | date: 'dd MMM yyyy' }} ·
                  {{ money(i.total) }} · {{ i.status }}
                </div>
              }
            </section>
          }
        } @else {
          <mat-progress-bar mode="indeterminate" />
        }
      }
      @case ('invoice') {
        @if (invoice(); as i) {
          <trishul-page-header
            [title]="'Invoice ' + i.invoiceNo"
            [subtitle]="
              i.customerName + ' · ' + (i.invoiceDate | date: 'dd MMM yyyy')
            "
          >
            <a mat-stroked-button routerLink="/sales/invoices"
              ><mat-icon>arrow_back</mat-icon>Invoices</a
            >
            <a
              mat-stroked-button
              [routerLink]="['/print/sales/invoices', i.id]"
              target="_blank"
              ><mat-icon>print</mat-icon>Print / PDF</a
            >
            @if (n0(i.outstanding) > 0 && can.receive) {
              <a
                mat-flat-button
                routerLink="/sales/receipts/new"
                [queryParams]="{ customerId: i.customerId }"
                ><mat-icon>payments</mat-icon>Record receipt</a
              >
            }
            @if (i.state !== 'Cancelled' && can.cancelInvoice) {
              <button mat-stroked-button (click)="cancelInvoice(i)">
                <mat-icon>block</mat-icon>Cancel invoice
              </button>
            }
          </trishul-page-header>
          <div class="tiles">
            <div class="tile">
              <div class="value">{{ money(i.total) }}</div>
              <div class="label">Total</div>
            </div>
            <div class="tile">
              <div class="value">{{ money(i.allocated) }}</div>
              <div class="label">Received / adjusted</div>
            </div>
            <div class="tile">
              <div class="value">{{ money(i.advanceAdjusted) }}</div>
              <div class="label">From order advances</div>
            </div>
            <div class="tile">
              <div class="value" [class.negative]="i.overdueDays > 0">
                {{ money(i.outstanding) }}
              </div>
              <div class="label">
                Outstanding{{
                  i.overdueDays > 0 ? ' · ' + i.overdueDays + ' days late' : ''
                }}
              </div>
            </div>
          </div>
          <section class="card">
            <dl class="facts">
              <div>
                <dt>State</dt>
                <dd>
                  <trishul-status-badge
                    [status]="i.state"
                    [severities]="invoiceState"
                  />
                </dd>
              </div>
              <div>
                <dt>Customer</dt>
                <dd>
                  <a
                    class="name"
                    [routerLink]="['/sales/customers', i.customerId]"
                    >{{ i.customerName }}</a
                  >
                  <div class="muted">{{ i.customerGstin ?? 'No GSTIN' }}</div>
                </dd>
              </div>
              <div>
                <dt>Due</dt>
                <dd>
                  {{ i.dueDate ? (i.dueDate | date: 'dd MMM yyyy') : '—' }}
                </dd>
              </div>
              <div>
                <dt>Type · source</dt>
                <dd>{{ i.invoiceType }} · {{ i.sourceType }}</dd>
              </div>
              <div>
                <dt>Brand · branch</dt>
                <dd>{{ i.principalName }} · {{ i.branchName }}</dd>
              </div>
              <div>
                <dt>Place of supply</dt>
                <dd>{{ i.placeOfSupply }}</dd>
              </div>
              @if (i.orderNo) {
                <div>
                  <dt>Order</dt>
                  <dd>
                    <a
                      class="name"
                      [routerLink]="['/sales/orders', i.salesOrderId]"
                      >{{ i.orderNo }}</a
                    >
                  </dd>
                </div>
              }
              @if (i.locationName) {
                <div>
                  <dt>Stock taken from</dt>
                  <dd>{{ i.locationName }}</dd>
                </div>
              }
              <div>
                <dt>Posted by</dt>
                <dd>{{ i.postedBy ?? '—' }}</dd>
              </div>
              @if (i.creditOverrideBy) {
                <div>
                  <dt>Credit limit overridden</dt>
                  <dd>{{ i.creditOverrideBy }}</dd>
                </div>
              }
              @if (i.cancelledAt) {
                <div>
                  <dt>Cancelled</dt>
                  <dd>{{ i.cancelledBy }} · {{ i.cancelReason }}</dd>
                </div>
              }
              <div style="grid-column: span 2">
                <dt>Billing address</dt>
                <dd>{{ i.billToAddress ?? '—' }}</dd>
              </div>
              <div style="grid-column: span 2">
                <dt>Delivery address</dt>
                <dd>{{ i.shipToAddress ?? '—' }}</dd>
              </div>
            </dl>
          </section>
          <div class="table-card">
            <div class="table-scroll">
              <table class="plain wide">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Item</th>
                    <th>From</th>
                    <th class="num">Qty</th>
                    <th class="num">Price</th>
                    <th class="num">Disc</th>
                    <th class="num">Taxable</th>
                    <th class="num">GST</th>
                    <th class="num">Total</th>
                  </tr>
                </thead>
                <tbody>
                  @for (l of i.lines; track l.id) {
                    <tr>
                      <td>{{ l.lineNo }}</td>
                      <td>
                        {{ l.itemCode ?? '' }}
                        <div [class.muted]="!!l.itemCode">
                          {{ l.description }}
                        </div>
                      </td>
                      <td>
                        {{ l.deliveryNo ?? 'Direct'
                        }}{{ l.orderNo ? ' · ' + l.orderNo : '' }}
                      </td>
                      <td class="num">
                        {{ l.quantity | number: '1.0-3' }} {{ l.uomCode ?? '' }}
                      </td>
                      <td class="num">{{ money(l.unitPrice) }}</td>
                      <td class="num">
                        {{
                          n0(l.discountPct)
                            ? (l.discountPct | number: '1.0-2') + '%'
                            : ''
                        }}
                      </td>
                      <td class="num">{{ money(l.taxableValue) }}</td>
                      <td class="num">{{ l.gstPct | number: '1.0-2' }}%</td>
                      <td class="num">{{ money(l.lineTotal) }}</td>
                    </tr>
                  }
                </tbody>
                <tfoot>
                  <tr>
                    <td colspan="8">Taxable</td>
                    <td class="num">{{ money(i.taxableValue) }}</td>
                  </tr>
                  @if (n0(i.igst)) {
                    <tr>
                      <td colspan="8">IGST</td>
                      <td class="num">{{ money(i.igst) }}</td>
                    </tr>
                  } @else {
                    <tr>
                      <td colspan="8">CGST + SGST</td>
                      <td class="num">
                        {{ money(i.cgst) }} + {{ money(i.sgst) }}
                      </td>
                    </tr>
                  }
                  @if (n0(i.otherCharges)) {
                    <tr>
                      <td colspan="8">Other charges</td>
                      <td class="num">{{ money(i.otherCharges) }}</td>
                    </tr>
                  }
                  @if (n0(i.roundOff)) {
                    <tr>
                      <td colspan="8">Round off</td>
                      <td class="num">{{ money(i.roundOff) }}</td>
                    </tr>
                  }
                  <tr>
                    <td colspan="8">Total</td>
                    <td class="num">{{ money(i.total) }}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
          <ng-container
            *ngTemplateOutlet="allocs; context: { rows: i.allocations }"
          />
        } @else {
          <mat-progress-bar mode="indeterminate" />
        }
      }
      @case ('receipt') {
        @if (receipt(); as r) {
          <trishul-page-header
            [title]="'Receipt ' + r.receiptNo"
            [subtitle]="
              r.customerName + ' · ' + (r.receiptDate | date: 'dd MMM yyyy')
            "
          >
            <a mat-stroked-button routerLink="/sales/receipts"
              ><mat-icon>arrow_back</mat-icon>Receipts</a
            >
            <a
              mat-stroked-button
              [routerLink]="['/print/sales/receipts', r.id]"
              target="_blank"
              ><mat-icon>print</mat-icon>Receipt voucher</a
            >
            @if (n0(r.unallocated) > 0 && can.allocate) {
              <a
                mat-flat-button
                routerLink="/sales/allocations"
                [queryParams]="{ receiptId: r.id }"
                ><mat-icon>link</mat-icon>Allocate</a
              >
            }
          </trishul-page-header>
          <section class="card">
            <dl class="facts">
              <div>
                <dt>Customer</dt>
                <dd>
                  <a
                    class="name"
                    [routerLink]="['/sales/customers', r.customerId]"
                    >{{ r.customerName }}</a
                  >
                </dd>
              </div>
              <div>
                <dt>Type</dt>
                <dd>
                  {{ r.receiptType }}
                  @if (r.salesOrderId) {
                    ·
                    <a
                      class="name"
                      [routerLink]="['/sales/orders', r.salesOrderId]"
                      >{{ r.orderNo }}</a
                    >
                  }
                </dd>
              </div>
              <div>
                <dt>Mode</dt>
                <dd>{{ r.paymentMode }}</dd>
              </div>
              <div>
                <dt>Reference</dt>
                <dd>
                  {{ r.referenceNo ?? '—'
                  }}{{
                    r.chequeDate
                      ? ' dated ' + (r.chequeDate | date: 'dd MMM yyyy')
                      : ''
                  }}
                </dd>
              </div>
              <div>
                <dt>Bank</dt>
                <dd>{{ r.bankName ?? '—' }}</dd>
              </div>
              <div>
                <dt>Amount</dt>
                <dd>
                  {{ money(r.amount) }}
                  <div class="muted">{{ r.amountInWords }}</div>
                </dd>
              </div>
              <div>
                <dt>Unallocated</dt>
                <dd [class.positive]="n0(r.unallocated) > 0">
                  {{ money(r.unallocated) }}
                </dd>
              </div>
              <div>
                <dt>Received at · by</dt>
                <dd>{{ r.branchName }} · {{ r.postedBy ?? '—' }}</dd>
              </div>
              @if (r.remarks) {
                <div style="grid-column: 1 / -1">
                  <dt>Remarks</dt>
                  <dd>{{ r.remarks }}</dd>
                </div>
              }
            </dl>
          </section>
          <ng-container
            *ngTemplateOutlet="allocs; context: { rows: r.allocations }"
          />
        } @else {
          <mat-progress-bar mode="indeterminate" />
        }
      }
    }

    <ng-template #allocs let-rows="rows">
      <section class="card" style="margin-top: 1rem">
        <h2>Allocations</h2>
        <table class="plain">
          <thead>
            <tr>
              <th>Invoice</th>
              <th>Receipt</th>
              <th>On</th>
              <th>By</th>
              <th class="num">Amount</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (a of asAllocations(rows); track a.id) {
              <tr [class.muted]="!a.isActive">
                <td>
                  <a
                    class="name"
                    [routerLink]="['/sales/invoices', a.salesInvoiceId]"
                    >{{ a.invoiceNo }}</a
                  >
                </td>
                <td>
                  @if (a.receiptId) {
                    <a
                      class="name"
                      [routerLink]="['/sales/receipts', a.receiptId]"
                      >{{ a.receiptNo }}</a
                    >
                    <div class="muted">{{ a.receiptType }}</div>
                  }
                </td>
                <td class="nowrap">
                  {{ a.allocatedOn | date: 'dd MMM yyyy' }}
                </td>
                <td>{{ a.allocatedBy ?? '—' }}</td>
                <td class="num">{{ money(a.amount) }}</td>
                <td>
                  @if (a.isActive && can.reverse) {
                    <button mat-button (click)="reverse(a)">Reverse</button>
                  } @else if (!a.isActive) {
                    <span class="muted"
                      >Reversed by {{ a.reversedBy }}:
                      {{ a.reversalReason }}</span
                    >
                  }
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="6" class="empty">Nothing allocated.</td>
              </tr>
            }
          </tbody>
        </table>
      </section>
    </ng-template>
  `,
})
export class SalesDocumentDetailPage {
  private readonly api = inject(ApiClient);
  private readonly dialog = inject(MatDialog);
  private readonly auth = inject(AuthStore);
  readonly kind = input.required<SalesDocKind>();
  readonly documentId = input.required<string>();

  protected readonly can = {
    deliver: this.auth.hasPermission(SAL_DELIVERY_MANAGE),
    invoice: this.auth.hasPermission(SAL_INVOICE_MANAGE),
    cancelInvoice: this.auth.hasPermission(SAL_INVOICE_CANCEL),
    receive: this.auth.hasPermission(SAL_RECEIPT_MANAGE),
    allocate: this.auth.hasPermission(SAL_ALLOCATION_MANAGE),
    reverse: this.auth.hasPermission(SAL_ALLOCATION_REVERSE),
  };
  protected readonly deliveryStatus = DELIVERY_STATUS;
  protected readonly invoiceState = INVOICE_STATE;
  protected readonly money = rupees;
  protected readonly n0 = n0;
  protected readonly delivery = signal<DeliveryDetail | null>(null);
  protected readonly invoice = signal<SalesInvoiceDetail | null>(null);
  protected readonly receipt = signal<ReceiptDetail | null>(null);
  private readonly id = computed(() => Number(this.documentId()));

  constructor() {
    effect(() => {
      const kind = this.kind();
      const id = this.id();
      untracked(() => this.load(kind, id));
    });
  }

  private load(kind: SalesDocKind, id: number): void {
    if (kind === 'delivery')
      this.api
        .call(getDelivery, { deliveryId: id })
        .pipe(catchError(() => EMPTY))
        .subscribe((d) => this.delivery.set(d));
    if (kind === 'invoice')
      this.api
        .call(getSalesInvoice, { invoiceId: id })
        .pipe(catchError(() => EMPTY))
        .subscribe((i) => this.invoice.set(i));
    if (kind === 'receipt')
      this.api
        .call(getReceipt, { receiptId: id })
        .pipe(catchError(() => EMPTY))
        .subscribe((r) => this.receipt.set(r));
  }

  protected live(status: string): boolean {
    return status === 'Dispatched' || status === 'Delivered';
  }

  protected asAllocations(rows: unknown): CustomerAllocationOut[] {
    return rows as CustomerAllocationOut[];
  }

  protected confirmReceived(d: DeliveryDetail): void {
    openFieldsDialog<DeliveryDetail>(this.dialog, {
      title: `Received: ${d.deliveryNo}`,
      submitText: 'Mark received',
      value: { receivedByName: d.receivedByName },
      fields: [
        {
          key: 'receivedByName',
          label: 'Received by',
          required: true,
          maxLength: 100,
          wide: true,
        },
      ],
      save: (v) =>
        this.api.call(confirmDelivery, {
          deliveryId: d.id,
          body: { receivedByName: v['receivedByName'] as string },
        }),
    })
      .pipe(filter((x): x is DeliveryDetail => !!x))
      .subscribe((x) => this.delivery.set(x));
  }

  protected cancelNote(d: DeliveryDetail): void {
    openFieldsDialog<DeliveryDetail>(this.dialog, {
      title: `Cancel delivery ${d.deliveryNo}`,
      submitText: 'Cancel delivery',
      fields: [
        {
          key: 'reason',
          label: 'Why (the goods go back to their GRN batches)',
          type: 'textarea',
          required: true,
          maxLength: 300,
        },
      ],
      save: (v) =>
        this.api.call(cancelDelivery, {
          deliveryId: d.id,
          body: { reason: v['reason'] as string },
        }),
    })
      .pipe(filter((x): x is DeliveryDetail => !!x))
      .subscribe((x) => this.delivery.set(x));
  }

  protected cancelInvoice(i: SalesInvoiceDetail): void {
    openFieldsDialog<SalesInvoiceDetail>(this.dialog, {
      title: `Cancel invoice ${i.invoiceNo}`,
      submitText: 'Cancel invoice',
      fields: [
        {
          key: 'reason',
          label:
            'Why (allocations are reversed, delivered goods become invoiceable again)',
          type: 'textarea',
          required: true,
          maxLength: 300,
        },
      ],
      save: (v) =>
        this.api.call(cancelSalesInvoice, {
          invoiceId: i.id,
          body: { reason: v['reason'] as string },
        }),
    })
      .pipe(filter((x): x is SalesInvoiceDetail => !!x))
      .subscribe((x) => this.invoice.set(x));
  }

  protected reverse(a: CustomerAllocationOut): void {
    openFieldsDialog<CustomerAllocationOut>(this.dialog, {
      title: `Reverse ${this.money(a.amount)} on ${a.invoiceNo}`,
      submitText: 'Reverse',
      fields: [
        {
          key: 'reason',
          label: 'Why',
          type: 'textarea',
          required: true,
          maxLength: 300,
        },
      ],
      save: (v) =>
        this.api.call(reverseCustomerAllocation, {
          allocationId: a.id,
          body: { reason: v['reason'] as string },
        }),
    })
      .pipe(filter((x): x is CustomerAllocationOut => !!x))
      .subscribe(() => this.load(this.kind(), this.id()));
  }
}
