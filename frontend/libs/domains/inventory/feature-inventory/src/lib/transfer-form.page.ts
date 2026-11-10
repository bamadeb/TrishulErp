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
  ApiClient,
  ItemListItem,
  RackOut,
  TransferLineIn,
  createTransfer,
} from '@trishul/core-api';
import { PageHeader, confirmAction } from '@trishul/shared-ui';
import { EMPTY, catchError, filter, finalize, switchMap } from 'rxjs';
import { ItemPicker } from './item-picker';
import { InventoryLookups, isoDate, locationLabel } from './inventory.shared';
import { StockLine, batchLabel } from './stock-line';

/** Move stock between branches, warehouses or racks. Each GRN batch keeps its original GRN date. */
@Component({
  selector: 'trishul-transfer-form-page',
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
      title="New stock transfer"
      subtitle="Oldest GRN batch first unless you pick one; the GRN date moves with the stock"
    />
    <form [formGroup]="form" (ngSubmit)="post()">
      <section class="card">
        <h2>From and to</h2>
        <div class="form-grid">
          <mat-form-field appearance="outline">
            <mat-label>From</mat-label>
            <mat-select formControlName="fromLocationId">
              @for (l of locations(); track l.id) {
                <mat-option [value]="l.id">{{ label(l) }}</mat-option>
              }
            </mat-select>
            <mat-error>Choose where the stock is now.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>To</mat-label>
            <mat-select formControlName="toLocationId">
              @for (l of locations(); track l.id) {
                <mat-option [value]="l.id">{{ label(l) }}</mat-option>
              }
            </mat-select>
            <mat-hint>The same location moves stock between racks</mat-hint>
            <mat-error>Choose where the stock goes.</mat-error>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Transfer date</mat-label>
            <input
              matInput
              [matDatepicker]="picker"
              formControlName="transferDate"
              [max]="today"
            />
            <mat-datepicker-toggle matSuffix [for]="picker" />
            <mat-datepicker #picker />
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
                <mat-label>Quantity</mat-label>
                <input
                  matInput
                  type="number"
                  min="0"
                  formControlName="quantity"
                />
                @if (line.form.controls.item.value) {
                  <mat-hint
                    >{{
                      line.available() | number: '1.0-3'
                    }}
                    available</mat-hint
                  >
                }
              </mat-form-field>
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>From rack</mat-label>
                <mat-select formControlName="fromBinId">
                  <mat-option [value]="null">Any rack</mat-option>
                  @for (r of fromRacks(); track r.id) {
                    <mat-option [value]="r.id">{{ r.code }}</mat-option>
                  }
                </mat-select>
              </mat-form-field>
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>To rack</mat-label>
                <mat-select formControlName="toBinId">
                  <mat-option [value]="null">No rack</mat-option>
                  @for (r of toRacks(); track r.id) {
                    <mat-option [value]="r.id">{{ r.code }}</mat-option>
                  }
                </mat-select>
              </mat-form-field>
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>GRN batch</mat-label>
                <mat-select formControlName="stockLotId">
                  <mat-option [value]="null">Oldest first</mat-option>
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
          Post transfer
        </button>
      </div>
    </form>
  `,
})
export class TransferFormPage {
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
  protected readonly fromRacks = signal<RackOut[]>([]);
  protected readonly toRacks = signal<RackOut[]>([]);
  protected readonly saving = signal(false);

  protected readonly form = new FormGroup({
    fromLocationId: new FormControl<number | null>(null, Validators.required),
    toLocationId: new FormControl<number | null>(null, Validators.required),
    transferDate: new FormControl<Date | null>(new Date(), Validators.required),
    remarks: new FormControl<string | null>(null, Validators.maxLength(300)),
  });
  protected readonly lines = signal([this.newLine()]);

  constructor() {
    this.form.controls.fromLocationId.valueChanges.subscribe((id) => {
      this.lookups.racks(id).subscribe((racks) => this.fromRacks.set(racks));
      for (const line of this.lines()) {
        line.form.controls.fromBinId.setValue(null);
        line.loadBatches(this.api, id);
      }
    });
    this.form.controls.toLocationId.valueChanges.subscribe((id) => {
      this.lookups.racks(id).subscribe((racks) => this.toRacks.set(racks));
      for (const line of this.lines())
        line.form.controls.toBinId.setValue(null);
    });
  }

  private newLine(): StockLine {
    const line = new StockLine();
    line.form.controls.quantity.addValidators(Validators.min(0.001));
    line.form.controls.item.valueChanges.subscribe(() =>
      line.loadBatches(this.api, this.form.controls.fromLocationId.value),
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
    const lines: TransferLineIn[] = this.lines().map((l) => {
      const x = l.form.getRawValue();
      return {
        itemId: (x.item as ItemListItem).id,
        quantity: x.quantity as number,
        fromBinId: x.fromBinId,
        toBinId: x.toBinId,
        stockLotId: x.stockLotId,
      };
    });
    const from = this.locations().find((l) => l.id === v.fromLocationId);
    const to = this.locations().find((l) => l.id === v.toLocationId);
    confirmAction(this.dialog, {
      title: 'Post this transfer?',
      message: `${lines.length} line(s) move from ${from ? this.label(from) : ''} to ${to ? this.label(to) : ''} now. The batches keep their GRN dates.`,
      confirmText: 'Post transfer',
    })
      .pipe(
        filter(Boolean),
        switchMap(() => {
          this.saving.set(true);
          return this.api
            .call(createTransfer, {
              body: {
                fromLocationId: v.fromLocationId as number,
                toLocationId: v.toLocationId as number,
                transferDate: v.transferDate ? isoDate(v.transferDate) : null,
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
        (transfer) =>
          void this.router.navigate(['/inventory/transfers', transfer.id]),
      );
  }
}
