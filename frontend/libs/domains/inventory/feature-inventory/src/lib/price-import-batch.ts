import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { DatePipe, DecimalPipe } from '@angular/common';
import { MatButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
import {
  MatFormField,
  MatLabel,
  MatPrefix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { RouterLink } from '@angular/router';
import {
  EMPTY,
  Observable,
  Subject,
  catchError,
  debounceTime,
  distinctUntilChanged,
  filter,
  finalize,
  switchMap,
  tap,
} from 'rxjs';
import {
  PRICE_IMPORT_SEVERITY,
  PriceImportApi,
  PriceImportBatch,
  PriceImportLineOut,
  PriceImportLineQuery,
} from '@trishul/inventory-data-access';
import { StatusBadge, confirmAction } from '@trishul/shared-ui';

type LineFilter = NonNullable<PriceImportLineQuery['status']>;

/** One price change of a row, for the comparison cell. */
interface PriceCell {
  old: number | null;
  new: number | null;
  diff: number | null;
  pct: number | null;
}

/**
 * One uploaded price file: counts, the comparison of current and new prices, and what to do next (confirm,
 * approve or reject, download). Used after an upload and for a batch opened from the history.
 */
@Component({
  selector: 'trishul-price-import-batch',
  imports: [
    DatePipe,
    DecimalPipe,
    RouterLink,
    MatButton,
    MatCheckbox,
    MatFormField,
    MatLabel,
    MatPrefix,
    MatIcon,
    MatInput,
    MatPaginator,
    MatProgressBar,
    MatSelect,
    MatOption,
    MatTableModule,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './item-import.scss',
  styles: `
    .price {
      white-space: nowrap;
    }
    .price .now {
      font-weight: 600;
    }
    .up {
      color: var(--trishul-success);
    }
    .down {
      color: var(--trishul-danger);
    }
    tr.over-limit td {
      background: var(--trishul-warn-container);
    }
    .decision {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.5rem;
      margin: 0.5rem 0;
    }
    .decision mat-form-field {
      flex: 1 1 18rem;
    }
  `,
  template: `
    @let b = batch();
    <div class="batch-head">
      <div class="batch-title">
        <span class="batch-no">{{ b.batchNo ?? '#' + b.id }}</span>
        <trishul-status-badge [status]="b.status" [severities]="severity" />
        <span class="muted">
          {{ b.fileName }} · uploaded
          {{ b.uploadedAt | date: 'dd MMM yyyy, HH:mm' }} by
          {{ b.uploadedByName ?? '—' }}
          @if (b.priceListName) {
            · selling prices on {{ b.priceListName }}
          }
          @if (b.fileLayout === 'SAP') {
            · SAP price file, ZAmount → {{ b.sapPriceField }}
          }
        </span>
        <span class="muted">Reason: {{ b.reason }}</span>
      </div>
      <div class="batch-actions">
        @if (b.hasFile) {
          <button
            mat-stroked-button
            type="button"
            (click)="api.downloadFile(b)"
          >
            <mat-icon>download</mat-icon>Original file
          </button>
        }
        @if (b.invalidCount + b.duplicateCount + b.failedCount > 0) {
          <button
            mat-stroked-button
            type="button"
            (click)="api.downloadErrorReport(b)"
          >
            <mat-icon>summarize</mat-icon>Error report
          </button>
        }
      </div>
    </div>

    <div class="cards">
      <div class="card">
        <span class="label">Total records</span>
        <span class="value">{{ b.totalRows | number }}</span>
      </div>
      <div class="card success">
        <span class="label">Valid</span>
        <span class="value">{{ b.validCount | number }}</span>
        <span class="hint"
          >{{ b.changedCount | number }} with price changes ·
          {{ b.unchangedCount | number }} unchanged</span
        >
      </div>
      <div class="card danger">
        <span class="label">Invalid</span>
        <span class="value">{{ b.invalidCount | number }}</span>
      </div>
      <div class="card warn">
        <span class="label">Duplicates</span>
        <span class="value">{{ b.duplicateCount | number }}</span>
      </div>
      @if (b.overLimitCount) {
        <div class="card warn">
          <span class="label">Over the {{ b.maxChangePct }}% limit</span>
          <span class="value">{{ b.overLimitCount | number }}</span>
          <span class="hint">need approval</span>
        </div>
      }
      @if (isDone()) {
        <div class="card success">
          <span class="label">Updated</span>
          <span class="value">{{ b.updatedCount | number }}</span>
          @if (b.failedCount) {
            <span class="hint">{{ b.failedCount | number }} failed</span>
          }
        </div>
      }
    </div>

    @switch (b.status) {
      @case ('Pending') {
        <div class="banner note">
          <mat-icon>visibility</mat-icon>
          <span>
            Compared with the current prices; nothing has changed yet.
            @if (b.canConfirm) {
              Check the comparison, then choose <b>Update prices</b>:
              {{ b.changedCount | number }} item(s) change, rows with errors or
              duplicates are left out.
              @if (b.overLimitCount) {
                {{ b.overLimitCount | number }} change(s) are bigger than
                {{ b.maxChangePct }}% and need approval first.
              }
            } @else if (!b.changedCount) {
              No price in this file differs from the current one.
            } @else {
              Only the person who uploaded the file can confirm it.
            }
          </span>
        </div>
        @if (b.repeatOfBatchNo) {
          <div class="banner warn">
            <mat-icon>content_copy</mat-icon>
            <span
              >This same file was already imported in batch
              <b>{{ b.repeatOfBatchNo }}</b
              >. Make sure you really want to apply it again.</span
            >
          </div>
        }
        @if (b.canConfirm) {
          <div class="decision">
            @if (b.repeatOfBatchNo) {
              <mat-checkbox
                [checked]="importAgain()"
                (change)="importAgain.set($event.checked)"
                >Import this file again</mat-checkbox
              >
            }
            <span class="spacer"></span>
            <button
              mat-flat-button
              type="button"
              [disabled]="busy() || (!!b.repeatOfBatchNo && !importAgain())"
              (click)="confirm()"
            >
              <mat-icon>price_change</mat-icon>Update prices of
              {{ b.changedCount | number }} item(s)
            </button>
          </div>
        }
      }
      @case ('Pending approval') {
        <div class="banner warn">
          <mat-icon>gavel</mat-icon>
          <span>
            Waiting for approval: {{ b.overLimitCount | number }} change(s) are
            bigger than {{ b.maxChangePct }}%. Confirmed by
            {{ b.confirmedByName ?? '—' }}
            {{ b.confirmedAt | date: 'dd MMM yyyy, HH:mm' }}. No price has
            changed yet.
          </span>
        </div>
        @if (b.canApprove) {
          <div class="decision">
            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>Note (optional)</mat-label>
              <input
                matInput
                maxlength="500"
                [value]="note()"
                (input)="note.set($any($event.target).value)"
              />
            </mat-form-field>
            <button
              mat-stroked-button
              type="button"
              [disabled]="busy()"
              (click)="decide(false)"
            >
              <mat-icon>block</mat-icon>Reject
            </button>
            <button
              mat-flat-button
              type="button"
              [disabled]="busy()"
              (click)="decide(true)"
            >
              <mat-icon>task_alt</mat-icon>Approve and update
            </button>
          </div>
        }
      }
      @case ('Processing') {
        <div class="banner note">
          <mat-icon>hourglass_top</mat-icon>
          <span>Updating prices…</span>
        </div>
      }
      @case ('Completed') {
        <div class="banner done">
          <mat-icon>check_circle</mat-icon>
          <span>
            @if (b.updatedCount) {
              Prices of {{ b.updatedCount | number }} item(s) updated
              {{ b.completedAt | date: 'dd MMM yyyy, HH:mm' }}.
            } @else {
              {{ b.errorMessage ?? 'Nothing to update.' }}
            }
            @if (b.approvedByName) {
              Approved by {{ b.approvedByName }}.
            }
          </span>
        </div>
      }
      @case ('Partially Completed') {
        <div class="banner warn">
          <mat-icon>warning</mat-icon>
          <span
            >Prices of {{ b.updatedCount | number }} item(s) updated;
            {{ b.failedCount | number }} row(s) failed and
            {{ b.skippedCount | number }} skipped. Download the error report for
            the reasons.</span
          >
        </div>
      }
      @case ('Rejected') {
        <div class="banner error">
          <mat-icon>block</mat-icon>
          <span
            >Rejected by {{ b.rejectedByName ?? '—' }}
            {{ b.rejectedAt | date: 'dd MMM yyyy, HH:mm' }}; no price was
            changed.</span
          >
        </div>
      }
      @case ('Failed') {
        <div class="banner error">
          <mat-icon>error</mat-icon>
          <span>{{
            b.errorMessage ?? 'The import failed; no price was changed.'
          }}</span>
        </div>
      }
    }
    @if (b.decisionNote) {
      <p class="muted">Approver's note: {{ b.decisionNote }}</p>
    }
    @if (busy()) {
      <mat-progress-bar mode="indeterminate" />
    }

    @if (b.totalRows) {
      <div class="filters">
        <mat-form-field
          class="search"
          appearance="outline"
          subscriptSizing="dynamic"
        >
          <mat-icon matPrefix>search</mat-icon>
          <input
            matInput
            type="search"
            placeholder="Item code or name"
            aria-label="Search the rows"
            (input)="search$.next($any($event.target).value)"
          />
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Show</mat-label>
          <mat-select
            [value]="lineFilter()"
            (valueChange)="setFilter($event)"
            aria-label="Filter the rows"
          >
            <mat-option [value]="null">All rows</mat-option>
            @for (f of filters(); track f.value) {
              <mat-option [value]="f.value">{{ f.label }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
      </div>

      <div class="table-card">
        @if (loading()) {
          <mat-progress-bar mode="indeterminate" />
        }
        <div class="table-scroll">
          <table mat-table [dataSource]="lines()">
            <ng-container matColumnDef="rowNumber">
              <th mat-header-cell *matHeaderCellDef>Row</th>
              <td mat-cell *matCellDef="let l">{{ l.rowNumber }}</td>
            </ng-container>
            <ng-container matColumnDef="item">
              <th mat-header-cell *matHeaderCellDef>Item</th>
              <td mat-cell *matCellDef="let l">
                @if (l.itemId) {
                  <a
                    class="name"
                    [routerLink]="['/inventory/items', l.itemId]"
                    >{{ l.itemCode }}</a
                  >
                } @else {
                  {{ l.itemCode ?? '—' }}
                }
                <div class="muted">{{ l.itemName ?? '' }}</div>
              </td>
            </ng-container>
            @for (p of priceColumns; track p.key) {
              <ng-container [matColumnDef]="p.key">
                <th mat-header-cell *matHeaderCellDef class="num">
                  {{ p.label }}
                </th>
                <td mat-cell *matCellDef="let l" class="num">
                  @let c = cell(l, p.key);
                  @if (c.new === null) {
                    <span class="muted">{{
                      c.old === null ? '—' : '₹' + (c.old | number: '1.2-2')
                    }}</span>
                  } @else {
                    <div class="price">
                      <span class="muted">{{
                        c.old === null
                          ? 'none'
                          : '₹' + (c.old | number: '1.2-2')
                      }}</span>
                      →
                      <span class="now">₹{{ c.new | number: '1.2-2' }}</span>
                    </div>
                    @if (c.diff) {
                      <div
                        class="price"
                        [class.up]="c.diff > 0"
                        [class.down]="c.diff < 0"
                      >
                        {{ c.diff > 0 ? '▲ +' : '▼ −' }}₹{{
                          abs(c.diff) | number: '1.2-2'
                        }}
                        @if (c.pct !== null) {
                          ({{ c.pct > 0 ? '+' : ''
                          }}{{ c.pct | number: '1.0-2' }}%)
                        }
                      </div>
                    }
                  }
                </td>
              </ng-container>
            }
            <ng-container matColumnDef="result">
              <th mat-header-cell *matHeaderCellDef>Result</th>
              <td mat-cell *matCellDef="let l">
                <trishul-status-badge
                  [status]="label(l)"
                  [severities]="severity"
                />
              </td>
            </ng-container>
            <ng-container matColumnDef="details">
              <th mat-header-cell *matHeaderCellDef>Details</th>
              <td mat-cell *matCellDef="let l">
                @if (l.reason) {
                  <div class="muted">Reason: {{ l.reason }}</div>
                }
                @for (m of l.messages; track $index) {
                  <div
                    [class.issue-error]="
                      l.action === 'Error' || l.outcome === 'Failed'
                    "
                    [class.issue]="
                      l.action !== 'Error' && l.outcome !== 'Failed'
                    "
                  >
                    {{ m }}
                  </div>
                }
              </td>
            </ng-container>
            <tr mat-header-row *matHeaderRowDef="columns; sticky: true"></tr>
            <tr
              mat-row
              *matRowDef="let row; columns: columns"
              [class.over-limit]="row.overLimit && row.action === 'Change'"
            ></tr>
            <tr class="mat-mdc-row" *matNoDataRow>
              <td class="muted empty" [attr.colspan]="columns.length">
                @if (loading()) {
                  Loading…
                } @else {
                  No rows match.
                }
              </td>
            </tr>
          </table>
        </div>
        <mat-paginator
          [length]="total()"
          [pageIndex]="page() - 1"
          [pageSize]="pageSize()"
          [pageSizeOptions]="[25, 50, 100, 200]"
          aria-label="Pages of rows"
          (page)="onPage($event)"
        />
      </div>
    }
  `,
})
export class PriceImportBatchView {
  protected readonly api = inject(PriceImportApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  readonly batch = input.required<PriceImportBatch>();
  /** The batch after it was confirmed, approved or rejected. */
  readonly changed = output<PriceImportBatch>();

  protected readonly severity = PRICE_IMPORT_SEVERITY;
  protected readonly abs = Math.abs;
  protected readonly priceColumns = [
    { key: 'selling', label: 'Selling price' },
    { key: 'purchase', label: 'Purchase price' },
    { key: 'mrp', label: 'MRP' },
  ] as const;
  protected readonly columns = [
    'rowNumber',
    'item',
    'selling',
    'purchase',
    'mrp',
    'result',
    'details',
  ];

  protected readonly isDone = computed(() =>
    ['Completed', 'Partially Completed'].includes(this.batch().status),
  );
  protected readonly filters = computed<{ value: LineFilter; label: string }[]>(
    () => {
      const common: { value: LineFilter; label: string }[] = [
        { value: 'Change', label: 'Price changes' },
        { value: 'Increase', label: 'Increases' },
        { value: 'Decrease', label: 'Decreases' },
        { value: 'OverLimit', label: 'Over the limit' },
        { value: 'Unchanged', label: 'Unchanged' },
        { value: 'Duplicate', label: 'Duplicates' },
        { value: 'Error', label: 'Invalid' },
      ];
      return this.isDone()
        ? [
            ...common,
            { value: 'Updated', label: 'Updated' },
            { value: 'Failed', label: 'Failed' },
          ]
        : common;
    },
  );

  protected readonly lineFilter = signal<LineFilter | null>(null);
  protected readonly page = signal(1);
  protected readonly pageSize = signal(50);
  private readonly search = signal('');
  protected readonly search$ = new Subject<string>();
  protected readonly loading = signal(false);
  protected readonly busy = signal(false);
  protected readonly importAgain = signal(false);
  protected readonly note = signal('');
  protected readonly lines = signal<PriceImportLineOut[]>([]);
  protected readonly total = signal(0);

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((value) => {
        this.page.set(1);
        this.search.set(value.trim());
      });

    const request = computed(() => ({
      id: this.batch().id,
      status: this.batch().status, // reload once the batch moves on
      query: {
        page: this.page(),
        pageSize: this.pageSize(),
        status: this.lineFilter(),
        search: this.search() || null,
      },
    }));
    toObservable(request)
      .pipe(
        tap(() => this.loading.set(true)),
        switchMap((r) =>
          this.api.lines(r.id, r.query).pipe(
            finalize(() => this.loading.set(false)),
            catchError(() => EMPTY), // the error toast has been shown
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((page) => {
        this.lines.set(page.items);
        this.total.set(page.total);
      });

    toObservable(computed(() => `${this.batch().id}:${this.batch().status}`))
      .pipe(distinctUntilChanged(), takeUntilDestroyed())
      .subscribe(() => {
        this.page.set(1);
        this.lineFilter.set(null);
        this.importAgain.set(false);
      });
  }

  protected cell(
    line: PriceImportLineOut,
    key: 'selling' | 'purchase' | 'mrp',
  ): PriceCell {
    const pick = {
      selling: [line.oldSelling, line.newSelling],
      purchase: [line.oldPurchase, line.newPurchase],
      mrp: [line.oldMrp, line.newMrp],
    }[key];
    const old = pick[0] === null ? null : Number(pick[0]);
    const now = pick[1] === null ? null : Number(pick[1]);
    const diff = old !== null && now !== null ? now - old : null;
    const pct = diff !== null && old ? (diff / old) * 100 : null;
    return { old, new: now, diff, pct };
  }

  protected label(line: PriceImportLineOut): string {
    if (line.outcome) return line.outcome;
    if (line.action === 'Change')
      return line.overLimit ? 'Needs approval' : 'Will change';
    return line.action;
  }

  protected setFilter(value: LineFilter | null): void {
    this.page.set(1);
    this.lineFilter.set(value);
  }

  protected onPage(event: PageEvent): void {
    this.page.set(event.pageIndex + 1);
    this.pageSize.set(event.pageSize);
  }

  protected confirm(): void {
    const b = this.batch();
    const approval = b.overLimitCount
      ? ` ${b.overLimitCount} change(s) are over the ${b.maxChangePct}% limit: unless you may approve price changes, the update waits for approval.`
      : '';
    this.act(
      {
        title: 'Update prices?',
        message:
          `The prices of ${b.changedCount} item(s) will change to the new prices shown in the comparison ` +
          `(reason: ${b.reason}).${approval} Rows with errors or duplicates are not touched.`,
        confirmText: 'Update prices',
      },
      () => this.api.confirm(b.id, this.importAgain()),
    );
  }

  protected decide(approve: boolean): void {
    const b = this.batch();
    const note = this.note().trim() || null;
    this.act(
      approve
        ? {
            title: 'Approve the price changes?',
            message: `The prices of ${b.changedCount} item(s) will be updated now, including ${b.overLimitCount} change(s) over the ${b.maxChangePct}% limit.`,
            confirmText: 'Approve and update',
          }
        : {
            title: 'Reject the price changes?',
            message: 'No price of this file will change.',
            confirmText: 'Reject',
            destructive: true,
          },
      () =>
        approve ? this.api.approve(b.id, note) : this.api.reject(b.id, note),
    );
  }

  private act(
    dialog: Parameters<typeof confirmAction>[1],
    call: () => Observable<PriceImportBatch>,
  ): void {
    const id = this.batch().id;
    confirmAction(this.dialog, dialog)
      .pipe(
        filter(Boolean),
        tap(() => this.busy.set(true)),
        switchMap(() =>
          call().pipe(
            finalize(() => this.busy.set(false)),
            catchError(() => {
              // The batch may have moved on (failed, already confirmed): show its current state.
              this.api.get(id).subscribe((fresh) => this.changed.emit(fresh));
              return EMPTY;
            }),
          ),
        ),
      )
      .subscribe((done) => {
        this.changed.emit(done);
        this.note.set('');
        this.snackBar.open(this.message(done), 'Dismiss', { duration: 6000 });
      });
  }

  private message(b: PriceImportBatch): string {
    switch (b.status) {
      case 'Pending approval':
        return 'Sent for approval: no price changes until it is approved.';
      case 'Completed':
        return `Prices of ${b.updatedCount} item(s) updated.`;
      case 'Partially Completed':
        return `Prices of ${b.updatedCount} item(s) updated; ${b.failedCount} row(s) failed.`;
      case 'Rejected':
        return 'Rejected: no price was changed.';
      default:
        return b.errorMessage ?? 'No price was changed.';
    }
  }
}
