import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { DatePipe, DecimalPipe } from '@angular/common';
import { MatButton } from '@angular/material/button';
import {
  MatFormField,
  MatHint,
  MatLabel,
  MatPrefix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTab, MatTabGroup } from '@angular/material/tabs';
import { RouterLink } from '@angular/router';
import { EMPTY, catchError, finalize, of } from 'rxjs';
import { RackOut } from '@trishul/core-api';
import {
  BarcodeApi,
  BinMoveApi,
  BinMoveLineIn,
  BinMoveOut,
  InventoryLookups,
  PutAwayRow,
} from '@trishul/inventory-data-access';
import { PageHeader } from '@trishul/shared-ui';

interface Resolved {
  id: number | null;
  code: string;
  label: string;
}

/** Put received stock away into bins, move stock between bins by scanning, and see the moves made. */
@Component({
  selector: 'trishul-bin-moves-page',
  imports: [
    DatePipe,
    DecimalPipe,
    RouterLink,
    MatButton,
    MatFormField,
    MatHint,
    MatLabel,
    MatPrefix,
    MatIcon,
    MatInput,
    MatPaginator,
    MatProgressBar,
    MatSelect,
    MatOption,
    MatTab,
    MatTabGroup,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../data-access/src/lib/inventory.scss',
  styles: `
    .bar {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      align-items: center;
      margin: 0.75rem 0;
    }
    .bar mat-form-field {
      width: 18rem;
    }
    .cell-field {
      width: 12rem;
    }
    .qty-field {
      width: 6.5rem;
    }
    .scan-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
      gap: 0.75rem;
      max-width: 64rem;
      margin: 0.75rem 0;
    }
    .resolved {
      font: var(--mat-sys-body-small);
      color: var(--mat-sys-on-surface-variant);
    }
    .table-wrap {
      overflow-x: auto;
    }
    tr.pick {
      cursor: pointer;
    }
  `,
  template: `
    <trishul-page-header
      title="Put-away & bin moves"
      subtitle="Put received stock into its bins, and move stock between bins of a location; every move keeps its GRN batch"
    />

    <div class="bar">
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Location</mat-label>
        <mat-select
          [value]="locationId()"
          (valueChange)="locationId.set($event)"
        >
          @for (l of locations(); track l.id) {
            <mat-option [value]="l.id">{{ l.code }} · {{ l.name }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
    </div>
    @if (busy()) {
      <mat-progress-bar mode="indeterminate" />
    }

    <mat-tab-group mat-stretch-tabs="false" animationDuration="0ms">
      <mat-tab label="Put-away ({{ rows().length }})">
        @if (!locationId()) {
          <p class="empty">Choose a location.</p>
        } @else {
          <div class="bar">
            <span class="muted"
              >Stock in a receiving bin, or kept here without a bin. Choose a
              bin (the suggestion is filled in) and move it.</span
            >
            <span class="spacer"></span>
            <button
              mat-flat-button
              type="button"
              [disabled]="!suggestedCount() || busy()"
              (click)="putAllAway()"
            >
              <mat-icon>done_all</mat-icon>Put {{ suggestedCount() }} away to
              the suggested bins
            </button>
          </div>
          <section class="card">
            <div class="table-wrap">
              <table class="plain">
                <thead>
                  <tr>
                    <th>Item</th>
                    <th>GRN batch</th>
                    <th>Now in</th>
                    <th class="num">Qty</th>
                    <th>Move to</th>
                    <th class="num">Qty to move</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  @for (r of rows(); track key(r)) {
                    <tr>
                      <td>
                        <a class="name" [routerLink]="['../items', r.itemId]">{{
                          r.itemCode
                        }}</a>
                        <div class="muted">{{ r.itemDescription }}</div>
                      </td>
                      <td>
                        {{ r.grnNo }}
                        <div class="muted">
                          {{ r.grnDate | date: 'dd MMM yyyy' }}
                        </div>
                      </td>
                      <td>{{ r.fromBinCode ?? 'No bin' }}</td>
                      <td class="num">
                        {{ r.qtyOnHand | number: '1.0-3' }} {{ r.uomCode }}
                      </td>
                      <td>
                        <mat-form-field
                          class="cell-field"
                          appearance="outline"
                          subscriptSizing="dynamic"
                        >
                          <mat-select
                            [value]="target(r)"
                            (valueChange)="setTarget(r, $event)"
                            aria-label="Bin to move to"
                          >
                            @for (b of targets(); track b.id) {
                              <mat-option [value]="b.id">{{
                                b.code
                              }}</mat-option>
                            }
                          </mat-select>
                          @if (r.suggestion) {
                            <mat-hint>{{ r.suggestion }}</mat-hint>
                          }
                        </mat-form-field>
                      </td>
                      <td class="num">
                        <mat-form-field
                          class="qty-field"
                          appearance="outline"
                          subscriptSizing="dynamic"
                        >
                          <input
                            matInput
                            type="number"
                            min="0"
                            [value]="quantity(r)"
                            (input)="setQuantity(r, $any($event.target).value)"
                            aria-label="Quantity to move"
                          />
                        </mat-form-field>
                      </td>
                      <td class="actions">
                        <button
                          mat-stroked-button
                          type="button"
                          [disabled]="!target(r) || busy()"
                          (click)="putAway(r)"
                        >
                          Move
                        </button>
                      </td>
                    </tr>
                  } @empty {
                    <tr>
                      <td colspan="7" class="empty">
                        Nothing waiting: all stock here is in its bins.
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          </section>
        }
      </mat-tab>

      <mat-tab label="Move by scan">
        @if (!locationId()) {
          <p class="empty">Choose a location.</p>
        } @else {
          <p class="muted">
            Scan (or type) each code and press Enter. Leave "From bin" empty to
            move stock kept without a bin.
          </p>
          <div class="scan-grid">
            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>From bin</mat-label>
              <mat-icon matPrefix>qr_code_scanner</mat-icon>
              <input
                matInput
                autocomplete="off"
                [value]="fromCode()"
                (input)="
                  fromCode.set($any($event.target).value); from.set(null)
                "
                (keydown.enter)="resolve('from')"
                (blur)="resolve('from')"
              />
              <mat-hint>{{ from()?.label ?? 'Empty = no bin' }}</mat-hint>
            </mat-form-field>
            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>Item</mat-label>
              <mat-icon matPrefix>qr_code_scanner</mat-icon>
              <input
                matInput
                autocomplete="off"
                [value]="itemCode()"
                (input)="
                  itemCode.set($any($event.target).value); item.set(null)
                "
                (keydown.enter)="resolve('item')"
                (blur)="resolve('item')"
              />
              <mat-hint>{{
                item()?.label ?? 'Item code, barcode or part no'
              }}</mat-hint>
            </mat-form-field>
            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>To bin</mat-label>
              <mat-icon matPrefix>qr_code_scanner</mat-icon>
              <input
                matInput
                autocomplete="off"
                [value]="toCode()"
                (input)="toCode.set($any($event.target).value); to.set(null)"
                (keydown.enter)="resolve('to')"
                (blur)="resolve('to')"
              />
              <mat-hint>{{ to()?.label ?? '' }}</mat-hint>
            </mat-form-field>
            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>Quantity</mat-label>
              <input
                matInput
                type="number"
                min="0"
                [value]="scanQty()"
                (input)="scanQty.set($any($event.target).value)"
                (keydown.enter)="scanMove()"
              />
            </mat-form-field>
          </div>
          <button
            mat-flat-button
            type="button"
            [disabled]="!item()?.id || !to()?.id || !(+scanQty() > 0) || busy()"
            (click)="scanMove()"
          >
            <mat-icon>swap_horiz</mat-icon>Move
          </button>
        }
      </mat-tab>

      <mat-tab label="History">
        <section class="card">
          <div class="table-wrap">
            <table class="plain">
              <thead>
                <tr>
                  <th>Move</th>
                  <th>When</th>
                  <th>Type</th>
                  <th>Location</th>
                  <th class="num">Lines</th>
                  <th>By</th>
                </tr>
              </thead>
              <tbody>
                @for (m of history()?.items ?? []; track m.id) {
                  <tr class="pick" (click)="open(m)">
                    <td>{{ m.moveNo }}</td>
                    <td>{{ m.movedAt | date: 'dd MMM yyyy, HH:mm' }}</td>
                    <td>{{ m.moveType }}</td>
                    <td>{{ m.locationCode }}</td>
                    <td class="num">{{ m.lineCount }}</td>
                    <td>{{ m.movedByName ?? '—' }}</td>
                  </tr>
                  @if (opened()?.id === m.id) {
                    @for (l of opened()!.lines; track $index) {
                      <tr>
                        <td></td>
                        <td colspan="2">
                          {{ l.itemCode }}
                          <div class="muted">{{ l.itemDescription }}</div>
                        </td>
                        <td colspan="2">
                          {{ l.fromBinCode ?? 'No bin' }} → {{ l.toBinCode }}
                        </td>
                        <td>{{ l.quantity | number: '1.0-3' }}</td>
                      </tr>
                    }
                  }
                } @empty {
                  <tr>
                    <td colspan="6" class="empty">No moves yet.</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
          <mat-paginator
            [length]="history()?.total ?? 0"
            [pageIndex]="page() - 1"
            [pageSize]="20"
            [hidePageSize]="true"
            aria-label="Pages of moves"
            (page)="onPage($event)"
          />
        </section>
      </mat-tab>
    </mat-tab-group>
  `,
})
export class BinMovesPage {
  private readonly moves = inject(BinMoveApi);
  private readonly barcodes = inject(BarcodeApi);
  private readonly lookups = inject(InventoryLookups);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly locations = toSignal(this.lookups.locations(), {
    initialValue: [],
  });
  protected readonly locationId = signal<number | null>(null);
  protected readonly busy = signal(false);

  // ------------------------------------------------------------------ put-away
  protected readonly rows = signal<PutAwayRow[]>([]);
  /** Bins stock may go to: active, not blocked, not a receiving bin. */
  protected readonly targets = signal<RackOut[]>([]);
  private readonly choices = signal<
    Record<string, { bin: number | null; qty: string }>
  >({});
  protected readonly suggestedCount = computed(
    () => this.rows().filter((r) => this.target(r)).length,
  );

  // ------------------------------------------------------------------ move by scan
  protected readonly fromCode = signal('');
  protected readonly itemCode = signal('');
  protected readonly toCode = signal('');
  protected readonly scanQty = signal('1');
  protected readonly from = signal<Resolved | null>(null);
  protected readonly item = signal<Resolved | null>(null);
  protected readonly to = signal<Resolved | null>(null);

  // ------------------------------------------------------------------ history
  protected readonly page = signal(1);
  protected readonly history = signal<{
    items: BinMoveOut[];
    total: number;
  } | null>(null);
  protected readonly opened = signal<BinMoveOut | null>(null);

  constructor() {
    effect(() => {
      const id = this.locationId();
      untracked(() => this.load(id));
    });
    effect(() => {
      const page = this.page();
      const locationId = this.locationId();
      untracked(() =>
        this.moves
          .history({ page, pageSize: 20, locationId })
          .pipe(catchError(() => of(null)))
          .subscribe((p) => this.history.set(p)),
      );
    });
  }

  private load(locationId: number | null): void {
    this.rows.set([]);
    this.targets.set([]);
    this.choices.set({});
    if (!locationId) return;
    this.busy.set(true);
    this.moves
      .putaway(locationId)
      .pipe(
        finalize(() => this.busy.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe((rows) => this.rows.set(rows));
    this.lookups
      .putAwayRacks(locationId)
      .subscribe((bins) =>
        this.targets.set(bins.filter((b) => !b.isReceiving)),
      );
  }

  protected key(r: PutAwayRow): string {
    return `${r.stockLotId}-${r.fromBinId ?? 0}`;
  }

  protected target(r: PutAwayRow): number | null {
    const chosen = this.choices()[this.key(r)];
    return chosen ? chosen.bin : r.suggestedBinId;
  }

  protected quantity(r: PutAwayRow): string {
    return this.choices()[this.key(r)]?.qty ?? String(Number(r.qtyOnHand));
  }

  protected setTarget(r: PutAwayRow, bin: number): void {
    this.choices.update((c) => ({
      ...c,
      [this.key(r)]: { bin, qty: this.quantity(r) },
    }));
  }

  protected setQuantity(r: PutAwayRow, qty: string): void {
    this.choices.update((c) => ({
      ...c,
      [this.key(r)]: { bin: this.target(r), qty },
    }));
  }

  private line(r: PutAwayRow): BinMoveLineIn | null {
    const bin = this.target(r);
    const qty = Number(this.quantity(r));
    if (!bin || !(qty > 0)) return null;
    return {
      itemId: r.itemId,
      stockLotId: r.stockLotId,
      fromBinId: r.fromBinId,
      toBinId: bin,
      quantity: String(qty),
    };
  }

  protected putAway(r: PutAwayRow): void {
    const line = this.line(r);
    if (line) this.post([line], 'Put-away');
  }

  protected putAllAway(): void {
    const lines = this.rows()
      .map((r) => this.line(r))
      .filter((l): l is BinMoveLineIn => l !== null);
    if (lines.length) this.post(lines, 'Put-away');
  }

  private post(
    lines: BinMoveLineIn[],
    moveType: 'Put-away' | 'Bin move',
  ): void {
    const locationId = this.locationId();
    if (!locationId) return;
    this.busy.set(true);
    this.moves
      .move({ locationId, moveType, lines })
      .pipe(
        finalize(() => this.busy.set(false)),
        catchError(() => EMPTY), // the error toast has been shown (blocked bin, not enough stock ...)
      )
      .subscribe((done) => {
        this.snackBar.open(
          `${done.moveNo}: ${done.lineCount} line(s) moved.`,
          'OK',
          { duration: 3000 },
        );
        this.load(locationId);
        this.page.set(1);
        this.reloadHistory();
      });
  }

  private reloadHistory(): void {
    this.moves
      .history({
        page: this.page(),
        pageSize: 20,
        locationId: this.locationId(),
      })
      .pipe(catchError(() => of(null)))
      .subscribe((p) => this.history.set(p));
  }

  /** Looks the typed / scanned code up and keeps what it is (a bin of this location, or an item). */
  protected resolve(field: 'from' | 'item' | 'to'): void {
    const code = { from: this.fromCode, item: this.itemCode, to: this.toCode }
      [field]()
      .trim();
    const slot = { from: this.from, item: this.item, to: this.to }[field];
    if (!code) {
      slot.set(null);
      return;
    }
    if (slot()?.code === code) return;
    this.barcodes
      .scan(code, 'bin-move')
      .pipe(catchError(() => EMPTY))
      .subscribe((result) => {
        const wanted = field === 'item' ? 'Item' : 'Bin';
        const match = result.matches.filter((m) => m.kind === wanted);
        if (match.length !== 1) {
          slot.set({
            id: null,
            code,
            label: match.length
              ? 'Several matches: type the exact code'
              : `Not a ${wanted.toLowerCase()}`,
          });
          return;
        }
        const m = match[0];
        if (wanted === 'Bin' && m.locationId !== this.locationId()) {
          slot.set({
            id: null,
            code,
            label: 'That bin is in another location',
          });
          return;
        }
        slot.set({
          id: m.id,
          code,
          label: `${m.code}${m.name ? ' · ' + m.name : ''}`,
        });
        if (field === 'item' && m.packQty && Number(m.packQty) !== 1) {
          this.scanQty.set(String(Number(m.packQty)));
        }
      });
  }

  protected scanMove(): void {
    const item = this.item();
    const to = this.to();
    const qty = Number(this.scanQty());
    if (!item?.id || !to?.id || !(qty > 0)) return;
    if (this.fromCode().trim() && !this.from()?.id) {
      this.snackBar.open(
        'The "From bin" code is not a bin of this location.',
        'OK',
        { duration: 4000 },
      );
      return;
    }
    this.post(
      [
        {
          itemId: item.id,
          fromBinId: this.from()?.id ?? null,
          toBinId: to.id,
          quantity: String(qty),
        },
      ],
      'Bin move',
    );
    this.itemCode.set('');
    this.item.set(null);
    this.scanQty.set('1');
  }

  protected onPage(event: PageEvent): void {
    this.page.set(event.pageIndex + 1);
  }

  protected open(move: BinMoveOut): void {
    if (this.opened()?.id === move.id) {
      this.opened.set(null);
      return;
    }
    this.moves
      .get(move.id)
      .pipe(catchError(() => EMPTY))
      .subscribe((full) => this.opened.set(full));
  }
}
