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
  AttendancePolicy,
  FACE_ATTENDANCE_MANAGE_PERMISSION,
  FaceAttendanceApi,
} from '@trishul/hr-data-access';
import { StatusBadge } from '@trishul/shared-ui';
import { FaPolicyDialog, FaPolicyDialogData } from './fa-policy.dialog';

/** Attendance policies: OFFICE and FIELD come ready; HR can tune them or add more. */
@Component({
  selector: 'trishul-fa-policies-page',
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
          <h2>Policies</h2>
          <p>
            A policy decides where an employee may punch, which liveness check
            the app asks for and how strict the checks are.
          </p>
        </div>
        @if (canManage()) {
          <button mat-flat-button type="button" (click)="open()">
            <mat-icon>add</mat-icon> Add policy
          </button>
        }
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Policy</th>
              <th>Where</th>
              <th>Liveness check</th>
              <th>Offline</th>
              <th>GPS</th>
              <th>Employees</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (row of rows(); track row.id) {
              <tr>
                <td>
                  <strong>{{ row.code }}</strong
                  ><br />
                  <span class="muted">{{ row.name }}</span>
                </td>
                <td>{{ row.mode }}</td>
                <td>
                  {{ row.challenge }}
                  <br /><span class="muted">{{
                    row.challengeOnCheckOut
                      ? 'also on check-out'
                      : 'check-out: blink only'
                  }}</span>
                </td>
                <td>
                  @if (row.allowOffline) {
                    Allowed
                    <span class="muted"
                      >({{
                        row.offlineAutoAccept ? 'auto-accept' : 'HR reviews'
                      }}, {{ row.maxOfflineHours }} h)</span
                    >
                  } @else {
                    Not allowed
                  }
                </td>
                <td>±{{ row.maxGpsAccuracyM }} m</td>
                <td>{{ row.employeeCount }}</td>
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
                <td colspan="8">
                  <div class="empty">
                    <mat-icon>rule</mat-icon
                    >{{ loading() ? 'Loading…' : 'No policies.' }}
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
export class FaPoliciesPage implements OnInit {
  private readonly api = inject(FaceAttendanceApi);
  private readonly auth = inject(AuthStore);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly canManage = computed(() =>
    this.auth.hasPermission(FACE_ATTENDANCE_MANAGE_PERMISSION),
  );
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly rows = signal<AttendancePolicy[]>([]);

  ngOnInit(): void {
    this.reload();
  }

  protected open(row?: AttendancePolicy): void {
    const data: FaPolicyDialogData = { row };
    this.dialog
      .open(FaPolicyDialog, { data, width: '34rem' })
      .afterClosed()
      .subscribe((saved?: boolean) => {
        if (!saved) return;
        this.snackBar.open(row ? 'Policy updated.' : 'Policy added.', 'OK', {
          duration: 3000,
        });
        this.reload();
      });
  }

  private reload(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.listPolicies().subscribe({
      next: (rows) => {
        this.rows.set(rows);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Policies could not be loaded.');
        this.loading.set(false);
      },
    });
  }
}
