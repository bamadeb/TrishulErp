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
  PoDetail,
  approvePurchaseOrder,
  cancelPurchaseOrder,
  closePurchaseOrder,
  getPurchaseOrder,
  rejectPurchaseOrder,
  submitPurchaseOrder,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import { n0, openFieldsDialog } from '@trishul/inventory-data-access';
import {
  PUR_GRN_MANAGE,
  PUR_INVOICE_CREATE_PERMISSIONS,
  PUR_PO_APPROVE,
  PUR_PO_CLOSE,
  PUR_PO_MANAGE,
} from '@trishul/purchases-data-access';
import { PageHeader, StatusBadge, confirmAction } from '@trishul/shared-ui';
import { EMPTY, Observable, catchError, filter, switchMap } from 'rxjs';
import { PO_STATUS, rupees } from './purchases.shared';

type Action = 'approve' | 'reject' | 'close' | 'cancel';
const NOTE_TEXT: Record<
  Action,
  { title: string; label: string; button: string; required: boolean }
> = {
  approve: {
    title: 'Approve order',
    label: 'Note (optional)',
    button: 'Approve',
    required: false,
  },
  reject: {
    title: 'Send back to draft',
    label: 'What needs changing',
    button: 'Send back',
    required: true,
  },
  close: {
    title: 'Close the order',
    label: 'Why the rest will not come',
    button: 'Close order',
    required: true,
  },
  cancel: {
    title: 'Cancel the order',
    label: 'Why it is cancelled',
    button: 'Cancel order',
    required: true,
  },
};

