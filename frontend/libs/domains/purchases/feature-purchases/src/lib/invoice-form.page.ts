import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  signal,
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
  MatError,
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
  InvoiceLineIn,
  ItemListItem,
  UninvoicedLine,
  createSupplierInvoice,
  listUninvoicedGrnLines,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import {
  InventoryLookups,
  ItemPicker,
  isoDate,
  num,
} from '@trishul/inventory-data-access';
import { PUR_INVOICE_DIRECT } from '@trishul/purchases-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { EMPTY, catchError, finalize, of } from 'rxjs';
import { lineAmounts, rupees } from './purchases.shared';

function billedLine(line: UninvoicedLine, selected: boolean) {
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
      Validators.maxLength(200),
    ),
    quantity: new FormControl<number | null>(1, [
      Validators.required,
      Validators.min(0.001),
    ]),
    unitPrice: new FormControl<number | null>(null, [
      Validators.required,
      Validators.min(0),
    ]),
    gstPct: new FormControl<number | null>(18, [
      Validators.required,
      Validators.min(0),
      Validators.max(100),
    ]),
  });
}
type DirectLine = ReturnType<typeof directLine>;

/** Record a supplier invoice: bill goods received (GRN lines), or direct lines with permission. Never adds stock. */
@Component({
  selector: 'trishul-invoice-form-page',
  imports: [
    DatePipe,
    DecimalPipe,
    ReactiveFormsModule,
    RouterLink,
    MatFormField,
    MatLabel,
    MatHint,
    MatError,
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
    ItemPicker,
    PageHeader,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  template: `
    <trishul-page-header
      title="Record supplier invoice"
      subtitle="Bill the goods received; the invoice does not add stock again"
    />
    <form [formGroup]="form" (ngSubmit)="save()">
      <section class="card">
        <h2>Invoice</h2>
        <div class="form-grid">
          <mat-form-field appearance="outline">
            <mat-label>Supplier</mat-label>
            <mat-select
              formControlName="supplierId"
              (valueChange)="loadLines($event, null)"
            >
              @for (s of suppliers(); track s.id) {
                <mat-option [value]="s.id"
                  >{{ s.name }} ({{ s.code }})</mat-option
                >
              }
            </mat-select>
            <mat-error>Choose the supplier.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Supplier's invoice no</mat-label>
            <input matInput formControlName="supplierInvoiceNo" />
            <mat-hint>Each number can be recorded once per supplier</mat-hint>
            <mat-error>Required.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Invoice date</mat-label>
            <input
              matInput
              [matDatepicker]="datePicker"
              formControlName="supplierInvoiceDate"
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
            <mat-hint>Blank: from the supplier's payment terms</mat-hint>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Branch</mat-label>
            <mat-select formControlName="branchId">
              <mat-option [value]="null">The GRN's branch</mat-option>
              @for (b of branches(); track b.id) {
                <mat-option [value]="b.id">{{ b.name }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Other charges (₹)</mat-label>
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
        </div>
      </section>

      <section class="card">
        <h2>Goods received, not invoiced yet</h2>
        <table class="plain">
          <thead>
            <tr>
              <th></th>
              <th>GRN</th>
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
            @for (b of billed(); track b.source.grnLineId) {
              <tr [formGroup]="b.form">
                <td><mat-checkbox formControlName="selected" /></td>
                <td>
                  {{ b.source.grnNo }}
                  <div class="muted">
                    {{ b.source.grnDate | date: 'dd MMM'
                    }}{{ b.source.poNo ? ' · ' + b.source.poNo : '' }}
                  </div>
                </td>
                <td>
                  {{ b.source.itemCode }}
                  <div class="muted">{{ b.source.itemDescription }}</div>
                </td>
                <td class="num">
                  {{ b.source.qtyToInvoice | number: '1.0-3' }}
                  {{ b.source.uomCode }}
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
                    form.controls.supplierId.value
                      ? 'Everything received from this supplier is invoiced.'
                      : 'Choose the supplier.'
                  }}
                </td>
              </tr>
            }
          </tbody>
        </table>
      </section>

      @if (canDirect) {
        <section class="card">
          <h2>Lines without a GRN</h2>
          <p class="muted">
            Services, freight, or items not received through a GRN. These don't
            change stock.
          </p>
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
                  <mat-label>Price (₹)</mat-label>
                  <input
                    matInput
                    type="number"
                    min="0"
                    formControlName="unitPrice"
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
        <span class="summary"
          >Taxable {{ money(totals().taxable) }} · GST
          {{ money(totals().tax) }} ·
          <strong>Total {{ money(totals().total) }}</strong> (rounded to the
          rupee)</span
        >
        <a mat-button routerLink="/purchases/invoices">Cancel</a>
        <button mat-flat-button type="submit" [disabled]="saving()">
          Record invoice
        </button>
      </div>
    </form>
  `,
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
})
export class InvoiceFormPage {
  private readonly api = inject(ApiClient);
  private readonly router = inject(Router);
  private readonly lookups = inject(InventoryLookups);
  protected readonly canDirect =
    inject(AuthStore).hasPermission(PUR_INVOICE_DIRECT);

  /** ?supplierId=…&grnId=… from a supplier, order or GRN page. */
  readonly supplierId = input<string>();
  readonly grnId = input<string>();

  protected readonly today = new Date();
  protected readonly money = (v: number | string) => rupees(v);
  protected readonly suppliers = toSignal(this.lookups.suppliers(), {
    initialValue: [],
  });
  protected readonly branches = toSignal(this.lookups.branches(), {
    initialValue: [],
  });
  protected readonly billed = signal<BilledLine[]>([]);
  protected readonly direct = signal<DirectLine[]>([]);
  protected readonly saving = signal(false);
  private readonly changes = signal(0);

  protected readonly form = new FormGroup({
    supplierId: new FormControl<number | null>(null, Validators.required),
    supplierInvoiceNo: new FormControl<string | null>(null, [
      Validators.required,
      Validators.maxLength(40),
    ]),
    supplierInvoiceDate: new FormControl<Date | null>(
      new Date(),
      Validators.required,
    ),
    dueDate: new FormControl<Date | null>(null),
    branchId: new FormControl<number | null>(null),
    otherCharges: new FormControl<number | null>(0, Validators.min(0)),
    remarks: new FormControl<string | null>(null, Validators.maxLength(300)),
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
      const a = lineAmounts(v.quantity, v.unitPrice, 0, v.gstPct);
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
    queueMicrotask(() => {
      const supplier = Number(this.supplierId());
      if (supplier) {
        this.form.controls.supplierId.setValue(supplier);
        this.loadLines(supplier, Number(this.grnId()) || null);
      }
    });
  }

  protected loadLines(supplierId: number, grnId: number | null): void {
    this.billed.set([]);
    this.api
      .call(listUninvoicedGrnLines, { supplierId })
      .pipe(catchError(() => of([] as UninvoicedLine[])))
      .subscribe((lines) => {
        this.billed.set(
          lines.map((l) => {
            const line = billedLine(l, grnId === null || l.grnId === grnId);
            line.form.valueChanges.subscribe(() =>
              this.changes.update((n) => n + 1),
            );
            return line;
          }),
        );
      });
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
    for (const b of chosen) b.form.markAllAsTouched();
    for (const d of this.direct()) d.markAllAsTouched();
    const directOk = this.direct().every(
      (d) => d.valid && (d.controls.item.value || d.controls.description.value),
    );
    if (
      this.form.invalid ||
      chosen.some((b) => b.form.invalid) ||
      !directOk ||
      this.saving()
    )
      return;
    const lines: InvoiceLineIn[] = [
      ...chosen.map((b) => {
        const v = b.form.getRawValue();
        return {
          grnLineId: b.source.grnLineId,
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
          gstPct: v.gstPct ?? 0,
        };
      }),
    ];
    if (!lines.length) return;
    const v = this.form.getRawValue();
    this.saving.set(true);
    this.api
      .call(createSupplierInvoice, {
        body: {
          supplierId: v.supplierId as number,
          supplierInvoiceNo: (v.supplierInvoiceNo as string).trim(),
          supplierInvoiceDate: isoDate(v.supplierInvoiceDate as Date),
          dueDate: v.dueDate ? isoDate(v.dueDate) : null,
          branchId: v.branchId,
          otherCharges: v.otherCharges ?? 0,
          remarks: v.remarks?.trim() || null,
          lines,
        },
      })
      .pipe(
        finalize(() => this.saving.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe(
        (invoice) =>
          void this.router.navigate(['/purchases/invoices', invoice.id]),
      );
  }
}
