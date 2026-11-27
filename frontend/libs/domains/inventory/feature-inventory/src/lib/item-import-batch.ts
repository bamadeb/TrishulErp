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
  ITEM_IMPORT_SEVERITY,
  ItemImportBatch,
  ItemImportLineOut,
  ItemImportLineQuery,
  ItemListImportApi,
  itemImportLineLabel,
} from '@trishul/inventory-data-access';
import { StatusBadge, confirmAction } from '@trishul/shared-ui';

type LineFilter = NonNullable<ItemImportLineQuery['status']>;

/**
 * One item list upload: its counts, what to do next (confirm / download the error report), and its rows,
 * paged from the server. Used for the preview after an upload and for a batch opened from the history.
 */
@Component({
  selector: 'trishul-item-import-batch',
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
    MatTableModule,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './item-import.scss',
  template: `
    @let b = batch();
    <div class="batch-head">
      <div class="batch-title">
        <span class="batch-no">{{ b.batchNo ?? '#' + b.id }}</span>
        <trishul-status-badge [status]="b.status" [severities]="severity" />
        <span class="muted">
          {{ b.fileName }} · {{ b.fileSize / 1024 | number: '1.0-0' }} KB ·
          uploaded {{ b.uploadedAt | date: 'dd MMM yyyy, HH:mm' }} by
          {{ b.uploadedByName ?? '—' }}
          @if (b.duplicateMode === 'Update') {
            · updates existing items
          }
        </span>
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
        @if (hasProblems()) {
          <button
            mat-stroked-button
            type="button"
            (click)="api.downloadErrorReport(b)"
          >
            <mat-icon>summarize</mat-icon>Error report
          </button>
        }
        @if (b.canConfirm) {
          <button
            mat-flat-button
            type="button"
            [disabled]="confirming()"
            (click)="confirm()"
          >
            <mat-icon>publish</mat-icon>Import {{ b.validCount | number }} valid
            row{{ b.validCount === 1 ? '' : 's' }}
          </button>
        }
      </div>
    </div>

    <div class="cards">
      <div class="card">
        <span class="label">Total records</span>
        <span class="value">{{ b.totalRows | number }}</span>
      </div>
      @if (isDone()) {
        <div class="card success">
          <span class="label">Imported</span>
          <span class="value">{{
            b.createdCount + b.updatedCount | number
          }}</span>
          <span class="hint"
            >{{ b.createdCount | number }} new ·
            {{ b.updatedCount | number }} updated</span
          >
        </div>
      } @else {
        <div class="card success">
          <span class="label">Valid</span>
          <span class="value">{{ b.validCount | number }}</span>
          <span class="hint">ready to import</span>
        </div>
      }
      <div class="card danger">
        <span class="label">{{ isDone() ? 'Failed' : 'With errors' }}</span>
        <span class="value">{{ b.failedCount | number }}</span>
      </div>
      <div class="card warn">
        <span class="label">Duplicates skipped</span>
        <span class="value">{{ b.skippedCount | number }}</span>
      </div>
    </div>

    @switch (b.status) {
      @case ('Pending') {
        <div class="banner note">
          <mat-icon>visibility</mat-icon>
          <span>
            Checked, nothing imported yet.
            @if (b.canConfirm) {
              Review the rows, then choose <b>Import</b>: only the
              {{ b.validCount | number }} valid row(s) are added.
            } @else {
              Only the person who uploaded the file can confirm it.
            }
            @if (hasProblems()) {
              Rows with errors and duplicates are left out; download the error
              report to fix and upload them again.
            }
          </span>
        </div>
      }
      @case ('Processing') {
        <div class="banner note">
          <mat-icon>hourglass_top</mat-icon>
          <span>The import is running…</span>
        </div>
      }
      @case ('Completed') {
        <div class="banner done">
          <mat-icon>check_circle</mat-icon>
          <span>
            Import complete: {{ b.createdCount | number }} item(s) created,
            {{ b.updatedCount | number }} updated.
            <a routerLink="/inventory/items">Open the items</a>
          </span>
        </div>
      }
      @case ('Partially Completed') {
        <div class="banner warn">
          <mat-icon>warning</mat-icon>
          <span>
            Partly imported: {{ b.createdCount | number }} created,
            {{ b.updatedCount | number }} updated;
            {{ b.failedCount | number }} failed and
            {{ b.skippedCount | number }} skipped. Download the error report for
            the reasons.
          </span>
        </div>
      }
      @case ('Failed') {
        <div class="banner error">
          <mat-icon>error</mat-icon>
          <span>{{
            b.errorMessage ?? 'The import failed; nothing was imported.'
          }}</span>
        </div>
      }
    }

    @if (b.totalRows) {
      <div class="filters">
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-icon matPrefix>search</mat-icon>
          <input
            matInput
            type="search"
            placeholder="Item code or description"
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
            <ng-container matColumnDef="itemCode">
              <th mat-header-cell *matHeaderCellDef>Item code</th>
              <td mat-cell *matCellDef="let l">
                @if (l.itemId && l.outcome) {
                  <a
                    class="name"
                    [routerLink]="['/inventory/items', l.itemId]"
                    >{{ l.itemCode }}</a
                  >
                } @else {
                  {{ l.itemCode ?? '—' }}
                }
              </td>
            </ng-container>
            <ng-container matColumnDef="description">
              <th mat-header-cell *matHeaderCellDef>Description</th>
              <td mat-cell *matCellDef="let l">{{ l.description ?? '—' }}</td>
            </ng-container>
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
                @for (c of l.changes; track c.field) {
                  <div>
                    {{ c.field }}: {{ c.from ?? '—' }} → {{ c.to ?? '—' }}
                  </div>
                }
                @for (m of l.messages; track $index) {
                  <div
                    [class.issue-error]="l.action === 'Error'"
                    [class.issue]="l.action !== 'Error'"
                  >
                    {{ m }}
                  </div>
                }
              </td>
            </ng-container>
            <tr mat-header-row *matHeaderRowDef="columns; sticky: true"></tr>
            <tr mat-row *matRowDef="let row; columns: columns"></tr>
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
export class ItemImportBatchView {
  protected readonly api = inject(ItemListImportApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  readonly batch = input.required<ItemImportBatch>();
  /** The batch after it was confirmed. */
  readonly changed = output<ItemImportBatch>();

  protected readonly severity = ITEM_IMPORT_SEVERITY;
  protected readonly label = itemImportLineLabel;
  protected readonly columns = [
    'rowNumber',
    'itemCode',
    'description',
    'result',
    'details',
  ];

  protected readonly isDone = computed(() =>
    ['Completed', 'Partially Completed'].includes(this.batch().status),
  );
  protected readonly hasProblems = computed(
    () => this.batch().failedCount + this.batch().skippedCount > 0,
  );
  protected readonly filters = computed<{ value: LineFilter; label: string }[]>(
    () =>
      this.batch().status === 'Pending' || this.batch().status === 'Failed'
        ? [
            { value: 'Create', label: 'Will be created' },
            { value: 'Update', label: 'Will be updated' },
            { value: 'Error', label: 'With errors' },
            { value: 'Skip', label: 'Duplicates' },
          ]
        : [
            { value: 'Created', label: 'Created' },
            { value: 'Updated', label: 'Updated' },
            { value: 'Failed', label: 'Failed' },
            { value: 'Skipped', label: 'Skipped' },
          ],
  );

  protected readonly lineFilter = signal<LineFilter | null>(null);
  protected readonly page = signal(1);
  protected readonly pageSize = signal(50);
  private readonly search = signal('');
  protected readonly search$ = new Subject<string>();
  protected readonly loading = signal(false);
  protected readonly confirming = signal(false);
  protected readonly lines = signal<ItemImportLineOut[]>([]);
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
      status: this.batch().status, // reload once the batch is imported
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

    // A new batch (or a confirmed one) starts with every row.
    toObservable(computed(() => `${this.batch().id}:${this.batch().status}`))
      .pipe(distinctUntilChanged(), takeUntilDestroyed())
      .subscribe(() => {
        this.page.set(1);
        this.lineFilter.set(null);
      });
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
    const left = b.failedCount + b.skippedCount;
    confirmAction(this.dialog, {
      title: 'Import items?',
      message:
        `${b.validCount} valid row(s) of ${b.fileName} will be added to the item master` +
        (b.duplicateMode === 'Update' ? ' (existing items are updated)' : '') +
        (left
          ? `; ${left} row(s) with errors or duplicates are left out.`
          : '.'),
      confirmText: 'Import',
    })
      .pipe(
        filter(Boolean),
        tap(() => this.confirming.set(true)),
        switchMap(() =>
          this.api.confirm(b.id).pipe(
            finalize(() => this.confirming.set(false)),
            catchError(() => {
              // The batch may have failed on the server: show its current state.
              this.api.get(b.id).subscribe((fresh) => this.changed.emit(fresh));
              return EMPTY;
            }),
          ),
        ),
      )
      .subscribe((done) => {
        this.changed.emit(done);
        const message =
          done.status === 'Completed'
            ? `Imported ${done.createdCount} new and ${done.updatedCount} updated item(s).`
            : done.status === 'Partially Completed'
              ? `Imported ${done.createdCount + done.updatedCount} item(s); ${done.failedCount + done.skippedCount} row(s) were not imported.`
              : (done.errorMessage ?? 'Nothing was imported.');
        this.snackBar.open(message, 'Dismiss', { duration: 6000 });
      });
  }
}
