import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  inject,
  signal,
  viewChild,
  afterNextRender,
} from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import {
  MatFormField,
  MatHint,
  MatLabel,
  MatPrefix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { RouterLink } from '@angular/router';
import { EMPTY, catchError, finalize } from 'rxjs';
import { ItemListItem } from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import {
  BARCODE_TYPES,
  BarcodeApi,
  BarcodeType,
  INV_BARCODE_LINK,
  INV_BARCODE_MANAGE,
  INV_GRN_MANAGE,
  INV_LOCATION_MANAGE,
  ItemPicker,
  ScanMatch,
  ScanResult,
  guessBarcodeType,
} from '@trishul/inventory-data-access';
import { PageHeader } from '@trishul/shared-ui';

/**
 * Scan or type any code (item code, part number, barcode, bin, rack or location) and see what it is and where
 * its stock is. A hardware scanner types the code followed by Enter; typing works the same way.
 */
@Component({
  selector: 'trishul-scan-page',
  imports: [
    DatePipe,
    DecimalPipe,
    ReactiveFormsModule,
    RouterLink,
    MatButton,
    MatFormField,
    MatHint,
    MatLabel,
    MatPrefix,
    MatIcon,
    MatInput,
    MatProgressBar,
    MatSelect,
    MatOption,
    ItemPicker,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../data-access/src/lib/inventory.scss',
  styles: `
    .scan {
      display: flex;
      gap: 0.75rem;
      align-items: center;
      flex-wrap: wrap;
      margin-bottom: 1rem;
    }
    .scan mat-form-field {
      flex: 1 1 22rem;
      max-width: 36rem;
    }
    .scan input {
      font: var(--mat-sys-title-large);
    }
    .match {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      padding: 0.5rem 0;
      border-bottom: 1px solid var(--mat-sys-outline-variant);
    }
    .match .kind {
      min-width: 5rem;
      font: var(--mat-sys-label-medium);
      color: var(--mat-sys-on-surface-variant);
    }
    .match button {
      margin-left: auto;
    }
    .notice {
      padding: 0.75rem 1rem;
      border-radius: var(--mat-sys-corner-medium);
      background: var(--trishul-warn-container);
      color: var(--trishul-warn);
      margin-bottom: 1rem;
    }
    .link-form {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      align-items: flex-start;
      margin-top: 0.75rem;
    }
    .link-form trishul-item-picker {
      flex: 1 1 20rem;
    }
    .total {
      font: var(--mat-sys-title-small);
      margin: 0.5rem 0;
    }
    .table-wrap {
      overflow-x: auto;
    }
    .age {
      font-weight: 500;
      white-space: nowrap;
    }
    .batch-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      margin-top: 1.25rem;
    }
  `,
  template: `
    <trishul-page-header
      title="Scan & find"
      subtitle="Scan or type an item code, part number, barcode, bin or rack to see what it is and where its stock is"
    />

    <div class="scan">
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-icon matPrefix>qr_code_scanner</mat-icon>
        <input
          #box
          matInput
          autocomplete="off"
          aria-label="Code to find"
          placeholder="Scan or type, then Enter"
          [value]="code()"
          (input)="code.set($any($event.target).value)"
          (keydown.enter)="find()"
        />
        <mat-hint>A scanner types the code and presses Enter for you</mat-hint>
      </mat-form-field>
      <button
        mat-flat-button
        type="button"
        [disabled]="!code().trim() || busy()"
        (click)="find()"
      >
        <mat-icon>search</mat-icon>Find
      </button>
    </div>
    @if (busy()) {
      <mat-progress-bar mode="indeterminate" />
    }

    @if (result(); as r) {
      @switch (r.resolvedType) {
        @case ('Unknown') {
          <div class="notice">
            Nothing has the code <b>{{ r.code }}</b
            >: it is not an item code, part number, registered barcode, bin,
            rack or location.
          </div>
          @if (canLink) {
            <section class="card">
              <h2>Link this barcode to an item</h2>
              <p class="muted">
                If {{ r.code }} is printed on an item's packing, link it once;
                the next scan finds the item directly.
              </p>
              <div class="link-form">
                <trishul-item-picker
                  [formControl]="linkItem"
                  [stockOnly]="false"
                  label="Item"
                />
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>Type</mat-label>
                  <mat-select
                    [value]="linkType()"
                    (valueChange)="linkType.set($event)"
                  >
                    @for (t of barcodeTypes; track t.value) {
                      <mat-option [value]="t.value">{{ t.label }}</mat-option>
                    }
                  </mat-select>
                </mat-form-field>
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>Units per scan</mat-label>
                  <input
                    matInput
                    type="number"
                    min="0.001"
                    [value]="linkPack()"
                    (input)="linkPack.set($any($event.target).value)"
                  />
                </mat-form-field>
                <button
                  mat-flat-button
                  type="button"
                  [disabled]="!linkItem.value || busy()"
                  (click)="link(r.code)"
                >
                  <mat-icon>link</mat-icon>Link barcode
                </button>
              </div>
            </section>
          }
        }
        @case ('Many') {
          <section class="card">
            <h2>{{ r.matches.length }} matches for {{ r.code }}</h2>
            <p class="muted">Choose the one you mean.</p>
            @for (m of r.matches; track m.kind + m.id) {
              <div class="match">
                <span class="kind">{{ m.kind }}</span>
                <span
                  ><b>{{ m.code }}</b> {{ m.name ?? '' }}
                  <span class="muted">· {{ m.via }}</span></span
                >
                <button mat-button type="button" (click)="choose(m)">
                  Show
                </button>
              </div>
            }
          </section>
        }
        @default {
          @let m = r.matches[0];
          <section class="card">
            <h2>
              <span>
                {{ m.kind }} <b>{{ m.code }}</b>
                @if (m.name) {
                  · {{ m.name }}
                }
              </span>
              @if (m.kind === 'Item') {
                <a mat-button [routerLink]="['../items', m.id]"
                  ><mat-icon>open_in_new</mat-icon>Item</a
                >
              }
              @if (m.kind === 'Lot' && r.batches.length) {
                <a mat-button [routerLink]="['../items', r.batches[0].itemId]"
                  ><mat-icon>open_in_new</mat-icon>Item</a
                >
              }
            </h2>
            <p class="muted">
              Found by {{ m.via }}
              @if (m.packQty && +m.packQty !== 1) {
                · one scan counts {{ m.packQty | number: '1.0-3' }}
              }
            </p>
            <p class="total">
              @if (r.stock.length) {
                {{ totalQty() | number: '1.0-3' }}
                {{ r.stock[0].uomCode }} in {{ r.stockTotal }} place(s)
              } @else {
                No stock
              }
            </p>
            @if (r.stock.length) {
              <div class="table-wrap">
                <table class="plain">
                  <thead>
                    <tr>
                      <th>Location</th>
                      <th>Rack / bin</th>
                      @if (m.kind !== 'Item') {
                        <th>Item</th>
                      }
                      <th class="num">Qty</th>
                      <th>Oldest GRN</th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (s of r.stock; track $index) {
                      <tr>
                        <td>
                          {{ s.locationCode }}
                          <div class="muted">{{ s.branchName }}</div>
                        </td>
                        <td>
                          {{ s.binCode ?? 'No bin' }}
                          @if (s.binBlocked) {
                            <div class="muted">Blocked</div>
                          }
                        </td>
                        @if (m.kind !== 'Item') {
                          <td>
                            {{ s.itemCode }}
                            <div class="muted">{{ s.itemDescription }}</div>
                          </td>
                        }
                        <td class="num">
                          {{ s.qtyOnHand | number: '1.0-3' }} {{ s.uomCode }}
                        </td>
                        <td>{{ s.oldestGrnDate | date: 'dd MMM yyyy' }}</td>
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
            }
            @if (m.kind === 'Item' || m.kind === 'Lot') {
              <div class="batch-head">
                <h3>
                  Ageing by GRN batch
                  <span class="muted"
                    >· each receipt aged from its own GRN date</span
                  >
                </h3>
                @if (canPrintBatches && r.batches.length > 1) {
                  <button mat-button type="button" (click)="printBatches()">
                    <mat-icon>print</mat-icon>Batch labels
                  </button>
                }
              </div>
              @if (r.batches.length) {
                <div class="table-wrap">
                  <table class="plain">
                    <thead>
                      <tr>
                        <th>Batch</th>
                        <th>GRN</th>
                        <th>GRN date</th>
                        <th class="num">Received</th>
                        <th class="num">Available</th>
                        <th>Where</th>
                        <th>Age</th>
                        @if (canPrintBatches) {
                          <th></th>
                        }
                      </tr>
                    </thead>
                    <tbody>
                      @for (b of r.batches; track b.stockLotId) {
                        <tr>
                          <td>
                            {{ b.lotNo }}
                            @if (b.sourceType !== 'GRN') {
                              <div class="muted">{{ b.sourceType }}</div>
                            }
                          </td>
                          <td>
                            {{ b.grnNo }}
                            @if (b.supplierName) {
                              <div class="muted">{{ b.supplierName }}</div>
                            }
                          </td>
                          <td>{{ b.grnDate | date: 'dd MMM yyyy' }}</td>
                          <td class="num">
                            {{ b.qtyReceived | number: '1.0-3' }}
                          </td>
                          <td class="num">
                            {{ b.qtyAvailable | number: '1.0-3' }}
                            {{ b.uomCode }}
                          </td>
                          <td>
                            @for (p of b.places; track p) {
                              <div>{{ p }}</div>
                            }
                          </td>
                          <td>
                            <span class="age">{{ b.ageText }}</span>
                            <div class="muted">{{ b.ageDays }} days</div>
                          </td>
                          @if (canPrintBatches) {
                            <td>
                              <button
                                mat-button
                                type="button"
                                (click)="printBatches([b.stockLotId])"
                              >
                                <mat-icon>print</mat-icon>Label
                              </button>
                            </td>
                          }
                        </tr>
                      }
                    </tbody>
                  </table>
                </div>
              } @else {
                <p class="muted">No batch of it is in stock.</p>
              }
            }
          </section>
        }
      }
    }
  `,
})
export class ScanPage {
  private readonly api = inject(BarcodeApi);
  private readonly snackBar = inject(MatSnackBar);
  private readonly auth = inject(AuthStore);
  private readonly box =
    viewChild.required<ElementRef<HTMLInputElement>>('box');

  protected readonly canLink = this.auth.hasAnyPermission([
    INV_BARCODE_LINK,
    INV_BARCODE_MANAGE,
  ]);
  /** Batch labels: storekeepers who post GRNs, or barcode / location managers. */
  protected readonly canPrintBatches = this.auth.hasAnyPermission([
    INV_GRN_MANAGE,
    INV_BARCODE_MANAGE,
    INV_LOCATION_MANAGE,
  ]);
  protected readonly barcodeTypes = BARCODE_TYPES;
  protected readonly code = signal('');
  protected readonly busy = signal(false);
  protected readonly result = signal<ScanResult | null>(null);
  protected readonly linkItem = new FormControl<ItemListItem | null>(null);
  protected readonly linkType = signal<BarcodeType>('Code128');
  protected readonly linkPack = signal('1');

  protected readonly totalQty = computed(() =>
    (this.result()?.stock ?? []).reduce((t, s) => t + Number(s.qtyOnHand), 0),
  );

  constructor() {
    afterNextRender(() => this.box().nativeElement.focus());
  }

  protected find(value = this.code()): void {
    const code = value.trim();
    if (!code || this.busy()) return;
    this.busy.set(true);
    this.api
      .scan(code)
      .pipe(
        finalize(() => this.busy.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe((result) => {
        this.result.set(result);
        if (result.resolvedType === 'Unknown') {
          this.linkItem.reset(null);
          this.linkType.set(guessBarcodeType(result.code));
          this.linkPack.set('1');
        }
        // Ready for the next scan: select the text so the next one replaces it.
        this.box().nativeElement.select();
      });
  }

  /** Labels for GRN batches (all shown when none are named), to stick on the parts and scan later. */
  protected printBatches(ids?: number[]): void {
    const batches = this.result()?.batches ?? [];
    const chosen = ids ?? batches.map((b) => b.stockLotId);
    if (chosen.length) this.api.printLabels({ kind: 'Lot', ids: chosen });
  }

  /** One of several matches: look it up by its own code. */
  protected choose(match: ScanMatch): void {
    this.code.set(match.code);
    this.find(match.code);
  }

  protected link(code: string): void {
    const item = this.linkItem.value;
    if (!item) return;
    this.busy.set(true);
    this.api
      .link({
        itemId: item.id,
        barcode: code,
        barcodeType: this.linkType(),
        packQty: this.linkPack() || '1',
      })
      .pipe(
        finalize(() => this.busy.set(false)),
        catchError(() => EMPTY), // the error toast has been shown (wrong check digit, already used ...)
      )
      .subscribe(() => {
        this.snackBar.open(`${code} now finds ${item.itemCode}.`, 'OK', {
          duration: 4000,
        });
        this.find(code);
      });
  }
}
