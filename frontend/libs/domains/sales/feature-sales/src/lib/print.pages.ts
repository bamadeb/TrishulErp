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
  DeliveryDetail,
  OrderDetail,
  QuotationDetail,
  ReceiptDetail,
  SalesInvoiceDetail,
  getDelivery,
  getQuotation,
  getReceipt,
  getSalesInvoice,
  getSalesOrder,
} from '@trishul/core-api';
import { n0 } from '@trishul/inventory-data-access';
import { EMPTY, Observable, catchError } from 'rxjs';
import { rupees } from './sales.shared';

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
  .bar { display: flex; justify-content: flex-end; gap: 0.5rem; margin-bottom: 1rem; }
  .bar button { padding: 0.4rem 1rem; font: inherit; cursor: pointer; }
  header { display: flex; justify-content: space-between; border-bottom: 2px solid #000; padding-bottom: 8px;
    margin-bottom: 10px; }
  h1 { margin: 0; font-size: 18px; }
  h2 { margin: 0; font-size: 16px; text-align: right; }
  .parties { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 10px; }
  .box { border: 1px solid #000; padding: 6px 8px; }
  .label { font-weight: bold; font-size: 11px; text-transform: uppercase; }
  table { width: 100%; border-collapse: collapse; }
  th, td { border: 1px solid #000; padding: 4px 6px; vertical-align: top; }
  th { background: #eee; text-align: left; }
  .num { text-align: right; white-space: nowrap; }
  .sign { display: flex; justify-content: space-between; margin-top: 48px; }
  .stamp { font-weight: bold; border: 2px solid #000; padding: 2px 6px; display: inline-block; }
  @media print { .bar { display: none; } :host { padding: 0; } }
`;

/** Loads one document for a print view by its route id. */
function printable<T>(id: () => string, load: (id: number) => Observable<T>) {
  const value = signal<T | null>(null);
  effect(() => {
    const n = Number(id());
    untracked(() =>
      load(n)
        .pipe(catchError(() => EMPTY))
        .subscribe((v) => value.set(v)),
    );
  });
  return value;
}

/** Printable quotation (print, or save as PDF from the browser's print dialog). */
@Component({
  selector: 'trishul-quotation-print-page',
  imports: [DatePipe, DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: PRINT_STYLES,
  template: `
    @if (q(); as q) {
      <div class="bar">
        <button type="button" (click)="print()">Print / save as PDF</button>
      </div>
      <header>
        <div>
          <h1>{{ q.companyName }}</h1>
          <div>
            {{ q.branchName
            }}{{ q.branchAddress ? ', ' + q.branchAddress : '' }}
          </div>
          @if (q.companyAddress) {
            <div>{{ q.companyAddress }}</div>
          }
        </div>
        <div>
          <h2>QUOTATION</h2>
          <div class="num">
            No: <strong>{{ q.quotationNo }}</strong> (rev
            {{ q.currentVersion }})
          </div>
          <div class="num">
            Date: {{ q.quotationDate | date: 'dd-MM-yyyy' }}
          </div>
          @if (q.validUntil) {
            <div class="num">
              Valid until: {{ q.validUntil | date: 'dd-MM-yyyy' }}
            </div>
          }
          @if (q.state === 'Draft' || q.state === 'Pending approval') {
            <div class="num"><span class="stamp">DRAFT</span></div>
          }
        </div>
      </header>
      <div class="parties">
        <div class="box">
          <div class="label">To</div>
          <strong>{{ q.customerName }}</strong> ({{ q.customerCode }})
          @if (q.customerSiteName) {
            <div>{{ q.customerSiteName }}</div>
          }
          <div>{{ q.customerAddress ?? '' }}</div>
          @if (q.customerGstin) {
            <div>GSTIN: {{ q.customerGstin }}</div>
          }
          @if (q.customerPhone) {
            <div>Phone: {{ q.customerPhone }}</div>
          }
        </div>
        <div class="box">
          <div class="label">Details</div>
          <div>Brand: {{ q.principalName }}</div>
          <div>Type: {{ q.quotationType }}</div>
          <div>Place of supply: {{ q.placeOfSupply }}</div>
        </div>
      </div>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Description</th>
            <th class="num">Qty</th>
            <th class="num">Rate</th>
            <th class="num">Disc %</th>
            <th class="num">Taxable</th>
            <th class="num">GST %</th>
            <th class="num">Amount</th>
          </tr>
        </thead>
        <tbody>
          @for (l of q.lines; track l.id; let i = $index) {
            <tr>
              <td>{{ i + 1 }}</td>
              <td>
                @if (l.itemCode) {
                  <strong>{{ l.itemCode }}</strong>
                }
                {{ l.description }}
              </td>
              <td class="num">
                {{ l.quantity | number: '1.0-3' }} {{ l.uomCode ?? '' }}
              </td>
              <td class="num">{{ l.unitPrice | number: '1.2-2' }}</td>
              <td class="num">
                {{ n0(l.discountPct) ? (l.discountPct | number: '1.0-2') : '' }}
              </td>
              <td class="num">{{ l.taxableValue | number: '1.2-2' }}</td>
              <td class="num">{{ l.gstPct | number: '1.0-2' }}</td>
              <td class="num">{{ l.lineTotal | number: '1.2-2' }}</td>
            </tr>
          }
        </tbody>
        <tfoot>
          <tr>
            <td colspan="7" class="num">Taxable value</td>
            <td class="num">{{ q.taxableValue | number: '1.2-2' }}</td>
          </tr>
          @if (n0(q.igst)) {
            <tr>
              <td colspan="7" class="num">IGST</td>
              <td class="num">{{ q.igst | number: '1.2-2' }}</td>
            </tr>
          } @else {
            <tr>
              <td colspan="7" class="num">CGST</td>
              <td class="num">{{ q.cgst | number: '1.2-2' }}</td>
            </tr>
            <tr>
              <td colspan="7" class="num">SGST</td>
              <td class="num">{{ q.sgst | number: '1.2-2' }}</td>
            </tr>
          }
          @if (n0(q.otherCharges)) {
            <tr>
              <td colspan="7" class="num">Other charges</td>
              <td class="num">{{ q.otherCharges | number: '1.2-2' }}</td>
            </tr>
          }
          <tr>
            <td colspan="7" class="num"><strong>Total (₹)</strong></td>
            <td class="num">
              <strong>{{ q.total | number: '1.2-2' }}</strong>
            </td>
          </tr>
        </tfoot>
      </table>
      @if (q.terms) {
        <p style="white-space: pre-line">
          <strong>Terms and conditions:</strong><br />{{ q.terms }}
        </p>
      }
      <div class="sign">
        <div>Prepared by: {{ q.createdBy ?? '' }}</div>
        <div>For {{ q.companyName }}<br /><br />Authorised signatory</div>
      </div>
    }
  `,
})
export class QuotationPrintPage {
  private readonly api = inject(ApiClient);
  readonly quotationId = input.required<string>();
  protected readonly q = printable(this.quotationId, (id) =>
    this.api.call(getQuotation, { quotationId: id }),
  );
  protected readonly n0 = n0;
  protected print(): void {
    window.print();
  }
}

/** Printable sales order (order confirmation). */
@Component({
  selector: 'trishul-order-print-page',
  imports: [DatePipe, DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: PRINT_STYLES,
  template: `
    @if (o(); as o) {
      <div class="bar">
        <button type="button" (click)="print()">Print / save as PDF</button>
      </div>
      <header>
        <div>
          <h1>{{ o.companyName }}</h1>
          <div>
            {{ o.branchName
            }}{{ o.branchAddress ? ', ' + o.branchAddress : '' }}
          </div>
        </div>
        <div>
          <h2>SALES ORDER</h2>
          <div class="num">
            No: <strong>{{ o.orderNo }}</strong>
          </div>
          <div class="num">Date: {{ o.orderDate | date: 'dd-MM-yyyy' }}</div>
          @if (o.customerPoNo) {
            <div class="num">
              Your PO: {{ o.customerPoNo
              }}{{
                o.customerPoDate
                  ? ' dt ' + (o.customerPoDate | date: 'dd-MM-yyyy')
                  : ''
              }}
            </div>
          }
          @if (o.status === 'Draft' || o.status === 'Pending approval') {
            <div class="num"><span class="stamp">NOT APPROVED</span></div>
          }
        </div>
      </header>
      <div class="parties">
        <div class="box">
          <div class="label">Bill to</div>
          <strong>{{ o.customerName }}</strong> ({{ o.customerCode }})
          <div>{{ o.billToAddress ?? '' }}</div>
          @if (o.customerGstin) {
            <div>GSTIN: {{ o.customerGstin }}</div>
          }
        </div>
        <div class="box">
          <div class="label">Deliver to</div>
          @if (o.customerSiteName) {
            <strong>{{ o.customerSiteName }}</strong>
          }
          <div>{{ o.shipToAddress ?? '' }}</div>
          <div>
            Expected:
            {{
              o.expectedDeliveryDate
                ? (o.expectedDeliveryDate | date: 'dd-MM-yyyy')
                : 'As agreed'
            }}
          </div>
          <div>
            Payment: {{ o.paymentTerms ?? 'As agreed'
            }}{{ o.isPrepaid ? ' (advance)' : '' }}
          </div>
        </div>
      </div>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Item</th>
            <th class="num">Qty</th>
            <th class="num">Rate</th>
            <th class="num">Disc %</th>
            <th class="num">Taxable</th>
            <th class="num">GST %</th>
            <th class="num">Amount</th>
          </tr>
        </thead>
        <tbody>
          @for (l of o.lines; track l.id; let i = $index) {
            <tr>
              <td>{{ i + 1 }}</td>
              <td>
                <strong>{{ l.itemCode }}</strong> {{ l.description }}
              </td>
              <td class="num">
                {{ l.quantity | number: '1.0-3' }} {{ l.uomCode ?? '' }}
              </td>
              <td class="num">{{ l.unitPrice | number: '1.2-2' }}</td>
              <td class="num">
                {{ n0(l.discountPct) ? (l.discountPct | number: '1.0-2') : '' }}
              </td>
              <td class="num">{{ l.taxableValue | number: '1.2-2' }}</td>
              <td class="num">{{ l.gstPct | number: '1.0-2' }}</td>
              <td class="num">{{ l.lineTotal | number: '1.2-2' }}</td>
            </tr>
          }
        </tbody>
        <tfoot>
          <tr>
            <td colspan="7" class="num">Taxable value</td>
            <td class="num">{{ o.subtotal | number: '1.2-2' }}</td>
          </tr>
          <tr>
            <td colspan="7" class="num">
              {{ n0(o.igst) ? 'IGST' : 'CGST + SGST' }}
            </td>
            <td class="num">{{ o.taxTotal | number: '1.2-2' }}</td>
          </tr>
          @if (n0(o.otherCharges)) {
            <tr>
              <td colspan="7" class="num">Other charges</td>
              <td class="num">{{ o.otherCharges | number: '1.2-2' }}</td>
            </tr>
          }
          <tr>
            <td colspan="7" class="num"><strong>Total (₹)</strong></td>
            <td class="num">
              <strong>{{ o.total | number: '1.2-2' }}</strong>
            </td>
          </tr>
          @if (n0(o.advanceReceived)) {
            <tr>
              <td colspan="7" class="num">Advance received</td>
              <td class="num">{{ o.advanceReceived | number: '1.2-2' }}</td>
            </tr>
          }
        </tfoot>
      </table>
      <div class="sign">
        <div>Prepared by: {{ o.createdBy ?? '' }}</div>
        <div>Approved by: {{ o.approvedBy ?? '' }}</div>
        <div>For {{ o.companyName }}<br /><br />Authorised signatory</div>
      </div>
    }
  `,
})
export class OrderPrintPage {
  private readonly api = inject(ApiClient);
  readonly orderId = input.required<string>();
  protected readonly o = printable(this.orderId, (id) =>
    this.api.call(getSalesOrder, { orderId: id }),
  );
  protected readonly n0 = n0;
  protected print(): void {
    window.print();
  }
}

/** Delivery challan (goes with the goods). */
@Component({
  selector: 'trishul-delivery-print-page',
  imports: [DatePipe, DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: PRINT_STYLES,
  template: `
    @if (d(); as d) {
      <div class="bar">
        <button type="button" (click)="print()">Print</button>
      </div>
      <header>
        <div>
          <h1>{{ d.companyName }}</h1>
          <div>{{ d.locationName }} · {{ d.branchName }}</div>
          <div>{{ d.locationAddress ?? d.branchAddress ?? '' }}</div>
        </div>
        <div>
          <h2>DELIVERY CHALLAN</h2>
          <div class="num">
            No: <strong>{{ d.deliveryNo }}</strong>
          </div>
          <div class="num">Date: {{ d.deliveryDate | date: 'dd-MM-yyyy' }}</div>
          @if (d.orderNo) {
            <div class="num">Order: {{ d.orderNo }}</div>
          }
          @if (d.status === 'Cancelled') {
            <div class="num"><span class="stamp">CANCELLED</span></div>
          }
        </div>
      </header>
      <div class="parties">
        <div class="box">
          <div class="label">Consignee</div>
          <strong>{{ d.customerName }}</strong> ({{ d.customerCode }})
          @if (d.customerSiteName) {
            <div>{{ d.customerSiteName }}</div>
          }
          <div>{{ d.shipToAddress ?? '' }}</div>
          @if (d.customerGstin) {
            <div>GSTIN: {{ d.customerGstin }}</div>
          }
          @if (d.customerPhone) {
            <div>Phone: {{ d.customerPhone }}</div>
          }
        </div>
        <div class="box">
          <div class="label">Transport</div>
          <div>Vehicle: {{ d.vehicleNo ?? '—' }}</div>
          <div>Transporter: {{ d.transporter ?? '—' }}</div>
          <div>LR / docket: {{ d.lrNo ?? '—' }}</div>
          <div>Reference: {{ d.deliveryReference ?? '—' }}</div>
        </div>
      </div>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Item</th>
            <th>Batch (GRN)</th>
            <th class="num">Qty</th>
          </tr>
        </thead>
        <tbody>
          @for (l of d.lines; track l.id; let i = $index) {
            <tr>
              <td>{{ i + 1 }}</td>
              <td>
                <strong>{{ l.itemCode }}</strong> {{ l.description }}
              </td>
              <td>
                @for (b of l.batches; track $index) {
                  <div>{{ b.grnNo }} · {{ b.quantity | number: '1.0-3' }}</div>
                }
              </td>
              <td class="num">
                {{ l.quantity | number: '1.0-3' }} {{ l.uomCode ?? '' }}
              </td>
            </tr>
          }
        </tbody>
      </table>
      @if (d.remarks) {
        <p><strong>Remarks:</strong> {{ d.remarks }}</p>
      }
      <p>Goods received in good condition.</p>
      <div class="sign">
        <div>Dispatched by: {{ d.postedBy ?? '' }}</div>
        <div>
          Receiver: {{ d.receivedByName ?? '' }}<br /><br />Signature &amp; seal
        </div>
        <div>For {{ d.companyName }}<br /><br />Authorised signatory</div>
      </div>
    }
  `,
})
export class DeliveryPrintPage {
  private readonly api = inject(ApiClient);
  readonly deliveryId = input.required<string>();
  protected readonly d = printable(this.deliveryId, (id) =>
    this.api.call(getDelivery, { deliveryId: id }),
  );
  protected print(): void {
    window.print();
  }
}

/** GST tax invoice. */
@Component({
  selector: 'trishul-sales-invoice-print-page',
  imports: [DatePipe, DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: PRINT_STYLES,
  template: `
    @if (i(); as i) {
      <div class="bar">
        <button type="button" (click)="print()">Print / save as PDF</button>
      </div>
      <header>
        <div>
          <h1>{{ i.companyName }}</h1>
          <div>
            {{ i.branchName
            }}{{ i.branchAddress ? ', ' + i.branchAddress : '' }}
          </div>
          @if (i.ourGstin) {
            <div>GSTIN: {{ i.ourGstin }}</div>
          }
        </div>
        <div>
          <h2>
            {{
              i.invoiceType === 'Bill of supply'
                ? 'BILL OF SUPPLY'
                : 'TAX INVOICE'
            }}
          </h2>
          <div class="num">
            No: <strong>{{ i.invoiceNo }}</strong>
          </div>
          <div class="num">Date: {{ i.invoiceDate | date: 'dd-MM-yyyy' }}</div>
          @if (i.dueDate) {
            <div class="num">Due: {{ i.dueDate | date: 'dd-MM-yyyy' }}</div>
          }
          @if (i.orderNo) {
            <div class="num">Order: {{ i.orderNo }}</div>
          }
          @if (i.state === 'Cancelled') {
            <div class="num"><span class="stamp">CANCELLED</span></div>
          }
        </div>
      </header>
      <div class="parties">
        <div class="box">
          <div class="label">Bill to</div>
          <strong>{{ i.customerName }}</strong> ({{ i.customerCode }})
          <div>{{ i.billToAddress ?? '' }}</div>
          <div>GSTIN: {{ i.customerGstin ?? 'Unregistered' }}</div>
        </div>
        <div class="box">
          <div class="label">Ship to</div>
          <div>{{ i.shipToAddress ?? i.billToAddress ?? '' }}</div>
          <div>Place of supply: {{ i.placeOfSupply }}</div>
        </div>
      </div>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Description</th>
            <th>HSN</th>
            <th class="num">Qty</th>
            <th class="num">Rate</th>
            <th class="num">Disc %</th>
            <th class="num">Taxable</th>
            <th class="num">GST %</th>
            @if (n0(i.igst)) {
              <th class="num">IGST</th>
            } @else {
              <th class="num">CGST</th>
              <th class="num">SGST</th>
            }
            <th class="num">Amount</th>
          </tr>
        </thead>
        <tbody>
          @for (l of i.lines; track l.id; let x = $index) {
            <tr>
              <td>{{ x + 1 }}</td>
              <td>
                @if (l.itemCode) {
                  <strong>{{ l.itemCode }}</strong>
                }
                {{ l.description }}
              </td>
              <td>{{ l.hsnCode ?? '' }}</td>
              <td class="num">
                {{ l.quantity | number: '1.0-3' }} {{ l.uomCode ?? '' }}
              </td>
              <td class="num">{{ l.unitPrice | number: '1.2-2' }}</td>
              <td class="num">
                {{ n0(l.discountPct) ? (l.discountPct | number: '1.0-2') : '' }}
              </td>
              <td class="num">{{ l.taxableValue | number: '1.2-2' }}</td>
              <td class="num">{{ l.gstPct | number: '1.0-2' }}</td>
              @if (n0(i.igst)) {
                <td class="num">{{ l.igstAmount | number: '1.2-2' }}</td>
              } @else {
                <td class="num">{{ l.cgstAmount | number: '1.2-2' }}</td>
                <td class="num">{{ l.sgstAmount | number: '1.2-2' }}</td>
              }
              <td class="num">{{ l.lineTotal | number: '1.2-2' }}</td>
            </tr>
          }
        </tbody>
        <tfoot>
          <tr>
            <td [attr.colspan]="cols(i)" class="num">Taxable value</td>
            <td class="num">{{ i.taxableValue | number: '1.2-2' }}</td>
          </tr>
          @if (n0(i.igst)) {
            <tr>
              <td [attr.colspan]="cols(i)" class="num">IGST</td>
              <td class="num">{{ i.igst | number: '1.2-2' }}</td>
            </tr>
          } @else {
            <tr>
              <td [attr.colspan]="cols(i)" class="num">CGST</td>
              <td class="num">{{ i.cgst | number: '1.2-2' }}</td>
            </tr>
            <tr>
              <td [attr.colspan]="cols(i)" class="num">SGST</td>
              <td class="num">{{ i.sgst | number: '1.2-2' }}</td>
            </tr>
          }
          @if (n0(i.otherCharges)) {
            <tr>
              <td [attr.colspan]="cols(i)" class="num">Other charges</td>
              <td class="num">{{ i.otherCharges | number: '1.2-2' }}</td>
            </tr>
          }
          @if (n0(i.roundOff)) {
            <tr>
              <td [attr.colspan]="cols(i)" class="num">Round off</td>
              <td class="num">{{ i.roundOff | number: '1.2-2' }}</td>
            </tr>
          }
          <tr>
            <td [attr.colspan]="cols(i)" class="num">
              <strong>Invoice total (₹)</strong>
            </td>
            <td class="num">
              <strong>{{ i.total | number: '1.2-2' }}</strong>
            </td>
          </tr>
          @if (n0(i.advanceAdjusted)) {
            <tr>
              <td [attr.colspan]="cols(i)" class="num">
                Less: advance adjusted
              </td>
              <td class="num">{{ i.advanceAdjusted | number: '1.2-2' }}</td>
            </tr>
            <tr>
              <td [attr.colspan]="cols(i)" class="num">
                <strong>Balance payable</strong>
              </td>
              <td class="num">
                <strong>{{ i.outstanding | number: '1.2-2' }}</strong>
              </td>
            </tr>
          }
        </tfoot>
      </table>
      <p>
        <strong>{{ i.amountInWords }}</strong>
      </p>
      @if (i.remarks) {
        <p><strong>Remarks:</strong> {{ i.remarks }}</p>
      }
      <div class="sign">
        <div>Prepared by: {{ i.postedBy ?? '' }}</div>
        <div>Customer's signature</div>
        <div>For {{ i.companyName }}<br /><br />Authorised signatory</div>
      </div>
    }
  `,
})
export class SalesInvoicePrintPage {
  private readonly api = inject(ApiClient);
  readonly invoiceId = input.required<string>();
  protected readonly i = printable(this.invoiceId, (id) =>
    this.api.call(getSalesInvoice, { invoiceId: id }),
  );
  protected readonly n0 = n0;
  protected cols(i: SalesInvoiceDetail): number {
    return n0(i.igst) ? 9 : 10;
  }
  protected print(): void {
    window.print();
  }
}

/** Receipt voucher given to the customer. */
@Component({
  selector: 'trishul-receipt-print-page',
  imports: [DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: PRINT_STYLES,
  template: `
    @if (r(); as r) {
      <div class="bar">
        <button type="button" (click)="print()">Print</button>
      </div>
      <header>
        <div>
          <h1>{{ r.companyName }}</h1>
          <div>
            {{ r.branchName
            }}{{ r.branchAddress ? ', ' + r.branchAddress : '' }}
          </div>
        </div>
        <div>
          <h2>RECEIPT</h2>
          <div class="num">
            No: <strong>{{ r.receiptNo }}</strong>
          </div>
          <div class="num">Date: {{ r.receiptDate | date: 'dd-MM-yyyy' }}</div>
        </div>
      </header>
      <div class="parties">
        <div class="box">
          <div class="label">Received from</div>
          <strong>{{ r.customerName }}</strong> ({{ r.customerCode }})
          <div>{{ r.customerAddress ?? '' }}</div>
          @if (r.customerGstin) {
            <div>GSTIN: {{ r.customerGstin }}</div>
          }
        </div>
        <div class="box">
          <div class="label">Payment</div>
          <div>
            {{ r.receiptType }}{{ r.orderNo ? ' for order ' + r.orderNo : '' }}
          </div>
          <div>Mode: {{ r.paymentMode }}</div>
          <div>
            Reference: {{ r.referenceNo ?? '—'
            }}{{
              r.chequeDate
                ? ' dated ' + (r.chequeDate | date: 'dd-MM-yyyy')
                : ''
            }}
          </div>
          <div>Bank: {{ r.bankName ?? '—' }}</div>
          <div>
            Amount: <strong>{{ money(r.amount) }}</strong>
          </div>
        </div>
      </div>
      <p>
        <strong>{{ r.amountInWords }}</strong>
      </p>
      <table>
        <thead>
          <tr>
            <th>Against invoice</th>
            <th class="num">Invoice total</th>
            <th class="num">Adjusted</th>
          </tr>
        </thead>
        <tbody>
          @for (a of r.allocations; track a.id) {
            @if (a.isActive) {
              <tr>
                <td>{{ a.invoiceNo }}</td>
                <td class="num">{{ money(a.invoiceTotal) }}</td>
                <td class="num">{{ money(a.amount) }}</td>
              </tr>
            }
          }
          @if (n0(r.unallocated) > 0) {
            <tr>
              <td colspan="2">
                {{
                  r.salesOrderId ? 'Advance held for the order' : 'On account'
                }}
              </td>
              <td class="num">{{ money(r.unallocated) }}</td>
            </tr>
          }
        </tbody>
      </table>
      <div class="sign">
        <div>Received by: {{ r.postedBy ?? '' }}</div>
        <div>For {{ r.companyName }}<br /><br />Authorised signatory</div>
      </div>
    }
  `,
})
export class ReceiptPrintPage {
  private readonly api = inject(ApiClient);
  readonly receiptId = input.required<string>();
  protected readonly r = printable(this.receiptId, (id) =>
    this.api.call(getReceipt, { receiptId: id }),
  );
  protected readonly money = rupees;
  protected readonly n0 = n0;
  protected print(): void {
    window.print();
  }
}

export type PrintedDocument =
  | QuotationDetail
  | OrderDetail
  | DeliveryDetail
  | SalesInvoiceDetail
  | ReceiptDetail;
