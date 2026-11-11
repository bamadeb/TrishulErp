import { DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  effect,
  inject,
  input,
  model,
  signal,
} from '@angular/core';
import { ReactiveFormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatFormField, MatHint, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatTooltip } from '@angular/material/tooltip';
import { ItemSaleInfo } from '@trishul/core-api';
import { ItemPicker, num } from '@trishul/inventory-data-access';
import { SalesLookups } from '@trishul/sales-data-access';
import {
  SaleLineForm,
  rupees,
  saleLine,
  saleLineAmounts,
} from './sales.shared';

/**
 * The priced lines of a quotation or order: item (or, where allowed, just a description), qty, price,
 * discount and GST. Picking an item fills its selling price and shows the stock on hand.
 */
@Component({
  selector: 'trishul-sale-lines',
  imports: [
    DecimalPipe,
    ReactiveFormsModule,
    MatFormField,
    MatLabel,
    MatHint,
    MatInput,
    MatButton,
    MatIconButton,
    MatIcon,
    MatTooltip,
    ItemPicker,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../../inventory/data-access/src/lib/inventory.scss',
  template: `
    <div class="lines">
      @for (line of lines(); track line; let i = $index) {
        <div class="line sale" [formGroup]="line">
          <span class="index">{{ i + 1 }}</span>
          <div>
            <trishul-item-picker
              formControlName="item"
              [label]="allowText() ? 'Item (optional)' : 'Item'"
              [stockOnly]="false"
            />
            @if (info(line); as info) {
              <div class="muted stock">
                {{
                  info.priceList
                    ? info.priceList + ' ' + money(info.price)
                    : 'No price list'
                }}
                ·
                @for (s of info.stock; track s.locationId) {
                  {{ s.locationName }} {{ s.qtyOnHand | number: '1.0-3' }}
                } @empty {
                  no stock
                }
              </div>
            }
          </div>
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Description</mat-label>
            <input matInput formControlName="description" />
          </mat-form-field>
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label
              >Qty{{
                line.controls.item.value
                  ? ' (' + line.controls.item.value.uomCode + ')'
                  : ''
              }}</mat-label
            >
            <input matInput type="number" min="0" formControlName="quantity" />
          </mat-form-field>
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Price (₹)</mat-label>
            <input matInput type="number" min="0" formControlName="unitPrice" />
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
            (click)="remove(i)"
          >
            <mat-icon>delete</mat-icon>
          </button>
        </div>
      }
    </div>
    <button mat-button type="button" (click)="add()">
      <mat-icon>add</mat-icon>Add line
    </button>
  `,
  styles: `
    .line.sale {
      grid-template-columns:
        2rem minmax(14rem, 2fr) minmax(10rem, 1.5fr) repeat(
          4,
          minmax(5rem, 1fr)
        )
        2.5rem;
    }
    .stock {
      font-size: 0.8em;
      margin-top: 0.2rem;
    }
    @media (max-width: 900px) {
      .line.sale {
        grid-template-columns: 1fr 1fr;
      }
    }
  `,
})
export class SaleLines {
  private readonly lookups = inject(SalesLookups);
  readonly lines = model.required<SaleLineForm[]>();
  /** A line may be just a description (quotations: services, freight). */
  readonly allowText = input(false);
  /** The document's brand: the price list of that brand is preferred. */
  readonly principalId = input<number | null>(null);
  /** Called for every new line so the parent can watch it for totals. */
  readonly watch = input<(line: SaleLineForm) => SaleLineForm>((l) => l);

  protected readonly money = rupees;
  private readonly infos = signal(new Map<SaleLineForm, ItemSaleInfo>());
  private readonly hooked = new WeakSet<SaleLineForm>();

  constructor() {
    // Every line (from the parent or added here) fills its price when an item is picked.
    effect(() => {
      for (const line of this.lines()) {
        if (this.hooked.has(line)) continue;
        this.hooked.add(line);
        line.controls.item.valueChanges.subscribe(() => this.itemPicked(line));
      }
    });
  }

  protected info(line: SaleLineForm): ItemSaleInfo | undefined {
    return this.infos().get(line);
  }

  protected amounts(line: SaleLineForm) {
    return saleLineAmounts(line);
  }

  /** A newly picked item: fill the description and selling price, show its stock. */
  protected itemPicked(line: SaleLineForm): void {
    const item = line.controls.item.value;
    if (!item || this.infos().get(line)?.itemId === item.id) return;
    this.lookups.itemInfo(item.id, this.principalId()).subscribe((info) => {
      if (!info) return;
      this.infos.update((m) => new Map(m).set(line, info));
      if (line.controls.unitPrice.value === null) {
        line.controls.unitPrice.setValue(num(info.price) ?? num(info.mrp));
      }
    });
  }

  protected add(): void {
    this.lines.update((lines) => [...lines, this.watch()(saleLine())]);
  }

  protected remove(index: number): void {
    this.lines.update((lines) => lines.filter((_, i) => i !== index));
  }
}
