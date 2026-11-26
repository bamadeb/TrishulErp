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
  tap,
} from 'rxjs';
import { AuthStore } from '@trishul/core-auth';
import {
  INV_ITEM_IMPORT,
  INV_ITEM_IMPORT_OVERWRITE,
  INV_ITEM_IMPORT_VIEW,
  ITEM_IMPORT_SEVERITY,
  ItemImportBatch,
  ItemImportDuplicateMode,
  ItemImportHistoryQuery,
  ItemImportStatus,
  ItemListImportApi,
} from '@trishul/inventory-data-access';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { ItemImportBatchView } from './item-import-batch';

const ACCEPT = '.xlsx,.xls,.csv';
const MAX_MB = 10;
const STATUSES: ItemImportStatus[] = [
  'Pending',
  'Processing',
  'Completed',
  'Partially Completed',
  'Failed',
];

/**
 * Item list import: upload an Excel / CSV item list, check it, review the rows and import the valid ones
 * (tab 1); every upload with its counts, files and row results (tab 2).
 */
@Component({
  selector: 'trishul-item-list-import-page',
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
    ItemImportBatchView,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './item-import.scss',
  template: `
    <trishul-page-header
      title="Item list import"
      subtitle="Add items in bulk from an Excel or CSV file, and see every import"
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
        <mat-tab label="Import items">
          <div class="toolbar">
            <span class="muted">
              Fill the sample template (codes of categories, units and brands
              are on its Lists sheet), then upload it. Nothing is imported until
              you confirm.
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
              <mat-icon>upload_file</mat-icon>
              @if (file(); as f) {
                <span class="title">{{ f.name }}</span>
                <span class="muted"
                  >{{ f.size / 1024 | number: '1.0-0' }} KB · click to choose
                  another file</span
                >
              } @else {
                <span class="title"
                  >Drop the item list here, or click to choose it</span
                >
                <span class="muted"
                  >Excel (.xlsx, .xls) or CSV · up to {{ maxMb }} MB and 10,000
                  rows</span
                >
              }
            </div>

            <div class="options">
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Items that already exist</mat-label>
                <mat-select
                  [value]="duplicateMode()"
                  (valueChange)="duplicateMode.set($event)"
                  [disabled]="!canOverwrite"
                  aria-label="What to do with items that already exist"
                >
                  <mat-option value="Skip">Skip them (no change)</mat-option>
                  <mat-option value="Update"
                    >Update them from the filled cells</mat-option
                  >
                </mat-select>
                @if (!canOverwrite) {
                  <mat-hint
                    >Updating existing items needs extra permission.</mat-hint
                  >
                }
              </mat-form-field>
              <span class="spacer"></span>
              <button
                mat-flat-button
                type="button"
                [disabled]="!file() || uploading()"
                (click)="upload()"
              >
                <mat-icon>fact_check</mat-icon>Upload and check
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
            <trishul-item-import-batch
              [batch]="batch()!"
              (changed)="batchChanged($event)"
            />
          }
        </mat-tab>
      }

      @if (canViewHistory) {
        <mat-tab label="Import history">
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
                placeholder="Batch ID or file name"
                aria-label="Search by batch ID or file name"
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
                    @if (b.duplicateMode === 'Update') {
                      <div class="muted">updates existing items</div>
                    }
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
                    Imported · failed · skipped
                  </th>
                  <td mat-cell *matCellDef="let b">
                    <div class="counts">
                      @if (b.status === 'Pending') {
                        <span class="chip"
                          >{{ b.validCount | number }} valid</span
                        >
                      } @else {
                        <span class="chip success"
                          >{{
                            b.createdCount + b.updatedCount | number
                          }}
                          imported</span
                        >
                      }
                      <span class="chip danger"
                        >{{ b.failedCount | number }} failed</span
                      >
                      <span class="chip warn"
                        >{{ b.skippedCount | number }} skipped</span
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
                    @if (b.failedCount + b.skippedCount) {
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
                      No imports found.
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
              aria-label="Pages of imports"
              (page)="onPage($event)"
            />
          </div>
        </mat-tab>
      }
    </mat-tab-group>
  `,
})
export class ItemListImportPage {
  protected readonly api = inject(ItemListImportApi);
  private readonly auth = inject(AuthStore);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly canImport = this.auth.hasPermission(INV_ITEM_IMPORT);
  protected readonly canOverwrite = this.auth.hasPermission(
    INV_ITEM_IMPORT_OVERWRITE,
  );
  protected readonly canViewHistory =
    this.canImport || this.auth.hasPermission(INV_ITEM_IMPORT_VIEW);
  protected readonly accept = ACCEPT;
  protected readonly maxMb = MAX_MB;
  protected readonly statuses = STATUSES;
  protected readonly severity = ITEM_IMPORT_SEVERITY;
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

  protected readonly file = signal<File | null>(null);
  protected readonly duplicateMode = signal<ItemImportDuplicateMode>('Skip');
  protected readonly dragging = signal(false);
  protected readonly uploading = signal(false);
  protected readonly batch = signal<ItemImportBatch | null>(null);

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
    if (!file || this.uploading()) return;
    this.uploading.set(true);
    this.api
      .upload(file, this.duplicateMode())
      .pipe(
        finalize(() => this.uploading.set(false)),
        catchError(() => EMPTY), // the error toast has been shown
      )
      .subscribe((batch) => {
        this.batch.set(batch);
        this.reloadHistory();
      });
  }

  protected batchChanged(batch: ItemImportBatch): void {
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

  protected readonly query = signal<ItemImportHistoryQuery>({
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

  constructor() {
    this.search$
      .pipe(
        map((s) => s.trim()),
        debounceTime(350),
        distinctUntilChanged(),
        tap((search) => this.patch({ search: search || null })),
        takeUntilDestroyed(),
      )
      .subscribe();
  }

  protected patch(change: Partial<ItemImportHistoryQuery>): void {
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
    const sort =
      current === key ? `-${key}` : current === `-${key}` ? key : `-${key}`;
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
