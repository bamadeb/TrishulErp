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
import { DatePipe, DecimalPipe } from '@angular/common';
import { MatButton } from '@angular/material/button';
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
import { MatSlideToggle } from '@angular/material/slide-toggle';
import { MatTab, MatTabGroup } from '@angular/material/tabs';
import { ActivatedRoute, RouterLink } from '@angular/router';
import {
  ApiClient,
  ListBinStock$Params,
  listBinStock,
  listLocations,
  listStorageRacks,
} from '@trishul/core-api';
import { PageHeader } from '@trishul/shared-ui';
import {
  EMPTY,
  Subject,
  catchError,
  debounceTime,
  distinctUntilChanged,
  finalize,
  map,
  of,
  switchMap,
} from 'rxjs';

type Query = ListBinStock$Params;

/** Stock by location, rack, bin and item, including stock kept at a location without a bin. */
@Component({
  selector: 'trishul-bin-stock-page',
  imports: [
    DatePipe,
    DecimalPipe,
    RouterLink,
    MatButton,
    MatFormField,
    MatLabel,
    MatPrefix,
    MatIcon,
    MatInput,
    MatPaginator,
    MatProgressBar,
    MatSelect,
    MatOption,
    MatSlideToggle,
    MatTab,
    MatTabGroup,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../data-access/src/lib/inventory.scss',
  styles: `
    th.sortable {
      cursor: pointer;
      white-space: nowrap;
    }
    th.sortable mat-icon {
      width: 16px;
      height: 16px;
      font-size: 16px;
      vertical-align: middle;
    }
    .blocked {
      color: var(--trishul-danger);
      font: var(--mat-sys-label-small);
      font-weight: 600;
    }
    .filters mat-form-field {
      width: 14rem;
    }
    .filters .search {
      width: 18rem;
    }
    .table-wrap {
      overflow-x: auto;
    }
    .bar {
      display: inline-block;
      width: 5rem;
      height: 0.5rem;
      margin-right: 0.5rem;
      vertical-align: middle;
      border-radius: 999px;
      background: var(--mat-sys-surface-container-high);
      overflow: hidden;
    }
    .bar span {
      display: block;
      height: 100%;
      background: var(--mat-sys-primary);
    }
    .summary {
      margin: 0.75rem 0;
      font: var(--mat-sys-body-medium);
    }
  `,
  template: `
    <trishul-page-header
      title="Rack-wise stock"
      subtitle="What is kept in each rack and bin, and stock kept at a location without a bin"
    />

    <div class="filters">
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Location</mat-label>
        <mat-select
          [value]="query().locationId ?? null"
          (valueChange)="
            patch({ locationId: $event, storageRackId: null, binId: null })
          "
        >
          <mat-option [value]="null">All my locations</mat-option>
          @for (l of locations(); track l.id) {
            <mat-option [value]="l.id">{{ l.code }} · {{ l.name }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Rack</mat-label>
        <mat-select
          [value]="query().storageRackId ?? null"
          (valueChange)="patch({ storageRackId: $event, binId: null })"
        >
          <mat-option [value]="null">Any rack</mat-option>
          @for (r of racks(); track r.id) {
            <mat-option [value]="r.id">{{ r.code }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-form-field
        class="search"
        appearance="outline"
        subscriptSizing="dynamic"
      >
        <mat-icon matPrefix>search</mat-icon>
        <input
          matInput
          type="search"
          placeholder="Item code, name, part no or bin"
          aria-label="Search stock"
          [value]="query().search ?? ''"
          (input)="search$.next($any($event.target).value)"
        />
      </mat-form-field>
      <mat-slide-toggle
        [checked]="!!query().withoutBin"
        (change)="patch({ withoutBin: $event.checked })"
        >Only stock without a bin</mat-slide-toggle
      >
    </div>
    @if (query().binId) {
      <p class="muted">
        Showing one bin.
        <button mat-button type="button" (click)="patch({ binId: null })">
          Show all bins
        </button>
      </p>
    }

    <mat-tab-group
      mat-stretch-tabs="false"
      animationDuration="0ms"
      [selectedIndex]="tab()"
      (selectedIndexChange)="tab.set($event)"
    >
      <mat-tab label="Stock by bin">
        <section class="card">
          @if (loading()) {
            <mat-progress-bar mode="indeterminate" />
          }
          <div class="table-wrap">
            <table class="plain">
              <thead>
                <tr>
                  <th class="sortable" (click)="sortBy('locationCode')">
                    Location<mat-icon>{{ sortIcon('locationCode') }}</mat-icon>
                  </th>
                  <th class="sortable" (click)="sortBy('binCode')">
                    Rack / bin<mat-icon>{{ sortIcon('binCode') }}</mat-icon>
                  </th>
                  <th class="sortable" (click)="sortBy('itemCode')">
                    Item<mat-icon>{{ sortIcon('itemCode') }}</mat-icon>
                  </th>
                  <th class="num sortable" (click)="sortBy('qtyOnHand')">
                    Qty<mat-icon>{{ sortIcon('qtyOnHand') }}</mat-icon>
                  </th>
                  @if (showValue()) {
                    <th class="num">Value (₹)</th>
                  }
                  <th class="sortable" (click)="sortBy('oldestGrnDate')">
                    Oldest GRN<mat-icon>{{
                      sortIcon('oldestGrnDate')
                    }}</mat-icon>
                  </th>
                </tr>
              </thead>
              <tbody>
                @for (r of page()?.items ?? []; track $index) {
                  <tr>
                    <td>
                      {{ r.locationCode }}
                      <div class="muted">{{ r.branchName }}</div>
                    </td>
                    <td>
                      @if (r.binCode) {
                        {{ r.binCode }}
                        <div class="muted">
                          {{
                            r.storageRackCode
                              ? r.binType
                              : r.binType + ' · no rack'
                          }}
                        </div>
                        @if (r.binBlocked) {
                          <div class="blocked">Blocked</div>
                        }
                      } @else {
                        <span class="muted">No bin (at the location)</span>
                      }
                    </td>
                    <td>
                      <a class="name" [routerLink]="['../items', r.itemId]">{{
                        r.itemCode
                      }}</a>
                      <div class="muted">{{ r.itemDescription }}</div>
                    </td>
                    <td class="num">
                      {{ r.qtyOnHand | number: '1.0-3' }} {{ r.uomCode }}
                    </td>
                    @if (showValue()) {
                      <td class="num">{{ r.value | number: '1.2-2' }}</td>
                    }
                    <td>{{ r.oldestGrnDate | date: 'dd MMM yyyy' }}</td>
                  </tr>
                } @empty {
                  <tr>
                    <td [attr.colspan]="showValue() ? 6 : 5" class="empty">
                      @if (loading()) {
                        Loading…
                      } @else {
                        No stock matches.
                      }
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
          <mat-paginator
            [length]="page()?.total ?? 0"
            [pageIndex]="(query().page ?? 1) - 1"
            [pageSize]="query().pageSize ?? 50"
            [pageSizeOptions]="[50, 100, 200]"
            aria-label="Pages of stock"
            (page)="onPage($event)"
          />
        </section>
      </mat-tab>
      <mat-tab label="Rack occupancy">
        <p class="summary">
          {{ occupancy().racks }} rack(s) · {{ occupancy().occupied }} of
          {{ occupancy().bins }} bins in use · {{ occupancy().empty }} empty ·
          {{ occupancy().blocked }} blocked
        </p>
        <section class="card">
          <div class="table-wrap">
            <table class="plain">
              <thead>
                <tr>
                  <th>Location</th>
                  <th>Rack</th>
                  <th>Type</th>
                  <th class="num">Bins</th>
                  <th class="num">In use</th>
                  <th class="num">Empty</th>
                  <th class="num">Blocked</th>
                  <th>Use</th>
                  <th class="num">Qty</th>
                </tr>
              </thead>
              <tbody>
                @for (r of racks(); track r.id) {
                  <tr>
                    <td>{{ r.locationCode }}</td>
                    <td>
                      <a
                        class="name"
                        (click)="showRack(r.locationId, r.id)"
                        (keydown.enter)="showRack(r.locationId, r.id)"
                        tabindex="0"
                        role="link"
                        >{{ r.code }}</a
                      >
                      @if (r.name) {
                        <div class="muted">{{ r.name }}</div>
                      }
                      @if (r.isBlocked) {
                        <div class="blocked">Blocked</div>
                      }
                    </td>
                    <td>{{ r.rackType }}</td>
                    <td class="num">{{ r.binCount }}</td>
                    <td class="num">{{ r.occupiedBins }}</td>
                    <td class="num">{{ r.binCount - r.occupiedBins }}</td>
                    <td class="num">{{ r.blockedBins }}</td>
                    <td>
                      <span class="bar"
                        ><span [style.width.%]="usePct(r)"></span></span
                      >{{ usePct(r) | number: '1.0-0' }}%
                    </td>
                    <td class="num">{{ r.qtyOnHand | number: '1.0-3' }}</td>
                  </tr>
                } @empty {
                  <tr>
                    <td colspan="9" class="empty">
                      No racks yet. Add them under Storage locations.
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        </section>
      </mat-tab>
    </mat-tab-group>
  `,
})
export class BinStockPage {
  private readonly api = inject(ApiClient);
  private readonly route = inject(ActivatedRoute);

  private static number(value: string | null): number | null {
    return value ? Number(value) : null;
  }

  protected readonly query = signal<Query>({
    page: 1,
    pageSize: 50,
    sort: 'binCode',
    locationId: BinStockPage.number(
      this.route.snapshot.queryParamMap.get('locationId'),
    ),
    storageRackId: BinStockPage.number(
      this.route.snapshot.queryParamMap.get('storageRackId'),
    ),
    binId: BinStockPage.number(this.route.snapshot.queryParamMap.get('binId')),
  });
  protected readonly loading = signal(false);
  protected readonly tab = signal(0);
  protected readonly search$ = new Subject<string>();

  protected readonly locations = toSignal(
    this.api
      .call(listLocations, { status: 'active' })
      .pipe(catchError(() => of([]))),
    { initialValue: [] },
  );
  protected readonly racks = toSignal(
    toObservable(computed(() => this.query().locationId ?? null)).pipe(
      switchMap((locationId) =>
        this.api
          .call(listStorageRacks, { locationId, status: 'active' })
          .pipe(catchError(() => of([]))),
      ),
    ),
    { initialValue: [] },
  );
  protected readonly page = toSignal(
    toObservable(this.query).pipe(
      switchMap((query) => {
        this.loading.set(true);
        return this.api.call(listBinStock, query).pipe(
          finalize(() => this.loading.set(false)),
          catchError(() => EMPTY),
        );
      }),
    ),
  );
  /** Totals over the racks shown (the location filter applies). */
  protected readonly occupancy = computed(() => {
    const racks = this.racks();
    const sum = (pick: (r: (typeof racks)[number]) => number) =>
      racks.reduce((total, r) => total + pick(r), 0);
    const bins = sum((r) => r.binCount);
    const occupied = sum((r) => r.occupiedBins);
    return {
      racks: racks.length,
      bins,
      occupied,
      empty: bins - occupied,
      blocked: sum((r) => r.blockedBins),
    };
  });

  protected usePct(rack: { binCount: number; occupiedBins: number }): number {
    return rack.binCount ? (rack.occupiedBins / rack.binCount) * 100 : 0;
  }

  /** From the occupancy list to that rack's stock. */
  protected showRack(locationId: number, storageRackId: number): void {
    this.patch({ locationId, storageRackId, binId: null, withoutBin: false });
    this.tab.set(0);
  }

  /** Values come back empty for users who may not see costs. */
  protected readonly showValue = computed(() =>
    (this.page()?.items ?? []).some((r) => r.value !== null),
  );

  constructor() {
    this.search$
      .pipe(
        map((s) => s.trim()),
        debounceTime(350),
        distinctUntilChanged(),
        takeUntilDestroyed(),
      )
      .subscribe((search) => this.patch({ search: search || null }));
  }

  protected patch(change: Partial<Query>): void {
    this.query.update((q) => ({ ...q, ...change, page: 1 }));
  }

  protected onPage(event: PageEvent): void {
    this.query.update((q) => ({
      ...q,
      page: event.pageIndex + 1,
      pageSize: event.pageSize,
    }));
  }

  protected sortBy(key: string): void {
    const current = this.query().sort ?? '';
    const sort = current === key ? `-${key}` : key;
    this.query.update((q) => ({ ...q, sort, page: 1 }));
  }

  protected sortIcon(key: string): string {
    const current = this.query().sort ?? '';
    if (current === key) return 'arrow_upward';
    if (current === `-${key}`) return 'arrow_downward';
    return '';
  }
}
