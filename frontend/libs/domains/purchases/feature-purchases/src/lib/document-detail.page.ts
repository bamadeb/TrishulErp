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
  AllocationOut,
  ApiClient,
  CreditNoteDetail,
  GrnDetail,
  InvoiceDetail,
  PaymentDetail,
  getCreditNote,
  getGrn,
  getSupplierInvoice,
  getSupplierPayment,
  reverseAllocation,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import { n0, openFieldsDialog } from '@trishul/inventory-data-access';
import {
  PUR_ALLOCATION_REVERSE,
  PUR_CREDIT_NOTE_MANAGE,
  PUR_INVOICE_CREATE_PERMISSIONS,
} from '@trishul/purchases-data-access';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { EMPTY, Observable, catchError, filter } from 'rxjs';
import { PurchaseDocKind } from './documents.page';
import { INVOICE_STATE, rupees } from './purchases.shared';

type Detail = GrnDetail | InvoiceDetail | PaymentDetail | CreditNoteDetail;

/** One GRN, supplier invoice, payment or credit note (route data.kind), with its allocations. */
@Component({
  selector: 'trishul-purchase-document-detail-page',
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
    @if (!detail()) {
      <mat-progress-bar mode="indeterminate" />
    }
    @switch (kind()) {
      @case ('grn') {
        @if (grn(); as g) {
          <trishul-page-header
            [title]="'GRN ' + g.grnNo"
            [subtitle]="
              g.supplierName + ' · ' + (g.grnDate | date: 'dd MMM yyyy')
            "
          >
            <a mat-stroked-button routerLink=".."
              ><mat-icon>arrow_back</mat-icon>All GRNs</a
            >
            @if (canInvoice && hasUninvoiced(g)) {
              <a
                mat-flat-button
                routerLink="/purchases/invoices/new"
                [queryParams]="{ supplierId: g.supplierId, grnId: g.id }"
              >
                <mat-icon>receipt_long</mat-icon>Record invoice</a
              >
            }
          </trishul-page-header>
          <section class="card">
            <dl class="facts">
              <div>
                <dt>GRN date (age starts)</dt>
                <dd>{{ g.grnDate | date: 'dd MMM yyyy' }}</dd>
              </div>
              <div>
                <dt>Received at</dt>
                <dd>{{ g.branchName }} · {{ g.locationName }}</dd>
              </div>
              <div>
                <dt>Supplier</dt>
                <dd>
                  <a
                    class="name"
                    [routerLink]="['/purchases/suppliers', g.supplierId]"
                    >{{ g.supplierName }}</a
                  >
                </dd>
              </div>
              <div>
                <dt>Purchase order</dt>
                <dd>
                  @if (g.purchaseOrderId) {
                    <a
                      class="name"
                      [routerLink]="['/purchases/orders', g.purchaseOrderId]"
                      >{{ g.poNo }}</a
                    >
                  } @else {
                    Direct
                  }
                </dd>
              </div>
              <div>
                <dt>Supplier invoice / challan</dt>
                <dd>{{ g.supplierInvoiceNo ?? '—' }}</dd>
              </div>
              <div>
                <dt>Vehicle / LR</dt>
                <dd>{{ g.vehicleNo ?? '—' }} / {{ g.lrNo ?? '—' }}</dd>
              </div>
              <div>
                <dt>Value</dt>
                <dd>{{ money(g.totalValue) }}</dd>
              </div>
              <div>
                <dt>Posted by</dt>
                <dd>
                  {{ g.createdBy ?? '—' }} ·
                  {{ g.createdAt | date: 'dd MMM yyyy, HH:mm' }}
                </dd>
              </div>
              @if (g.remarks) {
                <div>
                  <dt>Remarks</dt>
                  <dd>{{ g.remarks }}</dd>
                </div>
              }
            </dl>
          </section>
          <div class="table-card">
            <div class="table-scroll">
              <table class="plain wide">
                <thead>
                  <tr>
                    <th>Item</th>
                    <th class="num">Accepted</th>
                    <th class="num">Rejected</th>
                    <th class="num">Invoiced</th>
                    <th class="num">Cost</th>
                    <th class="num">Value</th>
                    <th>Rack</th>
                    <th>Batch</th>
                    <th class="num">Still in stock</th>
                  </tr>
                </thead>
                <tbody>
                  @for (l of g.lines; track l.id) {
                    <tr>
                      <td>
                        <a
                          class="name"
                          [routerLink]="['/inventory/items', l.itemId]"
                          >{{ l.itemCode }}</a
                        >
                        <div class="muted">{{ l.itemDescription }}</div>
                        @if (l.entryUomCode) {
                          <div class="muted">
                            received as {{ l.entryQty | number: '1.0-3' }}
                            {{ l.entryUomCode }}
                          </div>
                        }
                      </td>
                      <td class="num">
                        {{ l.qtyAccepted | number: '1.0-3' }} {{ l.uomCode }}
                      </td>
                      <td class="num">
                        {{
                          n0(l.qtyRejected)
                            ? (l.qtyRejected | number: '1.0-3')
                            : '—'
                        }}
                        @if (l.rejectionReason) {
                          <div class="muted">{{ l.rejectionReason }}</div>
                        }
                      </td>
                      <td class="num">{{ l.qtyInvoiced | number: '1.0-3' }}</td>
                      <td class="num">{{ l.unitCost | number: '1.2-4' }}</td>
                      <td class="num">{{ money(l.value) }}</td>
                      <td>{{ l.binCode ?? '—' }}</td>
                      <td>{{ l.lotNo ?? '—' }}</td>
                      <td class="num">
                        {{ l.qtyRemaining | number: '1.0-3' }}
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          </div>
        }
      }
      @case ('invoice') {
        @if (invoice(); as i) {
          <trishul-page-header
            [title]="'Invoice ' + i.invoiceNo"
            [subtitle]="i.supplierName + ' · their no ' + i.supplierInvoiceNo"
          >
            <a mat-stroked-button routerLink=".."
              ><mat-icon>arrow_back</mat-icon>All invoices</a
            >
            @if (n0(i.outstanding) > 0) {
              <a
                mat-flat-button
                routerLink="/purchases/payments/new"
                [queryParams]="{ supplierId: i.supplierId }"
                ><mat-icon>payments</mat-icon>Pay</a
              >
            }
          </trishul-page-header>
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
                <dt>Invoice date</dt>
                <dd>{{ i.supplierInvoiceDate | date: 'dd MMM yyyy' }}</dd>
              </div>
              <div>
                <dt>Due</dt>
                <dd [class.negative]="i.overdueDays > 0">
                  {{ i.dueDate ? (i.dueDate | date: 'dd MMM yyyy') : '—'
                  }}{{
                    i.overdueDays ? ' (' + i.overdueDays + ' days late)' : ''
                  }}
                </dd>
              </div>
              <div>
                <dt>Supplier</dt>
                <dd>
                  <a
                    class="name"
                    [routerLink]="['/purchases/suppliers', i.supplierId]"
                    >{{ i.supplierName }}</a
                  >
                </dd>
              </div>
              <div>
                <dt>Branch</dt>
                <dd>{{ i.branchName }} · {{ i.placeOfSupply }}</dd>
              </div>
              <div>
                <dt>Against</dt>
                <dd>
                  {{ i.grnNo ?? '' }} {{ i.poNo ?? '' }}
                  {{ i.isDirect ? '(direct lines)' : '' }}
                </dd>
              </div>
              <div>
                <dt>Total</dt>
                <dd>{{ money(i.total) }}</dd>
              </div>
              <div>
                <dt>Settled</dt>
                <dd>{{ money(i.allocated) }}</dd>
              </div>
              <div>
                <dt>Outstanding</dt>
                <dd [class.negative]="n0(i.outstanding) > 0">
                  {{ money(i.outstanding) }}
                </dd>
              </div>
              <div>
                <dt>Recorded by</dt>
                <dd>{{ i.postedBy ?? '—' }}</dd>
              </div>
              @if (i.remarks) {
                <div>
                  <dt>Remarks</dt>
                  <dd>{{ i.remarks }}</dd>
                </div>
              }
            </dl>
          </section>
          <div class="table-card">
            <div class="table-scroll">
              <table class="plain wide">
                <thead>
                  <tr>
                    <th>Item / description</th>
                    <th>GRN</th>
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
                      <td>
                        {{ l.itemCode ?? '' }}
                        <div [class.muted]="!!l.itemCode">
                          {{ l.description }}
                        </div>
                      </td>
                      <td>{{ l.grnNo ?? '—' }}</td>
                      <td class="num">{{ l.quantity | number: '1.0-3' }}</td>
                      <td class="num">{{ money(l.unitPrice) }}</td>
                      <td class="num">
                        {{
                          n0(l.discountPct)
                            ? (l.discountPct | number: '1.0-2') + '%'
                            : ''
                        }}
                      </td>
                      <td class="num">{{ money(l.taxableValue) }}</td>
                      <td class="num">
                        {{ money(l.taxAmount) }}
                        <span class="muted"
                          >{{ l.gstPct | number: '1.0-2' }}%</span
                        >
                      </td>
                      <td class="num">{{ money(l.lineTotal) }}</td>
                    </tr>
                  }
                </tbody>
                <tfoot>
                  <tr>
                    <td colspan="7">Taxable</td>
                    <td class="num">{{ money(i.taxableValue) }}</td>
                  </tr>
                  @if (n0(i.igst)) {
                    <tr>
                      <td colspan="7">IGST</td>
                      <td class="num">{{ money(i.igst) }}</td>
                    </tr>
                  } @else {
                    <tr>
                      <td colspan="7">CGST + SGST</td>
                      <td class="num">{{ money(n0(i.cgst) + n0(i.sgst)) }}</td>
                    </tr>
                  }
                  @if (n0(i.otherCharges)) {
                    <tr>
                      <td colspan="7">Other charges</td>
                      <td class="num">{{ money(i.otherCharges) }}</td>
                    </tr>
                  }
                  @if (n0(i.roundOff)) {
                    <tr>
                      <td colspan="7">Round off</td>
                      <td class="num">{{ money(i.roundOff) }}</td>
                    </tr>
                  }
                  <tr>
                    <td colspan="7">Total</td>
                    <td class="num">{{ money(i.total) }}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
          <ng-container
            *ngTemplateOutlet="
              allocationTable;
              context: { $implicit: i.allocations }
            "
          />
        }
      }
      @case ('payment') {
        @if (payment(); as p) {
          <trishul-page-header
            [title]="'Payment ' + p.paymentNo"
            [subtitle]="
              p.supplierName + ' · ' + (p.paymentDate | date: 'dd MMM yyyy')
            "
          >
            <a mat-stroked-button routerLink=".."
              ><mat-icon>arrow_back</mat-icon>All payments</a
            >
            <a
              mat-stroked-button
              [routerLink]="['/print/supplier-payments', p.id]"
              target="_blank"
              ><mat-icon>print</mat-icon>Voucher</a
            >
            @if (n0(p.unallocated) > 0) {
              <a
                mat-flat-button
                routerLink="/purchases/allocations"
                [queryParams]="{ supplierId: p.supplierId }"
                ><mat-icon>link</mat-icon>Allocate</a
              >
            }
          </trishul-page-header>
          <section class="card">
            <dl class="facts">
              <div>
                <dt>Amount</dt>
                <dd>{{ money(p.amount) }}</dd>
              </div>
              <div>
                <dt>Mode</dt>
                <dd>{{ p.paymentMode }}</dd>
              </div>
              <div>
                <dt>Reference</dt>
                <dd>
                  {{ p.referenceNo ?? '—'
                  }}{{
                    p.chequeDate
                      ? ' · ' + (p.chequeDate | date: 'dd MMM yyyy')
                      : ''
                  }}
                </dd>
              </div>
              <div>
                <dt>Bank</dt>
                <dd>{{ p.bankName ?? '—' }}</dd>
              </div>
              <div>
                <dt>Supplier</dt>
                <dd>
                  <a
                    class="name"
                    [routerLink]="['/purchases/suppliers', p.supplierId]"
                    >{{ p.supplierName }}</a
                  >
                </dd>
              </div>
              <div>
                <dt>Branch</dt>
                <dd>{{ p.branchName }}</dd>
              </div>
              <div>
                <dt>Allocated</dt>
                <dd>{{ money(p.allocated) }}</dd>
              </div>
              <div>
                <dt>Unallocated (advance)</dt>
                <dd>{{ money(p.unallocated) }}</dd>
              </div>
              <div>
                <dt>Recorded by</dt>
                <dd>{{ p.postedBy ?? '—' }}</dd>
              </div>
              <div style="grid-column: 1 / -1">
                <dt>In words</dt>
                <dd>{{ p.amountInWords }}</dd>
              </div>
              @if (p.remarks) {
                <div>
                  <dt>Remarks</dt>
                  <dd>{{ p.remarks }}</dd>
                </div>
              }
            </dl>
          </section>
          <ng-container
            *ngTemplateOutlet="
              allocationTable;
              context: { $implicit: p.allocations }
            "
          />
        }
      }
      @case ('credit') {
        @if (credit(); as c) {
          <trishul-page-header
            [title]="'Credit note ' + c.debitNoteNo"
            [subtitle]="c.supplierName + ' · ' + c.noteType"
          >
            <a mat-stroked-button routerLink=".."
              ><mat-icon>arrow_back</mat-icon>All credit notes</a
            >
            @if (n0(c.unallocated) > 0) {
              <a
                mat-flat-button
                routerLink="/purchases/allocations"
                [queryParams]="{ supplierId: c.supplierId }"
                ><mat-icon>link</mat-icon>Allocate</a
              >
            }
          </trishul-page-header>
          <section class="card">
            <dl class="facts">
              <div>
                <dt>Date</dt>
                <dd>{{ c.noteDate | date: 'dd MMM yyyy' }}</dd>
              </div>
              <div>
                <dt>Supplier's note</dt>
                <dd>
                  {{ c.supplierNoteNo ?? '—'
                  }}{{
                    c.supplierNoteDate
                      ? ' · ' + (c.supplierNoteDate | date: 'dd MMM yyyy')
                      : ''
                  }}
                </dd>
              </div>
              <div>
                <dt>Supplier</dt>
                <dd>
                  <a
                    class="name"
                    [routerLink]="['/purchases/suppliers', c.supplierId]"
                    >{{ c.supplierName }}</a
                  >
                </dd>
              </div>
              <div>
                <dt>Against invoice</dt>
                <dd>
                  @if (c.supplierInvoiceId) {
                    <a
                      class="name"
                      [routerLink]="[
                        '/purchases/invoices',
                        c.supplierInvoiceId,
                      ]"
                      >{{ c.invoiceNo }}</a
                    >
                  } @else {
                    —
                  }
                </dd>
              </div>
              <div>
                <dt>Reason</dt>
                <dd>{{ c.reason ?? '—' }}</dd>
              </div>
              @if (c.locationName) {
                <div>
                  <dt>Returned from</dt>
                  <dd>{{ c.branchName }} · {{ c.locationName }}</dd>
                </div>
              }
              <div>
                <dt>Total</dt>
                <dd>{{ money(c.total) }}</dd>
              </div>
              <div>
                <dt>Unallocated</dt>
                <dd>{{ money(c.unallocated) }}</dd>
              </div>
              <div>
                <dt>Recorded by</dt>
                <dd>{{ c.postedBy ?? '—' }}</dd>
              </div>
              @if (c.remarks) {
                <div>
                  <dt>Remarks</dt>
                  <dd>{{ c.remarks }}</dd>
                </div>
              }
            </dl>
          </section>
          <div class="table-card">
            <div class="table-scroll">
              <table class="plain wide">
                <thead>
                  <tr>
                    <th>Item / description</th>
                    <th class="num">Qty</th>
                    <th class="num">Price</th>
                    <th class="num">Taxable</th>
                    <th class="num">GST</th>
                    <th class="num">Total</th>
                    <th>Batch returned</th>
                  </tr>
                </thead>
                <tbody>
                  @for (l of c.lines; track l.id) {
                    <tr>
                      <td>
                        {{ l.itemCode ?? '' }}
                        <div [class.muted]="!!l.itemCode">
                          {{ l.description }}
                        </div>
                      </td>
                      <td class="num">{{ l.quantity | number: '1.0-3' }}</td>
                      <td class="num">{{ money(l.unitPrice) }}</td>
                      <td class="num">{{ money(l.taxableValue) }}</td>
                      <td class="num">{{ money(l.taxAmount) }}</td>
                      <td class="num">{{ money(l.lineTotal) }}</td>
                      <td>
                        {{
                          l.lotNo
                            ? l.lotNo +
                              ' · ' +
                              l.grnNo +
                              (l.binCode ? ' · ' + l.binCode : '')
                            : '—'
                        }}
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          </div>
          <ng-container
            *ngTemplateOutlet="
              allocationTable;
              context: { $implicit: c.allocations }
            "
          />
        }
      }
    }

    <ng-template #allocationTable let-rows>
      <section class="card" style="margin-top: 1rem">
        <h2>Allocations</h2>
        <table class="plain">
          <thead>
            <tr>
              <th>Invoice</th>
              <th>Settled by</th>
              <th class="num">Amount</th>
              <th>On</th>
              <th>By</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (a of asAllocations(rows); track a.id) {
              <tr [class.muted]="!a.isActive">
                <td>
                  <a
                    class="name"
                    [routerLink]="['/purchases/invoices', a.supplierInvoiceId]"
                    >{{ a.invoiceNo }}</a
                  >
                  · {{ a.supplierInvoiceNo }}
                </td>
                <td>
                  {{ a.paymentNo ?? a.creditNoteNo
                  }}{{ a.paymentReference ? ' · ' + a.paymentReference : '' }}
                </td>
                <td class="num">{{ money(a.amount) }}</td>
                <td class="nowrap">
                  {{ a.allocatedOn | date: 'dd MMM yyyy' }}
                </td>
                <td>
                  {{ a.allocatedBy ?? '—' }}
                  @if (!a.isActive) {
                    <div>
                      Reversed by {{ a.reversedBy }}: {{ a.reversalReason }}
                    </div>
                  }
                </td>
                <td class="actions">
                  @if (a.isActive && canReverse) {
                    <button mat-button (click)="reverse(a)">Reverse</button>
                  }
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="6" class="empty">Not allocated.</td>
              </tr>
            }
          </tbody>
        </table>
      </section>
    </ng-template>
  `,
})
export class DocumentDetailPage {
  private readonly api = inject(ApiClient);
  private readonly dialog = inject(MatDialog);
  private readonly auth = inject(AuthStore);
  readonly kind = input.required<PurchaseDocKind>();
  readonly documentId = input.required<string>();

  protected readonly canReverse = this.auth.hasPermission(
    PUR_ALLOCATION_REVERSE,
  );
  protected readonly canInvoice = this.auth.hasAnyPermission(
    PUR_INVOICE_CREATE_PERMISSIONS,
  );
  protected readonly canCredit = this.auth.hasPermission(
    PUR_CREDIT_NOTE_MANAGE,
  );
  protected readonly invoiceState = INVOICE_STATE;
  protected readonly money = rupees;
  protected readonly n0 = n0;

  protected readonly detail = signal<Detail | null>(null);
  protected readonly grn = computed(() =>
    this.kind() === 'grn' ? (this.detail() as GrnDetail | null) : null,
  );
  protected readonly invoice = computed(() =>
    this.kind() === 'invoice' ? (this.detail() as InvoiceDetail | null) : null,
  );
  protected readonly payment = computed(() =>
    this.kind() === 'payment' ? (this.detail() as PaymentDetail | null) : null,
  );
  protected readonly credit = computed(() =>
    this.kind() === 'credit'
      ? (this.detail() as CreditNoteDetail | null)
      : null,
  );

  constructor() {
    effect(() => {
      const id = Number(this.documentId());
      const kind = this.kind();
      untracked(() => this.load(kind, id));
    });
  }

  private load(kind: PurchaseDocKind, id: number): void {
    const requests: Record<PurchaseDocKind, () => Observable<Detail>> = {
      grn: () => this.api.call(getGrn, { grnId: id }),
      invoice: () => this.api.call(getSupplierInvoice, { invoiceId: id }),
      payment: () => this.api.call(getSupplierPayment, { paymentId: id }),
      credit: () => this.api.call(getCreditNote, { noteId: id }),
    };
    requests[kind]()
      .pipe(catchError(() => EMPTY))
      .subscribe((d) => this.detail.set(d));
  }

  protected hasUninvoiced(grn: GrnDetail): boolean {
    return grn.lines.some((l) => n0(l.qtyAccepted) > n0(l.qtyInvoiced));
  }

  protected asAllocations(rows: unknown): AllocationOut[] {
    return rows as AllocationOut[];
  }

  protected reverse(allocation: AllocationOut): void {
    openFieldsDialog(this.dialog, {
      title: `Reverse ${rupees(allocation.amount)} on ${allocation.invoiceNo}`,
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
        this.api.call(reverseAllocation, {
          allocationId: allocation.id,
          body: { reason: v['reason'] as string },
        }),
    })
      .pipe(filter((done) => !!done))
      .subscribe(() => this.load(this.kind(), Number(this.documentId())));
  }
}
