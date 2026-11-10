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
  ItemListItem,
  PoCreate,
  PoDetail,
  createPurchaseOrder,
  getItem,
  getPurchaseOrder,
  getSupplierFormOptions,
  updatePurchaseOrder,
  withRowVersion,
} from '@trishul/core-api';
import {
  InventoryLookups,
  ItemPicker,
  fromIso,
  isoDate,
  locationLabel,
  num,
} from '@trishul/inventory-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { EMPTY, catchError, finalize, forkJoin, of } from 'rxjs';
import { lineAmounts, rupees } from './purchases.shared';

function poLine() {
  return new FormGroup({
    item: new FormControl<ItemListItem | null>(null, Validators.required),
    quantity: new FormControl<number | null>(null, [
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
type PoLineForm = ReturnType<typeof poLine>;

/** New purchase order, or change a draft (/purchases/orders/:poId/edit). Saved as a draft. */
@Component({
  selector: 'trishul-po-form-page',
  imports: [
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
      [title]="existing() ? 'Edit ' + existing()!.poNo : 'New purchase order'"
      subtitle="Saved as a draft; send it for approval from the order page"
    />
    <form [formGroup]="form" (ngSubmit)="save()">
      <section class="card">
        <h2>Order</h2>
        <div class="form-grid">
          <mat-form-field appearance="outline">
            <mat-label>Supplier</mat-label>
            <mat-select
              formControlName="supplierId"
              (valueChange)="supplierChanged()"
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
            <mat-label>Deliver to</mat-label>
            <mat-select formControlName="deliveryLocationId">
              @for (l of locations(); track l.id) {
                <mat-option [value]="l.id">{{ label(l) }}</mat-option>
              }
            </mat-select>
            <mat-hint>The order belongs to this location's branch</mat-hint>
            <mat-error>Choose where the goods go.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Order date</mat-label>
            <input
              matInput
              [matDatepicker]="poPicker"
              formControlName="poDate"
            />
            <mat-datepicker-toggle matSuffix [for]="poPicker" /><mat-datepicker
              #poPicker
            />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Expected by</mat-label>
            <input
              matInput
              [matDatepicker]="expPicker"
              formControlName="expectedDate"
            />
            <mat-datepicker-toggle matSuffix [for]="expPicker" /><mat-datepicker
              #expPicker
            />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Payment terms</mat-label>
            <mat-select formControlName="paymentTermsId">
              <mat-option [value]="null">Supplier's terms</mat-option>
              @for (t of terms().paymentTerms; track t.id) {
                <mat-option [value]="t.id">{{ t.name }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Type</mat-label>
            <mat-select formControlName="poType">
              <mat-option value="Local">Local</mat-option>
              <mat-option value="OEM">OEM</mat-option>
              <mat-option value="Import">Import</mat-option>
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>OEM PO ref</mat-label>
            <input matInput formControlName="oemPoRef" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Other charges (₹)</mat-label>
            <input
              matInput
              type="number"
              min="0"
              formControlName="otherCharges"
            />
            <mat-hint>Freight, packing, insurance</mat-hint>
          </mat-form-field>
          <mat-form-field appearance="outline" class="wide">
            <mat-label>Remarks</mat-label>
            <textarea matInput rows="2" formControlName="remarks"></textarea>
          </mat-form-field>
        </div>
      </section>

      <section class="card">
        <h2>Items</h2>
        <div class="lines">
          @for (line of lines(); track line; let i = $index) {
            <div class="line" [formGroup]="line">
              <span class="index">{{ i + 1 }}</span>
              <trishul-item-picker
                formControlName="item"
                (focusout)="defaultPrice(line)"
              />
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label
                  >Qty{{
                    line.controls.item.value
                      ? ' (' + line.controls.item.value.uomCode + ')'
                      : ''
                  }}</mat-label
                >
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
                <mat-label>Disc %</mat-label>
                <input
                  matInput
                  type="number"
                  min="0"
                  max="100"
                  formControlName="discountPct"
                />
              </mat-form-field>
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>GST %</mat-label>
                <input
                  matInput
                  type="number"
                  min="0"
                  max="100"
                  formControlName="gstPct"
                />
                <mat-hint>{{ money(amounts(line).total) }}</mat-hint>
              </mat-form-field>
              <button
                mat-icon-button
                type="button"
                class="remove"
                matTooltip="Remove line"
                [disabled]="lines().length === 1"
                (click)="removeLine(i)"
              >
                <mat-icon>delete</mat-icon>
              </button>
            </div>
          }
        </div>
        <button mat-button type="button" (click)="addLine()">
          <mat-icon>add</mat-icon>Add line
        </button>
      </section>

      <div class="form-actions">
        <span class="summary">
          Taxable {{ money(totals().taxable) }} · GST
          {{ money(totals().tax) }} · Other {{ money(totals().other) }} ·
          <strong>Total {{ money(totals().total) }}</strong>
        </span>
        <a
          mat-button
          [routerLink]="
            existing()
              ? ['/purchases/orders', existing()!.id]
              : ['/purchases/orders']
          "
          >Cancel</a
        >
        <button mat-flat-button type="submit" [disabled]="saving()">
          Save draft
        </button>
      </div>
    </form>
  `,
})
export class PoFormPage {
  private readonly api = inject(ApiClient);
  private readonly router = inject(Router);
  private readonly lookups = inject(InventoryLookups);

  readonly poId = input<string>();

  protected readonly label = locationLabel;
  protected readonly money = (v: number) => rupees(v);
  protected readonly suppliers = toSignal(this.lookups.suppliers(), {
    initialValue: [],
  });
  protected readonly locations = toSignal(this.lookups.locations(), {
    initialValue: [],
  });
  protected readonly terms = toSignal(
    this.api
      .call(getSupplierFormOptions)
      .pipe(catchError(() => of({ states: [], paymentTerms: [] }))),
    { initialValue: { states: [], paymentTerms: [] } },
  );
  protected readonly existing = signal<PoDetail | null>(null);
  protected readonly saving = signal(false);
  private readonly changes = signal(0);

  protected readonly form = new FormGroup({
    supplierId: new FormControl<number | null>(null, Validators.required),
    deliveryLocationId: new FormControl<number | null>(
      null,
      Validators.required,
    ),
    poDate: new FormControl<Date | null>(new Date()),
    expectedDate: new FormControl<Date | null>(null),
    paymentTermsId: new FormControl<number | null>(null),
    poType: new FormControl<'Local' | 'OEM' | 'Import'>('Local', {
      nonNullable: true,
    }),
    oemPoRef: new FormControl<string | null>(null, Validators.maxLength(40)),
    otherCharges: new FormControl<number | null>(0, Validators.min(0)),
    remarks: new FormControl<string | null>(null, Validators.maxLength(500)),
  });
  protected readonly lines = signal<PoLineForm[]>([this.watched(poLine())]);

  protected readonly totals = computed(() => {
    this.changes();
    let taxable = 0;
    let tax = 0;
    for (const line of this.lines()) {
      const a = this.amounts(line);
      taxable += a.taxable;
      tax += a.tax;
    }
    const other = this.form.controls.otherCharges.value ?? 0;
    return { taxable, tax, other, total: taxable + tax + other };
  });

  constructor() {
    this.form.valueChanges.subscribe(() => this.changes.update((n) => n + 1));
    effect(() => {
      const id = Number(this.poId());
      if (id) untracked(() => this.load(id));
    });
  }

  private load(id: number): void {
    this.api
      .call(getPurchaseOrder, { poId: id })
      .pipe(catchError(() => EMPTY))
      .subscribe((po) => {
        this.existing.set(po);
        this.form.patchValue({
          supplierId: po.supplierId,
          deliveryLocationId: po.deliveryLocationId,
          poDate: fromIso(po.poDate),
          expectedDate: fromIso(po.expectedDate),
          paymentTermsId: po.paymentTermsId,
          poType: po.poType,
          oemPoRef: po.oemPoRef,
          otherCharges: num(po.otherCharges),
          remarks: po.remarks,
        });
        // The picker needs the item as listed; fetch each item once.
        forkJoin(
          po.lines.map((l) => this.api.call(getItem, { itemId: l.itemId })),
        ).subscribe((items) => {
          this.lines.set(
            po.lines.map((l, i) => {
              const line = this.watched(poLine());
              line.patchValue({
                item: items[i] as unknown as ItemListItem,
                quantity: num(l.quantity),
                unitPrice: num(l.unitPrice),
                discountPct: num(l.discountPct),
                gstPct: num(l.gstPct),
              });
              return line;
            }),
          );
        });
      });
  }

  private watched(line: PoLineForm): PoLineForm {
    line.valueChanges.subscribe(() => this.changes.update((n) => n + 1));
    return line;
  }

  protected amounts(line: PoLineForm) {
    const v = line.getRawValue();
    return lineAmounts(v.quantity, v.unitPrice, v.discountPct, v.gstPct);
  }

  protected supplierChanged(): void {
    this.form.controls.paymentTermsId.setValue(null);
  }

  /** A picked item starts at its standard cost. */
  protected defaultPrice(line: PoLineForm): void {
    const item = line.controls.item.value;
    if (
      item &&
      line.controls.unitPrice.value === null &&
      item.standardCost !== null
    ) {
      line.controls.unitPrice.setValue(num(item.standardCost));
    }
  }

  protected addLine(): void {
    this.lines.update((lines) => [...lines, this.watched(poLine())]);
  }

  protected removeLine(index: number): void {
    this.lines.update((lines) => lines.filter((_, i) => i !== index));
  }

  protected save(): void {
    this.form.markAllAsTouched();
    for (const line of this.lines()) line.markAllAsTouched();
    if (
      this.form.invalid ||
      this.lines().some((l) => l.invalid) ||
      this.saving()
    )
      return;
    const v = this.form.getRawValue();
    const body: PoCreate = {
      supplierId: v.supplierId as number,
      deliveryLocationId: v.deliveryLocationId as number,
      poDate: v.poDate ? isoDate(v.poDate) : null,
      expectedDate: v.expectedDate ? isoDate(v.expectedDate) : null,
      paymentTermsId: v.paymentTermsId,
      poType: v.poType,
      oemPoRef: v.oemPoRef?.trim() || null,
      otherCharges: v.otherCharges ?? 0,
      remarks: v.remarks?.trim() || null,
      lines: this.lines().map((l) => {
        const x = l.getRawValue();
        return {
          itemId: (x.item as ItemListItem).id,
          quantity: x.quantity as number,
          unitPrice: x.unitPrice as number,
          discountPct: x.discountPct ?? 0,
          gstPct: x.gstPct ?? 0,
        };
      }),
    };
    const existing = this.existing();
    this.saving.set(true);
    const request = existing
      ? this.api.call(
          updatePurchaseOrder,
          { poId: existing.id, body },
          withRowVersion(existing.rowVersion),
        )
      : this.api.call(createPurchaseOrder, { body });
    request
      .pipe(
        finalize(() => this.saving.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe(
        (po) => void this.router.navigate(['/purchases/orders', po.id]),
      );
  }
}
