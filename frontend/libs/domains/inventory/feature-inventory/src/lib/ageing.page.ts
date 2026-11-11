import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import {
  takeUntilDestroyed,
  toObservable,
  toSignal,
} from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import {
  MatButtonToggle,
  MatButtonToggleGroup,
} from '@angular/material/button-toggle';
import {
  MatFormField,
  MatLabel,
  MatPrefix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { Router } from '@angular/router';
import {
  AgeingReport,
  AgeingRow,
  ApiClient,
  GetAgeingReport$Params,
  getAgeingReport,
  listItemCategories,
} from '@trishul/core-api';
import { PageHeader } from '@trishul/shared-ui';
import {
  Subject,
  catchError,
  debounceTime,
  distinctUntilChanged,
  finalize,
  of,
  switchMap,
} from 'rxjs';
import {
  InventoryLookups,
  downloadCsv,
  n0,
} from '@trishul/inventory-data-access';

type AgeingGroup = NonNullable<GetAgeingReport$Params['groupBy']>;

const GROUPS: { value: AgeingGroup; label: string; column: string }[] = [
  { value: 'item', label: 'Item', column: 'Item' },
  { value: 'grn', label: 'GRN', column: 'GRN' },
  {
    value: 'branch',
    label: 'Branch / warehouse',
    column: 'Branch / warehouse',
  },
  { value: 'location', label: 'Location', column: 'Location' },
  { value: 'rack', label: 'Rack', column: 'Rack' },
];

/**
 * Inventory ageing from the GRN date of every batch on hand, in 0-30 / 31-60 / 61-90 / 91-180 / 180+
 * day buckets, by item, GRN, branch, location or rack. Values are at each batch's actual GRN cost.
 */
@Component({
  selector: 'trishul-ageing-page',
  imports: [
    DatePipe,
    DecimalPipe,
    MatButton,
    MatButtonToggleGroup,
    MatButtonToggle,
    MatFormField,
    MatLabel,
    MatPrefix,
    MatInput,
    MatSelect,
    MatOption,
    MatIcon,
    MatProgressBar,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../data-access/src/lib/inventory.scss',
  styles: `
    .buckets {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 0.75rem;
      margin-bottom: 1rem;
    }
    .bucket {
      padding: 0.75rem 0.9rem;
      border-radius: var(--mat-sys-corner-small);
      border: 1px solid var(--mat-sys-outline-variant);
      background: var(--mat-sys-surface);
    }
    .bucket .value {
      font: var(--mat-sys-title-large);
      font-weight: 600;
    }
    .bucket .bar {
      height: 6px;
      margin-top: 0.5rem;
      border-radius: 3px;
      background: var(--mat-sys-surface-container-high);
      overflow: hidden;
    }
    .bucket .bar span {
      display: block;
      height: 100%;
    }
    .tone0 .bar span {
      background: #16a34a;
    }
    .tone1 .bar span {
      background: #65a30d;
    }
    .tone2 .bar span {
      background: #d97706;
    }
    .tone3 .bar span {
      background: #ea580c;
    }
    .tone4 .bar span {
      background: var(--mat-sys-error);
    }
    .tone4 .value {
      color: var(--mat-sys-error);
    }
    td.cell .qty {
      font: var(--mat-sys-body-small);
      color: var(--mat-sys-on-surface-variant);
    }
    td.zero {
      color: var(--mat-sys-outline);
    }
    tbody tr {
      cursor: pointer;
    }
    @media (max-width: 800px) {
      .buckets {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
  `,
  template: `
    <trishul-page-header
      title="Inventory ageing"
      [subtitle]="
        'Age from the original GRN date, valued at GRN cost · as of ' +
        (report()?.asOf ?? '' | date: 'dd MMM yyyy')
      "
    >
      <button
        mat-stroked-button
        (click)="export()"
        [disabled]="!report()?.rows?.length"
      >
        <mat-icon>download</mat-icon>Export
      </button>
    </trishul-page-header>

    <div class="filters">
      <mat-button-toggle-group
        [value]="query().groupBy"
        (change)="update({ groupBy: $event.value })"
        aria-label="Group by"
      >
        @for (g of groups; track g.value) {
          <mat-button-toggle [value]="g.value">{{ g.label }}</mat-button-toggle>
        }
      </mat-button-toggle-group>
    </div>
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
          placeholder="Item, GRN no or batch no"
          aria-label="Search"
          (input)="search$.next($any($event.target).value)"
        />
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Branch / warehouse</mat-label>
        <mat-select
          [value]="query().branchId ?? null"
          (valueChange)="update({ branchId: $event, locationId: null })"
        >
          <mat-option [value]="null">All</mat-option>
          @for (b of branches(); track b.id) {
            <mat-option [value]="b.id">{{ b.name }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Location</mat-label>
        <mat-select
          [value]="query().locationId ?? null"
          (valueChange)="update({ locationId: $event })"
        >
          <mat-option [value]="null">All</mat-option>
          @for (l of locationsShown(); track l.id) {
            <mat-option [value]="l.id">{{ l.code }} · {{ l.name }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Category</mat-label>
        <mat-select
          [value]="query().categoryId ?? null"
          (valueChange)="update({ categoryId: $event })"
        >
          <mat-option [value]="null">All</mat-option>
          @for (c of categories(); track c.id) {
            <mat-option [value]="c.id">{{ c.path }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
    </div>

    @if (report(); as r) {
      <div class="buckets">
        @for (label of r.buckets; track label; let i = $index) {
          <div [class]="'bucket tone' + i">
            <div class="label">{{ label }}</div>
            <div class="value">₹{{ r.totals[i].value | number: '1.0-0' }}</div>
            <div class="muted">
              {{ r.totals[i].qty | number: '1.0-3' }} units ·
              {{ share(r.totals[i].value) | number: '1.0-0' }}%
            </div>
            <div class="bar">
              <span [style.width.%]="share(r.totals[i].value)"></span>
            </div>
          </div>
        }
      </div>
    }

    <div class="table-card">
      <div class="progress">
        @if (loading()) {
          <mat-progress-bar mode="indeterminate" />
        }
      </div>
      <div class="table-scroll">
        <table class="plain wide">
          <thead>
            <tr>
              <th>{{ groupColumn() }}</th>
              <th class="num">Oldest</th>
              @for (label of report()?.buckets ?? []; track label) {
                <th class="num">{{ label }}</th>
              }
              <th class="num">Total</th>
            </tr>
          </thead>
          <tbody>
            @for (row of report()?.rows ?? []; track row.key) {
              <tr
                (click)="drill(row)"
                tabindex="0"
                (keydown.enter)="drill(row)"
              >
                <td>
                  <strong>{{ row.code }}</strong>
                  @if (row.name !== row.code) {
                    · {{ row.name }}
                  }
                  @if (row.context) {
                    <div class="muted">{{ row.context }}</div>
                  }
                </td>
                <td class="num">
                  {{ row.oldestAgeDays }} days
                  <div class="muted">
                    {{ row.oldestGrnDate | date: 'dd MMM yy' }}
                  </div>
                </td>
                @for (cell of row.buckets; track $index) {
                  <td class="num cell" [class.zero]="!n0(cell.qty)">
                    @if (n0(cell.qty)) {
                      ₹{{ cell.value | number: '1.0-0' }}
                      <div class="qty">{{ cell.qty | number: '1.0-3' }}</div>
                    } @else {
                      —
                    }
                  </td>
                }
                <td class="num cell">
                  <strong>₹{{ row.value | number: '1.0-0' }}</strong>
                  <div class="qty">{{ row.qty | number: '1.0-3' }}</div>
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="8" class="empty">
                  {{
                    loading()
                      ? 'Loading…'
                      : 'No stock on hand for these filters.'
                  }}
                </td>
              </tr>
            }
          </tbody>
          @if (report()?.rows?.length) {
            <tfoot>
              <tr>
                <td>Total ({{ report()!.rows.length }})</td>
                <td></td>
                @for (cell of report()!.totals; track $index) {
                  <td class="num cell">
                    ₹{{ cell.value | number: '1.0-0' }}
                    <div class="qty">{{ cell.qty | number: '1.0-3' }}</div>
                  </td>
                }
                <td class="num cell">
                  ₹{{ report()!.totalValue | number: '1.0-0' }}
                  <div class="qty">
                    {{ report()!.totalQty | number: '1.0-3' }}
                  </div>
                </td>
              </tr>
            </tfoot>
          }
        </table>
      </div>
    </div>
  `,
})
export class AgeingPage {
  private readonly api = inject(ApiClient);
  private readonly router = inject(Router);
  private readonly lookups = inject(InventoryLookups);
  protected readonly groups = GROUPS;
  protected readonly n0 = n0;

  protected readonly branches = toSignal(this.lookups.branches(), {
    initialValue: [],
  });
  private readonly locations = toSignal(this.lookups.locations(), {
    initialValue: [],
  });
  protected readonly categories = toSignal(
    this.api
      .call(listItemCategories, { status: 'active' })
      .pipe(catchError(() => of([]))),
    { initialValue: [] },
  );
  protected readonly query = signal<GetAgeingReport$Params>({
    groupBy: 'item',
  });
  protected readonly loading = signal(false);
  protected readonly report = toSignal(
    toObservable(this.query).pipe(
      debounceTime(0),
      switchMap((q) => {
        this.loading.set(true);
        return this.api.call(getAgeingReport, q).pipe(
          catchError(() => of(null as AgeingReport | null)),
          finalize(() => this.loading.set(false)),
        );
      }),
    ),
    { initialValue: null },
  );
  protected readonly groupColumn = computed(
    () => GROUPS.find((g) => g.value === this.query().groupBy)?.column ?? '',
  );
  protected readonly locationsShown = computed(() => {
    const branch = this.query().branchId;
    return this.locations().filter((l) => !branch || l.branchId === branch);
  });
  protected readonly search$ = new Subject<string>();

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) => this.update({ search: search.trim() || null }));
  }

  protected update(change: Partial<GetAgeingReport$Params>): void {
    this.query.update((q) => ({ ...q, ...change }));
  }

  protected share(value: string): number {
    const total = n0(this.report()?.totalValue);
    return total ? (n0(value) / total) * 100 : 0;
  }

  /** The batches behind a row, on the stock page with the same filters. */
  protected drill(row: AgeingRow): void {
    const q = this.query();
    const params: Record<string, string | number | null | undefined> = {
      branchId: row.branchId ?? q.branchId,
      locationId: row.locationId ?? q.locationId,
      binId: row.binId,
      itemId: row.itemId ?? q.itemId,
      search: row.grnNo ?? q.search,
    };
    const queryParams = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== null && v !== undefined),
    );
    void this.router.navigate(['/inventory/stock'], { queryParams });
  }

  protected export(): void {
    const report = this.report();
    if (!report) return;
    const header = [
      this.groupColumn(),
      'Name',
      'Details',
      'Oldest GRN date',
      'Oldest age (days)',
      ...report.buckets.flatMap((b) => [`${b} qty`, `${b} value`]),
      'Total qty',
      'Total value',
    ];
    const rows = report.rows.map((r) => [
      r.code,
      r.name,
      r.context,
      r.oldestGrnDate,
      r.oldestAgeDays,
      ...r.buckets.flatMap((c) => [n0(c.qty), n0(c.value)]),
      n0(r.qty),
      n0(r.value),
    ]);
    downloadCsv(
      `inventory-ageing-by-${report.groupBy}-${report.asOf}.csv`,
      header,
      rows,
    );
  }
}
