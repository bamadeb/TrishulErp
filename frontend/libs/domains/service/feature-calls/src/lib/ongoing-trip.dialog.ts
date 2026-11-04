import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { CallTripHistoryItem, TripApi } from '@trishul/service-data-access';

export interface OngoingTripData {
  callId: number;
  callNo: string;
}

const IN_PROGRESS = 'In progress';

/** Read-only details of the trip currently running on a service call. */
@Component({
  selector: 'trishul-ongoing-trip-dialog',
  imports: [
    DatePipe,
    DecimalPipe,
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatProgressBarModule,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Ongoing trips</h2>
    <mat-dialog-content>
      <p class="sub">
        Call {{ data.callNo }} · {{ trips().length }}
        {{ trips().length === 1 ? 'trip' : 'trips' }} running
      </p>
      @if (loading()) {
        <mat-progress-bar mode="indeterminate" aria-label="Loading trip" />
      } @else if (error()) {
        <p class="msg error" role="alert">
          <mat-icon inline>error_outline</mat-icon> {{ error() }}
        </p>
      } @else {
        @for (t of trips(); track t.id) {
          <section class="trip">
            <h3>
              {{ t.engineerName ?? 'Engineer' }}
              <span class="visit">· visit {{ t.visitNo }}</span>
            </h3>
            <dl>
              <dt>Trip ID</dt>
              <dd>#{{ t.id }}</dd>
              <dt>Service call ID</dt>
              <dd>{{ data.callId }}</dd>
              <dt>Service engineer</dt>
              <dd>{{ t.engineerName ?? '—' }}</dd>
              <dt>Status</dt>
              <dd>
                <span class="status"
                  ><span class="dot" aria-hidden="true"></span> Ongoing</span
                >
              </dd>
              <dt>Started</dt>
              <dd>{{ t.startAt | date: 'dd MMM yyyy, hh:mm a' }}</dd>
              <dt>Start location</dt>
              <dd>
                <a
                  [href]="mapUrl(t.startLatitude, t.startLongitude)"
                  target="_blank"
                  rel="noopener"
                  >{{ t.startLatitude | number: '1.5-5' }},
                  {{ t.startLongitude | number: '1.5-5' }}</a
                >
              </dd>
              <dt>Last known location</dt>
              <dd>
                @if (t.lastLatitude !== null && t.lastLongitude !== null) {
                  <a
                    [href]="mapUrl(t.lastLatitude, t.lastLongitude)"
                    target="_blank"
                    rel="noopener"
                    >{{ t.lastLatitude | number: '1.5-5' }},
                    {{ t.lastLongitude | number: '1.5-5' }}</a
                  >
                } @else {
                  No GPS fix received yet
                }
              </dd>
              <dt>Last GPS update</dt>
              <dd>
                {{
                  t.lastGpsAt
                    ? (t.lastGpsAt | date: 'dd MMM yyyy, hh:mm:ss a')
                    : '—'
                }}
              </dd>
              <dt>Distance travelled</dt>
              <dd>
                {{
                  t.effectiveDistanceKm !== null
                    ? (t.effectiveDistanceKm | number: '1.1-2') + ' km'
                    : 'Not available yet'
                }}
              </dd>
            </dl>
          </section>
        }
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>Close</button>
    </mat-dialog-actions>
  `,
  styles: `
    .sub {
      margin: 0 0 1rem;
      color: var(--mat-sys-on-surface-variant);
    }
    .trip + .trip {
      margin-top: 1rem;
      padding-top: 1rem;
      border-top: 1px solid var(--mat-sys-outline-variant);
    }
    h3 {
      margin: 0 0 0.5rem;
      font: var(--mat-sys-title-small);
    }
    .visit {
      font-weight: 400;
      color: var(--mat-sys-on-surface-variant);
    }
    dl {
      display: grid;
      grid-template-columns: max-content 1fr;
      gap: 0.5rem 1.25rem;
      margin: 0;
    }
    dt {
      color: var(--mat-sys-on-surface-variant);
    }
    dd {
      margin: 0;
      font-weight: 500;
      overflow-wrap: anywhere;
    }
    .status {
      display: inline-flex;
      align-items: center;
      gap: 0.25rem;
      color: #15803d;
    }
    .dot {
      width: 0.5rem;
      height: 0.5rem;
      border-radius: 50%;
      background: #22c55e;
    }
    .msg {
      display: flex;
      align-items: center;
      gap: 0.375rem;
      margin: 0;
    }
    .error {
      color: var(--mat-sys-error);
    }
    @media (max-width: 480px) {
      dl {
        grid-template-columns: 1fr;
        gap: 0.125rem;
      }
      dd {
        margin-bottom: 0.5rem;
      }
    }
  `,
})
export class OngoingTripDialog implements OnInit {
  protected readonly data = inject<OngoingTripData>(MAT_DIALOG_DATA);
  private readonly api = inject(TripApi);

  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly trips = signal<CallTripHistoryItem[]>([]);

  ngOnInit(): void {
    this.api.callTrips(this.data.callId).subscribe({
      next: (trips) => {
        // One trip per team member working the call, earliest start first.
        const ongoing = trips
          .filter((t) => t.status === IN_PROGRESS && !t.endAt)
          .sort((a, b) => a.startAt.localeCompare(b.startAt));
        this.trips.set(ongoing);
        if (!ongoing.length) {
          this.error.set('This call has no ongoing trip any more.');
        }
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Could not load the trip details. Please try again.');
        this.loading.set(false);
      },
    });
  }

  protected mapUrl(lat: number, lng: number): string {
    return `https://www.google.com/maps?q=${lat},${lng}`;
  }
}
