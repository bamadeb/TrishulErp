import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { catchError, forkJoin, of } from 'rxjs';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import {
  MatFormField,
  MatLabel,
  MatPrefix,
} from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltip } from '@angular/material/tooltip';
import { ActivatedRoute } from '@angular/router';
import { AuthStore } from '@trishul/core-auth';
import {
  AttendanceApi,
  AttendanceStatus,
  FacePunch,
  FacePunchStatus,
  FACE_ATTENDANCE_MANAGE_PERMISSION,
  FACE_PHOTO_PERMISSION,
  FaceAttendanceApi,
  faceAttendanceError,
} from '@trishul/hr-data-access';
import { StatusBadge } from '@trishul/shared-ui';
import { AttendanceRegularizeDrawer } from '../attendance/attendance-regularize-drawer';
import { FaPhotoDialog, FaPhotoDialogData } from './fa-photo.dialog';
import { askText } from './fa-text.dialog';
import {
  PUNCH_STATUS_SEVERITIES,
  indiaToday,
  mapLink,
} from './face-attendance.shared';

/**
 * Mobile face punches. "With HR" (Pending) is the review queue: punches the server was not sure about
 * (uncertain face match, weak GPS, outside the office, offline with a doubtful clock...).
 */
@Component({
  selector: 'trishul-fa-punches-page',
  imports: [
    DatePipe,
    DecimalPipe,
    FormsModule,
    MatButton,
    MatFormField,
    MatIcon,
    MatIconButton,
    MatInput,
    MatLabel,
    MatOption,
    MatPrefix,
    MatProgressBar,
    MatSelect,
    MatTooltip,
    StatusBadge,
    AttendanceRegularizeDrawer,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (loading()) {
      <mat-progress-bar mode="indeterminate" />
    }
    @if (error()) {
      <p class="error">{{ error() }}</p>
    }
    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>{{ ownLogs() ? 'My Punch Logs' : 'Punches' }}</h2>
          <p>
            @if (ownLogs()) {
              Your check-ins and check-outs. Request a correction when that attendance date is eligible.
            } @else {
              Check-ins and check-outs from the mobile app. Punches waiting for
              review count as attendance only after they are accepted here.
            }
          </p>
        </div>
        <div class="head-actions">
          @if (ownLogs()) {
            <button mat-flat-button color="primary" type="button" (click)="openCorrect(null)">
              <mat-icon>edit_calendar</mat-icon> Request Regularization
            </button>
          }
          <button mat-stroked-button type="button" (click)="reload()">
            <mat-icon>refresh</mat-icon> Refresh
          </button>
        </div>
      </div>
      <div class="filters">
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Status</mat-label>
          <mat-select
            [ngModel]="status()"
            (ngModelChange)="status.set($event); reload()"
          >
            <mat-option value="Pending">Waiting for review</mat-option>
            <mat-option value="Present">Accepted</mat-option>
            <mat-option value="Rejected">Rejected</mat-option>
            <mat-option value="">All</mat-option>
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>From</mat-label>
          <input
            matInput
            type="date"
            [ngModel]="fromDate()"
            (ngModelChange)="fromDate.set($event); reload()"
          />
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>To</mat-label>
          <input
            matInput
            type="date"
            [ngModel]="toDate()"
            (ngModelChange)="toDate.set($event); reload()"
          />
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-icon matPrefix>search</mat-icon>
          <input
            matInput
            type="search"
            placeholder="Search name or code"
            [ngModel]="search()"
            (ngModelChange)="search.set($event)"
          />
        </mat-form-field>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Employee</th>
              <th>Punch</th>
              <th>Status</th>
              <th>Face</th>
              <th>Location</th>
              <th>Check</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (row of filtered(); track row.id) {
              <tr>
                <td>
                  <strong>{{ row.employeeName }}</strong
                  ><br />
                  <span class="muted">{{ row.employeeCode }}</span>
                </td>
                <td>
                  {{ row.punchType === 'In' ? 'Check-in' : 'Check-out' }}
                  {{ row.effectiveAt | date: 'h:mm a' }}<br />
                  <span class="muted">
                    {{ row.attendanceDate | date: 'd MMM y'
                    }}{{
                      row.captureMode === 'Offline'
                        ? ' · offline, phone time'
                        : ''
                    }}
                  </span>
                </td>
                <td>
                  <trishul-status-badge
                    [status]="statusLabel(row.status)"
                    [severities]="severities"
                  />
                  @if (row.statusReason) {
                    <div class="reason">{{ row.statusReason }}</div>
                  }
                  @if (row.reviewRemarks) {
                    <div class="reason">HR: {{ row.reviewRemarks }}</div>
                  }
                </td>
                <td>
                  {{ row.faceStatus }}
                  @if (row.serverScore != null) {
                    <br /><span class="muted"
                      >score {{ row.serverScore | number: '1.2-2' }}</span
                    >
                  }
                </td>
                <td>
                  @if (mapLink(row.latitude, row.longitude); as link) {
                    <a class="map" [href]="link" target="_blank" rel="noopener">
                      {{ row.workLocationName || 'Map' }}
                    </a>
                    <br />
                    <span class="muted">
                      @if (row.insideGeofence === true) {
                        inside
                      } @else if (row.insideGeofence === false) {
                        {{ row.distanceM | number: '1.0-0' }} m away
                      }
                      @if (row.gpsAccuracyM != null) {
                        · ±{{ row.gpsAccuracyM | number: '1.0-0' }} m
                      }
                      @if (row.isMockLocation) {
                        · <strong>fake GPS</strong>
                      }
                    </span>
                  } @else {
                    <span class="muted">No location</span>
                  }
                </td>
                <td>
                  <span class="muted"
                    >{{ row.challenge || '—' }}:
                    {{ row.challengeResult || '—' }}</span
                  >
                </td>
                <td class="actions-cell">
                  @if (canSeePhoto() && row.hasPhoto) {
                    <button
                      mat-icon-button
                      type="button"
                      matTooltip="View photo"
                      (click)="viewPhoto(row)"
                    >
                      <mat-icon>photo</mat-icon>
                    </button>
                  }
                  @if (canCorrect(row)) {
                    <button
                      mat-stroked-button
                      type="button"
                      (click)="openCorrect(row.attendanceDate)"
                    >
                      Correct
                    </button>
                  }
                  @if (canManage() && row.status === 'Pending') {
                    <button
                      mat-flat-button
                      type="button"
                      (click)="decide(row, 'Present')"
                    >
                      Accept
                    </button>
                    <button
                      mat-button
                      type="button"
                      (click)="decide(row, 'Rejected')"
                    >
                      Reject
                    </button>
                  }
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="7">
                  <div class="empty">
                    <mat-icon>fact_check</mat-icon>
                    {{
                      loading()
                        ? 'Loading…'
                        : status() === 'Pending'
                          ? 'Nothing is waiting for review.'
                          : 'No punches match.'
                    }}
                  </div>
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    </section>
    @for (key of drawerKeys(); track key) {
      <trishul-attendance-regularize-drawer
        [initialDate]="drawerDate()"
        (closed)="closeDrawer()"
        (submitted)="onRegularized()"
      />
    }
  `,
  styleUrl: './face-attendance.shared.scss',
})
export class FaPunchesPage implements OnInit {
  private readonly api = inject(FaceAttendanceApi);
  private readonly attendance = inject(AttendanceApi);
  private readonly auth = inject(AuthStore);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  private readonly route = inject(ActivatedRoute);
  protected readonly ownLogs = signal(false);
  protected readonly selfEmployeeId = signal<number | null>(null);
  protected readonly eligibleDates = signal<ReadonlySet<string>>(new Set());
  protected readonly drawerKeys = signal<number[]>([]);
  protected readonly drawerDate = signal<string | null>(null);

  protected readonly severities = {
    ...PUNCH_STATUS_SEVERITIES,
    'With HR': 'warn' as const,
    Accepted: 'success' as const,
  };
  protected readonly mapLink = mapLink;
  protected readonly canManage = computed(() =>
    this.auth.hasPermission(FACE_ATTENDANCE_MANAGE_PERMISSION),
  );
  protected readonly canSeePhoto = computed(() =>
    this.auth.hasPermission(FACE_PHOTO_PERMISSION),
  );
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly rows = signal<FacePunch[]>([]);
  protected readonly status = signal<FacePunchStatus | ''>('Pending');
  protected readonly fromDate = signal(shiftDays(indiaToday(), -7));
  protected readonly toDate = signal(indiaToday());
  protected readonly search = signal('');
  protected readonly filtered = computed(() => {
    const q = this.search().trim().toLowerCase();
    return this.rows().filter(
      (r) =>
        !q || `${r.employeeName} ${r.employeeCode}`.toLowerCase().includes(q),
    );
  });

  ngOnInit(): void {
    if (this.route.snapshot.data['ownLogs'] === true) {
      this.ownLogs.set(true);
      this.status.set('');
    }
    this.reload();
  }

  protected statusLabel(status: FacePunchStatus): string {
    return status === 'Pending'
      ? 'With HR'
      : status === 'Present'
        ? 'Accepted'
        : status;
  }

  protected reload(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api
      .listPunches({
        status: this.status(),
        fromDate: this.fromDate(),
        toDate: this.toDate(),
        mineOnly: this.ownLogs(),
        limit: 500,
      })
      .subscribe({
        next: (rows) => {
          this.rows.set(rows);
          this.loading.set(false);
          if (this.ownLogs()) this.refreshEligibility();
        },
        error: () => {
          this.error.set('Punches could not be loaded.');
          this.loading.set(false);
        },
      });
  }

  protected canCorrect(row: FacePunch): boolean {
    if (!this.ownLogs()) return false;
    const selfId = this.selfEmployeeId();
    if (selfId == null || row.employeeId !== selfId) return false;
    return this.eligibleDates().has(row.attendanceDate.slice(0, 10));
  }

  protected openCorrect(date: string | null): void {
    this.drawerDate.set(date ? date.slice(0, 10) : null);
    this.drawerKeys.set([Date.now()]);
  }

  protected closeDrawer(): void {
    this.drawerKeys.set([]);
  }

  protected onRegularized(): void {
    this.drawerKeys.set([]);
    this.refreshEligibility();
  }

  private refreshEligibility(): void {
    const months = monthsBetween(this.fromDate(), this.toDate());
    if (!months.length) {
      this.eligibleDates.set(new Set());
      return;
    }
    forkJoin(
      months.map(([year, month]) => this.attendance.mine(year, month).pipe(catchError(() => of(null)))),
    ).subscribe((pages) => {
      const dates = new Set<string>();
      let selfId: number | null = null;
      for (const page of pages) {
        if (!page) continue;
        selfId = page.employeeId;
        if (page.canRegularize === false || page.isMonthFinalized) continue;
        const requested = new Set((page.regularizations ?? []).map((row) => row.attendanceDate.slice(0, 10)));
        for (const day of page.items) {
          const iso = day.date.slice(0, 10);
          if (requested.has(iso) || !eligibleStatus(day.status)) continue;
          dates.add(iso);
        }
      }
      this.selfEmployeeId.set(selfId);
      this.eligibleDates.set(dates);
    });
  }

  protected viewPhoto(row: FacePunch): void {
    const data: FaPhotoDialogData = {
      title: `${row.employeeName} — ${row.punchType === 'In' ? 'check-in' : 'check-out'}`,
      caption: new Date(row.effectiveAt).toLocaleString('en-IN'),
      load: () => this.api.punchPhoto(row.id),
    };
    this.dialog.open(FaPhotoDialog, { data });
  }

  protected decide(row: FacePunch, decision: 'Present' | 'Rejected'): void {
    const accept = decision === 'Present';
    askText(this.dialog, {
      title: accept ? 'Accept punch' : 'Reject punch',
      message: `${row.employeeName}: ${row.statusReason ?? ''}`,
      label: accept
        ? 'Why it is fine (e.g. client site visit)'
        : 'Why it is rejected',
      confirmText: accept ? 'Accept' : 'Reject',
      destructive: !accept,
    }).subscribe((remarks) => {
      if (!remarks) return;
      this.api.reviewPunch(row.id, decision, remarks).subscribe({
        next: () => {
          this.snackBar.open(
            accept ? 'Punch accepted.' : 'Punch rejected.',
            'OK',
            { duration: 3000 },
          );
          this.reload();
        },
        error: (err) =>
          this.snackBar.open(
            faceAttendanceError(err, 'The punch could not be updated.'),
            'OK',
            { duration: 6000 },
          ),
      });
    });
  }
}

function shiftDays(isoDate: string, days: number): string {
  const d = new Date(`${isoDate}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function monthsBetween(from: string, to: string): [number, number][] {
  const start = new Date(`${from}T00:00:00`);
  const end = new Date(`${to}T00:00:00`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) return [];
  const out: [number, number][] = [];
  const cursor = new Date(start.getFullYear(), start.getMonth(), 1);
  const last = new Date(end.getFullYear(), end.getMonth(), 1);
  while (cursor <= last && out.length < 4) {
    out.push([cursor.getFullYear(), cursor.getMonth() + 1]);
    cursor.setMonth(cursor.getMonth() + 1);
  }
  return out;
}

function eligibleStatus(status: AttendanceStatus): boolean {
  return status === 'Present' || status === 'Late' || status === 'Missing Punch' || status === 'Absent';
}
