import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatTableModule } from '@angular/material/table';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltip } from '@angular/material/tooltip';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { HasPermission } from '@trishul/core-auth';
import {
  CallTripHistoryItem,
  TRIP_ADJUST_PERMISSION,
  TripHistoryStore,
  TripStatus,
} from '@trishul/service-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { openAdjustDistanceDialog } from './adjust-distance.dialog';

const TRIP_STATUS_SEVERITY: Record<TripStatus, StatusSeverity> = {
  'In progress': 'warn',
  Completed: 'success',
  'Auto closed': 'neutral',
};

interface DistanceRow {
  label: string;
  value: number;
  cls: 'gps' | 'maps' | 'eff';
  pct: number;
}

/** Trip history for one service call: every trip across its visits, with GPS vs. adjusted distance. */
@Component({
  selector: 'trishul-trip-history-page',
  imports: [
    DatePipe,
    RouterLink,
    MatTableModule,
    MatProgressBar,
    MatButton,
    MatIconButton,
    MatIcon,
    MatTooltip,
    HasPermission,
    PageHeader,
    StatusBadge,
  ],
  providers: [TripHistoryStore],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './trip-history.page.html',
  styleUrl: './trip-history.page.scss',
})
export class TripHistoryPage {
  protected readonly store = inject(TripHistoryStore);
  protected readonly adjustPermission = TRIP_ADJUST_PERMISSION;
  protected readonly statusSeverity = TRIP_STATUS_SEVERITY;
  protected readonly columns = ['visit', 'trip', 'when', 'distance', 'actions'];

  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  constructor() {
    const callId = Number(inject(ActivatedRoute).snapshot.paramMap.get('callId'));
    if (callId) this.store.load(callId);
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

  /** Can this trip be adjusted? Completed / auto-closed only; an in-progress trip has no distance yet. */
  protected canAdjust(trip: CallTripHistoryItem): boolean {
    return trip.status !== 'In progress';
  }

  /** GPS / Maps / Effective bars for the detail pane, scaled to the trip's largest value. */
  protected distanceRows(trip: CallTripHistoryItem): DistanceRow[] {
    const rows: Omit<DistanceRow, 'pct'>[] = [];
    if (trip.gpsDistanceKm !== null)
      rows.push({ label: 'GPS', value: trip.gpsDistanceKm, cls: 'gps' });
    if (trip.mapDistanceKm !== null)
      rows.push({ label: 'Maps API', value: trip.mapDistanceKm, cls: 'maps' });
    if (trip.effectiveDistanceKm !== null)
      rows.push({
        label: 'Effective',
        value: trip.effectiveDistanceKm,
        cls: 'eff',
      });
    const max = Math.max(1, ...rows.map((r) => r.value));
    return rows.map((r) => ({ ...r, pct: (r.value / max) * 100 }));
  }

  protected adjust(trip: CallTripHistoryItem, event?: Event): void {
    event?.stopPropagation();
    openAdjustDistanceDialog(this.dialog, trip).subscribe((updated) => {
      if (!updated) return;
      this.store.onAdjusted(updated);
      this.snackBar.open(
        `Distance adjusted to ${this.fmtKm(updated.effectiveDistanceKm)} km`,
        'OK',
        { duration: 4000 },
      );
    });
  }
}
