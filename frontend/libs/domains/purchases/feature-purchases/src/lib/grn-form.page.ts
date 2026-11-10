import { DecimalPipe } from '@angular/common';
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
import { provideNativeDateAdapter } from '@angular/material/core';
import {
  MatDatepicker,
  MatDatepickerInput,
  MatDatepickerToggle,
} from '@angular/material/datepicker';
import { MatDialog } from '@angular/material/dialog';
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
  GrnLineIn,
  ItemListItem,
  PoDetail,
  PoListItem,
  RackOut,
  createGrn,
  getItem,
  getPurchaseOrder,
  listPurchaseOrders,
} from '@trishul/core-api';
import {
  InventoryLookups,
  ItemPicker,
  isoDate,
  locationLabel,
  num,
} from '@trishul/inventory-data-access';
import { PageHeader, confirmAction } from '@trishul/shared-ui';
import {
  EMPTY,
  catchError,
  filter,
  finalize,
  forkJoin,
  of,
  switchMap,
} from 'rxjs';
import { rupees } from './purchases.shared';

function grnLine() {
  return new FormGroup({
    item: new FormControl<ItemListItem | null>(null, Validators.required),
    quantity: new FormControl<number | null>(null, [
      Validators.required,
      Validators.min(0.001),
    ]),
    uomId: new FormControl<number | null>(null),
    unitCost: new FormControl<number | null>(null, [
      Validators.required,
      Validators.min(0),
    ]),
    rejectedQty: new FormControl<number | null>(null, Validators.min(0)),
    binId: new FormControl<number | null>(null),
    rejectionReason: new FormControl<string | null>(
      null,
      Validators.maxLength(200),
    ),
    purchaseOrderLineId: new FormControl<number | null>(null),
    pending: new FormControl<number | null>(null),
  });
}
type GrnLineForm = ReturnType<typeof grnLine>;

