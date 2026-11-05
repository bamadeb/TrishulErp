import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
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
  ManualTravelOut,
  TRIP_ADJUST_PERMISSION,
  TRIP_MANAGE_PERMISSION,
  TripApi,
  TripHistoryStore,
  TripRoute,
  TripStatus,
} from '@trishul/service-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { openAdjustDistanceDialog } from './adjust-distance.dialog';
import { ManualTravelDialog } from './manual-travel.dialog';

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

const MAP_W = 300;
const MAP_H = 200;
const MAP_PAD = 16;

interface MapPoint {
  x: number;
  y: number;
}

interface RouteMap {
  path: string;
  start: MapPoint;
  end: MapPoint;
  mock: MapPoint[];
}

/** Friendly names for the diagnostic event codes the phone sends; unknown codes are shown as sent. */
const EVENT_LABELS: Record<string, string> = {
  GPS_DISABLED: 'GPS turned off',
  GPS_ENABLED: 'GPS turned on',
  PERMISSION_REVOKED: 'Location permission removed',
  PERMISSION_DENIED: 'Location permission denied',
  POWER_SAVE_ON: 'Power saving turned on',
  LOCATION_GAP: 'Gap in location updates',
  NETWORK_LOST: 'Network lost',
  NETWORK_RESTORED: 'Network back',
};

/** Trip history for one service call: every trip across its visits, with GPS vs. adjusted distance. */
@Component({
  selector: 'trishul-trip-history-page',
  imports: [
    DatePipe,
    DecimalPipe,
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
  protected readonly manageTripPermission = TRIP_MANAGE_PERMISSION;
  protected readonly statusSeverity = TRIP_STATUS_SEVERITY;
  protected readonly columns = ['visit', 'trip', 'when', 'distance', 'actions'];

  protected readonly manualColumns = [
    'date',
    'engineer',
    'vehicle',
    'km',
    'notes',
    'docs',
    'manualActions',
  ];
  protected readonly confirmDeleteId = signal<number | null>(null);

  private readonly tripApi = inject(TripApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  constructor() {
    const callId = Number(inject(ActivatedRoute).snapshot.paramMap.get('callId'));
    if (callId) this.store.load(callId);
  }

  /** The selected trip's trail projected onto a 300x200 canvas (equirectangular, aspect kept). */
  protected readonly map = computed<RouteMap | null>(() => {
    const points = this.store.route()?.points ?? [];
    if (!points.length) return null;
    const lats = points.map((p) => p.latitude);
    const lngs = points.map((p) => p.longitude);
    const minLat = Math.min(...lats);
    const minLng = Math.min(...lngs);
    const kx = Math.cos(((minLat + Math.max(...lats)) / 2) * (Math.PI / 180));
    const w = Math.max((Math.max(...lngs) - minLng) * kx, 1e-6);
    const h = Math.max(Math.max(...lats) - minLat, 1e-6);
    const scale = Math.min((MAP_W - 2 * MAP_PAD) / w, (MAP_H - 2 * MAP_PAD) / h);
    const offX = (MAP_W - w * scale) / 2;
    const offY = (MAP_H - h * scale) / 2;
    const at = (p: { latitude: number; longitude: number }): MapPoint => ({
      x: offX + (p.longitude - minLng) * kx * scale,
      y: MAP_H - (offY + (p.latitude - minLat) * scale),
    });
    const xy = points.map(at);
    return {
      path: xy.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' '),
      start: xy[0],
      end: xy[xy.length - 1],
      mock: xy.filter((_, i) => points[i].isMockLocation),
    };
  });

  protected mapsUrl(route: TripRoute): string {
    const pts = route.points;
    if (!pts.length) return '#';
    const f = (p: { latitude: number; longitude: number }) =>
      `${p.latitude},${p.longitude}`;
    // Sample a few points in between so Google follows the real path, not the shortest road.
    const mid = [0.25, 0.5, 0.75].map((r) => pts[Math.floor(pts.length * r)]);
    return (
      'https://www.google.com/maps/dir/?api=1&travelmode=driving' +
      `&origin=${f(pts[0])}&destination=${f(pts[pts.length - 1])}` +
      `&waypoints=${mid.map(f).join('|')}`
    );
  }

  protected accuracy(m: number | null | undefined): string {
    return m === null || m === undefined ? '—' : `${m.toFixed(1)} m`;
  }

  protected eventLabel(type: string): string {
    return EVENT_LABELS[type] ?? type.replace(/_/g, ' ').toLowerCase();
  }

  protected addManualTravel(): void {
    const callId = this.store.callId();
    if (callId === null) return;
    this.openManualDialog({ callId, callNo: this.callNo() });
  }

  protected openManualTravel(entry: ManualTravelOut): void {
    this.openManualDialog({
      callId: entry.serviceCallId,
      callNo: this.callNo(),
      entry,
    });
  }

  protected deleteManualTravel(entry: ManualTravelOut): void {
    this.tripApi.deleteManualTravel(entry).subscribe(() => {
      this.confirmDeleteId.set(null);
      this.store.reloadManualTravel();
      this.snackBar.open('Travel entry removed', 'OK', { duration: 3000 });
    });
  }

  private callNo(): string {
    return `#${this.store.callId() ?? ''}`;
  }

  private openManualDialog(data: {
    callId: number;
    callNo: string;
    entry?: ManualTravelOut;
  }): void {
    this.dialog
      .open(ManualTravelDialog, {
        data,
        width: '36rem',
        maxWidth: '95vw',
        autoFocus: 'dialog',
      })
      .afterClosed()
      // Saved, corrected or documents added: any of them can change the row, so always refresh.
      .subscribe(() => this.store.reloadManualTravel());
  }

  protected fmtKm(value: number | null | undefined): string {
    return value === null || value === undefined ? '—' : value.toFixed(2);
  }

  protected battery(pct: number | null | undefined): string {
    return pct === null || pct === undefined ? '—' : `${pct}%`;
  }

  /** e.g. "samsung SM-E025F · Android 12 · app 1.7". */
  protected device(trip: CallTripHistoryItem): string {
    const name = [trip.deviceManufacturer, trip.deviceModel]
      .filter(Boolean)
      .join(' ');
    const os = [trip.devicePlatform, trip.deviceOsVersion]
      .filter(Boolean)
      .join(' ');
    const app = trip.deviceAppVersion ? `app ${trip.deviceAppVersion}` : '';
    return [name, os, app].filter(Boolean).join(' · ') || '—';
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
