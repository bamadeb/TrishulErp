import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatFormField, MatLabel, MatPrefix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { BiometricApi, BiometricPunch } from '@trishul/hr-data-access';
import { StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import {
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

interface PunchQueryState {
  page: number;
  pageSize: number;
  search: string;
  punchType: string;
}

@Component({
  selector: 'trishul-biometric-punches-page',
  imports: [
    DatePipe,
    DecimalPipe,
    FormsModule,
    MatButton,
    MatFormField,
    MatIcon,
    MatInput,
    MatLabel,
    MatOption,
    MatPaginator,
    MatPrefix,
    MatProgressBar,
    MatSelect,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './biometric-punches.page.html',
  styleUrl: './biometric-punches.page.scss',
})
export class BiometricPunchesPage implements OnInit {
  private readonly api = inject(BiometricApi);
  private readonly destroyRef = inject(DestroyRef);
  private readonly query$ = new Subject<PunchQueryState>();

  protected readonly severities: Partial<Record<string, StatusSeverity>> = {
    IN: 'success',
    OUT: 'danger',
  };
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly rows = signal<BiometricPunch[]>([]);
  protected readonly total = signal(0);
  protected readonly search = signal('');
  protected readonly punchType = signal('');
  protected readonly page = signal(0);
  protected readonly pageSize = signal(20);

  ngOnInit(): void {
    this.query$
      .pipe(
        debounceTime(200),
        distinctUntilChanged(
          (a, b) =>
            a.page === b.page &&
            a.pageSize === b.pageSize &&
            a.search === b.search &&
            a.punchType === b.punchType,
        ),
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
          // Drop any previous rows so stale mock/session data cannot linger.
          this.rows.set([]);
        }),
        switchMap((query) =>
          this.api
            .listPunches({
              page: query.page + 1,
              pageSize: query.pageSize,
              search: query.search.trim() || undefined,
              punchType: query.punchType || undefined,
            })
            .pipe(
              map((page) => ({
                items: Array.isArray(page?.items) ? page.items.map((row) => this.normalize(row)) : [],
                total: typeof page?.total === 'number' ? page.total : 0,
              })),
              catchError(() => {
                this.error.set('Punch logs could not be loaded from the server.');
                return of({ items: [] as BiometricPunch[], total: 0 });
              }),
              finalize(() => this.loading.set(false)),
            ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(({ items, total }) => {
        this.rows.set(items);
        this.total.set(total);
      });

    this.emitQuery();
  }

  protected onPage(event: PageEvent): void {
    this.page.set(event.pageIndex);
    this.pageSize.set(event.pageSize);
    this.emitQuery();
  }

  protected onSearch(value: string): void {
    this.search.set(value);
    this.page.set(0);
    this.emitQuery();
  }

  protected onPunchType(value: string): void {
    this.punchType.set(value);
    this.page.set(0);
    this.emitQuery();
  }

  protected refresh(): void {
    this.emitQuery();
  }

  protected initials(name: string | null | undefined): string {
    return (name ?? '')
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? '')
      .join('');
  }

  private emitQuery(): void {
    this.query$.next({
      page: this.page(),
      pageSize: this.pageSize(),
      search: this.search(),
      punchType: this.punchType(),
    });
  }

  /** Accept camelCase API payloads only; never invent demo rows. */
  private normalize(row: BiometricPunch): BiometricPunch {
    return {
      id: row.id,
      deviceId: row.deviceId,
      deviceName: row.deviceName ?? null,
      deviceLocation: row.deviceLocation ?? null,
      employeeId: row.employeeId ?? null,
      employeeCode: row.employeeCode ?? null,
      employeeName: row.employeeName ?? null,
      departmentName: row.departmentName ?? null,
      biometricUserId: row.biometricUserId,
      punchedAt: row.punchedAt,
      punchType: row.punchType ?? null,
      externalPunchId: row.externalPunchId ?? null,
      source: row.source,
      syncLogId: row.syncLogId ?? null,
      createdAt: row.createdAt,
    };
  }
}
