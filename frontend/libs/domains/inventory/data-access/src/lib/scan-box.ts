import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  effect,
  inject,
  input,
  output,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { MatButton, MatIconButton } from '@angular/material/button';
import {
  MatFormField,
  MatHint,
  MatLabel,
  MatPrefix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { FormControl } from '@angular/forms';
import { MatTooltip } from '@angular/material/tooltip';
import {
  ApiClient,
  ItemListItem,
  ScanMatch,
  listItems,
} from '@trishul/core-api';
import { EMPTY, catchError, map } from 'rxjs';
import { BarcodeApi } from './barcode.api';

/** An item scanned (or typed) into a document: put it on a line, in the current bin. */
export interface ScanHit {
  item: ItemListItem;
  /** The bin scanned last in this box (null = none scanned, or cleared). */
  binId: number | null;
  binCode: string | null;
  /** 1, or the pack quantity of a box barcode. */
  quantity: number;
}

/** The controls of a document line that a scan fills. */
export interface ScanLineControls {
  item: FormControl<ItemListItem | null>;
  quantity: FormControl<number | null>;
  /** The line's bin (null when the line has no bin to set). */
  bin: FormControl<number | null> | null;
}

/**
 * Puts a scanned item on the lines: adds to the line with the same item and bin, else fills the first empty
 * line, else makes a new one. Returns the new list when a line was added, null when an existing line was used.
 */
export function placeScan<T>(
  rows: readonly T[],
  hit: ScanHit,
  controls: (row: T) => ScanLineControls,
  make: () => T,
): T[] | null {
  const same = rows.find((row) => {
    const c = controls(row);
    return (
      c.item.value?.id === hit.item.id &&
      (c.bin === null || (c.bin.value ?? null) === hit.binId)
    );
  });
  if (same) {
    const c = controls(same);
    c.quantity.setValue(round3((c.quantity.value ?? 0) + hit.quantity));
    c.quantity.markAsDirty();
    return null;
  }
  const empty = rows.find((row) => !controls(row).item.value);
  const row = empty ?? make();
  const c = controls(row);
  c.item.setValue(hit.item);
  if (c.bin && hit.binId !== null) c.bin.setValue(hit.binId);
  c.quantity.setValue(hit.quantity);
  return empty ? null : [...rows, row];
}

function round3(value: number): number {
  return Math.round(value * 1000) / 1000;
}

export interface ScannedBin {
  id: number;
  code: string;
}

/**
 * A scan box for documents (GRN, transfer, adjustment, opening stock, delivery, invoice). Scan a bin, then the
 * items in it: each item is emitted with that bin and its pack quantity. Typing a code, barcode or part number
 * and pressing Enter works the same, so nothing depends on a scanner. Optional: the form's own pickers still work.
 */
@Component({
  selector: 'trishul-scan-box',
  imports: [
    MatFormField,
    MatLabel,
    MatHint,
    MatPrefix,
    MatInput,
    MatIcon,
    MatButton,
    MatIconButton,
    MatTooltip,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="scan-box">
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>{{ label() }}</mat-label>
        <mat-icon matPrefix>qr_code_scanner</mat-icon>
        <input
          #box
          matInput
          autocomplete="off"
          [value]="code()"
          [disabled]="disabled()"
          (input)="code.set($any($event.target).value)"
          (keydown.enter)="$event.preventDefault(); lookUp()"
          placeholder="Scan a bin, then items (or type a code and press Enter)"
        />
        <mat-hint [class.error]="tone() === 'error'">{{ message() }}</mat-hint>
      </mat-form-field>
      @if (bins() && currentBin(); as bin) {
        <span class="bin-chip">
          <mat-icon>shelves</mat-icon>{{ bin.code }}
          <button
            mat-icon-button
            type="button"
            matTooltip="Stop using this bin"
            (click)="setBin(null)"
          >
            <mat-icon>close</mat-icon>
          </button>
        </span>
      }
    </div>
    @if (choices().length) {
      <div class="choices">
        <span class="muted">Several items match:</span>
        @for (c of choices(); track c.id) {
          <button mat-stroked-button type="button" (click)="useItem(c)">
            {{ c.code }}{{ c.name ? ' · ' + c.name : '' }}
          </button>
        }
      </div>
    }
  `,
  styles: `
    :host {
      display: block;
      margin-bottom: 0.75rem;
    }
    .scan-box {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      flex-wrap: wrap;
    }
    mat-form-field {
      flex: 1 1 22rem;
      max-width: 36rem;
    }
    .bin-chip {
      display: inline-flex;
      align-items: center;
      gap: 0.25rem;
      padding-left: 0.6rem;
      border-radius: 1rem;
      background: var(--mat-sys-secondary-container);
      color: var(--mat-sys-on-secondary-container);
      font-weight: 500;
    }
    .choices {
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
      align-items: center;
      margin-top: 0.5rem;
    }
    .error {
      color: var(--mat-sys-error);
    }
    .muted {
      color: var(--mat-sys-on-surface-variant);
    }
  `,
})
export class ScanBox {
  private readonly barcodes = inject(BarcodeApi);
  private readonly api = inject(ApiClient);
  private readonly box = viewChild<ElementRef<HTMLInputElement>>('box');

  readonly label = input('Scan');
  /** Bins must belong to this location; scanning a bin is refused until one is chosen. */
  readonly locationId = input<number | null>(null);
  /** Recorded in the scan log, e.g. grn, transfer, delivery. */
  readonly screen = input('document');
  /** Whether bins can be scanned here (false: items only). */
  readonly bins = input(true);
  /** Items only of type Stock (default), or any item (invoice lines may be services). */
  readonly stockOnly = input(true);
  readonly disabled = input(false);

  /** An item was scanned. */
  readonly scanned = output<ScanHit>();
  /** The current bin changed (scanned, or cleared). */
  readonly binChange = output<ScannedBin | null>();

  protected readonly code = signal('');
  protected readonly message = signal('');
  protected readonly tone = signal<'info' | 'error'>('info');
  protected readonly currentBin = signal<ScannedBin | null>(null);
  protected readonly choices = signal<ScanMatch[]>([]);

  constructor() {
    // A bin of another location is no use: forget it when the location changes.
    effect(() => {
      this.locationId();
      untracked(() => {
        if (this.currentBin()) this.setBin(null);
      });
    });
  }

  /** Focus the box (after a dialog, or when the form opens). */
  focus(): void {
    this.box()?.nativeElement.focus();
  }

  protected lookUp(): void {
    const code = this.code().trim();
    if (!code) return;
    this.choices.set([]);
    this.barcodes
      .scan(code, this.screen())
      .pipe(catchError(() => EMPTY)) // the error toast has been shown
      .subscribe((result) => {
        const bins = result.matches.filter((m) => m.kind === 'Bin');
        const items = result.matches.filter((m) => m.kind === 'Item');
        if (this.bins() && bins.length && !items.length) {
          const here = bins.find((b) => b.locationId === this.locationId());
          if (!this.locationId()) {
            this.fail(`${code} is a bin: choose the location first.`);
          } else if (!here) {
            this.fail(`Bin ${code} is in another location.`);
          } else {
            this.setBin({ id: here.id, code: here.code });
            this.done(`Bin ${here.code}: the next items go here.`);
          }
          return;
        }
        if (items.length === 1) {
          this.useItem(items[0]);
        } else if (items.length > 1) {
          this.choices.set(items);
          this.info('Choose the item.');
        } else if (result.matches.length) {
          this.fail(
            `${code} is a ${result.matches[0].kind.toLowerCase()}, not an item${this.bins() ? ' or a bin' : ''}.`,
          );
        } else {
          this.fail(`Nothing matches ${code}.`);
        }
      });
  }

  protected useItem(match: ScanMatch): void {
    this.choices.set([]);
    this.api
      .call(listItems, {
        search: match.code,
        pageSize: 20,
        ...(this.stockOnly() ? { itemType: 'Stock' as const } : {}),
      })
      .pipe(
        map((page) => page.items.find((i) => i.id === match.id) ?? null),
        catchError(() => EMPTY),
      )
      .subscribe((item) => {
        if (!item) {
          this.fail(
            this.stockOnly()
              ? `${match.code} is not a stock item.`
              : `${match.code} can't be used here.`,
          );
          return;
        }
        const quantity = match.packQty ? Number(match.packQty) : 1;
        const bin = this.bins() ? this.currentBin() : null;
        this.scanned.emit({
          item,
          binId: bin?.id ?? null,
          binCode: bin?.code ?? null,
          quantity: quantity > 0 ? quantity : 1,
        });
        this.done(
          `${item.itemCode} +${quantity > 0 ? quantity : 1}${bin ? ' in ' + bin.code : ''}`,
        );
      });
  }

  protected setBin(bin: ScannedBin | null): void {
    this.currentBin.set(bin);
    this.binChange.emit(bin);
    if (!bin) this.info('');
  }

  private done(text: string): void {
    this.info(text);
    this.code.set('');
    this.focus();
  }

  private info(text: string): void {
    this.tone.set('info');
    this.message.set(text);
  }

  private fail(text: string): void {
    this.tone.set('error');
    this.message.set(text);
    this.box()?.nativeElement.select();
  }
}
