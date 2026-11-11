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
import { MatButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { RouterLink } from '@angular/router';
import {
  ApiClient,
  OrderDetail,
  approveSalesOrder,
  cancelSalesOrder,
  closeSalesOrder,
  getSalesOrder,
  rejectSalesOrder,
  submitSalesOrder,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import { n0, openFieldsDialog } from '@trishul/inventory-data-access';
import {
  SAL_CREDIT_OVERRIDE,
  SAL_DELIVERY_MANAGE,
  SAL_INVOICE_MANAGE,
  SAL_ORDER_APPROVE,
  SAL_ORDER_CLOSE,
  SAL_ORDER_MANAGE,
  SAL_RECEIPT_MANAGE,
} from '@trishul/sales-data-access';
import { PageHeader, StatusBadge, confirmAction } from '@trishul/shared-ui';
import { EMPTY, Observable, catchError, filter, switchMap } from 'rxjs';
import { DELIVERY_STATUS, ORDER_STATUS, rupees } from './sales.shared';

type Action = 'reject' | 'close' | 'cancel';
const NOTE_TEXT: Record<Action, { title: string; label: string; button: string }> = {
  reject: { title: 'Send back to draft', label: 'What needs changing', button: 'Send back' },
  close: { title: 'Close the order', label: "Why the rest won't be delivered", button: 'Close order' },
  cancel: { title: 'Cancel the order', label: 'Why it is cancelled', button: 'Cancel order' },
}; // prettier-ignore
const OPEN = ['Approved', 'Part delivered', 'Delivered', 'Part invoiced'];

/** One sales order: ordered / delivered / invoiced per line, deliveries, invoices, advances and the workflow. */
@Component({
  selector: 'trishul-order-detail-page',
  imports: [
    DatePipe,
    DecimalPipe,
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
    @if (order(); as o) {
      <trishul-page-header
        [title]="'Sales order ' + o.orderNo"
        [subtitle]="
          o.customerName + ' · ' + (o.orderDate | date: 'dd MMM yyyy')
        "
      >
        <a mat-stroked-button routerLink="/sales/orders"
          ><mat-icon>arrow_back</mat-icon>Orders</a
        >
        <a
          mat-stroked-button
          [routerLink]="['/print/sales/orders', o.id]"
          target="_blank"
          ><mat-icon>print</mat-icon>Print</a
        >
        @if (o.status === 'Draft' && can.manage) {
          <a mat-stroked-button routerLink="edit"
            ><mat-icon>edit</mat-icon>Edit</a
          >
          <button mat-flat-button (click)="submit()">
            <mat-icon>send</mat-icon>Send for approval
          </button>
        }
        @if (o.status === 'Pending approval' && can.approve) {
          <button mat-stroked-button (click)="act('reject')">
            <mat-icon>undo</mat-icon>Send back
          </button>
          <button mat-flat-button (click)="approve()">
            <mat-icon>check</mat-icon>Approve
          </button>
        }
        @if (deliverable() && can.deliver) {
          <a
            mat-flat-button
            routerLink="/sales/deliveries/new"
            [queryParams]="{ orderId: o.id }"
            ><mat-icon>local_shipping</mat-icon>Deliver</a
          >
        }
        @if (invoiceable() && can.invoice) {
          <a
            mat-stroked-button
            routerLink="/sales/invoices/new"
            [queryParams]="{ customerId: o.customerId, orderId: o.id }"
            ><mat-icon>receipt_long</mat-icon>Invoice</a
          >
        }
        @if (can.receive && o.status !== 'Cancelled' && o.status !== 'Closed') {
          <a
            mat-stroked-button
            routerLink="/sales/receipts/new"
            [queryParams]="{ customerId: o.customerId, orderId: o.id }"
            ><mat-icon>savings</mat-icon>Record advance</a
          >
        }
        @if (closable() && can.close) {
          <button mat-stroked-button (click)="act('close')">
            <mat-icon>lock</mat-icon>Close
          </button>
        }
        @if (cancellable()) {
          <button mat-stroked-button (click)="act('cancel')">
            <mat-icon>cancel</mat-icon>Cancel
          </button>
        }
      </trishul-page-header>

      <div class="tiles">
        <div class="tile">
          <div class="value">{{ money(o.total) }}</div>
          <div class="label">Order value</div>
        </div>
        <div class="tile">
          <div class="value">{{ money(o.invoicedAmount) }}</div>
          <div class="label">Invoiced (lines)</div>
        </div>
        <div class="tile">
          <div class="value">{{ money(o.advanceReceived) }}</div>
          <div class="label">Advance received</div>
        </div>
        <div class="tile">
          <div class="value">{{ money(o.advanceAdjusted) }}</div>
          <div class="label">Advance adjusted</div>
        </div>
        <div class="tile">
          <div class="value" [class.positive]="n0(o.advanceRemaining) > 0">
            {{ money(o.advanceRemaining) }}
          </div>
          <div class="label">Advance left</div>
        </div>
        <div class="tile">
          <div class="value" [class.negative]="overLimit()">
            {{ money(o.customerBalance) }}
          </div>
          <div class="label">
            Customer balance{{
              o.creditLimit ? ' / limit ' + money(o.creditLimit) : ' (no limit)'
            }}
          </div>
        </div>
      </div>

      <section class="card">
        <dl class="facts">
          <div>
            <dt>Status</dt>
            <dd>
              <trishul-status-badge
                [status]="o.status"
                [severities]="statusSeverity"
              />
              @if (o.isPrepaid) {
                <span class="muted"> · prepaid</span>
              }
            </dd>
          </div>
          <div>
            <dt>Customer</dt>
            <dd>
              <a
                class="name"
                [routerLink]="['/sales/customers', o.customerId]"
                >{{ o.customerName }}</a
              >
              @if (o.customerSiteName) {
                <div class="muted">{{ o.customerSiteName }}</div>
              }
            </dd>
          </div>
          <div>
            <dt>Brand · branch</dt>
            <dd>{{ o.principalName }} · {{ o.branchName }}</dd>
          </div>
          <div>
            <dt>Customer PO</dt>
            <dd>
              {{ o.customerPoNo ?? '—'
              }}{{
                o.customerPoDate
                  ? ' · ' + (o.customerPoDate | date: 'dd MMM yyyy')
                  : ''
              }}
            </dd>
          </div>
          <div>
            <dt>Expected delivery</dt>
            <dd>
              {{
                o.expectedDeliveryDate
                  ? (o.expectedDeliveryDate | date: 'dd MMM yyyy')
                  : '—'
              }}
            </dd>
          </div>
          <div>
            <dt>Payment terms</dt>
            <dd>{{ o.paymentTerms ?? '—' }}</dd>
          </div>
          <div>
            <dt>Place of supply</dt>
            <dd>{{ o.placeOfSupply ?? '—' }}</dd>
          </div>
          <div>
            <dt>Credit check</dt>
            <dd>
              {{ o.creditCheckStatus
              }}{{ o.creditApprovedBy ? ' by ' + o.creditApprovedBy : '' }}
            </dd>
          </div>
          @if (o.quotationNo) {
            <div>
              <dt>From quotation</dt>
              <dd>
                <a
                  class="name"
                  [routerLink]="['/sales/quotations', o.quotationId]"
                  >{{ o.quotationNo }}</a
                >
              </dd>
            </div>
          }
          <div>
            <dt>Created by</dt>
            <dd>{{ o.createdBy ?? '—' }}</dd>
          </div>
          @if (o.approvedAt) {
            <div>
              <dt>Approved</dt>
              <dd>
                {{ o.approvedBy }} · {{ o.approvedAt | date: 'dd MMM, HH:mm' }}
              </dd>
            </div>
          }
          @if (o.approvalNote) {
            <div>
              <dt>Approval note</dt>
              <dd>{{ o.approvalNote }}</dd>
            </div>
          }
          @if (o.closedAt) {
            <div>
              <dt>{{ o.status === 'Cancelled' ? 'Cancelled' : 'Closed' }}</dt>
              <dd>{{ o.closedBy }} · {{ o.closeReason }}</dd>
            </div>
          }
          <div style="grid-column: span 2">
            <dt>Billing address</dt>
            <dd>{{ o.billToAddress ?? '—' }}</dd>
          </div>
          <div style="grid-column: span 2">
            <dt>Delivery address</dt>
            <dd>{{ o.shipToAddress ?? '—' }}</dd>
          </div>
          @if (o.remarks) {
            <div style="grid-column: 1 / -1">
              <dt>Remarks</dt>
              <dd>{{ o.remarks }}</dd>
            </div>
          }
        </dl>
      </section>

      <div class="table-card">
        <div class="table-scroll">
          <table class="plain wide">
            <thead>
              <tr>
                <th>#</th>
                <th>Item</th>
                <th class="num">Ordered</th>
                <th class="num">Delivered</th>
                <th class="num">To deliver</th>
                <th class="num">Invoiced</th>
                <th class="num">Price</th>
                <th class="num">Disc</th>
                <th class="num">GST</th>
                <th class="num">Total</th>
              </tr>
            </thead>
            <tbody>
              @for (l of o.lines; track l.id) {
                <tr>
                  <td>{{ l.lineNo }}</td>
                  <td>
                    <a
                      class="name"
                      [routerLink]="['/inventory/items', l.itemId]"
                      >{{ l.itemCode }}</a
                    >
                    <div class="muted">{{ l.description }}</div>
                  </td>
                  <td class="num">
                    {{ l.quantity | number: '1.0-3' }} {{ l.uomCode ?? '' }}
                  </td>
                  <td class="num">{{ l.qtyDelivered | number: '1.0-3' }}</td>
                  <td class="num" [class.negative]="n0(l.qtyToDeliver) > 0">
                    {{ l.qtyToDeliver | number: '1.0-3' }}
                  </td>
                  <td class="num">{{ l.qtyInvoiced | number: '1.0-3' }}</td>
                  <td class="num">{{ money(l.unitPrice) }}</td>
                  <td class="num">
                    {{
                      n0(l.discountPct)
                        ? (l.discountPct | number: '1.0-2') + '%'
                        : ''
                    }}
                  </td>
                  <td class="num">{{ l.gstPct | number: '1.0-2' }}%</td>
                  <td class="num">{{ money(l.lineTotal) }}</td>
                </tr>
              }
            </tbody>
            <tfoot>
              <tr>
                <td colspan="9">Taxable</td>
                <td class="num">{{ money(o.subtotal) }}</td>
              </tr>
              <tr>
                <td colspan="9">{{ n0(o.igst) ? 'IGST' : 'CGST + SGST' }}</td>
                <td class="num">{{ money(o.taxTotal) }}</td>
              </tr>
              @if (n0(o.otherCharges)) {
                <tr>
                  <td colspan="9">Other charges</td>
                  <td class="num">{{ money(o.otherCharges) }}</td>
                </tr>
              }
              <tr>
                <td colspan="9">Total</td>
                <td class="num">{{ money(o.total) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <div class="docs">
        <section class="card">
          <h2>Deliveries</h2>
          @for (d of o.deliveries; track d.id) {
            <div>
              <a class="name" [routerLink]="['/sales/deliveries', d.id]">{{
                d.number
              }}</a>
              · {{ d.date | date: 'dd MMM yyyy' }} ·
              <trishul-status-badge
                [status]="d.status"
                [severities]="deliverySeverity"
              />
            </div>
          } @empty {
            <p class="muted">Nothing delivered yet.</p>
          }
        </section>
        <section class="card">
          <h2>Invoices</h2>
          @for (i of o.invoices; track i.id) {
            <div>
              <a class="name" [routerLink]="['/sales/invoices', i.id]">{{
                i.number
              }}</a>
              · {{ i.date | date: 'dd MMM yyyy' }} · {{ money(i.amount) }} ·
              {{ i.status }}
            </div>
          } @empty {
            <p class="muted">Not invoiced yet.</p>
          }
        </section>
        <section class="card">
          <h2>Advances</h2>
          @for (a of o.advances; track a.id) {
            <div>
              <a class="name" [routerLink]="['/sales/receipts', a.id]">{{
                a.number
              }}</a>
              · {{ a.date | date: 'dd MMM yyyy' }} · {{ money(a.amount) }}
            </div>
          } @empty {
            <p class="muted">No advance received.</p>
          }
        </section>
      </div>
    } @else {
      <mat-progress-bar mode="indeterminate" />
    }
  `,
  styles: `
    .docs {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
      gap: 1rem;
      margin-top: 1rem;
    }
  `,
})
export class OrderDetailPage {
  private readonly api = inject(ApiClient);
  private readonly dialog = inject(MatDialog);
  private readonly auth = inject(AuthStore);
  readonly orderId = input.required<string>();

  protected readonly can = {
    manage: this.auth.hasPermission(SAL_ORDER_MANAGE),
    approve: this.auth.hasPermission(SAL_ORDER_APPROVE),
    close: this.auth.hasPermission(SAL_ORDER_CLOSE),
    deliver: this.auth.hasPermission(SAL_DELIVERY_MANAGE),
    invoice: this.auth.hasPermission(SAL_INVOICE_MANAGE),
    receive: this.auth.hasPermission(SAL_RECEIPT_MANAGE),
    override: this.auth.hasPermission(SAL_CREDIT_OVERRIDE),
  };
  protected readonly statusSeverity = ORDER_STATUS;
  protected readonly deliverySeverity = DELIVERY_STATUS;
  protected readonly money = rupees;
  protected readonly n0 = n0;
  protected readonly order = signal<OrderDetail | null>(null);
  protected readonly deliverable = computed(() => {
    const o = this.order();
    return (
      !!o &&
      OPEN.includes(o.status) &&
      o.lines.some((l) => n0(l.qtyToDeliver) > 0)
    );
  });
  protected readonly invoiceable = computed(() => {
    const o = this.order();
    return !!o && o.lines.some((l) => n0(l.qtyDelivered) > n0(l.qtyInvoiced));
  });
  protected readonly closable = computed(() =>
    OPEN.includes(this.order()?.status ?? ''),
  );
  protected readonly cancellable = computed(() => {
    const o = this.order();
    if (!o || n0(o.qtyDelivered) > 0 || n0(o.qtyInvoiced) > 0) return false;
    if (o.status === 'Draft') return this.can.manage;
    return (
      ['Pending approval', 'Approved'].includes(o.status) && this.can.close
    );
  });
  /** Approving this order would take the customer over the credit limit. */
  protected readonly overLimit = computed(() => {
    const o = this.order();
    if (!o || o.creditLimit === null || o.creditLimit === undefined)
      return false;
    const pending = o.status === 'Pending approval' ? n0(o.total) : 0;
    return n0(o.customerBalance) + pending > n0(o.creditLimit);
  });

  constructor() {
    effect(() => {
      const id = Number(this.orderId());
      untracked(() =>
        this.api
          .call(getSalesOrder, { orderId: id })
          .pipe(catchError(() => EMPTY))
          .subscribe((o) => this.order.set(o)),
      );
    });
  }

  protected submit(): void {
    const o = this.order();
    if (!o) return;
    confirmAction(this.dialog, {
      title: 'Send for approval?',
      message: `${o.orderNo} for ${rupees(o.total)} can't be edited while it waits for approval.`,
      confirmText: 'Send',
    })
      .pipe(
        filter(Boolean),
        switchMap(() =>
          this.api
            .call(submitSalesOrder, { orderId: o.id })
            .pipe(catchError(() => EMPTY)),
        ),
      )
      .subscribe((updated) => this.order.set(updated));
  }

  protected approve(): void {
    const o = this.order();
    if (!o) return;
    const over = this.overLimit();
    openFieldsDialog<OrderDetail>(this.dialog, {
      title: `Approve ${o.orderNo}`,
      submitText: 'Approve',
      fields: [
        {
          key: 'note',
          label: 'Note (optional)',
          type: 'textarea',
          maxLength: 300,
        },
        ...(over && this.can.override
          ? [
              {
                key: 'overrideCredit',
                label: `Override the credit limit (${rupees(o.creditLimit)}): this takes the customer to ${rupees(
                  n0(o.customerBalance) + n0(o.total),
                )}`,
                type: 'checkbox' as const,
              },
            ]
          : []),
      ],
      save: (v) =>
        this.api.call(approveSalesOrder, {
          orderId: o.id,
          body: {
            note: (v['note'] as string | null) ?? null,
            overrideCredit: Boolean(v['overrideCredit']),
          },
        }),
    })
      .pipe(filter((updated): updated is OrderDetail => !!updated))
      .subscribe((updated) => this.order.set(updated));
  }

  protected act(action: Action): void {
    const o = this.order();
    if (!o) return;
    const text = NOTE_TEXT[action];
    const calls: Record<
      Action,
      (note: string | null) => Observable<OrderDetail>
    > = {
      reject: (note) =>
        this.api.call(rejectSalesOrder, { orderId: o.id, body: { note } }),
      close: (note) =>
        this.api.call(closeSalesOrder, { orderId: o.id, body: { note } }),
      cancel: (note) =>
        this.api.call(cancelSalesOrder, { orderId: o.id, body: { note } }),
    };
    openFieldsDialog(this.dialog, {
      title: `${text.title} ${o.orderNo}`,
      submitText: text.button,
      fields: [
        {
          key: 'note',
          label: text.label,
          type: 'textarea',
          required: true,
          maxLength: 300,
        },
      ],
      save: (v) => calls[action]((v['note'] as string | null) ?? null),
    })
      .pipe(filter((updated): updated is OrderDetail => !!updated))
      .subscribe((updated) => this.order.set(updated));
  }
}
