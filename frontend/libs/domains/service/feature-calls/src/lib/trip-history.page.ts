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
import { DocumentApi, documentIcon } from '@trishul/core-documents';
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

const MAP_W = 600;
const MAP_H = 400;
const MAP_PAD = 36;
const TILE = 256;
const MAX_ZOOM = 18;

interface MapPoint {
  x: number;
  y: number;
}

interface MapTile {
  href: string;
  x: number;
  y: number;
}

interface RouteMap {
  width: number;
  height: number;
  /** OpenStreetMap street tiles under the trail. */
  tiles: MapTile[];
  /** Runs of the cleaned trail where the good fixes are close together. */
  paths: string[];
  /** Straight jumps over stretches without a good fix (drawn dashed). */
  gaps: { a: MapPoint; b: MapPoint }[];
  /** Every fix as sent, weak ones included, for the "all points" view. */
  rawPath: string;
  start: MapPoint;
  end: MapPoint;
  mock: MapPoint[];
  /** Weak or impossible fixes left out of the line. */
  hidden: number;
}

/** Web Mercator pixel position at a zoom level (the projection of the map tiles). */
function worldPx(lat: number, lng: number, zoom: number): MapPoint {
  const size = TILE * 2 ** zoom;
  const s = Math.sin((Math.max(-85, Math.min(85, lat)) * Math.PI) / 180);
  return {
    x: ((lng + 180) / 360) * size,
    y: (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * size,
  };
}

type TrailPoint = TripRoute['points'][number];

// Same cleaning as the distance on the server (backend trk/distance.py), so the line drawn is the
// trail the kilometres were counted from.
const MAX_ACCURACY_M = 30;
const MAX_SPEED_KMPH = 120;
const MIN_MOVE_M = 5;
/** Good fixes further apart than this leave a stretch whose real path is unknown. */
const GAP_M = 150;

function metresBetween(a: TrailPoint, b: TrailPoint): number {
  const rad = Math.PI / 180;
  const dLat = (b.latitude - a.latitude) * rad;
  const dLng = (b.longitude - a.longitude) * rad;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(a.latitude * rad) * Math.cos(b.latitude * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371008.8 * Math.asin(Math.sqrt(h));
}

/**
 * The trail without weak fixes (worse than 30 m), fake GPS, jumps faster than 120 km/h and
 * standing-still jitter. Network fixes of 50-500 m otherwise zig-zag the line off the road.
 * Falls back to every point when fewer than two survive.
 */
function cleanTrail(points: readonly TrailPoint[]): TrailPoint[] {
  const usable = points.filter(
    (p) => !p.isMockLocation && (p.accuracyM == null || p.accuracyM <= MAX_ACCURACY_M),
  );
  if (usable.length < 2) return [...points];
  const kept: TrailPoint[] = [usable[0]];
  for (const p of usable.slice(1)) {
    const anchor = kept[kept.length - 1];
    const seconds = (Date.parse(p.recordedAt) - Date.parse(anchor.recordedAt)) / 1000;
    if (seconds <= 0) continue;
    const m = metresBetween(anchor, p);
    if (m < MIN_MOVE_M || (m / 1000) / (seconds / 3600) > MAX_SPEED_KMPH) continue;
    kept.push(p);
  }
  // Keep the real end point so the line finishes where the trip did.
  const last = usable[usable.length - 1];
  if (kept[kept.length - 1] !== last && kept.length > 1) kept.push(last);
  return kept.length >= 2 ? kept : [...points];
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
  styleUrls: ['./trip-history.page.scss', './trip-history.summary.scss'],
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

  /** Manual travel entries whose long notes are shown in full. */
  protected readonly highlightedManualId = signal<number | null>(null);
  protected readonly expandedNotes = signal<ReadonlySet<number>>(new Set());

  /** The strip above the boxes: kilometres of the call, entry counts and tickets still missing. */
  protected readonly summary = computed(() => {
    const trips = this.store.items();
    const manual = this.store.manualTravel();
    // Kilometres measured by GPS (or Maps) and kilometres someone set by hand are kept apart.
    const km = (t: CallTripHistoryItem): number => t.effectiveDistanceKm ?? 0;
    const gps = trips.filter((t) => !t.isDistanceAdjusted).reduce((sum, t) => sum + km(t), 0);
    const adjusted = trips.filter((t) => t.isDistanceAdjusted).reduce((sum, t) => sum + km(t), 0);
    const hand = manual.reduce((sum, m) => sum + Number(m.distanceKm), 0);
    return {
      trips: trips.length,
      adjustedTrips: trips.filter((t) => t.isDistanceAdjusted).length,
      adjusted,
      entries: manual.length,
      tickets: manual.reduce((sum, m) => sum + m.documentCount, 0),
      missing: manual.filter((m) => m.documentCount === 0).length,
      gps,
      manual: hand,
      all: gps + adjusted + hand,
    };
  });

  private readonly tripApi = inject(TripApi);
  private readonly documents = inject(DocumentApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  constructor() {
    const callId = Number(inject(ActivatedRoute).snapshot.paramMap.get('callId'));
    if (callId) this.store.load(callId);
  }

  /** Draw every fix as sent (dashed), not only the cleaned trail. */
  protected readonly showAllPoints = signal(false);

  /**
   * The selected trip's trail on OpenStreetMap streets: the zoom is the closest at which the cleaned
   * trail fits the 600x400 canvas, and the tiles are placed in the same Web Mercator pixels.
   */
  protected readonly map = computed<RouteMap | null>(() => {
    const all = this.store.route()?.points ?? [];
    if (!all.length) return null;
    const points = cleanTrail(all);
    const lats = points.map((p) => p.latitude);
    const lngs = points.map((p) => p.longitude);
    const [minLat, maxLat] = [Math.min(...lats), Math.max(...lats)];
    const [minLng, maxLng] = [Math.min(...lngs), Math.max(...lngs)];

    let zoom = MAX_ZOOM;
    for (; zoom > 1; zoom--) {
      const a = worldPx(maxLat, minLng, zoom);
      const b = worldPx(minLat, maxLng, zoom);
      if (b.x - a.x <= MAP_W - 2 * MAP_PAD && b.y - a.y <= MAP_H - 2 * MAP_PAD) break;
    }
    const a = worldPx(maxLat, minLng, zoom);
    const b = worldPx(minLat, maxLng, zoom);
    const originX = (a.x + b.x) / 2 - MAP_W / 2;
    const originY = (a.y + b.y) / 2 - MAP_H / 2;

    const tiles: MapTile[] = [];
    const count = 2 ** zoom;
    for (let ty = Math.floor(originY / TILE); ty * TILE < originY + MAP_H; ty++) {
      if (ty < 0 || ty >= count) continue;
      for (let tx = Math.floor(originX / TILE); tx * TILE < originX + MAP_W; tx++) {
        const wrapped = ((tx % count) + count) % count;
        tiles.push({
          href: `https://tile.openstreetmap.org/${zoom}/${wrapped}/${ty}.png`,
          x: tx * TILE - originX,
          y: ty * TILE - originY,
        });
      }
    }

    const at = (p: { latitude: number; longitude: number }): MapPoint => {
      const w = worldPx(p.latitude, p.longitude, zoom);
      return { x: w.x - originX, y: w.y - originY };
    };
    const line = (list: readonly TrailPoint[]): string =>
      list
        .map(at)
        .map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`)
        .join(' ');
    const xy = points.map(at);
    const paths: string[] = [];
    const gaps: { a: MapPoint; b: MapPoint }[] = [];
    let run: TrailPoint[] = [points[0]];
    for (let i = 1; i < points.length; i++) {
      if (metresBetween(points[i - 1], points[i]) > GAP_M) {
        gaps.push({ a: xy[i - 1], b: xy[i] });
        if (run.length > 1) paths.push(line(run));
        run = [points[i]];
      } else {
        run.push(points[i]);
      }
    }
    if (run.length > 1) paths.push(line(run));
    return {
      width: MAP_W,
      height: MAP_H,
      tiles,
      paths,
      gaps,
      rawPath: line(all),
      start: xy[0],
      end: xy[xy.length - 1],
      // Fake GPS points are marked wherever they were, even though the line leaves them out.
      mock: all.filter((p) => p.isMockLocation).map(at),
      hidden: all.length - points.length,
    };
  });

  protected mapsUrl(route: TripRoute): string {
    const pts = cleanTrail(route.points);
    if (!pts.length) return '#';
    const f = (p: { latitude: number; longitude: number }) =>
      `${p.latitude.toFixed(6)},${p.longitude.toFixed(6)}`;
    // Good fixes spread along the trail, so Google follows the real path, not its own shortest road.
    // A weak fix here snaps to a nearby place and sends Google on a detour.
    const mid = [0.2, 0.4, 0.6, 0.8]
      .map((r) => pts[Math.floor((pts.length - 1) * r)])
      .filter((p, i, list) => i === 0 || p !== list[i - 1]);
    const waypoints = pts.length > 2 ? `&waypoints=${mid.map(f).join('|')}` : '';
    return (
      'https://www.google.com/maps/dir/?api=1&travelmode=driving' +
      `&origin=${f(pts[0])}&destination=${f(pts[pts.length - 1])}` +
      waypoints
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

  /** Public transport the same engineer entered for the day this trip started (matched by date only, not tied to the trip). */
  protected manualFor(
    trip: CallTripHistoryItem,
  ): { km: number; firstId: number } | null {
    const day = localDay(trip.startAt);
    const same = this.store
      .manualTravel()
      .filter((m) => m.employeeId === trip.engineerEmployeeId && m.travelDate.slice(0, 10) === day);
    if (!same.length) return null;
    return {
      km: same.reduce((sum, m) => sum + Number(m.distanceKm), 0),
      firstId: same[0].id,
    };
  }

  /** Where a finished trip's distance comes from, so a 0 or missing value is not mistaken for an error. */
  protected distanceSource(trip: CallTripHistoryItem): string | null {
    if (trip.status === 'In progress') return null;
    if (trip.isDistanceAdjusted) return 'Adjusted by hand';
    if (trip.effectiveDistanceKm) return trip.mapDistanceKm ? 'Maps' : 'GPS';
    if (!trip.isGpsTracked) return 'Not GPS tracked';
    return trip.gpsDistanceKm === 0 ? 'GPS: no movement' : 'No GPS distance';
  }

  /** Scrolls to the manual travel entry and highlights it for a moment. */
  protected focusManual(id: number, event: Event): void {
    event.stopPropagation();
    this.highlightedManualId.set(id);
    document
      .getElementById('manual-' + id)
      ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setTimeout(() => this.highlightedManualId.set(null), 2500);
  }

  protected toggleNotes(id: number): void {
    this.expandedNotes.update((open) => {
      const next = new Set(open);
      if (!next.delete(id)) next.add(id);
      return next;
    });
  }

  /** Notes longer than this get a "more" toggle. */
  protected longNote(notes: string | null | undefined): boolean {
    return (notes?.length ?? 0) > 90;
  }

  protected openDocument(doc: { id: number; fileName: string }): void {
    this.documents.view(doc.id, doc.fileName);
  }

  protected docIcon(contentType: string): string {
    return documentIcon(contentType);
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
    if (trip.isGpsTracked && trip.gpsDistanceKm !== null)
      rows.push({ label: 'GPS', value: trip.gpsDistanceKm, cls: 'gps' });
    if (trip.isGpsTracked && trip.mapDistanceKm !== null)
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

/** yyyy-mm-dd of an instant in the viewer's own time zone. */
function localDay(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number): string => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
