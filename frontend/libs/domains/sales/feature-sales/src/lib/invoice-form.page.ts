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
import { toSignal } from '@angular/core/rxjs-interop';
import {
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { provideNativeDateAdapter } from '@angular/material/core';
import {
  MatDatepicker,
  MatDatepickerInput,
  MatDatepickerToggle,
} from '@angular/material/datepicker';
import {
  MatFormField,
  MatHint,
  MatLabel,
  MatSuffix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatTooltip } from '@angular/material/tooltip';
import { Router, RouterLink } from '@angular/router';
import {
  ApiClient,
  ItemListItem,
  SalesInvoiceLineIn,
  UninvoicedDeliveryLine,
  createSalesInvoice,
  getCustomerAccount,
  listUninvoicedDeliveryLines,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import { ItemPicker, isoDate, num } from '@trishul/inventory-data-access';
import {
  CustomerPicker,
  NO_SALES_OPTIONS,
  PickedCustomer,
  SAL_CREDIT_OVERRIDE,
  SAL_INVOICE_DIRECT,
  SAL_INVOICE_MANAGE,
  SalesLookups,
} from '@trishul/sales-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { EMPTY, catchError, finalize, of } from 'rxjs';
import { lineAmounts, rupees } from './sales.shared';

function billedLine(line: UninvoicedDeliveryLine, selected: boolean) {
  return {
    source: line,
    form: new FormGroup({
      selected: new FormControl(selected, { nonNullable: true }),
      quantity: new FormControl<number | null>(num(line.qtyToInvoice), [
        Validators.required,
        Validators.min(0.001),
        Validators.max(num(line.qtyToInvoice) ?? 0),
      ]),
      unitPrice: new FormControl<number | null>(num(line.unitPrice), [
        Validators.required,
        Validators.min(0),
      ]),
      discountPct: new FormControl<number | null>(num(line.discountPct), [
        Validators.min(0),
        Validators.max(100),
      ]),
      gstPct: new FormControl<number | null>(num(line.gstPct), [
        Validators.required,
        Validators.min(0),
        Validators.max(100),
      ]),
    }),
  };
}
type BilledLine = ReturnType<typeof billedLine>;

function directLine() {
  return new FormGroup({
    item: new FormControl<ItemListItem | null>(null),
    description: new FormControl<string | null>(
      null,
      Validators.maxLength(300),
    ),
    quantity: new FormControl<number | null>(1, [
      Validators.required,
      Validators.min(0.001),
    ]),
    unitPrice: new FormControl<number | null>(null, [
      Validators.required,
      Validators.min(0),
    ]),
    discountPct: new FormControl<number | null>(0, [
      Validators.min(0),
      Validators.max(100),
    ]),
    gstPct: new FormControl<number | null>(18, [
      Validators.required,
      Validators.min(0),
      Validators.max(100),
    ]),
  });
}
type DirectLine = ReturnType<typeof directLine>;

/**
 * Raise a sales invoice: bill delivered goods (they don't leave stock again), or direct lines with
 * permission (a direct stock item leaves stock from the chosen location). Order advances are adjusted.
 */
@Component({
  selector: 'trishul-sales-invoice-form-page',
  imports: [
    DatePipe,
    DecimalPipe,
    ReactiveFormsModule,
    RouterLink,
    MatFormField,
    MatLabel,
    MatHint,
    MatSuffix,
    MatInput,
    MatSelect,
    MatOption,
    MatCheckbox,
    MatDatepicker,
    MatDatepickerInput,
    MatDatepickerToggle,
    MatButton,
    MatIconButton,
    MatIcon,
    MatTooltip,
    CustomerPicker,
    ItemPicker,
    PageHeader,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  styles: `
    input.cell {
      width: 6rem;
      padding: 0.3rem 0.4rem;
      border: 1px solid var(--mat-sys-outline-variant);
      border-radius: 4px;
      background: transparent;
      color: inherit;
      font: inherit;
    }
  `,
  template: `
    <trishul-page-header
      title="New sales invoice"
      subtitle="Bill delivered goods, or invoice directly; the invoice number follows the branch's GST series"
    />
    <form [formGroup]="form" (ngSubmit)="save()">
      <section class="card">
        <h2>Invoice</h2>
        <div class="form-grid">
          <trishul-customer-picker formControlName="customer" />
          <mat-form-field appearance="outline">
            <mat-label>Invoice date</mat-label>
            <input
              matInput
              [matDatepicker]="datePicker"
              formControlName="invoiceDate"
              [max]="today"
            />
            <mat-datepicker-toggle
              matSuffix
              [for]="datePicker"
            /><mat-datepicker #datePicker />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Due date</mat-label>
            <input
              matInput
              [matDatepicker]="duePicker"
              formControlName="dueDate"
            />
            <mat-datepicker-toggle matSuffix [for]="duePicker" /><mat-datepicker
              #duePicker
            />
            <mat-hint>Blank: from the payment terms</mat-hint>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Type</mat-label>
            <mat-select formControlName="invoiceType">
              <mat-option value="Tax invoice">Tax invoice</mat-option>
              <mat-option value="Bill of supply">Bill of supply</mat-option>
              <mat-option value="Export">Export</mat-option>
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Brand</mat-label>
            <mat-select formControlName="principalId">
              <mat-option [value]="null">The deliveries' brand</mat-option>
              @for (b of options().brands; track b.id) {
                <mat-option [value]="b.id">{{ b.name }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Branch</mat-label>
            <mat-select formControlName="branchId">
              <mat-option [value]="null">The deliveries' branch</mat-option>
              @for (b of options().branches; track b.id) {
                <mat-option [value]="b.id">{{ b.name }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Other charges (â‚¹)</mat-label>
            <input
              matInput
              type="number"
              min="0"
              formControlName="otherCharges"
            />
          </mat-form-field>
          <mat-form-field appearance="outline" class="wide">
            <mat-label>Remarks</mat-label>
            <input matInput formControlName="remarks" />
          </mat-form-field>
          <mat-checkbox formControlName="adjustAdvances">
            Set the orders' advances against this invoice
          </mat-checkbox>
          @if (canOverride) {
            <mat-checkbox formControlName="overrideCredit"
              >Override the credit limit if exceeded</mat-checkbox
            >
          }
        </div>
      </section>

      @if (canBillDeliveries) {
        <section class="card">
          <h2>Delivered, not invoiced yet</h2>
          <table class="plain">
            <thead>
              <tr>
                <th></th>
                <th>Delivery</th>
                <th>Item</th>
                <th class="num">To bill</th>
                <th>Qty</th>
                <th>Price</th>
                <th>Disc %</th>
                <th>GST %</th>
                <th class="num">Total</th>
              </tr>
            </thead>
            <tbody>
              @for (b of billed(); track b.source.deliveryNoteLineId) {
                <tr [formGroup]="b.form">
                  <td><mat-checkbox formControlName="selected" /></td>
                  <td>
                    {{ b.source.deliveryNo }}
                    <div class="muted">
                      {{ b.source.deliveryDate | date: 'dd MMM'
                      }}{{
                        b.source.orderNo
                          ? ' Â· ' + b.source.orderNo
                          : ' Â· direct'
                      }}
                    </div>
                  </td>
                  <td>
                    {{ b.source.itemCode }}
                    <div class="muted">{{ b.source.description }}</div>
                  </td>
                  <td class="num">
                    {{ b.source.qtyToInvoice | number: '1.0-3' }}
                    {{ b.source.uomCode ?? '' }}
                  </td>
                  <td>
                    <input
                      class="cell"
                      type="number"
                      min="0"
                      formControlName="quantity"
                      aria-label="Quantity"
                    />
                  </td>
                  <td>
                    <input
                      class="cell"
                      type="number"
                      min="0"
                      formControlName="unitPrice"
                      aria-label="Price"
                    />
                  </td>
                  <td>
                    <input
                      class="cell"
                      type="number"
                      min="0"
                      formControlName="discountPct"
                      aria-label="Discount %"
                    />
                  </td>
                  <td>
                    <input
                      class="cell"
                      type="number"
                      min="0"
                      formControlName="gstPct"
                      aria-label="GST %"
                    />
                  </td>
                  <td class="num">
                    {{
                      b.form.controls.selected.value
                        ? money(billedAmounts(b).total)
                        : ''
                    }}
                  </td>
                </tr>
              } @empty {
                <tr>
                  <td colspan="9" class="empty">
                    {{
                      form.controls.customer.value
                        ? 'Everything delivered to this customer is invoiced.'
                        : 'Choose the customer.'
                    }}
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </section>
      }

      @if (canDirect) {
        <section class="card">
          <h2>Direct lines (no delivery note)</h2>
          <p class="muted">
            Services, freight, or a counter sale. A stock item on a direct line
            leaves stock from the location below, oldest GRN batch first.
          </p>
          @if (direct().length) {
            <mat-form-field appearance="outline" style="max-width: 24rem">
              <mat-label>Take stock from</mat-label>
              <mat-select formControlName="locationId">
                <mat-option [value]="null">â€” (no stock items)</mat-option>
                @for (l of options().locations; track l.id) {
                  <mat-option [value]="l.id"
                    >{{ l.branchName }} Â· {{ l.name }}</mat-option
                  >
                }
              </mat-select>
            </mat-form-field>
          }
          <div class="lines">
            @for (line of direct(); track line; let i = $index) {
              <div class="line" [formGroup]="line">
                <span class="index">{{ i + 1 }}</span>
                <trishul-item-picker
                  formControlName="item"
                  label="Item (optional)"
                  [stockOnly]="false"
                />
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>Description</mat-label>
                  <input matInput formControlName="description" />
                </mat-form-field>
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>Qty</mat-label>
                  <input
                    matInput
                    type="number"
                    min="0"
                    formControlName="quantity"
                  />
                </mat-form-field>
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>Price (â‚¹)</mat-label>
                  <input
                    matInput
                    type="number"
                    min="0"
                    formControlName="unitPrice"
                  />
                </mat-form-field>
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>Disc %</mat-label>
                  <input
                    matInput
                    type="number"
                    min="0"
                    formControlName="discountPct"
                  />
                </mat-form-field>
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>GST %</mat-label>
                  <input
                    matInput
                    type="number"
                    min="0"
                    formControlName="gstPct"
                  />
                </mat-form-field>
                <button
                  mat-icon-button
                  type="button"
                  class="remove"
                  matTooltip="Remove line"
                  (click)="removeDirect(i)"
                >
                  <mat-icon>delete</mat-icon>
                </button>
              </div>
            }
          </div>
          <button mat-button type="button" (click)="addDirect()">
            <mat-icon>add</mat-icon>Add line
          </button>
        </section>
      }

      <div class="form-actions">
        <span class="summary">
          Taxable {{ money(totals().taxable) }} Â· GST
          {{ money(totals().tax) }} Â·
          <strong>Total {{ money(totals().total) }}</strong> (rounded to the
          rupee)
          @if (customerInfo(); as c) {
            Â· balance {{ money(c.balance)
            }}{{ c.creditLimit ? ' of limit ' + money(c.creditLimit) : '' }}
          }
        </span>
        <a mat-button routerLink="/sales/invoices">Cancel</a>
        <button mat-flat-button type="submit" [disabled]="saving()">
          Post invoice
        </button>
      </div>
    </form>
  `,
})
export class SalesInvoiceFormPage {
  private readonly api = inject(ApiClient);
  private readonly router = inject(Router);
  private readonly auth = inject(AuthStore);
  protected readonly canDirect = this.auth.hasPermission(SAL_INVOICE_DIRECT);
  protected readonly canBillDeliveries =
    this.auth.hasPermission(SAL_INVOICE_MANAGE);
  protected readonly canOverride = this.auth.hasPermission(SAL_CREDIT_OVERRIDE);

  /** ?customerId=â€¦&orderId=â€¦&deliveryId=â€¦ from an order, delivery or customer page. */
  readonly customerId = input<string>();
  readonly orderId = input<string>();
  readonly deliveryId = input<string>();

  protected readonly today = new Date();
  protected readonly money = (v: number | string | null | undefined) =>
    rupees(v);
  protected readonly options = toSignal(inject(SalesLookups).options(), {
    initialValue: NO_SALES_OPTIONS,
  });
  protected readonly billed = signal<BilledLine[]>([]);
  protected readonly direct = signal<DirectLine[]>([]);
  protected readonly saving = signal(false);
  protected readonly customerInfo = signal<PickedCustomer | null>(null);
  private readonly changes = signal(0);

  protected readonly form = new FormGroup({
    customer: new FormControl<PickedCustomer | null>(null, Validators.required),
    invoiceDate: new FormControl<Date | null>(new Date(), Validators.required),
    dueDate: new FormControl<Date | null>(null),
    invoiceType: new FormControl<'Tax invoice' | 'Bill of supply' | 'Export'>(
      'Tax invoice',
      { nonNullable: true },
    ),
    principalId: new FormControl<number | null>(null),
    branchId: new FormControl<number | null>(null),
    locationId: new FormControl<number | null>(null),
    otherCharges: new FormControl<number | null>(0, Validators.min(0)),
    remarks: new FormControl<string | null>(null, Validators.maxLength(500)),
    adjustAdvances: new FormControl(true, { nonNullable: true }),
    overrideCredit: new FormControl(false, { nonNullable: true }),
  });

  protected readonly totals = computed(() => {
    this.changes();
    let taxable = 0;
    let tax = 0;
    for (const b of this.billed()) {
      if (!b.form.controls.selected.value) continue;
      const a = this.billedAmounts(b);
      taxable += a.taxable;
      tax += a.tax;
    }
    for (const d of this.direct()) {
      const v = d.getRawValue();
      const a = lineAmounts(v.quantity, v.unitPrice, v.discountPct, v.gstPct);
      taxable += a.taxable;
      tax += a.tax;
    }
    return {
      taxable,
      tax,
      total: Math.round(
        taxable + tax + (this.form.controls.otherCharges.value ?? 0),
      ),
    };
  });

  constructor() {
    this.form.valueChanges.subscribe(() => this.changes.update((n) => n + 1));
    this.form.controls.customer.valueChanges.subscribe((c) => {
      this.customerInfo.set(c);
      this.loadLines(c?.id ?? null);
    });
    effect(() => {
      const customer = Number(this.customerId());
      if (customer)
        untracked(() =>
          this.api
            .call(getCustomerAccount, { customerId: customer })
            .pipe(catchError(() => EMPTY))
            .subscribe((c) => this.form.controls.customer.setValue(c)),
        );
    });
  }

  private loadLines(customerId: number | null): void {
    this.billed.set([]);
    if (!customerId || !this.canBillDeliveries) return;
    const order = Number(this.orderId()) || null;
    const delivery = Number(this.deliveryId()) || null;
    this.api
      .call(listUninvoicedDeliveryLines, { customerId })
      .pipe(catchError(() => of([] as UninvoicedDeliveryLine[])))
      .subscribe((lines) =>
        this.billed.set(
          lines.map((l) => {
            const pick =
              (order === null || l.salesOrderId === order) &&
              (delivery === null || l.deliveryNoteId === delivery);
            const line = billedLine(l, pick);
            line.form.valueChanges.subscribe(() =>
              this.changes.update((n) => n + 1),
            );
            return line;
          }),
        ),
      );
  }

  protected billedAmounts(b: BilledLine) {
    const v = b.form.getRawValue();
    return lineAmounts(v.quantity, v.unitPrice, v.discountPct, v.gstPct);
  }

  protected addDirect(): void {
    const line = directLine();
    line.valueChanges.subscribe(() => this.changes.update((n) => n + 1));
    this.direct.update((lines) => [...lines, line]);
  }

  protected removeDirect(index: number): void {
    this.direct.update((lines) => lines.filter((_, i) => i !== index));
  }

  protected save(): void {
    this.form.markAllAsTouched();
    const chosen = this.billed().filter((b) => b.form.controls.selected.value);
    chosen.forEach((b) => b.form.markAllAsTouched());
    this.direct().forEach((d) => d.markAllAsTouched());
    const directOk = this.direct().every(
      (d) =>
        d.valid &&
        (d.controls.item.value || d.controls.description.value?.trim()),
    );
    if (
      this.form.invalid ||
      chosen.some((b) => b.form.invalid) ||
      !directOk ||
      this.saving()
    )
      return;
    const lines: SalesInvoiceLineIn[] = [
      ...chosen.map((b) => {
        const v = b.form.getRawValue();
        return {
          deliveryNoteLineId: b.source.deliveryNoteLineId,
          quantity: v.quantity as number,
          unitPrice: v.unitPrice as number,
          discountPct: v.discountPct ?? 0,
          gstPct: v.gstPct ?? 0,
        };
      }),
      ...this.direct().map((d) => {
        const v = d.getRawValue();
        return {
          itemId: v.item?.id ?? null,
          description: v.description?.trim() || null,
          quantity: v.quantity as number,
          unitPrice: v.unitPrice as number,
          discountPct: v.discountPct ?? 0,
          gstPct: v.gstPct ?? 0,
        };
      }),
    ];
    if (!lines.length) return;
    const v = this.form.getRawValue();
    this.saving.set(true);
    this.api
      .call(createSalesInvoice, {
        body: {
          customerId: (v.customer as PickedCustomer).id,
          invoiceDate: isoDate(v.invoiceDate as Date),
          dueDate: v.dueDate ? isoDate(v.dueDate) : null,
          invoiceType: v.invoiceType,
          principalId: v.principalId,
          branchId: v.branchId,
          locationId: v.locationId,
          otherCharges: v.otherCharges ?? 0,
          remarks: v.remarks?.trim() || null,
          adjustAdvances: v.adjustAdvances,
          overrideCredit: v.overrideCredit,
          lines,
        },
      })
      .pipe(
        finalize(() => this.saving.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe(
        (invoice) => void this.router.navigate(['/sales/invoices', invoice.id]),
      );
  }
}
