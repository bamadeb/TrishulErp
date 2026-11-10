import { Signal, WritableSignal, computed, signal } from '@angular/core';
import { FormControl, FormGroup, Validators } from '@angular/forms';
import {
  ApiClient,
  ItemListItem,
  StockRow,
  listStock,
} from '@trishul/core-api';
import { catchError, of } from 'rxjs';
import { n0 } from '@trishul/inventory-data-access';

/**
 * One line of a transfer or adjustment: the item, the quantity, racks and (optionally) the GRN batch,
 * plus the batches of that item at the source location so the user can see what is there.
 */
export class StockLine {
  readonly form = new FormGroup({
    item: new FormControl<ItemListItem | null>(null, Validators.required),
    quantity: new FormControl<number | null>(null, [Validators.required]),
    fromBinId: new FormControl<number | null>(null),
    toBinId: new FormControl<number | null>(null),
    stockLotId: new FormControl<number | null>(null),
    unitCost: new FormControl<number | null>(null, Validators.min(0)),
    remarks: new FormControl<string | null>(null, Validators.maxLength(200)),
    /** Adjustments only: add stock or remove it. */
    direction: new FormControl<'add' | 'remove'>('remove', {
      nonNullable: true,
    }),
  });
  /** Stock of the item at the source location, one row per batch and rack, oldest GRN first. */
  readonly batches: WritableSignal<StockRow[]> = signal([]);
  private readonly rack = signal<number | null>(null);
  private readonly lot = signal<number | null>(null);

  /** Batches on the chosen rack (all racks when none is chosen). */
  readonly batchesHere: Signal<StockRow[]> = computed(() => {
    const rack = this.rack();
    return this.batches().filter((b) => rack === null || b.binId === rack);
  });

  /** What can be taken with the current rack / batch choice. */
  readonly available: Signal<number> = computed(() => {
    const lot = this.lot();
    return this.batchesHere()
      .filter((b) => lot === null || b.stockLotId === lot)
      .reduce((sum, b) => sum + n0(b.qtyOnHand), 0);
  });

  constructor() {
    this.form.controls.fromBinId.valueChanges.subscribe((rack) => {
      this.rack.set(rack);
      this.form.controls.stockLotId.setValue(null);
    });
    this.form.controls.stockLotId.valueChanges.subscribe((lot) =>
      this.lot.set(lot),
    );
  }

  /** Reload the batches for the line's item at the location. */
  loadBatches(api: ApiClient, locationId: number | null): void {
    const item = this.form.controls.item.value;
    this.batches.set([]);
    if (!item || !locationId) return;
    api
      .call(listStock, {
        itemId: item.id,
        locationId,
        pageSize: 200,
        sort: 'grnDate',
      })
      .pipe(catchError(() => of({ items: [] as StockRow[] })))
      .subscribe((page) => this.batches.set(page.items));
  }
}

/** "GRN/0003 · 12 Mar 2026 (45 days) · A1 · 5 left" */
export function batchLabel(row: StockRow): string {
  const date = new Date(row.grnDate).toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
  return `${row.grnNo} · ${date} (${row.ageDays} days)${row.binCode ? ' · ' + row.binCode : ''} · ${n0(row.qtyOnHand)} left`;
}
