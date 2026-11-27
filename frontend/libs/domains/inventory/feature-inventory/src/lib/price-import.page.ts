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
import { MatTableModule } from '@angular/material/table';
import { MatTab, MatTabGroup } from '@angular/material/tabs';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
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
import { AuthStore } from '@trishul/core-auth';
import {
  INV_PRICE_APPROVE,
  INV_PRICE_IMPORT,
  INV_PRICE_IMPORT_VIEW,
  PRICE_IMPORT_SEVERITY,
  PriceImportApi,
  PriceImportBatch,
  PriceImportHistoryQuery,
  PriceImportStatus,
  SapPriceField,
} from '@trishul/inventory-data-access';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { PriceImportBatchView } from './price-import-batch';

const ACCEPT = '.xlsx,.xls,.csv';
const MAX_MB = 10;
const STATUSES: PriceImportStatus[] = [
  'Pending',
  'Pending approval',
  'Processing',
  'Completed',
  'Partially Completed',
  'Failed',
  'Rejected',
];

/**
 * Bulk item price import (tab 1): upload a price file, compare current and new prices, confirm (or send for
 * approval). Price import history (tab 2): every upload, its result, files and the item-wise old/new prices.
 */
@Component({
  selector: 'trishul-price-import-page',
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
    MatTableModule,
    MatTabGroup,
    MatTab,
    PageHeader,
    StatusBadge,
    PriceImportBatchView,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './item-import.scss',
  styles: `
    .options mat-form-field.reason {
      flex: 1 1 22rem;
    }
  `,
  template: `
    <trishul-page-header
      title="Item price import"
      subtitle="Update the prices of existing items in bulk from an Excel or CSV file"
    >
      <a mat-stroked-button routerLink="/inventory/items">
        <mat-icon>list</mat-icon>Items
      </a>
    </trishul-page-header>

    <mat-tab-group
      mat-stretch-tabs="false"
      animationDuration="0ms"
      [selectedIndex]="tabIndex()"
      (selectedIndexChange)="selectTab($event)"
    >
      @if (canImport) {
        <mat-tab label="Bulk price import">
          <div class="toolbar">
            <span class="muted">
              Fill the template with item codes and the new Selling Price (price
              list), Purchase Price (standard cost) and/or MRP. A blank price
              stays as it is; items are never created here.
              @if (options(); as o) {
                Changes over {{ o.maxChangePct }}% need approval.
              }
            </span>
            <span class="spacer"></span>
            <button
              mat-stroked-button
              type="button"
              (click)="api.downloadTemplate()"
            >
              <mat-icon>download</mat-icon>Download template
            </button>
          </div>

          @if (!batch()) {
            <input
              type="file"
              hidden
              #fileInput
              [accept]="accept"
              (change)="
                onFile($any($event.target).files?.[0]); fileInput.value = ''
              "
            />
            <div
              class="drop"
              role="button"
              tabindex="0"
              [class.over]="dragging()"
              (click)="fileInput.click()"
              (keydown.enter)="fileInput.click()"
              (dragover)="$event.preventDefault(); dragging.set(true)"
              (dragleave)="dragging.set(false)"
              (drop)="onDrop($event)"
            >
              <mat-icon>request_quote</mat-icon>
              @if (file(); as f) {
                <span class="title">{{ f.name }}</span>
                <span class="muted"
                  >{{ f.size / 1024 | number: '1.0-0' }} KB · click to choose
                  another file</span
                >
              } @else {
                <span class="title"
                  >Drop the price file here, or click to choose it</span
                >
                <span class="muted"
                  >The template, or the SAP price file (External ID, ZAmount) ·
                  Excel (.xlsx, .xls) or CSV · up to {{ maxMb }} MB</span
                >
              }
            </div>

            <div class="options">
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Price list for selling prices</mat-label>
                <mat-select
                  [value]="priceListId()"
                  (valueChange)="chosenList.set($event)"
                >
                  <mat-option [value]="null"
                    >None (no selling prices)</mat-option
                  >
                  @for (p of options()?.priceLists ?? []; track p.id) {
                    <mat-option [value]="p.id"
                      >{{ p.name }} ({{ p.code
                      }}{{
                        p.principalCode ? ' · ' + p.principalCode : ''
                      }})</mat-option
                    >
                  }
                </mat-select>
              </mat-form-field>
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>SAP file: ZAmount is the</mat-label>
                <mat-select
                  [value]="sapPriceField()"
                  (valueChange)="sapPriceField.set($event)"
                >
                  <mat-option value="MRP">MRP</mat-option>
                  <mat-option value="Selling">Selling price</mat-option>
                  <mat-option value="Purchase">Purchase price</mat-option>
                </mat-select>
                <mat-hint>Only for SAP price files (brand at the top)</mat-hint>
              </mat-form-field>
              <mat-form-field
                class="reason"
                appearance="outline"
                subscriptSizing="dynamic"
              >
                <mat-label>Reason for the change</mat-label>
                <input
                  matInput
                  required
                  maxlength="300"
                  placeholder="e.g. OEM price revision Dec 2026"
                  [value]="reason()"
                  (input)="reason.set($any($event.target).value)"
                />
                <mat-hint>Kept in each item's price history</mat-hint>
              </mat-form-field>
              <button
                mat-flat-button
                type="button"
                [disabled]="!ready()"
                (click)="upload()"
              >
                <mat-icon>fact_check</mat-icon>Upload and compare
              </button>
            </div>
            @if (uploading()) {
              <mat-progress-bar mode="indeterminate" />
            }
          } @else {
            <div class="toolbar">
              <button mat-stroked-button type="button" (click)="startOver()">
                <mat-icon>restart_alt</mat-icon>Import another file
              </button>
            </div>
            <trishul-price-import-batch
              [batch]="batch()!"
              (changed)="batchChanged($event)"
            />
          }
        </mat-tab>
      }

      @if (canViewHistory) {
        <mat-tab label="Price import history">
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
                placeholder="Batch ID, file name or reason"
                aria-label="Search by batch ID, file name or reason"
                (input)="search$.next($any($event.target).value)"
              />
            </mat-form-field>
            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>Status</mat-label>
              <mat-select
                [value]="query().status ?? null"
                (valueChange)="patch({ status: $event })"
              >
                <mat-option [value]="null">All</mat-option>
                @for (s of statuses; track s) {
                  <mat-option [value]="s">{{ s }}</mat-option>
                }
              </mat-select>
            </mat-form-field>
            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>Uploaded by</mat-label>
              <mat-select
                [value]="query().uploadedByUserId ?? null"
                (valueChange)="patch({ uploadedByUserId: $event })"
              >
                <mat-option [value]="null">Anyone</mat-option>
                @for (u of uploaders(); track u.id) {
                  <mat-option [value]="u.id">{{ u.name }}</mat-option>
                }
              </mat-select>
            </mat-form-field>
            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>From</mat-label>
              <input
                matInput
                type="date"
                [value]="query().dateFrom ?? ''"
                (change)="
                  patch({ dateFrom: $any($event.target).value || null })
                "
              />
            </mat-form-field>
            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>To</mat-label>
              <input
                matInput
                type="date"
                [value]="query().dateTo ?? ''"
                (change)="patch({ dateTo: $any($event.target).value || null })"
              />
            </mat-form-field>
          </div>

          <div class="table-card">
            @if (loading()) {
              <mat-progress-bar mode="indeterminate" />
            }
            <div class="table-scroll">
              <table mat-table [dataSource]="history()?.items ?? []">
                <ng-container matColumnDef="batchNo">
                  <th
                    mat-header-cell
                    *matHeaderCellDef
                    class="sortable"
                    (click)="sortBy('batchNo')"
                  >
                    Batch ID<mat-icon>{{ sortIcon('batchNo') }}</mat-icon>
                  </th>
                  <td mat-cell *matCellDef="let b">
                    <a class="name" [routerLink]="[b.id]">{{
                      b.batchNo ?? '#' + b.id
                    }}</a>
                  </td>
                </ng-container>
                <ng-container matColumnDef="fileName">
                  <th
                    mat-header-cell
                    *matHeaderCellDef
                    class="sortable"
                    (click)="sortBy('fileName')"
                  >
                    File<mat-icon>{{ sortIcon('fileName') }}</mat-icon>
                  </th>
                  <td mat-cell *matCellDef="let b">
                    {{ b.fileName }}
                    <div class="muted">{{ b.reason }}</div>
                  </td>
                </ng-container>
                <ng-container matColumnDef="uploadedAt">
                  <th
                    mat-header-cell
                    *matHeaderCellDef
                    class="sortable"
                    (click)="sortBy('uploadedAt')"
                  >
                    Uploaded<mat-icon>{{ sortIcon('uploadedAt') }}</mat-icon>
                  </th>
                  <td mat-cell *matCellDef="let b">
                    {{ b.uploadedAt | date: 'dd MMM yyyy, HH:mm' }}
                    <div class="muted">{{ b.uploadedByName ?? '—' }}</div>
                  </td>
                </ng-container>
                <ng-container matColumnDef="totalRows">
                  <th
                    mat-header-cell
                    *matHeaderCellDef
                    class="sortable num"
                    (click)="sortBy('totalRows')"
                  >
                    Total<mat-icon>{{ sortIcon('totalRows') }}</mat-icon>
                  </th>
                  <td mat-cell *matCellDef="let b" class="num">
                    {{ b.totalRows | number }}
                  </td>
                </ng-container>
                <ng-container matColumnDef="counts">
                  <th mat-header-cell *matHeaderCellDef>
                    Updated · failed · skipped
                  </th>
                  <td mat-cell *matCellDef="let b">
                    <div class="counts">
                      @if (
                        b.status === 'Pending' ||
                        b.status === 'Pending approval'
                      ) {
                        <span class="chip"
                          >{{ b.changedCount | number }} to change</span
                        >
                      } @else {
                        <span class="chip success"
                          >{{ b.updatedCount | number }} updated</span
                        >
                      }
                      <span class="chip danger"
                        >{{ b.invalidCount | number }} failed</span
                      >
                      <span class="chip warn"
                        >{{ b.duplicateCount | number }} skipped</span
                      >
                    </div>
                  </td>
                </ng-container>
                <ng-container matColumnDef="status">
                  <th
                    mat-header-cell
                    *matHeaderCellDef
                    class="sortable"
                    (click)="sortBy('status')"
                  >
                    Status<mat-icon>{{ sortIcon('status') }}</mat-icon>
                  </th>
                  <td mat-cell *matCellDef="let b">
                    <trishul-status-badge
                      [status]="b.status"
                      [severities]="severity"
                    />
                    @if (b.errorMessage) {
                      <div class="muted">{{ b.errorMessage }}</div>
                    }
                  </td>
                </ng-container>
                <ng-container matColumnDef="files">
                  <th mat-header-cell *matHeaderCellDef>Files</th>
                  <td mat-cell *matCellDef="let b">
                    @if (b.hasFile) {
                      <button
                        mat-button
                        type="button"
                        (click)="api.downloadFile(b)"
                      >
                        <mat-icon>download</mat-icon>File
                      </button>
                    }
                    @if (b.invalidCount + b.duplicateCount + b.failedCount) {
                      <button
                        mat-button
                        type="button"
                        (click)="api.downloadErrorReport(b)"
                      >
                        <mat-icon>summarize</mat-icon>Errors
                      </button>
                    }
                  </td>
                </ng-container>
                <tr
                  mat-header-row
                  *matHeaderRowDef="historyColumns; sticky: true"
                ></tr>
                <tr mat-row *matRowDef="let row; columns: historyColumns"></tr>
                <tr class="mat-mdc-row" *matNoDataRow>
                  <td
                    class="muted empty"
                    [attr.colspan]="historyColumns.length"
                  >
                    @if (loading()) {
                      Loading…
                    } @else {
                      No price imports found.
                    }
                  </td>
                </tr>
              </table>
            </div>
            <mat-paginator
              [length]="history()?.total ?? 0"
              [pageIndex]="(query().page ?? 1) - 1"
              [pageSize]="query().pageSize ?? 20"
              [pageSizeOptions]="[20, 50, 100]"
              aria-label="Pages of price imports"
              (page)="onPage($event)"
            />
          </div>
        </mat-tab>
      }
    </mat-tab-group>
  `,
})
export class PriceImportPage {
  protected readonly api = inject(PriceImportApi);
  private readonly auth = inject(AuthStore);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly canImport = this.auth.hasPermission(INV_PRICE_IMPORT);
  protected readonly canViewHistory =
    this.canImport ||
    this.auth.hasAnyPermission([INV_PRICE_IMPORT_VIEW, INV_PRICE_APPROVE]);
  protected readonly accept = ACCEPT;
  protected readonly maxMb = MAX_MB;
  protected readonly statuses = STATUSES;
  protected readonly severity = PRICE_IMPORT_SEVERITY;
  protected readonly historyColumns = [
    'batchNo',
    'fileName',
    'uploadedAt',
    'totalRows',
    'counts',
    'status',
    'files',
  ];

