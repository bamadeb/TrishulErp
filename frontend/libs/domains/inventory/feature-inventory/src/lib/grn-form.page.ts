import { DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
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
  RackOut,
  createGrn,
} from '@trishul/core-api';
import { PageHeader, confirmAction } from '@trishul/shared-ui';
import { EMPTY, catchError, filter, finalize, switchMap } from 'rxjs';
import { ItemPicker } from './item-picker';
import { InventoryLookups, isoDate, locationLabel } from './inventory.shared';

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
  });
}

/** Receive goods from a supplier. Each line becomes a stock batch aged from the GRN date. */
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
  styleUrl: './inventory.scss',
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
            <mat-label>Received at</mat-label>
            <mat-select
              formControlName="locationId"
              (valueChange)="locationId.set($event)"
            >
              @for (l of locations(); track l.id) {
                <mat-option [value]="l.id">{{ label(l) }}</mat-option>
              }
            </mat-select>
            <mat-error>Choose where the goods arrived.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Supplier</mat-label>
            <mat-select formControlName="supplierId">
              @for (s of suppliers(); track s.id) {
                <mat-option [value]="s.id"
                  >{{ s.name }} ({{ s.code }})</mat-option
                >
              }
            </mat-select>
            @if (!suppliers().length) {
              <mat-hint
                ><a routerLink="../../suppliers">Add a supplier</a>
                first.</mat-hint
              >
            }
            <mat-error>Choose the supplier.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>GRN date</mat-label>
            <input
              matInput
              [matDatepicker]="grnPicker"
              formControlName="grnDate"
              [max]="today"
            />
            <mat-datepicker-toggle matSuffix [for]="grnPicker" />
            <mat-datepicker #grnPicker />
            <mat-hint>Inventory age starts here</mat-hint>
            <mat-error>A date, not in the future.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Supplier invoice no</mat-label>
            <input matInput formControlName="supplierInvoiceNo" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Supplier invoice date</mat-label>
            <input
              matInput
              [matDatepicker]="invoicePicker"
              formControlName="supplierInvoiceDate"
            />
            <mat-datepicker-toggle matSuffix [for]="invoicePicker" />
            <mat-datepicker #invoicePicker />
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
              </mat-form-field>
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Unit</mat-label>
                <mat-select formControlName="uomId">
                  <mat-option [value]="null">{{
                    line.controls.item.value?.uomCode ?? 'Stock unit'
                  }}</mat-option>
                  @for (u of uoms(); track u.id) {
                    @if (u.id !== line.controls.item.value?.uomId) {
                      <mat-option [value]="u.id">{{ u.code }}</mat-option>
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
        <button mat-button type="button" (click)="addLine()">
          <mat-icon>add</mat-icon>Add line
        </button>
      </section>

      <div class="form-actions">
        <span class="summary"
          >{{ lines().length }} line(s) · value ₹{{
            total() | number: '1.2-2'
          }}</span
        >
        <a mat-button routerLink="..">Cancel</a>
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

  protected readonly today = new Date();
  protected readonly label = locationLabel;
  protected readonly locations = toSignal(this.lookups.locations(), {
    initialValue: [],
  });
  protected readonly suppliers = toSignal(this.lookups.suppliers(), {
    initialValue: [],
  });
  protected readonly uoms = toSignal(this.lookups.uoms(), { initialValue: [] });
  protected readonly locationId = signal<number | null>(null);
  protected readonly racks = signal<RackOut[]>([]);
  protected readonly saving = signal(false);
  /** Bumped when a line value changes, so the total recomputes. */
  private readonly changes = signal(0);

  protected readonly form = new FormGroup({
    locationId: new FormControl<number | null>(null, Validators.required),
    supplierId: new FormControl<number | null>(null, Validators.required),
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
  protected readonly lines = signal([this.watched(grnLine())]);

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
  }

  private watched(
    line: ReturnType<typeof grnLine>,
  ): ReturnType<typeof grnLine> {
    line.valueChanges.subscribe(() => this.changes.update((n) => n + 1));
    return line;
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
      };
    });
    confirmAction(this.dialog, {
      title: 'Post this GRN?',
      message: `${lines.length} line(s) will be added to stock as new batches dated ${isoDate(v.grnDate as Date)}. A posted GRN can't be edited; correct mistakes with an adjustment.`,
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
        (grn) => void this.router.navigate(['/inventory/grns', grn.id]),
      );
  }
}
