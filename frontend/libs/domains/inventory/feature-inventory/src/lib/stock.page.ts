import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
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
import { MatSort, MatSortHeader, Sort } from '@angular/material/sort';
import { MatTableModule } from '@angular/material/table';
import { RouterLink } from '@angular/router';
import {
  ApiClient,
  ListStock$Params,
  RackOut,
  listItemCategories,
  listStock,
} from '@trishul/core-api';
import { HasPermission } from '@trishul/core-auth';
import { PageHeader } from '@trishul/shared-ui';
import {
  Subject,
  catchError,
  debounceTime,
  distinctUntilChanged,
  of,
} from 'rxjs';
import {
  INV_STOCK_VIEW,
  INV_TRANSFER_MANAGE,
} from '@trishul/inventory-data-access';
import {
  InventoryLookups,
  ageClass,
  downloadCsv,
  n0,
  pagedList,
} from '@trishul/inventory-data-access';

/** Stock on hand per GRN batch and place: what is where, since when, at what cost. */
@Component({
  selector: 'trishul-stock-page',
  imports: [
    DatePipe,
    DecimalPipe,
    RouterLink,
    MatTableModule,
    MatSort,
    MatSortHeader,
    MatPaginator,
    MatProgressBar,
    MatFormField,
    MatLabel,
    MatPrefix,
    MatInput,
    MatSelect,
    MatOption,
    MatButton,
    MatIcon,
    HasPermission,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../data-access/src/lib/inventory.scss',
  template: `
    <trishul-page-header
      title="Stock by batch"
      subtitle="Every GRN batch on hand, by branch, location and rack; age counts from the GRN date"
    >
      <a
        mat-stroked-button
        routerLink="../ageing"
        *trishulHasPermission="report"
        ><mat-icon>bar_chart</mat-icon>Ageing report</a
      >
      <button mat-stroked-button (click)="export()">
        <mat-icon>download</mat-icon>Export page
      </button>
      <a
        mat-flat-button
        routerLink="../transfers/new"
        *trishulHasPermission="transfer"
        ><mat-icon>swap_horiz</mat-icon>Transfer</a
      >
    </trishul-page-header>

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
          aria-label="Search stock"
          [value]="query().search ?? ''"
          (input)="search$.next($any($event.target).value)"
        />
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Branch / warehouse</mat-label>
        <mat-select
          [value]="query().branchId ?? null"
          (valueChange)="
            update({ branchId: $event, locationId: null, binId: null })
          "
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
          (valueChange)="locationChanged($event)"
        >
          <mat-option [value]="null">All</mat-option>
          @for (l of locationsShown(); track l.id) {
            <mat-option [value]="l.id">{{ l.code }} · {{ l.name }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Rack</mat-label>
        <mat-select
          [value]="query().binId ?? null"
          [disabled]="!query().locationId"
          (valueChange)="update({ binId: $event })"
        >
          <mat-option [value]="null">All</mat-option>
          @for (r of racks(); track r.id) {
            <mat-option [value]="r.id">{{ r.code }}</mat-option>
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
      @if (query().itemId) {
        <button mat-stroked-button (click)="update({ itemId: null })">
          <mat-icon>close</mat-icon>One item only
        </button>
      }
    </div>

    <div class="table-card">
      <div class="progress">
        @if (list.loading()) {
          <mat-progress-bar mode="indeterminate" />
        }
      </div>
      <div class="table-scroll">
        <table
          mat-table
          class="wide"
          [dataSource]="list.items()"
          matSort
          matSortActive="grnDate"
          matSortDirection="asc"
          (matSortChange)="onSort($event)"
        >
          <ng-container matColumnDef="itemCode">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>Item</th>
            <td mat-cell *matCellDef="let s">
              <a class="name" [routerLink]="['../items', s.itemId]">{{
                s.itemCode
              }}</a>
              <div class="muted">{{ s.itemDescription }}</div>
            </td>
          </ng-container>
          <ng-container matColumnDef="grnDate">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>
              GRN / batch
            </th>
            <td mat-cell *matCellDef="let s" class="nowrap">
              {{ s.grnNo }} · {{ s.grnDate | date: 'dd MMM yyyy' }}
              <div class="muted">
                {{ s.lotNo }} · {{ s.sourceType
                }}{{ s.supplierName ? ' · ' + s.supplierName : '' }}
              </div>
            </td>
          </ng-container>
          <ng-container matColumnDef="age">
            <th mat-header-cell *matHeaderCellDef>Age</th>
            <td mat-cell *matCellDef="let s">
              <span [class]="'age ' + ageClass(s.ageDays)"
                >{{ s.ageDays }} days</span
              >
            </td>
          </ng-container>
          <ng-container matColumnDef="locationCode">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>Where</th>
            <td mat-cell *matCellDef="let s">
              {{ s.branchName }}
              <div class="muted">{{ s.locationName }}</div>
            </td>
          </ng-container>
          <ng-container matColumnDef="binCode">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>Rack</th>
            <td mat-cell *matCellDef="let s">{{ s.binCode ?? '—' }}</td>
          </ng-container>
          <ng-container matColumnDef="qtyOnHand">
            <th mat-header-cell *matHeaderCellDef mat-sort-header class="num">
              Qty
            </th>
            <td mat-cell *matCellDef="let s" class="num">
              {{ s.qtyOnHand | number: '1.0-3' }} {{ s.uomCode }}
            </td>
          </ng-container>
          <ng-container matColumnDef="unitCost">
            <th mat-header-cell *matHeaderCellDef class="num">GRN cost</th>
            <td mat-cell *matCellDef="let s" class="num">
              {{ s.unitCost | number: '1.2-2' }}
            </td>
          </ng-container>
          <ng-container matColumnDef="value">
            <th mat-header-cell *matHeaderCellDef mat-sort-header class="num">
              Value (₹)
            </th>
            <td mat-cell *matCellDef="let s" class="num">
              {{ s.value | number: '1.2-2' }}
            </td>
          </ng-container>
          <tr mat-header-row *matHeaderRowDef="columns; sticky: true"></tr>
          <tr mat-row *matRowDef="let row; columns: columns"></tr>
          <tr class="mat-mdc-row" *matNoDataRow>
            <td class="empty" [attr.colspan]="columns.length">
              {{
                list.loading() ? 'Loading…' : 'No stock matches these filters.'
              }}
            </td>
          </tr>
        </table>
      </div>
      <mat-paginator
        [length]="list.total()"
        [pageIndex]="(query().page ?? 1) - 1"
        [pageSize]="query().pageSize"
        [pageSizeOptions]="[50, 100, 200]"
        aria-label="Pages of stock"
        (page)="onPage($event)"
      />
    </div>
  `,
})
export class StockPage {
  private readonly api = inject(ApiClient);
  private readonly lookups = inject(InventoryLookups);
  protected readonly report = INV_STOCK_VIEW;
  protected readonly transfer = INV_TRANSFER_MANAGE;
  protected readonly ageClass = ageClass;
  protected readonly columns = [
    'itemCode',
    'grnDate',
    'age',
    'locationCode',
    'binCode',
    'qtyOnHand',
    'unitCost',
    'value',
  ];

  // Query parameters, e.g. from the ageing report: /inventory/stock?locationId=3&binId=7
  readonly itemId = input<string>();
  readonly branchId = input<string>();
  readonly locationId = input<string>();
  readonly binId = input<string>();
  readonly search = input<string>();

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
  protected readonly racks = signal<RackOut[]>([]);
  protected readonly query = signal<ListStock$Params>({
    page: 1,
    pageSize: 50,
  });
  protected readonly list = pagedList(this.query, (q) =>
    this.api.call(listStock, q),
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
    queueMicrotask(() => {
      const id = (value: string | undefined) => (value ? Number(value) : null);
      const locationId = id(this.locationId());
      this.query.set({
        page: 1,
        pageSize: 50,
        itemId: id(this.itemId()),
        branchId: id(this.branchId()),
        locationId,
        binId: id(this.binId()),
        search: this.search() || null,
      });
      if (locationId)
        this.lookups
          .racks(locationId)
          .subscribe((racks) => this.racks.set(racks));
    });
  }

  protected update(change: Partial<ListStock$Params>): void {
    this.query.update((q) => ({ ...q, ...change, page: change.page ?? 1 }));
  }

  protected locationChanged(locationId: number | null): void {
    this.update({ locationId, binId: null });
    this.racks.set([]);
    if (locationId)
      this.lookups
        .racks(locationId)
        .subscribe((racks) => this.racks.set(racks));
  }

  protected onSort(sort: Sort): void {
    this.update({
      sort: sort.direction
        ? `${sort.direction === 'desc' ? '-' : ''}${sort.active}`
        : null,
    });
  }

  protected onPage(event: PageEvent): void {
    this.update({ page: event.pageIndex + 1, pageSize: event.pageSize });
  }

  protected export(): void {
    downloadCsv(
      'stock-by-batch.csv',
      [
        'Item code',
        'Description',
        'GRN no',
        'GRN date',
        'Age (days)',
        'Batch',
        'Branch',
        'Location',
        'Rack',
        'Qty',
        'Unit',
        'GRN cost',
        'Value',
      ],
      this.list
        .items()
        .map((s) => [
          s.itemCode,
          s.itemDescription,
          s.grnNo,
          s.grnDate,
          s.ageDays,
          s.lotNo,
          s.branchName,
          s.locationName,
          s.binCode,
          n0(s.qtyOnHand),
          s.uomCode,
          n0(s.unitCost),
          n0(s.value),
        ]),
    );
  }
}
