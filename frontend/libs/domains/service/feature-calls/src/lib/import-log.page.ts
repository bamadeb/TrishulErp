import { DatePipe } from '@angular/common';
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
import { MatButton } from '@angular/material/button';
import { MatFormField, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatTableModule } from '@angular/material/table';
import { RouterLink } from '@angular/router';
import {
  EMPTY,
  Subject,
  catchError,
  debounceTime,
  distinctUntilChanged,
  finalize,
  switchMap,
  tap,
} from 'rxjs';
import { AuthStore, HasPermission } from '@trishul/core-auth';
import {
  BydImportApi,
  ImportLogQuery,
  SERVICE_CALL_IMPORT_PERMISSION,
} from '@trishul/service-data-access';
import { PageHeader } from '@trishul/shared-ui';

/** Every BYD upload in the selected branch and brand: who, when, which file and what it did. */
@Component({
  selector: 'trishul-import-log-page',
  imports: [
    DatePipe,
    RouterLink,
    MatTableModule,
    MatPaginator,
    MatProgressBar,
    MatFormField,
    MatPrefix,
    MatInput,
    MatButton,
    MatIcon,
    HasPermission,
    PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './import-log.page.html',
  styleUrl: './byd-import.page.scss',
})
export class ImportLogPage {
  private readonly api = inject(BydImportApi);
  private readonly auth = inject(AuthStore);

  protected readonly importPermission = SERVICE_CALL_IMPORT_PERMISSION;
  protected readonly query = signal<ImportLogQuery>({ page: 1, pageSize: 20 });
  protected readonly loading = signal(false);
  protected readonly columns = [
    'importedAt',
    'fileName',
    'branch',
    'importedBy',
    'counts',
  ];

  /** Reloads when the query or the selected branch / brand changes. */
  private readonly request = computed(() => ({
    query: this.query(),
    branchId: this.auth.branchId(),
    principalId: this.auth.principalId(),
  }));

  protected readonly page = toSignal(
    toObservable(this.request).pipe(
      tap(() => this.loading.set(true)),
      switchMap(({ query }) =>
        this.api.log(query).pipe(
          finalize(() => this.loading.set(false)),
          catchError(() => EMPTY), // the error toast has been shown
        ),
      ),
    ),
  );
  protected readonly items = computed(() => this.page()?.items ?? []);

  private readonly search$ = new Subject<string>();

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) =>
        this.query.update((q) => ({
          ...q,
          page: 1,
          search: search || undefined,
        })),
      );
  }

  protected onSearch(value: string): void {
    this.search$.next(value.trim());
  }

  protected onPage(event: PageEvent): void {
    this.query.update((q) => ({
      ...q,
      page: event.pageIndex + 1,
      pageSize: event.pageSize,
    }));
  }
}