/** Receive goods, direct or against an approved order. Each line becomes a batch aged from the GRN date. */
@Component({
  selector: 'trishul-grn-form-page',
  imports: [
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
      title="Receive goods (GRN)"
      subtitle="Stock is added when you post; its age counts from the GRN date"
    />
    <form [formGroup]="form" (ngSubmit)="post()">
      <section class="card">
        <h2>Receipt</h2>
        <div class="form-grid">
          <mat-form-field appearance="outline">
            <mat-label>Supplier</mat-label>
            <mat-select
              formControlName="supplierId"
              (valueChange)="supplierChanged($event)"
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
            <mat-label>Against purchase order</mat-label>
            <mat-select
              formControlName="purchaseOrderId"
              (valueChange)="orderChosen($event)"
            >
              <mat-option [value]="null">None (direct GRN)</mat-option>
              @for (o of openOrders(); track o.id) {
                <mat-option [value]="o.id"
                  >{{ o.poNo }} · {{ o.qtyPending }} pending</mat-option
                >
              }
            </mat-select>
            <mat-hint
              >{{ openOrders().length }} open order(s) for this
              supplier</mat-hint
            >
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Received at</mat-label>
            <mat-select formControlName="locationId">
              @for (l of locations(); track l.id) {
                <mat-option [value]="l.id">{{ label(l) }}</mat-option>
              }
            </mat-select>
            <mat-error>Choose where the goods arrived.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>GRN date</mat-label>
            <input
              matInput
              [matDatepicker]="grnPicker"
              formControlName="grnDate"
              [max]="today"
            />
            <mat-datepicker-toggle matSuffix [for]="grnPicker" /><mat-datepicker
              #grnPicker
            />
            <mat-hint>Inventory age starts here</mat-hint>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Supplier invoice / challan no</mat-label>
            <input matInput formControlName="supplierInvoiceNo" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Its date</mat-label>
            <input
              matInput
              [matDatepicker]="invoicePicker"
              formControlName="supplierInvoiceDate"
            />
            <mat-datepicker-toggle
              matSuffix
              [for]="invoicePicker"
            /><mat-datepicker #invoicePicker />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Vehicle no</mat-label>
            <input matInput formControlName="vehicleNo" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>LR no</mat-label>
            <input matInput formControlName="lrNo" />
          </mat-form-field>
          <mat-form-field appearance="outline" class="wide">
            <mat-label>Remarks</mat-label>
            <input matInput formControlName="remarks" />
          </mat-form-field>
        </div>
      </section>

      <section class="card">
        <h2>Items received</h2>
        <div class="lines">
          @for (line of lines(); track line; let i = $index) {
            <div class="line" [formGroup]="line">
              <span class="index">{{ i + 1 }}</span>
              <trishul-item-picker formControlName="item" />
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Accepted qty</mat-label>
                <input
                  matInput
                  type="number"
                  min="0"
                  formControlName="quantity"
                />
                @if (line.controls.pending.value !== null) {
                  <mat-hint
                    >{{
                      line.controls.pending.value | number: '1.0-3'
                    }}
                    pending</mat-hint
                  >
                }
              </mat-form-field>
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Unit</mat-label>
                <mat-select formControlName="uomId">
                  <mat-option [value]="null">{{
                    line.controls.item.value?.uomCode ?? 'Stock unit'
                  }}</mat-option>
                  @if (line.controls.purchaseOrderLineId.value === null) {
                    @for (u of uoms(); track u.id) {
                      @if (u.id !== line.controls.item.value?.uomId) {
                        <mat-option [value]="u.id">{{ u.code }}</mat-option>
                      }
                    }
                  }
                </mat-select>
              </mat-form-field>
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Cost / unit (₹)</mat-label>
                <input
                  matInput
                  type="number"
                  min="0"
                  step="0.01"
                  formControlName="unitCost"
                />
              </mat-form-field>
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Rack</mat-label>
                <mat-select formControlName="binId">
                  <mat-option [value]="null">No rack</mat-option>
                  @for (r of racks(); track r.id) {
                    <mat-option [value]="r.id">{{ r.code }}</mat-option>
                  }
                </mat-select>
              </mat-form-field>
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Rejected qty</mat-label>
                <input
                  matInput
                  type="number"
                  min="0"
                  formControlName="rejectedQty"
                />
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
              @if ((line.controls.rejectedQty.value ?? 0) > 0) {
                <mat-form-field
                  appearance="outline"
                  class="line-note"
                  subscriptSizing="dynamic"
                >
                  <mat-label>Why rejected</mat-label>
                  <input matInput formControlName="rejectionReason" />
                </mat-form-field>
              }
            </div>
          }
        </div>
        @if (!form.controls.purchaseOrderId.value) {
          <button mat-button type="button" (click)="addLine()">
            <mat-icon>add</mat-icon>Add line
          </button>
        }
      </section>

      <div class="form-actions">
        <span class="summary"
          >{{ lines().length }} line(s) · value {{ money(total()) }}</span
        >
        <a mat-button routerLink="/purchases/grns">Cancel</a>
        <button mat-flat-button type="submit" [disabled]="saving()">
          Post GRN
        </button>
      </div>
    </form>
  `,
})
export class GrnFormPage {
  private readonly api = inject(ApiClient);
  private readonly router = inject(Router);
  private readonly dialog = inject(MatDialog);
  private readonly lookups = inject(InventoryLookups);

  /** ?poId=… opens the form against that order. */
  readonly poId = input<string>();

  protected readonly today = new Date();
  protected readonly label = locationLabel;
  protected readonly money = (v: number) => rupees(v);
  protected readonly locations = toSignal(this.lookups.locations(), {
    initialValue: [],
  });
  protected readonly suppliers = toSignal(this.lookups.suppliers(), {
    initialValue: [],
  });
  protected readonly uoms = toSignal(this.lookups.uoms(), { initialValue: [] });
  protected readonly racks = signal<RackOut[]>([]);
  protected readonly openOrders = signal<PoListItem[]>([]);
  protected readonly saving = signal(false);
  private readonly changes = signal(0);

  protected readonly form = new FormGroup({
    supplierId: new FormControl<number | null>(null, Validators.required),
    purchaseOrderId: new FormControl<number | null>(null),
    locationId: new FormControl<number | null>(null, Validators.required),
    grnDate: new FormControl<Date | null>(new Date(), Validators.required),
    supplierInvoiceNo: new FormControl<string | null>(
      null,
      Validators.maxLength(40),
    ),
    supplierInvoiceDate: new FormControl<Date | null>(null),
    vehicleNo: new FormControl<string | null>(null, Validators.maxLength(20)),
    lrNo: new FormControl<string | null>(null, Validators.maxLength(40)),
    remarks: new FormControl<string | null>(null, Validators.maxLength(300)),
  });
  protected readonly lines = signal<GrnLineForm[]>([this.watched(grnLine())]);
  protected readonly total = computed(() => {
    this.changes();
    return this.lines().reduce(
      (sum, l) =>
        sum +
        (l.controls.quantity.value ?? 0) * (l.controls.unitCost.value ?? 0),
      0,
    );
  });

  constructor() {
    this.form.controls.locationId.valueChanges.subscribe((id) => {
      this.racks.set([]);
      this.lookups.racks(id).subscribe((racks) => this.racks.set(racks));
      for (const line of this.lines()) line.controls.binId.setValue(null);
    });
    queueMicrotask(() => {
      const id = Number(this.poId());
      if (id) {
        this.api
          .call(getPurchaseOrder, { poId: id })
          .pipe(catchError(() => EMPTY))
          .subscribe((po) => {
            this.form.controls.supplierId.setValue(po.supplierId);
            this.loadOpenOrders(po.supplierId);
            this.form.controls.purchaseOrderId.setValue(po.id);
            this.fillFromOrder(po);
          });
      }
    });
  }

  private watched(line: GrnLineForm): GrnLineForm {
    line.valueChanges.subscribe(() => this.changes.update((n) => n + 1));
    return line;
  }

  protected supplierChanged(supplierId: number): void {
    this.form.controls.purchaseOrderId.setValue(null);
    this.lines.set([this.watched(grnLine())]);
    this.loadOpenOrders(supplierId);
  }

  private loadOpenOrders(supplierId: number): void {
    this.api
      .call(listPurchaseOrders, {
        supplierId,
        outstandingOnly: true,
        pageSize: 100,
      })
      .pipe(catchError(() => of({ items: [] as PoListItem[] })))
      .subscribe((page) => this.openOrders.set(page.items));
  }

  protected orderChosen(poId: number | null): void {
    if (!poId) {
      this.lines.set([this.watched(grnLine())]);
      return;
    }
    this.api
      .call(getPurchaseOrder, { poId })
      .pipe(catchError(() => EMPTY))
      .subscribe((po) => this.fillFromOrder(po));
  }

  /** One line per order line still pending, at the order's net price. */
  private fillFromOrder(po: PoDetail): void {
    this.form.controls.locationId.setValue(po.deliveryLocationId);
    const pending = po.lines.filter((l) => (num(l.qtyPending) ?? 0) > 0);
    if (!pending.length) {
      this.lines.set([]);
      return;
    }
    forkJoin(
      pending.map((l) => this.api.call(getItem, { itemId: l.itemId })),
    ).subscribe((items) => {
      this.lines.set(
        pending.map((l, i) => {
          const line = this.watched(grnLine());
          line.patchValue({
            item: items[i] as unknown as ItemListItem,
            quantity: num(l.qtyPending),
            unitCost: num(l.netPrice),
            purchaseOrderLineId: l.id,
            pending: num(l.qtyPending),
          });
          line.controls.item.disable();
          line.controls.quantity.addValidators(
            Validators.max(num(l.qtyPending) ?? 0),
          );
          return line;
        }),
      );
    });
  }

  protected addLine(): void {
    this.lines.update((lines) => [...lines, this.watched(grnLine())]);
  }

  protected removeLine(index: number): void {
    this.lines.update((lines) => lines.filter((_, i) => i !== index));
  }

  protected post(): void {
    this.form.markAllAsTouched();
    for (const line of this.lines()) line.markAllAsTouched();
    if (
      this.form.invalid ||
      !this.lines().length ||
      this.lines().some((l) => l.invalid) ||
      this.saving()
    )
      return;
    const v = this.form.getRawValue();
    const lines: GrnLineIn[] = this.lines().map((l) => {
      const x = l.getRawValue();
      return {
        itemId: (x.item as ItemListItem).id,
        quantity: x.quantity as number,
        uomId: x.uomId,
        unitCost: x.unitCost as number,
        rejectedQty: x.rejectedQty ?? 0,
        binId: x.binId,
        rejectionReason: x.rejectionReason?.trim() || null,
        purchaseOrderLineId: x.purchaseOrderLineId,
      };
    });
    confirmAction(this.dialog, {
      title: 'Post this GRN?',
      message: `${lines.length} line(s) will be added to stock as new batches dated ${isoDate(v.grnDate as Date)}. A posted GRN can't be edited.`,
      confirmText: 'Post GRN',
    })
      .pipe(
        filter(Boolean),
        switchMap(() => {
          this.saving.set(true);
          return this.api
            .call(createGrn, {
              body: {
                locationId: v.locationId as number,
                supplierId: v.supplierId as number,
                purchaseOrderId: v.purchaseOrderId,
                grnDate: isoDate(v.grnDate as Date),
                supplierInvoiceNo: v.supplierInvoiceNo?.trim() || null,
                supplierInvoiceDate: v.supplierInvoiceDate
                  ? isoDate(v.supplierInvoiceDate)
                  : null,
                vehicleNo: v.vehicleNo?.trim() || null,
                lrNo: v.lrNo?.trim() || null,
                remarks: v.remarks?.trim() || null,
                lines,
              },
            })
            .pipe(
              finalize(() => this.saving.set(false)),
              catchError(() => EMPTY),
            );
        }),
      )
      .subscribe(
        (grn) => void this.router.navigate(['/purchases/grns', grn.id]),
      );
  }
}
