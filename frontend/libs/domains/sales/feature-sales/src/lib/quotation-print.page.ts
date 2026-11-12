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
import {
  ApiClient,
  PricedLineOut,
  QuotationDetail,
  getQuotation,
} from '@trishul/core-api';
import { n0 } from '@trishul/inventory-data-access';
import { EMPTY, catchError } from 'rxjs';

/** One printed line: the OEM layout shows gross, discount, net and each GST part. */
interface PrintLine {
  line: PricedLineOut;
  gross: number;
  discount: number;
  net: number;
  rate: number;
  cgst: number;
  sgst: number;
  igst: number;
  total: number;
}

const round2 = (v: number) => Math.round(v * 100) / 100;

/** Amounts print in Indian price format: 12,34,567.89 (the column headers carry INR). */
const amount = (v: string | number | null | undefined) =>
  n0(v).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

/**
 * Printable sales quotation in the OEM (Tata Hitachi) layout: logo and branch block with bank and
 * contact details, quotation number / date / customer ref, billing and delivery address, customer code
 * and GSTIN, the line grid with CGST / SGST / IGST rate and amount, charge rows, totals and the amount
 * in words. Print, or save as PDF from the browser's print dialog.
 */
@Component({
  selector: 'trishul-quotation-print-page',
  imports: [DatePipe, DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: `
    :host {
      display: block;
      max-width: 297mm;
      margin: 0 auto;
      padding: 8mm;
      background: #fff;
      color: #000;
      font:
        10.5px/1.35 Arial,
        Helvetica,
        sans-serif;
    }
    .bar {
      display: flex;
      justify-content: flex-end;
      margin-bottom: 0.75rem;
    }
    .bar button {
      padding: 0.4rem 1rem;
      font: inherit;
      cursor: pointer;
    }
    .sheet {
      border: 1px solid #000;
    }
    table {
      width: 100%;
      border-collapse: collapse;
    }
    td,
    th {
      border: 1px solid #000;
      padding: 3px 5px;
      vertical-align: top;
    }
    th {
      font-weight: normal;
      text-align: center;
      vertical-align: middle;
    }
    .top td {
      border: none;
    }
    .logo {
      width: 22%;
      vertical-align: middle;
    }
    .logo img {
      max-width: 150px;
      max-height: 60px;
    }
    .brand {
      display: inline-block;
      padding: 6px 10px;
      font-weight: 800;
      font-size: 15px;
      letter-spacing: 0.04em;
      color: #fff;
      background: #00338d;
    }
    .company {
      text-align: center;
      width: 40%;
    }
    .company .name {
      font-weight: bold;
      font-size: 12px;
    }
    .bank {
      text-align: left;
      margin-top: 4px;
    }
    .bank span {
      font-size: 12px;
    }
    .title {
      text-align: right;
      font-weight: bold;
      font-size: 20px;
      vertical-align: top;
      padding-top: 10px;
    }
    .ids td {
      text-align: center;
    }
    .ids .head {
      font-weight: bold;
    }
    .parties td {
      height: 120px;
    }
    .num {
      text-align: right;
      white-space: nowrap;
    }
    .c {
      text-align: center;
    }
    .bold {
      font-weight: bold;
    }
    .charges td {
      border-top: none;
      border-bottom: none;
    }
    .foot {
      text-align: center;
      padding: 6px 0 2px;
    }
    .page {
      text-align: right;
      padding: 2px 4px;
    }
    .stamp {
      font-weight: bold;
      border: 2px solid #c00;
      color: #c00;
      padding: 2px 6px;
      display: inline-block;
      margin-top: 4px;
      font-size: 12px;
    }
    @media print {
      .bar {
        display: none;
      }
      :host {
        padding: 0;
      }
      @page {
        size: A4 landscape;
        margin: 8mm;
      }
    }
  `,
  template: `
    @if (q(); as q) {
      <div class="bar">
        <button type="button" (click)="print()">Print / save as PDF</button>
      </div>
      <div class="sheet">
        <!-- Logo, our branch with bank and contact details, title -->
        <table class="top">
          <tr>
            <td class="logo">
              @if (q.principalLogoUrl) {
                <img [src]="q.principalLogoUrl" [alt]="q.principalName" />
              } @else {
                <span class="brand">{{ q.principalName.toUpperCase() }}</span>
              }
            </td>
            <td class="company">
              <div class="name">{{ q.companyName }}</div>
              <div>{{ q.companyName }}</div>
              @for (
                part of addressLines(q.branchAddress ?? q.companyAddress);
                track $index
              ) {
                <div>{{ part }}</div>
              }
              <div class="bank">
                @if (bank.name) {
                  <div>
                    Bank Name:<span>{{ bank.name }}</span>
                  </div>
                  <div>
                    IFS Code:<span>{{ bank.ifsc }}</span>
                  </div>
                  <div>
                    Bank No:<span>{{ bank.accountNo }}</span>
                  </div>
                }
                @if (q.branchPhone) {
                  <div>
                    Mobile:<span>{{ q.branchPhone }}</span>
                  </div>
                }
                @if (q.branchEmail) {
                  <div>
                    Email :<span>{{ q.branchEmail }}</span>
                  </div>
                }
              </div>
            </td>
            <td class="title">
              Sales Quotation
              @if (q.state === 'Draft' || q.state === 'Pending approval') {
                <div><span class="stamp">DRAFT</span></div>
              }
            </td>
          </tr>
        </table>

        <!-- Quotation number / date / customer ref -->
        <table class="ids">
          <tr>
            <td
              style="width: 50%; border-left: none; border-bottom: none"
              rowspan="2"
            ></td>
            <td class="head">Quotation Number</td>
            <td class="head">Quotation Date</td>
            <td class="head" style="border-right: none">Customer Ref No</td>
          </tr>
          <tr>
            <td>
              {{ q.quotationNo
              }}{{
                q.currentVersion > 1 ? ' (Rev ' + q.currentVersion + ')' : ''
              }}
            </td>
            <td>{{ q.quotationDate | date: 'dd-MMM-yy' }}</td>
            <td style="border-right: none">{{ q.customerOemCode ?? '' }}</td>
          </tr>
        </table>

        <!-- Billing / delivery / customer / terms -->
        <table class="parties">
          <tr>
            <td style="width: 22%; border-left: none">
              Billing Address :
              {{ q.customerContactName ? 'Mr. ' + q.customerContactName : '' }}
              <div>{{ q.customerName }}</div>
              @for (part of addressLines(q.billingAddress); track $index) {
                <div>{{ part }}</div>
              }
            </td>
            <td style="width: 24%">
              Delivery Address : {{ q.customerSiteName ?? q.customerName }}
              @for (part of addressLines(q.deliveryAddress); track $index) {
                <div>{{ part }}</div>
              }
            </td>
            <td style="width: 28%">
              <div>
                <span class="bold">Customer Code :</span> {{ q.customerCode }}
              </div>
              <div>
                <span class="bold">Customer Name :</span> {{ q.customerName }}
              </div>
              <br /><br />
              <div>
                <span class="bold">GST Registration Number:</span>
                {{ q.customerGstin ?? '' }}
              </div>
              <div>
                <span class="bold">GST Registration Type :</span>
                {{ q.customerGstType ?? '' }}
              </div>
            </td>
            <td style="border-right: none">
              <div class="bold">Shipping Terms:</div>
              <div>
                <span class="bold">Payment Terms:</span>
                {{ q.paymentTerms ?? '' }}
              </div>
              <br />
              <div class="bold">Contact Details :</div>
              <div>
                <span class="bold">Name :</span>
                {{ q.contactName ?? q.createdBy ?? '' }}
              </div>
              <div>
                <span class="bold">Contact Number :</span>
                {{ q.contactPhone ?? '' }}
              </div>
              <div>
                <span class="bold">E-Mail:</span> {{ q.contactEmail ?? '' }}
              </div>
            </td>
          </tr>
        </table>

        <!-- Lines -->
        <table>
          <thead>
            <tr>
              <th rowspan="2" style="border-left: none">Sno</th>
              <th rowspan="2">Item Code/Product Description</th>
              <th rowspan="2">HSN/SAC Code</th>
              <th rowspan="2">Qty</th>
              <th rowspan="2">UOM</th>
              <th rowspan="2">Unit Price [INR]</th>
              <th rowspan="2">Total Before Discount [INR]</th>
              <th rowspan="2">Discount [INR]</th>
              <th rowspan="2">Discount (%)</th>
              <th rowspan="2">Net Price (INR)</th>
              <th colspan="2">CGST [INR]</th>
              <th colspan="2">SGST [INR]</th>
              <th colspan="2">IGST [INR]</th>
              <th rowspan="2" style="border-right: none">Line Total [INR]</th>
            </tr>
            <tr>
              <th>Rate</th>
              <th>Amount</th>
              <th>Rate</th>
              <th>Amount</th>
              <th>Rate</th>
              <th>Amount</th>
            </tr>
          </thead>
          <tbody>
            @for (p of lines(); track p.line.id) {
              <tr>
                <td class="c" style="border-left: none">{{ p.line.lineNo }}</td>
                <td class="c">
                  {{ p.line.itemCode ? p.line.itemCode + '/' : ''
                  }}{{ p.line.description }}
                </td>
                <td class="c">{{ p.line.hsnCode ?? '' }}</td>
                <td class="c">{{ p.line.quantity | number: '1.0-3' }}</td>
                <td class="c">{{ p.line.uomCode ?? '' }}</td>
                <td class="num">{{ amount(p.line.unitPrice) }}</td>
                <td class="num">{{ amount(p.gross) }}</td>
                <td class="num">
                  {{ p.discount ? amount(-p.discount) : '' }}
                </td>
                <td class="num">
                  {{
                    n0(p.line.discountPct)
                      ? (-n0(p.line.discountPct) | number: '1.2-2')
                      : ''
                  }}
                </td>
                <td class="num">{{ amount(p.net) }}</td>
                <td class="c">
                  {{ p.cgst ? (p.rate / 2 | number: '1.0-2') : '' }}
                </td>
                <td class="num">
                  {{ p.cgst ? amount(p.cgst) : '' }}
                </td>
                <td class="c">
                  {{ p.sgst ? (p.rate / 2 | number: '1.0-2') : '' }}
                </td>
                <td class="num">
                  {{ p.sgst ? amount(p.sgst) : '' }}
                </td>
                <td class="c">
                  {{ p.igst ? (p.rate | number: '1.0-2') : '' }}
                </td>
                <td class="num">
                  {{ p.igst ? amount(p.igst) : '' }}
                </td>
                <td class="num" style="border-right: none">
                  {{ amount(p.total) }}
                </td>
              </tr>
            }
            <tr>
              <td style="border-left: none">&nbsp;</td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td style="border-right: none"></td>
            </tr>
            <tr class="charges">
              <td style="border-left: none"></td>
              <td>
                <div>Frieght [INR]</div>
                <div style="margin-top: 6px">Insurance [INR]</div>
                <div style="margin-top: 6px">TCS%</div>
              </td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td class="num" style="border-right: none">
                {{
                  n0(q.otherCharges) ? amount(q.otherCharges) : ''
                }}
              </td>
            </tr>
            <tr>
              <td style="border-left: none"></td>
              <td>Packing and Forwarding Expenses [INR]</td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td style="border-right: none"></td>
            </tr>
            <tr class="bold">
              <td colspan="6" style="border-left: none">Total Amount [INR]</td>
              <td class="num">{{ amount(totals().gross) }}</td>
              <td class="num">{{ amount(totals().discount) }}</td>
              <td></td>
              <td class="num">{{ amount(totals().net) }}</td>
              <td colspan="2" class="num">
                {{ totals().cgst ? amount(totals().cgst) : '' }}
              </td>
              <td colspan="2" class="num">
                {{ totals().sgst ? amount(totals().sgst) : '' }}
              </td>
              <td colspan="2" class="num">
                {{ totals().igst ? amount(totals().igst) : '' }}
              </td>
              <td class="num" style="border-right: none">
                {{ amount(q.roundedTotal) }}
              </td>
            </tr>
            <tr>
              <td colspan="17" style="border-left: none; border-right: none">
                &nbsp;
              </td>
            </tr>
            <tr>
              <td colspan="10" style="border-left: none">
                Remarks : {{ q.terms ?? '' }}
              </td>
              <td colspan="7" style="border-right: none"></td>
            </tr>
            <tr>
              <td colspan="10" style="border-left: none; border-bottom: none">
                Amount In Words : (INR) {{ q.amountInWords }}
              </td>
              <td colspan="4" class="bold" style="border-bottom: none">
                Total [INR]
              </td>
              <td
                colspan="3"
                class="num bold"
                style="border-right: none; border-bottom: none"
              >
                {{ amount(q.roundedTotal) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="foot">
        @if (q.branchPhone) {
          Ph No : {{ q.branchPhone }}
        }
        @if (q.branchEmail) {
          &nbsp;&nbsp;&nbsp;&nbsp; Email ID : {{ q.branchEmail }}
        }
      </div>
      <div class="page">Page 1 of 1</div>
    }
  `,
})
export class QuotationPrintPage {
  private readonly api = inject(ApiClient);
  readonly quotationId = input.required<string>();
  protected readonly q = signal<QuotationDetail | null>(null);
  protected readonly n0 = n0;
  protected readonly amount = amount;
  /** Bank details print once they are kept for the branch; none are stored yet. */
  protected readonly bank = { name: '', ifsc: '', accountNo: '' };

  protected readonly lines = computed<PrintLine[]>(() => {
    const q = this.q();
    if (!q) return [];
    const interState = n0(q.igst) > 0;
    return q.lines.map((line) => {
      const gross = round2(n0(line.quantity) * n0(line.unitPrice));
      const net = n0(line.taxableValue);
      const tax = n0(line.taxAmount);
      const half = round2(tax / 2);
      return {
        line,
        gross,
        discount: round2(gross - net),
        net,
        rate: n0(line.gstPct),
        cgst: interState ? 0 : half,
        sgst: interState ? 0 : round2(tax - half),
        igst: interState ? tax : 0,
        total: n0(line.lineTotal),
      };
    });
  });

  protected readonly totals = computed(() => {
    const sum = (pick: (p: PrintLine) => number) =>
      round2(this.lines().reduce((s, p) => s + pick(p), 0));
    return {
      gross: sum((p) => p.gross),
      discount: sum((p) => p.discount),
      net: sum((p) => p.net),
      cgst: sum((p) => p.cgst),
      sgst: sum((p) => p.sgst),
      igst: sum((p) => p.igst),
    };
  });

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

  /** An address entered on one line with commas prints one part per line. */
  protected addressLines(address: string | null | undefined): string[] {
    return (address ?? '')
      .split(/\r?\n|,\s*/)
      .map((p) => p.trim())
      .filter(Boolean);
  }

  protected print(): void {
    window.print();
  }
}
