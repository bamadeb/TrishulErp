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
import { provideNativeDateAdapter } from '@angular/material/core';
import {
  MatDatepicker,
  MatDatepickerInput,
  MatDatepickerToggle,
} from '@angular/material/datepicker';
import {
  MatFormField,
  MatLabel,
  MatPrefix,
  MatSuffix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { Router, RouterLink } from '@angular/router';
import {
  AdjustmentListItem,
  ApiClient,
  ListTransfers$Params,
  TransferListItem,
  listAdjustments,
  listTransfers,
} from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import { PageHeader } from '@trishul/shared-ui';
import { Observable, Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import {
  INV_STOCK_ADJUST,
  INV_TRANSFER_MANAGE,
} from '@trishul/inventory-data-access';
import { InventoryLookups, isoDate } from '@trishul/inventory-data-access';

export type DocumentKind = 'transfer' | 'adjustment';
type Row = TransferListItem | AdjustmentListItem;

const TEXT: Record<
  DocumentKind,
  {
    title: string;
    subtitle: string;
    add: string;
    search: string;
    permission: string;
  }
> = {
  transfer: {
    title: 'Stock transfers',
    subtitle:
      'Between branches, warehouses and racks; batches keep their original GRN date',
    add: 'New transfer',
    search: 'Transfer no',
    permission: INV_TRANSFER_MANAGE,
  },
  adjustment: {
    title: 'Stock adjustments',
    subtitle: 'Increases and decreases with a reason and who posted them',
    add: 'New adjustment',
    search: 'Adjustment no',
    permission: INV_STOCK_ADJUST,
  },
};

/** Transfer or adjustment history (the route's data.kind), newest first. */
@Component({
  selector: 'trishul-document-list-page',
  imports: [
    DatePipe,
    DecimalPipe,
    RouterLink,
    MatButton,
    MatIcon,
    MatFormField,
    MatLabel,
    MatPrefix,
    MatSuffix,
    MatInput,
    MatSelect,
    MatOption,
    MatDatepicker,
    MatDatepickerInput,
    MatDatepickerToggle,
    MatPaginator,
    MatProgressBar,
    PageHeader,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../../../data-access/src/lib/inventory.scss',
  template: `
    <trishul-page-header [title]="text().title" [subtitle]="text().subtitle">
      @if (canAdd()) {
        <a mat-flat-button routerLink="new"
          ><mat-icon>add</mat-icon>{{ text().add }}</a
        >
      }
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
          [placeholder]="text().search"
          aria-label="Search"
          (input)="search$.next($any($event.target).value)"
        />
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Branch / warehouse</mat-label>
        <mat-select
          [value]="query().branchId ?? null"
          (valueChange)="update({ branchId: $event })"
        >
          <mat-option [value]="null">All</mat-option>
          @for (b of branches(); track b.id) {
            <mat-option [value]="b.id">{{ b.name }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>From</mat-label>
        <input
          matInput
          [matDatepicker]="fromPicker"
          (dateChange)="
            update({ fromDate: $event.value ? iso($event.value) : null })
          "
        />
        <mat-datepicker-toggle matSuffix [for]="fromPicker" />
        <mat-datepicker #fromPicker />
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>To</mat-label>
        <input
          matInput
          [matDatepicker]="toPicker"
          (dateChange)="
            update({ toDate: $event.value ? iso($event.value) : null })
          "
        />
        <mat-datepicker-toggle matSuffix [for]="toPicker" />
        <mat-datepicker #toPicker />
      </mat-form-field>
    </div>

    <div class="table-card">
      <div class="progress">
        @if (loading()) {
          <mat-progress-bar mode="indeterminate" />
        }
      </div>
      <div class="table-scroll">
        <table class="plain wide">
          @switch (kind()) {
            @case ('transfer') {
              <thead>
                <tr>
                  <th>Transfer no</th>
                  <th>Date</th>
                  <th>From</th>
                  <th>To</th>
                  <th class="num">Lines</th>
                  <th class="num">Qty</th>
                </tr>
              </thead>
              <tbody>
                @for (t of transfers(); track t.id) {
                  <tr>
                    <td>
                      <a class="name" [routerLink]="[t.id]">{{
                        t.transferNo
                      }}</a>
                    </td>
                    <td class="nowrap">
                      {{ t.transferDate | date: 'dd MMM yyyy' }}
                    </td>
                    <td>
                      {{ t.fromBranchName }}
                      <div class="muted">{{ t.fromLocationName }}</div>
                    </td>
                    <td>
                      {{ t.toBranchName }}
                      <div class="muted">{{ t.toLocationName }}</div>
                    </td>
                    <td class="num">{{ t.lineCount }}</td>
                    <td class="num">{{ t.totalQty | number: '1.0-3' }}</td>
                  </tr>
                } @empty {
                  <tr>
                    <td colspan="6" class="empty">
                      {{ loading() ? 'Loading…' : 'No transfers match.' }}
                    </td>
                  </tr>
                }
              </tbody>
            }
            @case ('adjustment') {
              <thead>
                <tr>
                  <th>Adjustment no</th>
                  <th>Date</th>
                  <th>Location</th>
                  <th>Reason</th>
                  <th class="num">Added</th>
                  <th class="num">Removed</th>
                  <th>Posted by</th>
                </tr>
              </thead>
              <tbody>
                @for (a of adjustments(); track a.id) {
                  <tr>
                    <td>
                      <a class="name" [routerLink]="[a.id]">{{
                        a.adjustmentNo
                      }}</a>
                    </td>
                    <td class="nowrap">
                      {{ a.adjustmentDate | date: 'dd MMM yyyy' }}
                    </td>
                    <td>
                      {{ a.branchName }}
                      <div class="muted">{{ a.locationName }}</div>
                    </td>
                    <td>{{ a.reason }}</td>
                    <td class="num positive">
                      {{ a.qtyIn | number: '1.0-3' }}
                    </td>
                    <td class="num negative">
                      {{ a.qtyOut | number: '1.0-3' }}
                    </td>
                    <td>
                      {{ a.postedBy ?? '—' }}
                      <div class="muted">
                        {{ a.postedAt | date: 'dd MMM, HH:mm' }}
                      </div>
                    </td>
                  </tr>
                } @empty {
                  <tr>
                    <td colspan="7" class="empty">
                      {{ loading() ? 'Loading…' : 'No adjustments match.' }}
                    </td>
                  </tr>
                }
              </tbody>
            }
          }
        </table>
      </div>
      <mat-paginator
        [length]="total()"
        [pageIndex]="(query().page ?? 1) - 1"
        [pageSize]="query().pageSize"
        [pageSizeOptions]="[20, 50, 100]"
        aria-label="Pages"
        (page)="onPage($event)"
      />
    </div>
  `,
})
export class DocumentListPage {
  private readonly api = inject(ApiClient);
  private readonly auth = inject(AuthStore);
  private readonly lookups = inject(InventoryLookups);
  protected readonly router = inject(Router);

  /** From the route's data. */
  readonly kind = input.required<DocumentKind>();

  protected readonly text = computed(() => TEXT[this.kind()]);
  protected readonly canAdd = computed(() =>
    this.auth.hasPermission(TEXT[this.kind()].permission),
  );
  protected readonly branches = toSignal(this.lookups.branches(), {
    initialValue: [],
  });
  protected readonly query = signal<ListTransfers$Params>({
    page: 1,
    pageSize: 20,
  });
  protected readonly search$ = new Subject<string>();
  protected readonly iso = isoDate;

  private readonly rows = signal<Row[]>([]);
  protected readonly total = signal(0);
  protected readonly loading = signal(false);
  protected readonly transfers = computed(
    () => this.rows() as TransferListItem[],
  );
  protected readonly adjustments = computed(
    () => this.rows() as AdjustmentListItem[],
  );

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) => this.update({ search: search.trim() || null }));
    queueMicrotask(() => this.load());
  }

  protected update(change: Partial<ListTransfers$Params>): void {
    this.query.update((q) => ({ ...q, ...change, page: change.page ?? 1 }));
    this.load();
  }

  protected onPage(event: PageEvent): void {
    this.update({ page: event.pageIndex + 1, pageSize: event.pageSize });
  }

  private load(): void {
    const q = this.query();
    const request: Observable<{ items: Row[]; total: number }> =
      this.kind() === 'transfer'
        ? this.api.call(listTransfers, q)
        : this.api.call(listAdjustments, q);
    this.loading.set(true);
    request.subscribe({
      next: (page) => {
        this.rows.set(page.items);
        this.total.set(page.total);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }
}
