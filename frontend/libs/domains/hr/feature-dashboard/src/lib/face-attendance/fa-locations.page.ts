import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltip } from '@angular/material/tooltip';
import { AuthStore } from '@trishul/core-auth';
import {
  FACE_ATTENDANCE_MANAGE_PERMISSION,
  FaceAttendanceApi,
  WorkLocation,
} from '@trishul/hr-data-access';
import { StatusBadge } from '@trishul/shared-ui';
import { forkJoin } from 'rxjs';
import { FaLocationDialog, FaLocationDialogData } from './fa-location.dialog';
import { mapLink } from './face-attendance.shared';

/** Office geofences: office staff (OFFICE policy) must punch inside one of their locations. */
@Component({
  selector: 'trishul-fa-locations-page',
  imports: [
    MatButton,
    MatIcon,
    MatIconButton,
    MatProgressBar,
    MatTooltip,
    StatusBadge,
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
          <h2>Work locations</h2>
          <p>
            Office staff must punch within the radius of one of their work
            locations; field staff may punch anywhere.
          </p>
        </div>
        @if (canManage()) {
          <button mat-flat-button type="button" (click)="open()">
            <mat-icon>add_location</mat-icon> Add location
          </button>
        }
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Branch</th>
              <th>Location</th>
              <th>Radius</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (row of rows(); track row.id) {
              <tr>
                <td>
                  <strong>{{ row.name }}</strong>
                  @if (row.address) {
                    <br /><span class="muted">{{ row.address }}</span>
                  }
                </td>
                <td>{{ row.branchName || '—' }}</td>
                <td>
                  <a
                    class="map"
                    [href]="mapLink(row.latitude, row.longitude)"
                    target="_blank"
                    rel="noopener"
                  >
                    {{ row.latitude }}, {{ row.longitude }}
                  </a>
                </td>
                <td>{{ row.radiusM }} m</td>
                <td>
                  <trishul-status-badge
                    [status]="row.isActive ? 'Active' : 'Inactive'"
                    [severities]="{ Active: 'success', Inactive: 'neutral' }"
                  />
                </td>
                <td class="actions-cell">
                  @if (canManage()) {
                    <button
                      mat-icon-button
                      type="button"
                      matTooltip="Edit"
                      (click)="open(row)"
                    >
                      <mat-icon>edit</mat-icon>
                    </button>
                  }
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="6">
                  <div class="empty">
                    <mat-icon>location_on</mat-icon>
                    {{
                      loading()
                        ? 'Loading…'
                        : 'No work locations yet. Add the offices where staff punch in.'
                    }}
                  </div>
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    </section>
  `,
  styleUrl: './face-attendance.shared.scss',
})
export class FaLocationsPage implements OnInit {
  private readonly api = inject(FaceAttendanceApi);
  private readonly auth = inject(AuthStore);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly mapLink = mapLink;
  protected readonly canManage = computed(() =>
    this.auth.hasPermission(FACE_ATTENDANCE_MANAGE_PERMISSION),
  );
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly rows = signal<WorkLocation[]>([]);
  private branches: { id: number; name: string }[] = [];

  ngOnInit(): void {
    this.reload();
  }

  protected open(row?: WorkLocation): void {
    const data: FaLocationDialogData = { row, branches: this.branches };
    this.dialog
      .open(FaLocationDialog, { data, width: '32rem' })
      .afterClosed()
      .subscribe((saved?: boolean) => {
        if (!saved) return;
        this.snackBar.open(
          row ? 'Work location updated.' : 'Work location added.',
          'OK',
          { duration: 3000 },
        );
        this.reload();
      });
  }

  private reload(): void {
    this.loading.set(true);
    this.error.set(null);
    forkJoin({
      locations: this.api.listLocations(),
      employees: this.api.listEmployees(),
    }).subscribe({
      next: ({ locations, employees }) => {
        this.rows.set(locations);
        // Branches for the form, from the employees list (no extra permission needed).
        const seen = new Map<number, string>();
        for (const e of employees)
          if (e.branchId && e.branchName) seen.set(e.branchId, e.branchName);
        this.branches = [...seen]
          .map(([id, name]) => ({ id, name }))
          .sort((a, b) => a.name.localeCompare(b.name));
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Work locations could not be loaded.');
        this.loading.set(false);
      },
    });
  }
}