  /** ?tab=history opens the history (also the only tab for users who can't import). */
  protected readonly tabIndex = toSignal(
    this.route.queryParamMap.pipe(
      map((p) => (this.canImport && p.get('tab') === 'history' ? 1 : 0)),
    ),
    { initialValue: 0 },
  );

  // ------------------------------------------------------------------ import tab

  protected readonly options = toSignal(
    this.canImport
      ? this.api.options().pipe(catchError(() => of(null)))
      : of(null),
    { initialValue: null },
  );
  protected readonly chosenList = signal<number | null | undefined>(undefined);
  /** What the user picked, else the default Retail list. */
  protected readonly priceListId = computed(() => {
    const chosen = this.chosenList();
    return chosen !== undefined
      ? chosen
      : (this.options()?.defaultPriceListId ?? null);
  });
  protected readonly sapPriceField = signal<SapPriceField>('MRP');
  protected readonly reason = signal('');
  protected readonly file = signal<File | null>(null);
  protected readonly dragging = signal(false);
  protected readonly uploading = signal(false);
  protected readonly batch = signal<PriceImportBatch | null>(null);
  protected readonly ready = computed(
    () =>
      this.file() !== null &&
      this.reason().trim().length >= 3 &&
      !this.uploading(),
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

  protected onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(false);
    this.onFile(event.dataTransfer?.files?.[0]);
  }

