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
import {
  ApiClient,
  PaymentDetail,
  PoDetail,
  getPurchaseOrder,
  getSupplierPayment,
} from '@trishul/core-api';
import { n0 } from '@trishul/inventory-data-access';
import { EMPTY, catchError } from 'rxjs';
import { rupees } from './purchases.shared';

const PRINT_STYLES = `
  :host {
    display: block;
    max-width: 210mm;
    margin: 0 auto;
    padding: 12mm;
    background: #fff;
    color: #000;
    font: 12px/1.45 Arial, Helvetica, sans-serif;
  }
  .bar {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }
  .bar button {
    padding: 0.4rem 1rem;
    font: inherit;
    cursor: pointer;
  }
  header {
    display: flex;
    justify-content: space-between;
    border-bottom: 2px solid #000;
    padding-bottom: 8px;
    margin-bottom: 10px;
  }
  h1 {
    margin: 0;
    font-size: 18px;
  }
  h2 {
    margin: 0;
    font-size: 16px;
    text-align: right;
  }
  .parties {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 10px;
  }
  .box {
    border: 1px solid #000;
    padding: 6px 8px;
  }
  .label {
    font-weight: bold;
    font-size: 11px;
    text-transform: uppercase;
  }
  table {
    width: 100%;
    border-collapse: collapse;
  }
  th,
  td {
    border: 1px solid #000;
    padding: 4px 6px;
    vertical-align: top;
  }
  th {
    background: #eee;
    text-align: left;
  }
  .num {
    text-align: right;
    white-space: nowrap;
  }
  .sign {
    display: flex;
    justify-content: space-between;
    margin-top: 48px;
  }
  @media print {
    .bar {
      display: none;
    }
    :host {
      padding: 0;
    }
  }
`;

