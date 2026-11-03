import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  LOCALE_ID,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import {
  MatButtonToggle,
  MatButtonToggleGroup,
} from '@angular/material/button-toggle';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { Router, RouterLink } from '@angular/router';
import { EMPTY, catchError, filter, finalize, switchMap, tap } from 'rxjs';
import { BydImportApi, BydImportRow } from '@trishul/service-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { ImportRowsTable } from './import-rows-table';

type RowFilter = 'all' | 'insert' | 'update' | 'changed' | 'skip' | 'link';

const FILTERS: Record<RowFilter, (row: BydImportRow) => boolean> = {
  all: () => true,
  insert: (r) => r.action === 'insert',
  update: (r) => r.action === 'update',
  changed: (r) => r.changes.length > 0,
  skip: (r) => r.action === 'skip',
  link: (r) => r.needsLinking,
};

/** One upload from the import log: its counts and what happened to every row of the file. */
@Component({
  selector: 'trishul-import-log-detail-page',
  imports: [
    RouterLink,
    MatButton,
    MatButtonToggleGroup,
    MatButtonToggle,
    MatIcon,
    MatProgressBar,
    PageHeader,
    ImportRowsTable,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './import-log-detail.page.html',
  styleUrl: './byd-import.page.scss',
})
export class ImportLogDetailPage {
  private readonly api = inject(BydImportApi);
  private readonly router = inject(Router);
  private readonly date = new DatePipe(inject(LOCALE_ID));

  readonly importId = input.required<string>();

  protected readonly loading = signal(false);
  protected readonly filter = signal<RowFilter>('all');

  protected readonly entry = toSignal(
    toObservable(this.importId).pipe(
      filter(Boolean),
      tap(() => this.loading.set(true)),
      switchMap((id) =>
        this.api.logEntry(Number(id)).pipe(
          finalize(() => this.loading.set(false)),
          catchError(() => {
            void this.router.navigate(['/service/imports']);
            return EMPTY;
          }),
        ),
      ),
    ),
  );

  /** When, who, branch and brand. */
  protected readonly subtitle = computed(() => {
    const e = this.entry();
    if (!e) return '';
    const when = this.date.transform(e.importedAt, 'dd MMM yyyy, HH:mm');
    return [
      when,
      e.importedByName ?? 'unknown user',
      e.branchName,
      e.principalCode,
    ].join(' · ');
  });

  protected readonly rows = computed(() =>
    (this.entry()?.rows ?? []).filter(FILTERS[this.filter()]),
  );
  protected readonly changedCount = computed(
    () => (this.entry()?.rows ?? []).filter(FILTERS.changed).length,
  );
}
