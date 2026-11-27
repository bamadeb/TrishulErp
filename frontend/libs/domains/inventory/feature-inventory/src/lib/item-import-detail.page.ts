import {
  ChangeDetectionStrategy,
  Component,
  inject,
  input,
  numberAttribute,
  signal,
} from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { RouterLink } from '@angular/router';
import { EMPTY, catchError, finalize, switchMap, tap } from 'rxjs';
import {
  ItemImportBatch,
  ItemListImportApi,
} from '@trishul/inventory-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { ItemImportBatchView } from './item-import-batch';

/** One item list import from the history: counts, files and the result of every row. */
@Component({
  selector: 'trishul-item-import-detail-page',
  imports: [
    RouterLink,
    MatButton,
    MatIcon,
    MatProgressBar,
    PageHeader,
    ItemImportBatchView,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './item-import.scss',
  template: `
    <trishul-page-header
      [title]="batch()?.batchNo ?? 'Item import'"
      subtitle="An item list import and what happened to each row"
    >
      <a mat-stroked-button routerLink="../" [queryParams]="{ tab: 'history' }">
        <mat-icon>history</mat-icon>Import history
      </a>
    </trishul-page-header>
    @if (loading()) {
      <mat-progress-bar mode="indeterminate" />
    }
    @if (batch(); as b) {
      <trishul-item-import-batch [batch]="b" (changed)="batch.set($event)" />
    }
  `,
})
export class ItemImportDetailPage {
  private readonly api = inject(ItemListImportApi);

  /** Route parameter (component input binding). */
  readonly importId = input.required({ transform: numberAttribute });

  protected readonly batch = signal<ItemImportBatch | null>(null);
  protected readonly loading = signal(false);

  constructor() {
    toObservable(this.importId)
      .pipe(
        tap(() => this.loading.set(true)),
        switchMap((id) =>
          this.api.get(id).pipe(
            finalize(() => this.loading.set(false)),
            catchError(() => EMPTY), // the error toast has been shown
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((batch) => this.batch.set(batch));
  }
}
