import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
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
import { Router, RouterLink } from '@angular/router';
import {
  ApiClient,
  OrderDetail,
  QuotationDetail,
  acceptQuotation,
  approveQuotation,
  convertQuotation,
  getQuotation,
  rejectQuotation,
  reviseQuotation,
  sendBackQuotation,
  submitQuotation,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import { n0, openFieldsDialog } from '@trishul/inventory-data-access';
import {
  SAL_ORDER_MANAGE,
  SAL_QUOTATION_APPROVE,
  SAL_QUOTATION_MANAGE,
} from '@trishul/sales-data-access';
import { PageHeader, StatusBadge, confirmAction } from '@trishul/shared-ui';
import { EMPTY, Observable, catchError, filter, switchMap } from 'rxjs';
import { QUOTATION_STATE, rupees } from './sales.shared';

type NoteAction = 'sendBack' | 'accept' | 'reject' | 'revise';
const NOTE_TEXT: Record<
  NoteAction,
  { title: string; label: string; button: string; required: boolean }
> = {
  sendBack: { title: 'Send back to draft', label: 'What needs changing', button: 'Send back', required: true },
  accept: { title: 'Customer accepted', label: 'Note (PO received, by mail, ...)', button: 'Mark accepted', required: false },
  reject: { title: 'Customer rejected', label: 'Why the customer rejected it', button: 'Mark rejected', required: true },
  revise: { title: 'Revise', label: 'What this revision changes', button: 'Start revision', required: true },
}; // prettier-ignore

/** One quotation: current version's lines, its revisions and the workflow up to a sales order. */
@Component({
  selector: 'trishul-quotation-detail-page',
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
    @if (q(); as q) {
      <trishul-page-header
        [title]="'Quotation ' + q.quotationNo"
        [subtitle]="
          q.customerName +
          ' · version ' +
          q.currentVersion +
          ' · ' +
          (q.quotationDate | date: 'dd MMM yyyy')
        "
      >
        <a mat-stroked-button routerLink="/sales/quotations"
          ><mat-icon>arrow_back</mat-icon>Quotations</a
        >
        <a
          mat-stroked-button
          [routerLink]="['/print/sales/quotations', q.id]"
          target="_blank"
          ><mat-icon>print</mat-icon>Print / PDF</a
        >
        @if (can.manage) {
          @if (q.state === 'Draft') {
            <a mat-stroked-button routerLink="edit"
              ><mat-icon>edit</mat-icon>Edit</a
            >
            <button mat-flat-button (click)="submit()">
              <mat-icon>send</mat-icon>Submit
            </button>
          }
          @if (q.state === 'Submitted') {
            <button mat-stroked-button (click)="act('reject')">
              <mat-icon>thumb_down</mat-icon>Rejected
            </button>
            <button mat-flat-button (click)="act('accept')">
              <mat-icon>thumb_up</mat-icon>Accepted
            </button>
          }
          @if (q.state === 'Expired') {
            <button mat-stroked-button (click)="act('reject')">
              <mat-icon>thumb_down</mat-icon>Rejected
            </button>
          }
          @if (revisable(q.state)) {
            <button mat-stroked-button (click)="act('revise')">
              <mat-icon>history_edu</mat-icon>Revise
            </button>
          }
        }
        @if (q.state === 'Pending approval' && can.approve) {
          <button mat-stroked-button (click)="act('sendBack')">
            <mat-icon>undo</mat-icon>Send back
          </button>
          <button mat-flat-button (click)="approve()">
            <mat-icon>check</mat-icon>Approve discounts
          </button>
        }
        @if (q.state === 'Accepted' && can.convert) {
          <button mat-flat-button (click)="convert()">
            <mat-icon>shopping_cart</mat-icon>Make sales order
          </button>
        }
        @if (q.salesOrderId) {
          <a mat-flat-button [routerLink]="['/sales/orders', q.salesOrderId]"
            ><mat-icon>shopping_cart</mat-icon>Order {{ q.orderNo }}</a
          >
        }
      </trishul-page-header>

      <section class="card">
        <dl class="facts">
          <div>
            <dt>Status</dt>
            <dd>
              <trishul-status-badge [status]="q.state" [severities]="states" />
            </dd>
          </div>
          <div>
            <dt>Customer</dt>
            <dd>
              <a
                class="name"
                [routerLink]="['/sales/customers', q.customerId]"
                >{{ q.customerName }}</a
              >
              @if (q.customerSiteName) {
                <div class="muted">{{ q.customerSiteName }}</div>
              }
            </dd>
          </div>
          <div>
            <dt>Valid until</dt>
            <dd>
              {{ q.validUntil ? (q.validUntil | date: 'dd MMM yyyy') : '—' }}
            </dd>
          </div>
          <div>
            <dt>Brand · branch</dt>
            <dd>{{ q.principalName }} · {{ q.branchName }}</dd>
          </div>
          <div>
            <dt>Type</dt>
            <dd>{{ q.quotationType }}</dd>
          </div>
          <div>
            <dt>Place of supply</dt>
            <dd>{{ q.placeOfSupply }}</dd>
          </div>
          <div>
            <dt>Created by</dt>
            <dd>{{ q.createdBy ?? '—' }}</dd>
          </div>
          @if (q.submittedAt) {
            <div>
              <dt>Submitted</dt>
              <dd>
                {{ q.submittedBy }} ·
                {{ q.submittedAt | date: 'dd MMM, HH:mm' }}
              </dd>
            </div>
          }
          @if (q.approvedAt) {
            <div>
              <dt>Discounts approved</dt>
              <dd>
                {{ q.approvedBy }} · {{ q.approvedAt | date: 'dd MMM, HH:mm' }}
              </dd>
            </div>
          }
          @if (q.respondedAt || q.responseNote) {
            <div>
              <dt>Customer's answer</dt>
              <dd>
                {{ q.respondedBy ?? '' }}
                {{ q.respondedAt ? (q.respondedAt | date: 'dd MMM') : '' }}
                {{ q.responseNote ? '· ' + q.responseNote : '' }}
              </dd>
            </div>
          }
          @if (q.needsDiscountApproval && q.state === 'Draft') {
            <div style="grid-column: 1 / -1">
              <dt>Discounts</dt>
              <dd class="muted">
                This quotation has discounts: submitting it needs a manager's
                approval unless you may approve discounts yourself.
              </dd>
            </div>
          }
          @if (q.terms) {
            <div style="grid-column: 1 / -1">
              <dt>Terms</dt>
              <dd style="white-space: pre-line">{{ q.terms }}</dd>
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
                <th class="num">Qty</th>
                <th class="num">Price</th>
                <th class="num">Disc</th>
                <th class="num">Taxable</th>
                <th class="num">GST</th>
                <th class="num">Total</th>
              </tr>
            </thead>
            <tbody>
              @for (l of q.lines; track l.id) {
                <tr>
                  <td>{{ l.lineNo }}</td>
                  <td>
                    {{ l.itemCode ?? '' }}
                    <div [class.muted]="!!l.itemCode">{{ l.description }}</div>
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
              @if (n0(q.discountTotal)) {
                <tr>
                  <td colspan="7">Before discount · discount</td>
                  <td class="num">
                    {{ money(q.subtotal) }} · {{ money(q.discountTotal) }}
                  </td>
                </tr>
              }
              <tr>
                <td colspan="7">Taxable</td>
                <td class="num">{{ money(q.taxableValue) }}</td>
              </tr>
              <tr>
                <td colspan="7">{{ n0(q.igst) ? 'IGST' : 'CGST + SGST' }}</td>
                <td class="num">{{ money(q.taxTotal) }}</td>
              </tr>
              @if (n0(q.otherCharges)) {
                <tr>
                  <td colspan="7">Other charges</td>
                  <td class="num">{{ money(q.otherCharges) }}</td>
                </tr>
              }
              <tr>
                <td colspan="7">Total</td>
                <td class="num">{{ money(q.total) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <section class="card" style="margin-top: 1rem">
        <h2>Revisions</h2>
        <table class="plain">
          <thead>
            <tr>
              <th>Version</th>
              <th>When</th>
              <th>By</th>
              <th>What changed</th>
              <th class="num">Total</th>
            </tr>
          </thead>
          <tbody>
            @for (v of q.versions; track v.versionNo) {
              <tr>
                <td>
                  {{ v.versionNo
                  }}{{ v.versionNo === q.currentVersion ? ' (current)' : '' }}
                </td>
                <td class="nowrap">
                  {{ v.createdAt | date: 'dd MMM yyyy, HH:mm' }}
                </td>
                <td>{{ v.createdBy ?? '—' }}</td>
                <td>{{ v.changeNote ?? '' }}</td>
                <td class="num">{{ money(v.total) }}</td>
              </tr>
            }
          </tbody>
        </table>
      </section>
    } @else {
      <mat-progress-bar mode="indeterminate" />
    }
  `,
})
export class QuotationDetailPage {
  private readonly api = inject(ApiClient);
  private readonly dialog = inject(MatDialog);
  private readonly router = inject(Router);
  private readonly auth = inject(AuthStore);
  readonly quotationId = input.required<string>();

  protected readonly can = {
    manage: this.auth.hasPermission(SAL_QUOTATION_MANAGE),
    approve: this.auth.hasPermission(SAL_QUOTATION_APPROVE),
    convert: this.auth.hasAnyPermission([
      SAL_QUOTATION_MANAGE,
      SAL_ORDER_MANAGE,
    ]),
  };
  protected readonly states = QUOTATION_STATE;
  protected readonly money = rupees;
  protected readonly n0 = n0;
  protected readonly q = signal<QuotationDetail | null>(null);

  constructor() {
    effect(() => {
      const id = Number(this.quotationId());
      untracked(() =>
        this.api
          .call(getQuotation, { quotationId: id })
          .pipe(catchError(() => EMPTY))
          .subscribe((q) => this.q.set(q)),
      );
    });
  }

  protected revisable(state: string): boolean {
    return [
      'Pending approval',
      'Submitted',
      'Accepted',
      'Rejected',
      'Expired',
    ].includes(state);
  }

  protected submit(): void {
    const q = this.q();
    if (!q) return;
    confirmAction(this.dialog, {
      title: 'Submit to the customer?',
      message: `${q.quotationNo} for ${rupees(q.total)} can't be edited after this; revise it to change it.`,
      confirmText: 'Submit',
    })
      .pipe(
        filter(Boolean),
        switchMap(() =>
          this.api
            .call(submitQuotation, { quotationId: q.id })
            .pipe(catchError(() => EMPTY)),
        ),
      )
      .subscribe((updated) => this.q.set(updated));
  }

  protected approve(): void {
    const q = this.q();
    if (!q) return;
    this.api
      .call(approveQuotation, { quotationId: q.id })
      .pipe(catchError(() => EMPTY))
      .subscribe((updated) => this.q.set(updated));
  }

  protected act(action: NoteAction): void {
    const q = this.q();
    if (!q) return;
    const text = NOTE_TEXT[action];
    const calls: Record<
      NoteAction,
      (note: string | null) => Observable<QuotationDetail>
    > = {
      sendBack: (note) =>
        this.api.call(sendBackQuotation, { quotationId: q.id, body: { note } }),
      accept: (note) =>
        this.api.call(acceptQuotation, { quotationId: q.id, body: { note } }),
      reject: (note) =>
        this.api.call(rejectQuotation, { quotationId: q.id, body: { note } }),
      revise: (note) =>
        this.api.call(reviseQuotation, { quotationId: q.id, body: { note } }),
    };
    openFieldsDialog(this.dialog, {
      title: `${text.title}: ${q.quotationNo}`,
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
      .pipe(filter((updated): updated is QuotationDetail => !!updated))
      .subscribe((updated) => {
        this.q.set(updated);
        if (action === 'revise')
          void this.router.navigate(['/sales/quotations', updated.id, 'edit']);
      });
  }

  protected convert(): void {
    const q = this.q();
    if (!q) return;
    openFieldsDialog<OrderDetail>(this.dialog, {
      title: `Sales order from ${q.quotationNo}`,
      submitText: 'Create order',
      fields: [
        { key: 'customerPoNo', label: "Customer's PO no", maxLength: 40 },
        { key: 'customerPoDate', label: 'PO date', type: 'date' },
        {
          key: 'expectedDeliveryDate',
          label: 'Expected delivery',
          type: 'date',
        },
        {
          key: 'isPrepaid',
          label: 'Prepaid: the customer pays in advance',
          type: 'checkbox',
        },
      ],
      save: (v) =>
        this.api.call(convertQuotation, {
          quotationId: q.id,
          body: {
            customerPoNo: (v['customerPoNo'] as string | null) ?? null,
            customerPoDate: (v['customerPoDate'] as string | null) ?? null,
            expectedDeliveryDate:
              (v['expectedDeliveryDate'] as string | null) ?? null,
            isPrepaid: Boolean(v['isPrepaid']),
          },
        }),
    })
      .pipe(filter((order): order is OrderDetail => !!order))
      .subscribe(
        (order) => void this.router.navigate(['/sales/orders', order.id]),
      );
  }
}