  protected onFile(file: File | undefined): void {
    if (!file) return;
    const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    if (!ACCEPT.split(',').includes(extension)) {
      this.notify('Choose an Excel (.xlsx, .xls) or CSV (.csv) file.');
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      this.notify(`The file is larger than ${MAX_MB} MB.`);
      return;
    }
    this.file.set(file);
  }

  protected upload(): void {
    const file = this.file();
    if (!file || !this.ready()) return;
    this.uploading.set(true);
    this.api
      .upload(file, {
        reason: this.reason().trim(),
        priceListId: this.priceListId(),
        sapPriceField: this.sapPriceField(),
      })
      .pipe(
        finalize(() => this.uploading.set(false)),
        catchError(() => EMPTY), // the error toast has been shown
      )
      .subscribe((batch) => {
        this.batch.set(batch);
        this.reloadHistory();
      });
  }

  protected batchChanged(batch: PriceImportBatch): void {
    this.batch.set(batch);
    this.reloadHistory();
  }

  protected startOver(): void {
    this.batch.set(null);
    this.file.set(null);
  }

  protected selectTab(index: number): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { tab: index === 1 || !this.canImport ? 'history' : null },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
  }

  // ------------------------------------------------------------------ history tab

  protected readonly query = signal<PriceImportHistoryQuery>({
    page: 1,
    pageSize: 20,
    sort: '-uploadedAt',
  });
  private readonly refresh = signal(0);
  protected readonly loading = signal(false);
  protected readonly search$ = new Subject<string>();

  protected readonly history = toSignal(
    toObservable(
      computed(() => ({ query: this.query(), refresh: this.refresh() })),
    ).pipe(
      switchMap(({ query }) => {
        if (!this.canViewHistory) return of(null);
        this.loading.set(true);
        return this.api.history(query).pipe(
          finalize(() => this.loading.set(false)),
          catchError(() => of(null)),
        );
      }),
    ),
  );

  protected readonly uploaders = toSignal(
    toObservable(this.refresh).pipe(
      switchMap(() =>
        this.canViewHistory
          ? this.api.uploaders().pipe(catchError(() => of([])))
          : of([]),
      ),
    ),
    { initialValue: [] },
  );

  protected patch(change: Partial<PriceImportHistoryQuery>): void {
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
    const sort = current === `-${key}` ? key : `-${key}`;
    this.query.update((q) => ({ ...q, sort, page: 1 }));
  }

  protected sortIcon(key: string): string {
    const current = this.query().sort ?? '';
    if (current === key) return 'arrow_upward';
    if (current === `-${key}`) return 'arrow_downward';
    return '';
  }

  private reloadHistory(): void {
    this.refresh.update((n) => n + 1);
  }

  private notify(message: string): void {
    this.snackBar.open(message, 'Dismiss', { duration: 5000 });
  }
}
