import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { DecimalPipe } from '@angular/common';
import { MatButton } from '@angular/material/button';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { RouterLink } from '@angular/router';
import { EMPTY, catchError, finalize, of } from 'rxjs';
import { ApiClient, getItemFormOptions } from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import {
  ItemImportApi,
  ItemImportPreview,
  ItemImportRow,
  ItemPriceField,
} from '@trishul/inventory-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';

const ACTION_SEVERITY: Record<string, StatusSeverity> = {
  Create: 'success',
  Update: 'info',
  Unchanged: 'neutral',
  Skip: 'warn',
};

/**
 * Upload the spare-part price file (External ID, Material, Description, HSN Code, ZAmount). New parts become
 * items, prices and missing HSN codes of existing items are updated, and duplicates / missing HSN are reported.
 */
@Component({
  selector: 'trishul-item-import-page',
  imports: [
    DecimalPipe,
    RouterLink,
    MatButton,
    MatFormField,
    MatLabel,
    MatIcon,
    MatProgressBar,
    MatSelect,
    MatOption,
    MatPaginator,
    MatSlideToggle,
    MatTableModule,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: `
    .controls {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.75rem;
      margin-bottom: 1rem;
    }
    .file {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .file-name,
    .muted {
      font: var(--mat-sys-body-small);
      color: var(--mat-sys-on-surface-variant);
    }
    .field {
      width: 14rem;
    }
    .spacer {
      flex: 1 1 auto;
    }
    .summary {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.5rem;
      margin: 0.75rem 0;
    }
    .summary .muted {
      margin-left: auto;
    }
    .chip {
      padding: 0.125rem 0.625rem;
      border-radius: 999px;
      font: var(--mat-sys-label-medium);
      font-weight: 600;
      background: var(--mat-sys-surface-container-high);
      color: var(--mat-sys-on-surface-variant);
    }
    .chip.total {
      color: var(--mat-sys-on-primary-container);
      background: var(--mat-sys-primary-container);
    }
    .chip.success {
      color: var(--trishul-success);
      background: var(--trishul-success-container);
    }
    .chip.info {
      color: var(--trishul-info);
      background: var(--trishul-info-container);
    }
    .chip.warn {
      color: var(--trishul-warn);
      background: var(--trishul-warn-container);
    }
    .banner {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.625rem 0.875rem;
      margin: 0.75rem 0;
      border-radius: var(--mat-sys-corner-medium);
      font: var(--mat-sys-body-medium);
    }
    .banner.done {
      color: var(--trishul-success);
      background: var(--trishul-success-container);
    }
    .banner.note {
      color: var(--trishul-info);
      background: var(--trishul-info-container);
    }
    .banner.warn {
      color: var(--trishul-warn);
      background: var(--trishul-warn-container);
    }
    .banner a {
      color: inherit;
      font-weight: 600;
    }
    .table-card {
      margin-top: 0.5rem;
      overflow: hidden;
      background: var(--mat-sys-surface);
      border: 1px solid var(--mat-sys-outline-variant);
      border-radius: var(--mat-sys-corner-medium);
    }
    .table-scroll {
      overflow-x: auto;
    }
    table {
      width: 100%;
      min-width: 960px;
      background: transparent;
    }
    td {
      vertical-align: top;
      padding-top: 0.4rem;
      padding-bottom: 0.4rem;
    }
    .num {
      text-align: right;
    }
    .issue {
      color: var(--trishul-warn);
      font: var(--mat-sys-body-small);
    }
    .empty {
      padding: 1.5rem;
      text-align: center;
    }
  `,
  template: `
    <trishul-page-header
      title="Import item prices"
      subtitle="Upload the spare-part price file: new parts become items, prices and missing HSN codes of existing items are updated"
    >
      <a mat-stroked-button routerLink="../">
        <mat-icon>list</mat-icon>Items
      </a>
    </trishul-page-header>

    @if (!hasBrand()) {
    <div class="banner warn">
      <mat-icon>warning</mat-icon>
      <span
        >Select a brand at the top first: parts are matched and created within
        that brand.</span
      >
    </div>
    }

    <div class="controls">
      <div class="file">
        <input
          type="file"
          hidden
          #fileInput
          accept=".xlsx"
          (change)="onFile($event)"
        />
        <button mat-stroked-button type="button" (click)="fileInput.click()">
          <mat-icon>upload_file</mat-icon>Choose file
        </button>
        <span class="file-name">{{ file()?.name ?? 'No file chosen' }}</span>
      </div>

      <mat-form-field
        appearance="outline"
        subscriptSizing="dynamic"
        class="field"
      >
        <mat-label>Category for new items</mat-label>
        <mat-select
          [value]="category()"
          (valueChange)="categoryId.set($event); clear()"
          aria-label="Category for new items"
        >
          @for (c of categories(); track c.id) {
          <mat-option [value]="c.id">{{ c.path }}</mat-option>
          }
        </mat-select>
      </mat-form-field>

      <mat-form-field
        appearance="outline"
        subscriptSizing="dynamic"
        class="field"
      >
        <mat-label>Stock unit</mat-label>
        <mat-select
          [value]="uomId()"
          (valueChange)="uomId.set($event); clear()"
          aria-label="Stock unit for new items"
        >
          <mat-option [value]="null">Category default</mat-option>
          @for (u of uoms(); track u.id) {
          <mat-option [value]="u.id">{{ u.code }}</mat-option>
          }
        </mat-select>
      </mat-form-field>

      <mat-form-field
        appearance="outline"
        subscriptSizing="dynamic"
        class="field"
      >
        <mat-label>Price (ZAmount) is the</mat-label>
        <mat-select
          [value]="priceField()"
          (valueChange)="priceField.set($event); clear()"
          aria-label="Where the price is stored"
        >
          <mat-option value="mrp">MRP</mat-option>
          <mat-option value="standardCost">Standard cost</mat-option>
        </mat-select>
      </mat-form-field>

      <span class="spacer"></span>
      <button mat-stroked-button [disabled]="!ready()" (click)="doPreview()">
        Preview
      </button>
      <button mat-flat-button [disabled]="!ready()" (click)="doImport()">
        <mat-icon>publish</mat-icon>Import
      </button>
    </div>

    @if (busy()) {
    <mat-progress-bar mode="indeterminate" />
    } @if (summary(); as s) {
    <div class="summary">
      <span class="chip total">Total records in Excel: {{ s.total | number }}</span>
      <span class="chip success">{{ s.creates }} new</span>
      <span class="chip info">{{ s.updates }} updated</span>
      <span class="chip">{{ s.unchanged }} unchanged</span>
      @if (s.skips) {
      <span class="chip warn">{{ s.skips }} skipped</span>
      } @if (s.duplicates) {
      <span class="chip warn">{{ s.duplicates }} duplicates</span>
      } @if (s.missingHsn) {
      <span class="chip warn">{{ s.missingHsn }} without HSN</span>
      } @if (s.unknownHsn) {
      <span class="chip warn">{{ s.unknownHsn }} unknown HSN</span>
      } @if (s.noPrice) {
      <span class="chip warn">{{ s.noPrice }} without price</span>
      }
      <span class="muted">{{ s.fileName }}</span>
    </div>
    @if (done()) {
    <div class="banner done">
      <mat-icon>check_circle</mat-icon>
      <span>Import complete. <a routerLink="../">Open the items</a>.</span>
    </div>
    } @else {
    <div class="banner note">
      <mat-icon>visibility</mat-icon>
      <span
        >Preview only — nothing has been saved. Review the rows, then choose
        Import.</span
      >
    </div>
    }
    <mat-slide-toggle
      [checked]="onlyIssues()"
      (change)="onlyIssues.set($event.checked); pageIndex.set(0)"
      >Only rows that need attention</mat-slide-toggle
    >
    <div class="table-card">
      <div class="table-scroll">
        <table mat-table [dataSource]="pagedRows()">
          <ng-container matColumnDef="rowNumber">
            <th mat-header-cell *matHeaderCellDef>Row</th>
            <td mat-cell *matCellDef="let r">{{ r.rowNumber }}</td>
          </ng-container>
          <ng-container matColumnDef="part">
            <th mat-header-cell *matHeaderCellDef>External ID / Material</th>
            <td mat-cell *matCellDef="let r">
              {{ r.externalId ?? '—' }}
              <div class="muted">{{ r.material ?? '' }}</div>
            </td>
          </ng-container>
          <ng-container matColumnDef="description">
            <th mat-header-cell *matHeaderCellDef>Description</th>
            <td mat-cell *matCellDef="let r">{{ r.description ?? '—' }}</td>
          </ng-container>
          <ng-container matColumnDef="hsn">
            <th mat-header-cell *matHeaderCellDef>HSN</th>
            <td mat-cell *matCellDef="let r">{{ r.hsnCode ?? '—' }}</td>
          </ng-container>
          <ng-container matColumnDef="price">
            <th mat-header-cell *matHeaderCellDef class="num">Price</th>
            <td mat-cell *matCellDef="let r" class="num">
              {{ r.price !== null ? (r.price | number: '1.2-2') : '—' }}
            </td>
          </ng-container>
          <ng-container matColumnDef="action">
            <th mat-header-cell *matHeaderCellDef>Action</th>
            <td mat-cell *matCellDef="let r">
              <trishul-status-badge
                [status]="r.action"
                [severities]="actionSeverity"
              />
              @if (r.itemCode) {
              <div class="muted">{{ r.itemCode }}</div>
              }
            </td>
          </ng-container>
          <ng-container matColumnDef="changes">
            <th mat-header-cell *matHeaderCellDef>Changed</th>
            <td mat-cell *matCellDef="let r">
              @for (c of r.changes; track c) {
              <div>{{ c }}</div>
              }
            </td>
          </ng-container>
          <ng-container matColumnDef="issues">
            <th mat-header-cell *matHeaderCellDef>Needs attention</th>
            <td mat-cell *matCellDef="let r">
              @for (i of r.issues; track i.code) {
              <div class="issue">{{ i.message }}</div>
              }
            </td>
          </ng-container>
          <tr mat-header-row *matHeaderRowDef="columns"></tr>
          <tr mat-row *matRowDef="let row; columns: columns"></tr>
          <tr class="mat-mdc-row" *matNoDataRow>
            <td class="empty" [attr.colspan]="columns.length">
              No rows need attention.
            </td>
          </tr>
        </table>
      </div>
      <mat-paginator
        [length]="shownRows().length"
        [pageIndex]="pageIndex()"
        [pageSize]="pageSize()"
        [pageSizeOptions]="[50, 100, 250, 500]"
        (page)="onPage($event)"
        aria-label="Rows of the file"
      />
    </div>
    }
  `,
})
export class ItemImportPage {
  private readonly importApi = inject(ItemImportApi);
  private readonly api = inject(ApiClient);
  private readonly auth = inject(AuthStore);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly columns = [
    'rowNumber',
    'part',
    'description',
    'hsn',
    'price',
    'action',
    'changes',
    'issues',
  ];
  protected readonly actionSeverity = ACTION_SEVERITY;

  private readonly options = toSignal(
    this.api.call(getItemFormOptions).pipe(catchError(() => of(null))),
    { initialValue: null },
  );
  protected readonly categories = computed(
    () => this.options()?.categories ?? [],
  );
  protected readonly uoms = computed(() => this.options()?.uoms ?? []);

  protected readonly file = signal<File | null>(null);
  private readonly categoryId = signal<number | null>(null);
  /** What the user picked, else the first spare-part category (what a price file holds). */
  protected readonly category = computed(
    () =>
      this.categoryId() ??
      this.categories().find((c) => c.isActive && c.itemNature === 'Spare part')
        ?.id ??
      null,
  );
  protected readonly uomId = signal<number | null>(null);
  protected readonly priceField = signal<ItemPriceField>('mrp');
  protected readonly result = signal<ItemImportPreview | null>(null);
  protected readonly done = signal(false);
  protected readonly busy = signal(false);
  protected readonly onlyIssues = signal(false);

  protected readonly hasBrand = computed(
    () => this.auth.principalId() !== null,
  );
  protected readonly summary = computed(() => this.result()?.summary ?? null);
  protected readonly shownRows = computed<ItemImportRow[]>(() => {
    const rows = this.result()?.rows ?? [];
    return this.onlyIssues()
      ? rows.filter((r) => r.issues.length || r.action === 'Skip')
      : rows;
  });
  protected readonly pageIndex = signal(0);
  protected readonly pageSize = signal(100);
  protected readonly pagedRows = computed(() => {
    const start = this.pageIndex() * this.pageSize();
    return this.shownRows().slice(start, start + this.pageSize());
  });
  protected readonly ready = computed(
    () => this.file() !== null && this.hasBrand() && !this.busy(),
  );

  protected onFile(event: Event): void {
    this.file.set((event.target as HTMLInputElement).files?.[0] ?? null);
    this.clear();
  }

  protected onPage(event: PageEvent): void {
    this.pageIndex.set(event.pageIndex);
    this.pageSize.set(event.pageSize);
  }

  protected clear(): void {
    this.pageIndex.set(0);
    this.result.set(null);
    this.done.set(false);
  }

  private request() {
    return {
      categoryId: this.category(),
      uomId: this.uomId(),
      priceField: this.priceField(),
    };
  }

  protected doPreview(): void {
    const file = this.file();
    if (!file || this.busy()) return;
    this.busy.set(true);
    this.done.set(false);
    this.importApi
      .preview(file, this.request())
      .pipe(
        finalize(() => this.busy.set(false)),
        catchError(() => EMPTY), // the global interceptor shows the error toast
      )
      .subscribe((preview) => {
        this.pageIndex.set(0);
        this.result.set(preview);
      });
  }

  protected doImport(): void {
    const file = this.file();
    if (!file || this.busy()) return;
    this.busy.set(true);
    this.importApi
      .apply(file, this.request())
      .pipe(
        finalize(() => this.busy.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe((result) => {
        this.result.set(result);
        this.done.set(true);
        const s = result.summary;
        this.snackBar.open(
          `Imported: ${s.creates} new, ${s.updates} updated` +
            (s.skips ? `, ${s.skips} skipped` : ''),
          'Dismiss',
          { duration: 6000 },
        );
      });
  }
}