/** One purchase order: lines with ordered / received / pending, its GRNs and invoices, and the workflow. */
@Component({
  selector: 'trishul-po-detail-page',
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
    @if (po(); as po) {
      <trishul-page-header
        [title]="'PO ' + po.poNo"
        [subtitle]="po.supplierName + ' · ' + (po.poDate | date: 'dd MMM yyyy')"
      >
        <a mat-stroked-button routerLink="/purchases/orders"
          ><mat-icon>arrow_back</mat-icon>Orders</a
        >
        <a
          mat-stroked-button
          [routerLink]="['/print/purchase-orders', po.id]"
          target="_blank"
          ><mat-icon>print</mat-icon>Print</a
        >
        @if (po.status === 'Draft' && can.manage) {
          <a mat-stroked-button routerLink="edit"
            ><mat-icon>edit</mat-icon>Edit</a
          >
          <button mat-flat-button (click)="submit()">
            <mat-icon>send</mat-icon>Send for approval
          </button>
        }
        @if (po.status === 'Pending approval' && can.approve) {
          <button mat-stroked-button (click)="act('reject')">
            <mat-icon>undo</mat-icon>Send back
          </button>
          <button mat-flat-button (click)="act('approve')">
            <mat-icon>check</mat-icon>Approve
          </button>
        }
        @if (receivable() && can.receive) {
          <a
            mat-flat-button
            routerLink="/purchases/grns/new"
            [queryParams]="{ poId: po.id }"
            ><mat-icon>move_to_inbox</mat-icon>Receive goods</a
          >
        }
        @if (n0(po.qtyReceived) > 0 && can.invoice) {
          <a
            mat-stroked-button
            routerLink="/purchases/invoices/new"
            [queryParams]="{ supplierId: po.supplierId }"
            ><mat-icon>receipt_long</mat-icon>Invoice</a
          >
        }
        @if (receivable() && can.close) {
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

      <section class="card">
        <dl class="facts">
          <div>
            <dt>Status</dt>
            <dd>
              <trishul-status-badge
                [status]="po.status"
                [severities]="statusSeverity"
              />
            </dd>
          </div>
          <div>
            <dt>Deliver to</dt>
            <dd>{{ po.branchName }} · {{ po.locationName }}</dd>
          </div>
          <div>
            <dt>Expected by</dt>
            <dd>
              {{
                po.expectedDate ? (po.expectedDate | date: 'dd MMM yyyy') : '—'
              }}
            </dd>
          </div>
          <div>
            <dt>Payment terms</dt>
            <dd>{{ po.paymentTerms ?? '—' }}</dd>
          </div>
          <div>
            <dt>Type</dt>
            <dd>{{ po.poType }}{{ po.oemPoRef ? ' · ' + po.oemPoRef : '' }}</dd>
          </div>
          <div>
            <dt>Place of supply</dt>
            <dd>{{ po.placeOfSupply }}</dd>
          </div>
          <div>
            <dt>Created by</dt>
            <dd>{{ po.createdBy ?? '—' }}</dd>
          </div>
          @if (po.submittedAt) {
            <div>
              <dt>Sent for approval</dt>
              <dd>
                {{ po.submittedBy }} ·
                {{ po.submittedAt | date: 'dd MMM, HH:mm' }}
              </dd>
            </div>
          }
          @if (po.approvedAt) {
            <div>
              <dt>Approved</dt>
              <dd>
                {{ po.approvedBy }} ·
                {{ po.approvedAt | date: 'dd MMM, HH:mm' }}
              </dd>
            </div>
          }
          @if (po.approvalNote) {
            <div>
              <dt>Approval note</dt>
              <dd>{{ po.approvalNote }}</dd>
            </div>
          }
          @if (po.closedAt) {
            <div>
              <dt>{{ po.status === 'Cancelled' ? 'Cancelled' : 'Closed' }}</dt>
              <dd>{{ po.closedBy }} · {{ po.closeReason }}</dd>
            </div>
          }
          @if (po.remarks) {
            <div style="grid-column: 1 / -1">
              <dt>Remarks</dt>
              <dd>{{ po.remarks }}</dd>
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
                <th class="num">Received</th>
                <th class="num">Pending</th>
                <th class="num">Invoiced</th>
                <th class="num">Price</th>
                <th class="num">Disc</th>
                <th class="num">GST</th>
                <th class="num">Total</th>
              </tr>
            </thead>
            <tbody>
              @for (l of po.lines; track l.id) {
                <tr>
                  <td>{{ l.lineNo }}</td>
                  <td>
                    <a
                      class="name"
                      [routerLink]="['/inventory/items', l.itemId]"
                      >{{ l.itemCode }}</a
                    >
                    <div class="muted">{{ l.itemDescription }}</div>
                  </td>
                  <td class="num">
                    {{ l.quantity | number: '1.0-3' }} {{ l.uomCode }}
                  </td>
                  <td class="num">{{ l.qtyReceived | number: '1.0-3' }}</td>
                  <td class="num" [class.negative]="n0(l.qtyPending) > 0">
                    {{ l.qtyPending | number: '1.0-3' }}
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
                <td class="num">{{ money(po.subtotal) }}</td>
              </tr>
              <tr>
                <td colspan="9">{{ n0(po.igst) ? 'IGST' : 'CGST + SGST' }}</td>
                <td class="num">{{ money(po.taxTotal) }}</td>
              </tr>
              @if (n0(po.otherCharges)) {
                <tr>
                  <td colspan="9">Other charges</td>
                  <td class="num">{{ money(po.otherCharges) }}</td>
                </tr>
              }
              <tr>
                <td colspan="9">Total</td>
                <td class="num">{{ money(po.total) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <div class="tiles" style="margin-top: 1rem">
        <section class="card">
          <h2>Goods received</h2>
          @for (g of po.grns; track g.id) {
            <div>
              <a class="name" [routerLink]="['/purchases/grns', g.id]">{{
                g.number
              }}</a>
              · {{ g.date | date: 'dd MMM yyyy' }} · {{ money(g.amount) }}
            </div>
          } @empty {
            <p class="muted">Nothing received yet.</p>
          }
        </section>
        <section class="card">
          <h2>Supplier invoices</h2>
          @for (i of po.invoices; track i.id) {
            <div>
              <a class="name" [routerLink]="['/purchases/invoices', i.id]">{{
                i.number
              }}</a>
              · {{ i.date | date: 'dd MMM yyyy' }} · {{ money(i.amount) }} ·
              {{ i.status }}
            </div>
          } @empty {
            <p class="muted">Not invoiced yet.</p>
          }
        </section>
      </div>
    } @else {
      <mat-progress-bar mode="indeterminate" />
    }
  `,
})
export class PoDetailPage {
  private readonly api = inject(ApiClient);
  private readonly dialog = inject(MatDialog);
  private readonly auth = inject(AuthStore);
  readonly poId = input.required<string>();

  protected readonly can = {
    manage: this.auth.hasPermission(PUR_PO_MANAGE),
    approve: this.auth.hasPermission(PUR_PO_APPROVE),
    close: this.auth.hasPermission(PUR_PO_CLOSE),
    receive: this.auth.hasPermission(PUR_GRN_MANAGE),
    invoice: this.auth.hasAnyPermission(PUR_INVOICE_CREATE_PERMISSIONS),
  };
  protected readonly statusSeverity = PO_STATUS;
  protected readonly money = rupees;
  protected readonly n0 = n0;
  protected readonly po = signal<PoDetail | null>(null);
  protected readonly receivable = computed(() =>
    ['Approved', 'Sent', 'Part received'].includes(this.po()?.status ?? ''),
  );
  protected readonly cancellable = computed(() => {
    const po = this.po();
    if (!po || n0(po.qtyReceived) > 0) return false;
    if (po.status === 'Draft') return this.can.manage;
    return (
      ['Pending approval', 'Approved', 'Sent'].includes(po.status) &&
      this.can.close
    );
  });

  constructor() {
    effect(() => {
      const id = Number(this.poId());
      untracked(() =>
        this.api
          .call(getPurchaseOrder, { poId: id })
          .pipe(catchError(() => EMPTY))
          .subscribe((po) => this.po.set(po)),
      );
    });
  }

  protected submit(): void {
    const po = this.po();
    if (!po) return;
    confirmAction(this.dialog, {
      title: 'Send for approval?',
      message: `${po.poNo} for ${rupees(po.total)} can't be edited while it waits for approval.`,
      confirmText: 'Send',
    })
      .pipe(
        filter(Boolean),
        switchMap(() =>
          this.api
            .call(submitPurchaseOrder, { poId: po.id })
            .pipe(catchError(() => EMPTY)),
        ),
      )
      .subscribe((updated) => this.po.set(updated));
  }

  protected act(action: Action): void {
    const po = this.po();
    if (!po) return;
    const text = NOTE_TEXT[action];
    const calls: Record<Action, (note: string | null) => Observable<PoDetail>> =
      {
        approve: (note) =>
          this.api.call(approvePurchaseOrder, { poId: po.id, body: { note } }),
        reject: (note) =>
          this.api.call(rejectPurchaseOrder, { poId: po.id, body: { note } }),
        close: (note) =>
          this.api.call(closePurchaseOrder, { poId: po.id, body: { note } }),
        cancel: (note) =>
          this.api.call(cancelPurchaseOrder, { poId: po.id, body: { note } }),
      };
    openFieldsDialog(this.dialog, {
      title: `${text.title} ${po.poNo}`,
      submitText: text.button,
      fields: [
        {
          key: 'note',
          label: text.label,
          type: 'textarea',
          required: text.required,
          maxLength: 300,
        },
      ],
      save: (v) => calls[action]((v['note'] as string | null) ?? null),
    })
      .pipe(filter((updated): updated is PoDetail => !!updated))
      .subscribe((updated) => this.po.set(updated));
  }
}
