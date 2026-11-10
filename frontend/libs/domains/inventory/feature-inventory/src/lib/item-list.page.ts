import { DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  inject,
  input,
  signal,
} from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
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
  ListItems$Params,
  listItemCategories,
  listItems,
} from '@trishul/core-api';
import { HasPermission } from '@trishul/core-auth';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import {
  Subject,
  catchError,
  debounceTime,
  distinctUntilChanged,
  of,
} from 'rxjs';
import { INV_ITEM_MANAGE } from '@trishul/inventory-data-access';
import { n0, pagedList } from '@trishul/inventory-data-access';

const ACTIVE: Record<string, StatusSeverity> = {
  Active: 'success',
  Inactive: 'neutral',
};

/** Item master with stock on hand at the user's locations. */
@Component({
  selector: 'trishul-item-list-page',
  imports: [
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
    MatCheckbox,
    MatButton,
    MatIcon,
    HasPermission,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../data-access/src/lib/inventory.scss',
  template: `
    <trishul-page-header
      title="Items"
      subtitle="Item master with stock on hand at your locations"
    >
      <a mat-stroked-button routerLink="../setup"
        ><mat-icon>tune</mat-icon>Categories, units & prices</a
      >
      <a mat-flat-button routerLink="new" *trishulHasPermission="manage">
        <mat-icon>add</mat-icon>Add item
      </a>
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
          placeholder="Code, description or OEM part no"
          aria-label="Search items"
          (input)="search$.next($any($event.target).value)"
        />
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Category</mat-label>
        <mat-select
          [value]="query().categoryId ?? null"
          (valueChange)="update({ categoryId: $event })"
        >
          <mat-option [value]="null">All categories</mat-option>
          @for (c of categories(); track c.id) {
            <mat-option [value]="c.id">{{ c.path }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Type</mat-label>
        <mat-select
          [value]="query().itemType ?? null"
          (valueChange)="update({ itemType: $event })"
        >
          <mat-option [value]="null">All types</mat-option>
          <mat-option value="Stock">Stock</mat-option>
          <mat-option value="Non stock">Non stock</mat-option>
          <mat-option value="Service">Service</mat-option>
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Status</mat-label>
        <mat-select
          [value]="query().status"
          (valueChange)="update({ status: $event })"
        >
          <mat-option value="active">Active</mat-option>
          <mat-option value="inactive">Inactive</mat-option>
          <mat-option value="all">All</mat-option>
        </mat-select>
      </mat-form-field>
      <mat-checkbox
        [checked]="!!query().belowReorder"
        (change)="update({ belowReorder: $event.checked })"
      >
        At or below reorder level
      </mat-checkbox>
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
          matSortActive="itemCode"
          matSortDirection="asc"
          (matSortChange)="onSort($event)"
        >
          <ng-container matColumnDef="itemCode">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>Code</th>
            <td mat-cell *matCellDef="let i" class="nowrap">
              <a class="name" [routerLink]="[i.id]">{{ i.itemCode }}</a>
              @if (i.principalCode) {
                <div class="muted">{{ i.principalCode }}</div>
              }
            </td>
          </ng-container>
          <ng-container matColumnDef="description">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>
              Description
            </th>
            <td mat-cell *matCellDef="let i">
              <div>{{ i.description }}</div>
              @if (i.oemPartNumber) {
                <div class="muted">OEM {{ i.oemPartNumber }}</div>
              }
            </td>
          </ng-container>
          <ng-container matColumnDef="categoryName">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>Category</th>
            <td mat-cell *matCellDef="let i">
              {{ i.categoryName }}
              <div class="muted">{{ i.itemType }}</div>
            </td>
          </ng-container>
          <ng-container matColumnDef="qtyOnHand">
            <th mat-header-cell *matHeaderCellDef mat-sort-header class="num">
              On hand
            </th>
            <td
              mat-cell
              *matCellDef="let i"
              class="num"
              [class.negative]="belowReorder(i)"
            >
              {{ i.qtyOnHand | number: '1.0-3' }} {{ i.uomCode }}
              @if (belowReorder(i)) {
                <div class="muted">
                  Reorder at {{ i.reorderLevel | number: '1.0-3' }}
                </div>
              }
            </td>
          </ng-container>
          <ng-container matColumnDef="stockValue">
            <th mat-header-cell *matHeaderCellDef class="num">
              Stock value (₹)
            </th>
            <td mat-cell *matCellDef="let i" class="num">
              {{ i.stockValue | number: '1.2-2' }}
            </td>
          </ng-container>
          <ng-container matColumnDef="standardCost">
            <th mat-header-cell *matHeaderCellDef mat-sort-header class="num">
              Std cost (₹)
            </th>
            <td mat-cell *matCellDef="let i" class="num">
              {{
                i.standardCost !== null
                  ? (i.standardCost | number: '1.2-2')
                  : '—'
              }}
            </td>
          </ng-container>
          <ng-container matColumnDef="status">
            <th mat-header-cell *matHeaderCellDef>Status</th>
            <td mat-cell *matCellDef="let i">
              <trishul-status-badge
                [status]="i.isActive ? 'Active' : 'Inactive'"
                [severities]="active"
              />
            </td>
          </ng-container>
          <tr mat-header-row *matHeaderRowDef="columns; sticky: true"></tr>
          <tr mat-row *matRowDef="let row; columns: columns"></tr>
          <tr class="mat-mdc-row" *matNoDataRow>
            <td class="empty" [attr.colspan]="columns.length">
              {{
                list.loading() ? 'Loading…' : 'No items match these filters.'
              }}
            </td>
          </tr>
        </table>
      </div>
      <mat-paginator
        [length]="list.total()"
        [pageIndex]="(query().page ?? 1) - 1"
        [pageSize]="query().pageSize"
        [pageSizeOptions]="[20, 50, 100]"
        aria-label="Pages of items"
        (page)="onPage($event)"
      />
    </div>
  `,
})
export class ItemListPage {
  private readonly api = inject(ApiClient);
  protected readonly manage = INV_ITEM_MANAGE;
  protected readonly active = ACTIVE;
  protected readonly columns = [
    'itemCode',
    'description',
    'categoryName',
    'qtyOnHand',
    'stockValue',
    'standardCost',
    'status',
  ];

  /** Opened from a category on the setup screen: /inventory/items?categoryId=… */
  readonly categoryId = input<string>();

  protected readonly query = signal<ListItems$Params>({
    page: 1,
    pageSize: 20,
    status: 'active',
  });
  protected readonly list = pagedList(this.query, (q) =>
    this.api.call(listItems, q),
  );
  protected readonly categories = toSignal(
    this.api
      .call(listItemCategories, { status: 'active' })
      .pipe(catchError(() => of([]))),
    { initialValue: [] },
  );
  protected readonly search$ = new Subject<string>();

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) => this.update({ search: search.trim() || null }));
    queueMicrotask(() => {
      const category = Number(this.categoryId());
      if (category) this.update({ categoryId: category });
    });
  }

  protected update(change: Partial<ListItems$Params>): void {
    this.query.update((q) => ({ ...q, ...change, page: change.page ?? 1 }));
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

  protected belowReorder(item: {
    qtyOnHand: string;
    reorderLevel: string | null;
  }): boolean {
    return (
      item.reorderLevel !== null && n0(item.qtyOnHand) <= n0(item.reorderLevel)
    );
  }
}
