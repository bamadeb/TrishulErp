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
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { RouterLink } from '@angular/router';
import {
  EMPTY,
  Subject,
  catchError,
  debounceTime,
  distinctUntilChanged,
  finalize,
  of,
  switchMap,
  tap,
} from 'rxjs';
import { PageUnassignedCallItem } from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import {
  CALL_PRIORITIES,
  CallCover,
  CallPriority,
  EngineerAvailability,
  EngineerWorkload,
  ServiceCallApi,
  UnassignedCallItem,
} from '@trishul/service-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';

const PRIORITY_SEVERITY: Record<CallPriority, StatusSeverity> = {
  Critical: 'danger',
  High: 'warn',
  Normal: 'info',
  Low: 'neutral',
};

const COVER_SEVERITY: Record<CallCover, StatusSeverity> = {
  'ASC + Warranty': 'success',
  ASC: 'success',
  Warranty: 'success',
  Chargeable: 'warn',
  Goodwill: 'info',
  'Not covered': 'warn',
  Unknown: 'neutral',
};

const AVAILABILITY_SEVERITY: Record<EngineerAvailability, StatusSeverity> = {
  Available: 'success',
  'Half-day leave': 'warn',
  Holiday: 'warn',
  'On leave': 'danger',
};

const NO_CALLS: PageUnassignedCallItem = {
  items: [],
  total: 0,
  page: 1,
  pageSize: 20,
};

/** yyyy-mm-dd in the user's own time zone (toISOString would give yesterday before 05:30 in India). */
function isoDate(day: Date): string {
  const month = String(day.getMonth() + 1).padStart(2, '0');
  const date = String(day.getDate()).padStart(2, '0');
  return `${day.getFullYear()}-${month}-${date}`;
}

function startOfToday(): Date {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

/** Team lead's board: pick a waiting call, compare the engineers for the day, and assign one. */
@Component({
  selector: 'trishul-call-assign-page',
  imports: [
    DatePipe,
    RouterLink,
    MatTableModule,
    MatPaginator,
    MatProgressBar,
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
    MatButton,
    MatIcon,
    PageHeader,
    StatusBadge,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './call-assign.page.html',
  styleUrl: './call-assign.page.scss',
})
export class CallAssignPage {
  private readonly api = inject(ServiceCallApi);
  private readonly auth = inject(AuthStore);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly priorities = CALL_PRIORITIES;
  protected readonly prioritySeverity = PRIORITY_SEVERITY;
  protected readonly coverSeverity = COVER_SEVERITY;
  protected readonly availabilitySeverity = AVAILABILITY_SEVERITY;
  protected readonly engineerColumns = [
    'engineer',
    'availability',
    'callsOnDate',
    'openCalls',
    'distance',
    'action',
  ];

  protected readonly today = startOfToday();
  protected readonly date = signal(this.today);
  protected readonly query = signal({
    page: 1,
    pageSize: 20,
    search: '',
    priority: [] as CallPriority[],
  });
  protected readonly selectedId = signal<number | null>(null);
  /** The engineer being assigned, so the buttons disable while it saves. */
  protected readonly busyId = signal<number | null>(null);
  protected readonly loadingCalls = signal(false);
  protected readonly loadingEngineers = signal(false);

  /** Bumped after an assignment, to load both lists again. */
  private readonly refresh = signal(0);
  private readonly search$ = new Subject<string>();

  private readonly callsRequest = computed(() => ({
    query: this.query(),
    refresh: this.refresh(),
    branchId: this.auth.branchId(),
    principalId: this.auth.principalId(),
  }));
  private readonly engineersRequest = computed(() => ({
    onDate: isoDate(this.date()),
    callId: this.selectedId() ?? undefined,
    refresh: this.refresh(),
    branchId: this.auth.branchId(),
    principalId: this.auth.principalId(),
  }));

  protected readonly callsPage = toSignal(
    toObservable(this.callsRequest).pipe(
      tap(() => this.loadingCalls.set(true)),
      // switchMap drops the response of a superseded query (fast typing, quick paging).
      switchMap(({ query }) =>
        this.api.unassigned(query).pipe(catchError(() => of(NO_CALLS))),
      ),
      tap(() => this.loadingCalls.set(false)),
    ),
    { initialValue: NO_CALLS },
  );

  protected readonly engineers = toSignal(
    toObservable(this.engineersRequest).pipe(
      tap(() => this.loadingEngineers.set(true)),
      switchMap(({ onDate, callId }) =>
        this.api
          .engineerWorkload(onDate, callId)
          .pipe(catchError(() => of<EngineerWorkload[]>([]))),
      ),
      tap(() => this.loadingEngineers.set(false)),
    ),
    { initialValue: [] as EngineerWorkload[] },
  );

  protected readonly selected = computed(
    () =>
      this.callsPage().items.find((c) => c.id === this.selectedId()) ?? null,
  );

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) =>
        this.query.update((q) => ({ ...q, search, page: 1 })),
      );
  }

  protected onSearch(value: string): void {
    this.search$.next(value.trim());
  }

  protected onPriority(priority: CallPriority[]): void {
    this.query.update((q) => ({ ...q, priority, page: 1 }));
  }

  protected onPage(event: PageEvent): void {
    this.query.update((q) => ({
      ...q,
      page: event.pageIndex + 1,
      pageSize: event.pageSize,
    }));
  }

  protected onDate(day: Date | null): void {
    if (day) this.date.set(day); // null: half-typed date, keep the last good one
  }

  protected isBreached(call: UnassignedCallItem): boolean {
    return !!call.slaDueAt && new Date(call.slaDueAt) < new Date();
  }

  protected assign(engineer: EngineerWorkload): void {
    const call = this.selected();
    if (!call) return;
    const day = this.date();
    this.busyId.set(engineer.id);
    this.api
      .updateTriage(call.id, call.rowVersion, {
        engineerId: engineer.id,
        visitDate: isoDate(day),
      })
      .pipe(
        finalize(() => this.busyId.set(null)),
        catchError(() => {
          this.refresh.update((n) => n + 1); // e.g. 409: someone else got there first
          return EMPTY;
        }),
      )
      .subscribe(() => {
        this.selectNextAfter(call);
        this.refresh.update((n) => n + 1);
        const when = day.toLocaleDateString('en-IN', {
          day: '2-digit',
          month: 'short',
        });
        this.snackBar.open(
          `${call.callNo} assigned to ${engineer.name} for ${when}`,
          'OK',
          { duration: 4000 },
        );
      });
  }

  /** Move on to the next waiting call, so a run of calls can be assigned in a row. */
  private selectNextAfter(call: UnassignedCallItem): void {
    const rows = this.callsPage().items;
    const index = rows.findIndex((c) => c.id === call.id);
    this.selectedId.set((rows[index + 1] ?? rows[index - 1])?.id ?? null);
  }
}