/** Printable purchase order (opened in a new tab without the app's menus). */
@Component({
  selector: 'trishul-po-print-page',
  imports: [DatePipe, DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: PRINT_STYLES,
  template: `
    @if (po(); as po) {
      <div class="bar">
        <button type="button" (click)="print()">Print</button>
      </div>
      <header>
        <div>
          <h1>{{ po.companyName }}</h1>
          <div>
            {{ po.branchName
            }}{{ po.branchAddress ? ', ' + po.branchAddress : '' }}
          </div>
          @if (po.companyAddress) {
            <div>{{ po.companyAddress }}</div>
          }
        </div>
        <div>
          <h2>PURCHASE ORDER</h2>
          <div class="num">
            No: <strong>{{ po.poNo }}</strong>
          </div>
          <div class="num">Date: {{ po.poDate | date: 'dd-MM-yyyy' }}</div>
          @if (po.expectedDate) {
            <div class="num">
              Deliver by: {{ po.expectedDate | date: 'dd-MM-yyyy' }}
            </div>
          }
          @if (
            po.status !== 'Approved' &&
            po.status !== 'Part received' &&
            po.status !== 'Received'
          ) {
            <div class="num">
              <strong>{{ po.status.toUpperCase() }}</strong>
            </div>
          }
        </div>
      </header>
      <div class="parties">
        <div class="box">
          <div class="label">Supplier</div>
          <strong>{{ po.supplierName }}</strong> ({{ po.supplierCode }})
          <div>{{ po.supplierAddress ?? '' }}</div>
          @if (po.supplierGstin) {
            <div>GSTIN: {{ po.supplierGstin }}</div>
          }
          @if (po.supplierPhone) {
            <div>Phone: {{ po.supplierPhone }}</div>
          }
        </div>
        <div class="box">
          <div class="label">Deliver to</div>
          <strong>{{ po.branchName }} · {{ po.locationName }}</strong>
          <div>{{ po.locationAddress ?? po.branchAddress ?? '' }}</div>
          <div>Place of supply: {{ po.placeOfSupply }}</div>
          <div>Payment terms: {{ po.paymentTerms ?? 'As agreed' }}</div>
        </div>
      </div>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Item</th>
            <th class="num">Qty</th>
            <th>Unit</th>
            <th class="num">Rate</th>
            <th class="num">Disc %</th>
            <th class="num">Taxable</th>
            <th class="num">GST %</th>
            <th class="num">GST</th>
            <th class="num">Amount</th>
          </tr>
        </thead>
        <tbody>
          @for (l of po.lines; track l.id; let i = $index) {
            <tr>
              <td>{{ i + 1 }}</td>
              <td>
                <strong>{{ l.itemCode }}</strong> {{ l.itemDescription }}
                @if (l.description) {
                  <div>{{ l.description }}</div>
                }
              </td>
              <td class="num">{{ l.quantity | number: '1.0-3' }}</td>
              <td>{{ l.uomCode }}</td>
              <td class="num">{{ l.unitPrice | number: '1.2-2' }}</td>
              <td class="num">
                {{ n0(l.discountPct) ? (l.discountPct | number: '1.0-2') : '' }}
              </td>
              <td class="num">{{ l.taxableValue | number: '1.2-2' }}</td>
              <td class="num">{{ l.gstPct | number: '1.0-2' }}</td>
              <td class="num">{{ l.taxAmount | number: '1.2-2' }}</td>
              <td class="num">{{ l.lineTotal | number: '1.2-2' }}</td>
            </tr>
          }
        </tbody>
        <tfoot>
          <tr>
            <td colspan="9" class="num">Taxable value</td>
            <td class="num">{{ po.subtotal | number: '1.2-2' }}</td>
          </tr>
          @if (n0(po.igst)) {
            <tr>
              <td colspan="9" class="num">IGST</td>
              <td class="num">{{ po.igst | number: '1.2-2' }}</td>
            </tr>
          } @else {
            <tr>
              <td colspan="9" class="num">CGST</td>
              <td class="num">{{ po.cgst | number: '1.2-2' }}</td>
            </tr>
            <tr>
              <td colspan="9" class="num">SGST</td>
              <td class="num">{{ po.sgst | number: '1.2-2' }}</td>
            </tr>
          }
          @if (n0(po.otherCharges)) {
            <tr>
              <td colspan="9" class="num">Other charges</td>
              <td class="num">{{ po.otherCharges | number: '1.2-2' }}</td>
            </tr>
          }
          <tr>
            <td colspan="9" class="num"><strong>Total (₹)</strong></td>
            <td class="num">
              <strong>{{ po.total | number: '1.2-2' }}</strong>
            </td>
          </tr>
        </tfoot>
      </table>
      @if (po.remarks) {
        <p><strong>Remarks:</strong> {{ po.remarks }}</p>
      }
      <p>Please quote the PO number on your invoice and delivery challan.</p>
      <div class="sign">
        <div>Prepared by: {{ po.createdBy ?? '' }}</div>
        <div>Approved by: {{ po.approvedBy ?? '' }}</div>
        <div>For {{ po.companyName }}<br /><br />Authorised signatory</div>
      </div>
    }
  `,
})
export class PoPrintPage {
  private readonly api = inject(ApiClient);
  readonly poId = input.required<string>();
  protected readonly po = signal<PoDetail | null>(null);
  protected readonly n0 = n0;

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

  protected print(): void {
    window.print();
  }
}

/** Printable payment voucher. */
@Component({
  selector: 'trishul-payment-voucher-page',
  imports: [DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: PRINT_STYLES,
  template: `
    @if (payment(); as p) {
      <div class="bar">
        <button type="button" (click)="print()">Print</button>
      </div>
      <header>
        <div>
          <h1>{{ p.companyName }}</h1>
          <div>{{ p.branchName }}</div>
        </div>
        <div>
          <h2>PAYMENT VOUCHER</h2>
          <div class="num">
            No: <strong>{{ p.paymentNo }}</strong>
          </div>
          <div class="num">Date: {{ p.paymentDate | date: 'dd-MM-yyyy' }}</div>
        </div>
      </header>
      <div class="parties">
        <div class="box">
          <div class="label">Paid to</div>
          <strong>{{ p.supplierName }}</strong> ({{ p.supplierCode }})
          <div>{{ p.supplierAddress ?? '' }}</div>
          @if (p.supplierGstin) {
            <div>GSTIN: {{ p.supplierGstin }}</div>
          }
        </div>
        <div class="box">
          <div class="label">Payment</div>
          <div>Mode: {{ p.paymentMode }}</div>
          <div>
            Reference: {{ p.referenceNo ?? '—'
            }}{{
              p.chequeDate
                ? ' dated ' + (p.chequeDate | date: 'dd-MM-yyyy')
                : ''
            }}
          </div>
          <div>Bank: {{ p.bankName ?? '—' }}</div>
          <div>
            Amount: <strong>{{ money(p.amount) }}</strong>
          </div>
        </div>
      </div>
      <p>
        <strong>{{ p.amountInWords }}</strong>
      </p>
      <table>
        <thead>
          <tr>
            <th>Against invoice</th>
            <th>Supplier's no</th>
            <th class="num">Invoice total</th>
            <th class="num">Paid now</th>
          </tr>
        </thead>
        <tbody>
          @for (a of p.allocations; track a.id) {
            @if (a.isActive) {
              <tr>
                <td>{{ a.invoiceNo }}</td>
                <td>{{ a.supplierInvoiceNo }}</td>
                <td class="num">{{ money(a.invoiceTotal) }}</td>
                <td class="num">{{ money(a.amount) }}</td>
              </tr>
            }
          }
          @if (n0(p.unallocated) > 0) {
            <tr>
              <td colspan="3">On account (advance)</td>
              <td class="num">{{ money(p.unallocated) }}</td>
            </tr>
          }
        </tbody>
      </table>
      @if (p.remarks) {
        <p><strong>Remarks:</strong> {{ p.remarks }}</p>
      }
      <div class="sign">
        <div>Prepared by: {{ p.postedBy ?? '' }}</div>
        <div>Checked by</div>
        <div>Receiver's signature</div>
      </div>
    }
  `,
})
export class PaymentVoucherPage {
  private readonly api = inject(ApiClient);
  readonly paymentId = input.required<string>();
  protected readonly payment = signal<PaymentDetail | null>(null);
  protected readonly money = rupees;
  protected readonly n0 = n0;

  constructor() {
    effect(() => {
      const id = Number(this.paymentId());
      untracked(() =>
        this.api
          .call(getSupplierPayment, { paymentId: id })
          .pipe(catchError(() => EMPTY))
          .subscribe((p) => this.payment.set(p)),
      );
    });
  }

  protected print(): void {
    window.print();
  }
}
