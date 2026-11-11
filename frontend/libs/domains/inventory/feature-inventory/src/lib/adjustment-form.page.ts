import { DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
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
  AdjustmentLineIn,
  ApiClient,
  ItemListItem,
  RackOut,
  createAdjustment,
  listAdjustmentReasons,
} from '@trishul/core-api';
import { PageHeader, confirmAction } from '@trishul/shared-ui';
import { EMPTY, catchError, filter, finalize, of, switchMap } from 'rxjs';
import { ItemPicker } from '@trishul/inventory-data-access';
import {
  InventoryLookups,
  isoDate,
  locationLabel,
} from '@trishul/inventory-data-access';
import { StockLine, batchLabel } from './stock-line';

/** Increase or decrease stock with a reason. Posted under the signed-in user's name. */
@Component({
  selector: 'trishul-adjustment-form-page',
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
  styleUrl: '../../../data-access/src/lib/inventory.scss',
  template: `
    <trishul-page-header
      title="New stock adjustment"
      subtitle="Removing takes the oldest GRN batch first unless you pick one"
    />
    <form [formGroup]="form" (ngSubmit)="post()">
      <section class="card">
        <h2>Adjustment</h2>
        <div class="form-grid">
          <mat-form-field appearance="outline">
            <mat-label>Location</mat-label>
            <mat-select formControlName="locationId">
              @for (l of locations(); track l.id) {
                <mat-option [value]="l.id">{{ label(l) }}</mat-option>
              }
            </mat-select>
            <mat-error>Choose the location.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Reason</mat-label>
            <mat-select formControlName="reasonId">
              @for (r of reasons(); track r.id) {
                <mat-option [value]="r.id">{{ r.label }}</mat-option>
              }
            </mat-select>
            <mat-error>Choose a reason.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Date</mat-label>
            <input
              matInput
              [matDatepicker]="picker"
              formControlName="adjustmentDate"
              [max]="today"
            />
            <mat-datepicker-toggle matSuffix [for]="picker" />
            <mat-datepicker #picker />
            <mat-hint
              >Stock added as a new batch is aged from this date</mat-hint
            >
          </mat-form-field>
          <mat-form-field appearance="outline" class="wide">
            <mat-label>Remarks</mat-label>
            <input matInput formControlName="remarks" />
          </mat-form-field>
        </div>
      </section>

      <section class="card">
        <h2>Items</h2>
        <div class="lines">
          @for (line of lines(); track line; let i = $index) {
            <div class="line" [formGroup]="line.form">
              <span class="index">{{ i + 1 }}</span>
              <trishul-item-picker formControlName="item" />
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Change</mat-label>
                <mat-select formControlName="direction">
                  <mat-option value="remove">Remove</mat-option>
                  <mat-option value="add">Add</mat-option>
                </mat-select>
              </mat-form-field>
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Quantity</mat-label>
                <input
                  matInput
                  type="number"
                  min="0"
                  formControlName="quantity"
                />
                @if (line.form.controls.item.value) {
                  <mat-hint
                    >{{ line.available() | number: '1.0-3' }} in stock
                    here</mat-hint
                  >
                }
              </mat-form-field>
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Rack</mat-label>
                <mat-select formControlName="fromBinId">
                  <mat-option [value]="null">{{
                    line.form.controls.direction.value === 'remove'
                      ? 'Any rack'
                      : 'No rack'
                  }}</mat-option>
                  @for (r of racks(); track r.id) {
                    <mat-option [value]="r.id">{{ r.code }}</mat-option>
                  }
                </mat-select>
              </mat-form-field>
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>GRN batch</mat-label>
                <mat-select formControlName="stockLotId">
                  <mat-option [value]="null">
                    {{
                      line.form.controls.direction.value === 'remove'
                        ? 'Oldest first'
                        : 'New batch (dated today)'
                    }}
                  </mat-option>
                  @for (b of line.batchesHere(); track b.lotBalanceId) {
                    <mat-option [value]="b.stockLotId">{{
                      batch(b)
                    }}</mat-option>
                  }
                </mat-select>
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
              @if (
                line.form.controls.direction.value === 'add' &&
                !line.form.controls.stockLotId.value
              ) {
                <mat-form-field
                  appearance="outline"
                  class="line-note"
                  subscriptSizing="dynamic"
                >
                  <mat-label>Cost / unit for the new batch (₹)</mat-label>
                  <input
                    matInput
                    type="number"
                    min="0"
                    formControlName="unitCost"
                  />
                  <mat-hint>Blank: the item's standard cost</mat-hint>
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
        <span class="summary">{{ lines().length }} line(s)</span>
        <a mat-button routerLink="..">Cancel</a>
        <button mat-flat-button type="submit" [disabled]="saving()">
          Post adjustment
        </button>
      </div>
    </form>
  `,
})
export class AdjustmentFormPage {
  private readonly api = inject(ApiClient);
  private readonly router = inject(Router);
  private readonly dialog = inject(MatDialog);
  private readonly lookups = inject(InventoryLookups);

