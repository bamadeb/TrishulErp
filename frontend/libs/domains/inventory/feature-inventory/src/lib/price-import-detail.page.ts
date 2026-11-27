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
  PriceImportApi,
  PriceImportBatch,
} from '@trishul/inventory-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { PriceImportBatchView } from './price-import-batch';

/** One price import from the history: counts, files, approval and the item-wise old and new prices. */
@Component({
  selector: 'trishul-price-import-detail-page',
  imports: [
    RouterLink,
    MatButton,
    MatIcon,
    MatProgressBar,
    PageHeader,
    PriceImportBatchView,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <trishul-page-header
      [title]="batch()?.batchNo ?? 'Price import'"
      subtitle="A price import and the old and new price of each item"
    >
      <a mat-stroked-button routerLink="../" [queryParams]="{ tab: 'history' }">
        <mat-icon>history</mat-icon>Price import history
      </a>
    </trishul-page-header>
    @if (loading()) {
      <mat-progress-bar mode="indeterminate" />
    }
    @if (batch(); as b) {
      <trishul-price-import-batch [batch]="b" (changed)="batch.set($event)" />
    }
  `,
})
export class PriceImportDetailPage {
  private readonly api = inject(PriceImportApi);

  /** Route parameter (component input binding). */
  readonly importId = input.required({ transform: numberAttribute });

  protected readonly batch = signal<PriceImportBatch | null>(null);
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
