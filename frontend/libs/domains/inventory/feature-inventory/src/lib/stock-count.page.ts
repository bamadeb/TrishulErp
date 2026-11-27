import { DatePipe, DecimalPipe } from '@angular/common';
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
import { MatButton } from '@angular/material/button';
import {
  MatButtonToggle,
  MatButtonToggleGroup,
} from '@angular/material/button-toggle';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatTooltip } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';
import { AuthStore } from '@trishul/core-auth';
import {
  INV_COUNT_APPROVE,
  INV_COUNT_MANAGE,
  ScanBox,
  ScanHit,
  StockCountApi,
  StockCountLineOut,
  StockCountOut,
  downloadCsv,
  n0,
} from '@trishul/inventory-data-access';
import { PageHeader, confirmAction } from '@trishul/shared-ui';
import { EMPTY, Observable, catchError, filter, finalize } from 'rxjs';

type Show = 'all' | 'uncounted' | 'differences';

/**
 * One count sheet: scan a bin, then the items in it (each scan adds one, or a box's pack quantity), or type the
 * counted quantity on a line. When counting is finished the differences are reviewed and posted as an adjustment.
 */
@Component({
  selector: 'trishul-stock-count-page',
  imports: [
    DatePipe,
    DecimalPipe,
    RouterLink,
    MatButton,
    MatButtonToggle,
    MatButtonToggleGroup,
    MatIcon,
    MatTooltip,
    PageHeader,
    ScanBox,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../data-access/src/lib/inventory.scss',
  styles: `
    .facts {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem 2rem;
      margin: 0 0 0.75rem;
    }
    .facts span {
      color: var(--mat-sys-on-surface-variant);
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      align-items: center;
    }
    .bar {
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 0.75rem;
    }
    .count-input {
      width: 6.5rem;
      text-align: right;
    }
    .short {
      color: var(--mat-sys-error);
    }
    .excess {
      color: var(--mat-sys-tertiary);
    }
    .tag {
      font-size: 0.75rem;
      padding: 0 0.4rem;
      border-radius: 0.6rem;
      margin-left: 0.25rem;
      background: var(--mat-sys-surface-container-high);
    }
    .tag.moved {
      background: var(--mat-sys-error-container);
      color: var(--mat-sys-on-error-container);
    }
  `,
  template: `
    @if (count(); as c) {
      <trishul-page-header
        [title]="'Stock count ' + c.countNo"
        [subtitle]="c.locationCode + ' · ' + c.locationName"
      >
        <a mat-button routerLink="/inventory/stock-counts">All counts</a>
      </trishul-page-header>

      <section class="card">
        <div class="facts">
          <div>
            <span>Status</span> <strong>{{ c.status }}</strong>
          </div>
          <div>
            <span>Counts</span>
            {{
              c.scope === 'Location'
                ? 'everything at the location'
                : c.scope === 'Rack'
                  ? 'rack ' + c.storageRackCode
                  : 'bins ' + c.binCodes.join(', ')
            }}
          </div>
          <div><span>Date</span> {{ c.countDate | date: 'dd MMM yyyy' }}</div>
          <div>
            <span>Lines</span> {{ c.countedCount }} of {{ c.lineCount }} counted
          </div>
          @if (c.isBlind) {
            <div>
              <span>Blind</span>
              {{ c.status === 'Open' ? 'system quantity hidden' : 'yes' }}
            </div>
          }
          @if (c.shortQty !== null && c.shortQty !== undefined) {
            <div>
              <span>Short</span>
              <strong class="short">{{ c.shortQty | number: '1.0-3' }}</strong>
              @if (c.shortValue) {
                (₹{{ c.shortValue | number: '1.0-2' }})
              }
            </div>
            <div>
              <span>Excess</span>
              <strong class="excess">{{
                c.excessQty | number: '1.0-3'
              }}</strong>
              @if (c.excessValue) {
                (₹{{ c.excessValue | number: '1.0-2' }})
              }
            </div>
          }
          @if (c.adjustmentId) {
            <div>
              <span>Adjustment</span>
              <a [routerLink]="['/inventory/adjustments', c.adjustmentId]">{{
                c.adjustmentNo
              }}</a>
            </div>
          }
          @if (c.remarks) {
            <div><span>Remarks</span> {{ c.remarks }}</div>
          }
        </div>
        <div class="actions">
          @if (c.status === 'Open' && canCount) {
            <button
              mat-flat-button
              type="button"
              [disabled]="busy()"
              (click)="finish(false)"
            >
              <mat-icon>done_all</mat-icon>Finish counting
            </button>
            <button
              mat-stroked-button
              type="button"
              [disabled]="busy()"
              matTooltip="Lines nobody counted are taken as found empty"
              (click)="finish(true)"
            >
              Finish, uncounted = 0
            </button>
          }
          @if (c.status === 'Counted') {
            @if (canApprove) {
              <button
                mat-flat-button
                type="button"
                [disabled]="busy()"
                (click)="post()"
              >
                <mat-icon>published_with_changes</mat-icon>Post differences
              </button>
            }
            @if (canCount) {
              <button
                mat-stroked-button
                type="button"
                [disabled]="busy()"
                (click)="act(api.reopen(c.id))"
              >
                Back to counting
              </button>
            }
          }
          @if ((c.status === 'Open' || c.status === 'Counted') && canCount) {
            <button
              mat-button
              type="button"
              [disabled]="busy()"
              (click)="cancel()"
            >
              Cancel count
            </button>
          }
          <button mat-button type="button" (click)="export()">
            <mat-icon>download</mat-icon>Excel
          </button>
        </div>
      </section>

      @if (c.status === 'Open' && canCount) {
        <section class="card">
          <h2>Count</h2>
          <trishul-scan-box
            screen="stock-count"
            label="Scan a bin, then the items in it"
            [locationId]="c.locationId"
            (scanned)="onScan($event)"
          />
          <p class="muted">
            Each scan adds one (a box barcode adds its pack quantity). Or type
            the counted quantity on a line below.
            {{
              c.scope === 'Location'
                ? 'Items scanned with no bin are stock kept without a bin.'
                : ''
            }}
          </p>
        </section>
      }

      <section class="card">
        <div class="bar">
          <mat-button-toggle-group
            [value]="show()"
            (change)="show.set($event.value)"
            hideSingleSelectionIndicator
          >
            <mat-button-toggle value="all"
              >All ({{ c.lines.length }})</mat-button-toggle
            >
            <mat-button-toggle value="uncounted"
              >Not counted ({{
                c.lineCount - c.countedCount
              }})</mat-button-toggle
            >
            @if (!hidden()) {
              <mat-button-toggle value="differences"
                >Differences ({{ differenceCount() }})</mat-button-toggle
              >
            }
          </mat-button-toggle-group>
        </div>
        <div class="table-wrap">
          <table class="plain">
            <thead>
              <tr>
                <th>Bin</th>
                <th>Item</th>
                @if (!hidden()) {
                  <th class="num">System</th>
                }
                <th class="num">Counted</th>
                @if (!hidden()) {
                  <th class="num">Difference</th>
                  <th class="num">Value (₹)</th>
                }
                <th>Counted by</th>
              </tr>
            </thead>
            <tbody>
              @for (l of shown(); track l.id) {
                <tr>
                  <td>{{ l.binCode ?? 'No bin' }}</td>
                  <td>
                    {{ l.itemCode }}
                    @if (!l.isExpected) {
                      <span
                        class="tag"
                        matTooltip="Not in the system here when the count started"
                        >found</span
                      >
                    }
                    @if (l.movedSinceCount) {
                      <span
                        class="tag moved"
                        matTooltip="Stock of this item moved in or out of the bin after it was counted"
                        >moved since</span
                      >
                    }
                    <div class="muted">{{ l.itemDescription }}</div>
                  </td>
                  @if (!hidden()) {
                    <td class="num">
                      {{ l.systemQty | number: '1.0-3' }} {{ l.uomCode }}
                    </td>
                  }
                  <td class="num">
                    @if (c.status === 'Open' && canCount) {
                      <input
                        class="cell count-input"
                        type="number"
                        min="0"
                        [value]="l.countedQty === null ? '' : +l.countedQty"
                        (change)="setCount(l, $any($event.target).value)"
                        [attr.aria-label]="'Counted ' + l.itemCode"
                      />
                    } @else {
                      {{
                        l.countedQty === null
                          ? '—'
                          : (l.countedQty | number: '1.0-3')
                      }}
                    }
                  </td>
                  @if (!hidden()) {
                    <td
                      class="num"
                      [class.short]="n0(l.variance) < 0"
                      [class.excess]="n0(l.variance) > 0"
                    >
                      {{
                        l.variance === null
                          ? ''
                          : (l.variance | number: '1.0-3')
                      }}
                    </td>
                    <td class="num">
                      {{
                        l.varianceValue === null
                          ? ''
                          : (l.varianceValue | number: '1.0-2')
                      }}
                    </td>
                  }
                  <td>
                    {{ l.countedByName ?? '' }}
                    @if (l.countedAt) {
                      <div class="muted">
                        {{ l.countedAt | date: 'dd MMM, HH:mm' }}
                      </div>
                    }
                  </td>
                </tr>
              } @empty {
                <tr>
                  <td colspan="7" class="empty">Nothing to show.</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      </section>
    }
  `,
})
export class StockCountPage {
  protected readonly api = inject(StockCountApi);
  private readonly dialog = inject(MatDialog);
  private readonly auth = inject(AuthStore);
  protected readonly canCount = this.auth.hasPermission(INV_COUNT_MANAGE);
  protected readonly canApprove = this.auth.hasPermission(INV_COUNT_APPROVE);
  protected readonly n0 = n0;

  /** Route parameter :countId. */
  readonly countId = input.required<string>();

  protected readonly count = signal<StockCountOut | null>(null);
  protected readonly busy = signal(false);
  protected readonly show = signal<Show>('all');

  /** The system quantity is hidden while a blind count is open. */
  protected readonly hidden = computed(() => {
    const c = this.count();
    return !c || (c.isBlind && c.status === 'Open');
  });
  protected readonly differenceCount = computed(
    () =>
      (this.count()?.lines ?? []).filter(
        (l) => l.variance !== null && n0(l.variance) !== 0,
      ).length,
  );
  protected readonly shown = computed(() => {
    const lines = this.count()?.lines ?? [];
    switch (this.show()) {
      case 'uncounted':
        return lines.filter((l) => l.countedQty === null);
      case 'differences':
        return lines.filter((l) => l.variance !== null && n0(l.variance) !== 0);
      default:
        return lines;
    }
  });

  constructor() {
    effect(() => {
      const id = Number(this.countId());
      untracked(() => this.load(id));
    });
  }

  private load(id = this.count()?.id): void {
    if (!id) return;
    this.api
      .get(id)
      .pipe(catchError(() => EMPTY))
      .subscribe((c) => this.count.set(c));
  }

  /** A scanned item adds to its line in the scanned bin (a new line when it was not expected there). */
  protected onScan(hit: ScanHit): void {
    const c = this.count();
    if (!c) return;
    this.api
      .record(c.id, {
        itemId: hit.item.id,
        binId: hit.binId,
        quantity: String(hit.quantity),
        mode: 'add',
      })
      .pipe(catchError(() => EMPTY))
      .subscribe((line) => this.replaceLine(line));
  }

  protected setCount(line: StockCountLineOut, value: string): void {
    const c = this.count();
    if (!c || value === '' || Number(value) < 0) return;
    this.api
      .record(c.id, {
        itemId: line.itemId,
        binId: line.binId,
        quantity: String(Number(value)),
        mode: 'set',
      })
      .pipe(catchError(() => EMPTY))
      .subscribe((saved) => this.replaceLine(saved));
  }

  private replaceLine(line: StockCountLineOut): void {
    this.count.update((c) => {
      if (!c) return c;
      const known = c.lines.some((l) => l.id === line.id);
      const lines = known
        ? c.lines.map((l) => (l.id === line.id ? line : l))
        : [...c.lines, line];
      return {
        ...c,
        lines,
        lineCount: lines.length,
        countedCount: lines.filter((l) => l.countedQty !== null).length,
      };
    });
  }

  protected finish(uncountedAsZero: boolean): void {
    const c = this.count();
    if (!c) return;
    const left = c.lineCount - c.countedCount;
    const message = uncountedAsZero
      ? `${left} line(s) nobody counted will be taken as found empty (the stock is missing). The differences can then be reviewed.`
      : `${left} line(s) nobody counted will be left out (no change). The differences can then be reviewed.`;
    confirmAction(this.dialog, {
      title: 'Finish counting?',
      message,
      confirmText: 'Finish counting',
    })
      .pipe(filter(Boolean))
      .subscribe(() => this.act(this.api.close(c.id, { uncountedAsZero })));
  }

  protected post(): void {
    const c = this.count();
    if (!c) return;
    const diff = this.differenceCount();
    confirmAction(this.dialog, {
      title: 'Post the differences?',
      message: diff
        ? `${diff} line(s) differ: one stock adjustment (reason Count difference) will add ${c.excessQty ?? 0} and remove ${c.shortQty ?? 0}. Posted adjustments can't be edited.`
        : 'Nothing differs; the count will be closed without an adjustment.',
      confirmText: 'Post',
      destructive: diff > 0,
    })
      .pipe(filter(Boolean))
      .subscribe(() => this.act(this.api.post(c.id)));
  }

  protected cancel(): void {
    const c = this.count();
    if (!c) return;
    confirmAction(this.dialog, {
      title: 'Cancel this count?',
      message:
        'Nothing is posted; the counted quantities stay on the sheet for reference.',
      confirmText: 'Cancel count',
      destructive: true,
    })
      .pipe(filter(Boolean))
      .subscribe(() => this.act(this.api.cancel(c.id)));
  }

  protected act(request: Observable<StockCountOut>): void {
    this.busy.set(true);
    request
      .pipe(
        finalize(() => this.busy.set(false)),
        catchError(() => EMPTY), // the error toast has been shown
      )
      .subscribe((c) => {
        this.count.set(c);
        this.show.set('all');
      });
  }

  protected export(): void {
    const c = this.count();
    if (!c) return;
    const hide = this.hidden();
    downloadCsv(
      `${c.countNo}.csv`,
      [
        'Bin',
        'Item',
        'Description',
        'Unit',
        ...(hide ? [] : ['System']),
        'Counted',
        ...(hide ? [] : ['Difference', 'Value']),
        'Counted by',
        'Found',
        'Moved since count',
      ],
      c.lines.map((l) => [
        l.binCode ?? '',
        l.itemCode,
        l.itemDescription,
        l.uomCode,
        ...(hide ? [] : [l.systemQty]),
        l.countedQty,
        ...(hide ? [] : [l.variance, l.varianceValue]),
        l.countedByName,
        l.isExpected ? '' : 'yes',
        l.movedSinceCount ? 'yes' : '',
      ]),
    );
  }
}