  protected readonly today = new Date();
  protected readonly label = locationLabel;
  protected readonly batch = batchLabel;
  protected readonly locations = toSignal(this.lookups.locations(), {
    initialValue: [],
  });
  protected readonly reasons = toSignal(
    this.api.call(listAdjustmentReasons).pipe(catchError(() => of([]))),
    {
      initialValue: [],
    },
  );
  protected readonly racks = signal<RackOut[]>([]);
  protected readonly saving = signal(false);

  protected readonly form = new FormGroup({
    locationId: new FormControl<number | null>(null, Validators.required),
    reasonId: new FormControl<number | null>(null, Validators.required),
    adjustmentDate: new FormControl<Date | null>(
      new Date(),
      Validators.required,
    ),
    remarks: new FormControl<string | null>(null, Validators.maxLength(300)),
  });
  protected readonly lines = signal([this.newLine()]);

  constructor() {
    this.form.controls.locationId.valueChanges.subscribe((id) => {
      this.lookups.racks(id).subscribe((racks) => this.racks.set(racks));
      for (const line of this.lines()) {
        line.form.controls.fromBinId.setValue(null);
        line.loadBatches(this.api, id);
      }
    });
  }

  private newLine(): StockLine {
    const line = new StockLine();
    line.form.controls.quantity.addValidators(Validators.min(0.001));
    line.form.controls.item.valueChanges.subscribe(() =>
      line.loadBatches(this.api, this.form.controls.locationId.value),
    );
    return line;
  }

  protected addLine(): void {
    this.lines.update((lines) => [...lines, this.newLine()]);
  }

  protected removeLine(index: number): void {
    this.lines.update((lines) => lines.filter((_, i) => i !== index));
  }

  protected post(): void {
    this.form.markAllAsTouched();
    for (const line of this.lines()) line.form.markAllAsTouched();
    if (
      this.form.invalid ||
      this.lines().some((l) => l.form.invalid) ||
      this.saving()
    )
      return;
    const v = this.form.getRawValue();
    const lines: AdjustmentLineIn[] = this.lines().map((l) => {
      const x = l.form.getRawValue();
      const quantity = x.quantity as number;
      return {
        itemId: (x.item as ItemListItem).id,
        qtyChange: x.direction === 'add' ? quantity : -quantity,
        binId: x.fromBinId,
        stockLotId: x.stockLotId,
        unitCost: x.direction === 'add' && !x.stockLotId ? x.unitCost : null,
        remarks: x.remarks?.trim() || null,
      };
    });
    const removed = lines.filter((l) => Number(l.qtyChange) < 0).length;
    confirmAction(this.dialog, {
      title: 'Post this adjustment?',
      message: `${lines.length - removed} line(s) add stock and ${removed} remove it, under your name. Posted adjustments can't be edited.`,
      confirmText: 'Post adjustment',
      destructive: removed > 0,
    })
      .pipe(
        filter(Boolean),
        switchMap(() => {
          this.saving.set(true);
          return this.api
            .call(createAdjustment, {
              body: {
                locationId: v.locationId as number,
                reasonId: v.reasonId as number,
                adjustmentDate: v.adjustmentDate
                  ? isoDate(v.adjustmentDate)
                  : null,
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
        (adjustment) =>
          void this.router.navigate(['/inventory/adjustments', adjustment.id]),
      );
  }
}
