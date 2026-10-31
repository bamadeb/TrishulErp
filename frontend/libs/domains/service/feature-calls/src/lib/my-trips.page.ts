import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
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
import { MatTableModule } from '@angular/material/table';
import { MatTooltip } from '@angular/material/tooltip';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import {
  MyTripsStore,
  TRIP_STATUSES,
  TripListItem,
  TripStatus,
} from '@trishul/service-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';

const TRIP_STATUS_SEVERITY: Record<TripStatus, StatusSeverity> = {
  'In progress': 'warn',
  Completed: 'success',
  'Auto closed': 'neutral',
};

const MODULE_LABEL: Record<TripListItem['module'], string> = {
  SVC: 'Service',
  PRE: 'Pre-sales',
};

interface DistanceRow {
  label: string;
  value: number;
  cls: 'gps' | 'eff';
  pct: number;
}

/** The signed-in engineer's own trips, with GPS vs. effective distance and any Team Lead adjustments. */
@Component({
  selector: 'trishul-my-trips-page',
  imports: [
    DatePipe,
    MatTableModule,
    MatPaginator,
    MatProgressBar,
    MatFormField,
    MatLabel,
    MatPrefix,
    MatInput,
    MatSelect,
    MatOption,
    MatIcon,
    MatTooltip,
    PageHeader,
    StatusBadge,
  ],
  providers: [MyTripsStore],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './my-trips.page.html',
  // Shares the trip-history layout so both trip screens look the same.
  styleUrls: ['./trip-history.page.scss', './my-trips.page.scss'],
})
export class MyTripsPage {
  protected readonly store = inject(MyTripsStore);
  protected readonly statusSeverity = TRIP_STATUS_SEVERITY;
  protected readonly statuses = TRIP_STATUSES;
  protected readonly columns = ['trip', 'when', 'distance'];

  private readonly search$ = new Subject<string>();

  constructor() {
    this.search$
      .pipe(debounceTime(350), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((search) => this.store.updateQuery({ search }));
  }

  protected onSearch(value: string): void {
    this.search$.next(value.trim());
  }

  protected onPage(event: PageEvent): void {
    this.store.updateQuery({
      page: event.pageIndex + 1,
      pageSize: event.pageSize,
    });
  }

  protected moduleName(module: TripListItem['module']): string {
    return MODULE_LABEL[module];
  }

  protected fmtKm(value: number | null | undefined): string {
    return value === null || value === undefined ? '—' : value.toFixed(2);
  }

  protected duration(minutes: number | null | undefined): string {
    if (minutes === null || minutes === undefined) return '—';
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return (h ? `${h}h ` : '') + `${m}m`;
  }

  /** GPS / Effective bars for the detail pane, scaled to the trip's larger value. */
  protected distanceRows(trip: TripListItem): DistanceRow[] {
    const rows: Omit<DistanceRow, 'pct'>[] = [];
    if (trip.gpsDistanceKm !== null)
      rows.push({ label: 'GPS', value: trip.gpsDistanceKm, cls: 'gps' });
    if (trip.effectiveDistanceKm !== null)
      rows.push({
        label: 'Effective',
        value: trip.effectiveDistanceKm,
        cls: 'eff',
      });
    const max = Math.max(1, ...rows.map((r) => r.value));
    return rows.map((r) => ({ ...r, pct: (r.value / max) * 100 }));
  }
}
