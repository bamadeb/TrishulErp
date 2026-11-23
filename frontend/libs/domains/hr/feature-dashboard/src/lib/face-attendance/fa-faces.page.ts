import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
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
import { AuthStore } from '@trishul/core-auth';
import {
  FACE_APPROVE_PERMISSION,
  FACE_PHOTO_PERMISSION,
  FACE_REGISTER_PERMISSION,
  FaceAttendanceApi,
  FaceRegistration,
  FaceRegistrationStatus,
  faceAttendanceError,
  num,
} from '@trishul/hr-data-access';
import { StatusBadge, confirmAction } from '@trishul/shared-ui';
import { FaPhotoDialog, FaPhotoDialogData } from './fa-photo.dialog';
import { askText } from './fa-text.dialog';
import { FACE_STATUS_SEVERITIES } from './face-attendance.shared';

/** Face registrations: approve or reject waiting ones (not your own), view photos, delete face data. */
@Component({
  selector: 'trishul-fa-faces-page',
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
          <h2>Face registrations</h2>
          <p>
            A face is used for punches only after a second HR user approves it.
            You cannot approve a face you registered.
          </p>
        </div>
      </div>
      <div class="filters">
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Status</mat-label>
          <mat-select
            [ngModel]="status()"
            (ngModelChange)="status.set($event); reload()"
          >
            <mat-option value="Pending approval"
              >Waiting for approval</mat-option
            >
            <mat-option value="Active">Active</mat-option>
            <mat-option value="Rejected">Rejected</mat-option>
            <mat-option value="Superseded">Replaced</mat-option>
            <mat-option value="Deleted">Deleted</mat-option>
            <mat-option value="">All</mat-option>
          </mat-select>
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
              <th>Status</th>
              <th>Registered</th>
              <th>Photo quality</th>
              <th>Model</th>
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
                  <trishul-status-badge
                    [status]="row.status"
                    [severities]="severities"
                  />
                  @if (row.rejectionReason) {
                    <div class="reason">{{ row.rejectionReason }}</div>
                  }
                </td>
                <td>
                  {{ row.registeredAt | date: 'd MMM y, h:mm a' }}
                  @if (row.approvedAt) {
                    <br /><span class="muted"
                      >Approved {{ row.approvedAt | date: 'd MMM y' }}</span
                    >
                  }
                </td>
                <td>
                  @if (row.faceConfidence != null) {
                    <span class="muted">
                      Face
                      {{
                        (num(row.faceConfidence) ?? 0) * 100 | number: '1.0-0'
                      }}% · sharp {{ row.sharpness | number: '1.0-0' }} · light
                      {{ row.brightness | number: '1.0-0' }}
                    </span>
                  } @else {
                    —
                  }
                </td>
                <td>
                  <span class="muted">{{ row.faceModel || '—' }}</span>
                </td>
                <td class="actions-cell">
                  @if (canSeePhoto() && row.status !== 'Deleted') {
                    <button
                      mat-icon-button
                      type="button"
                      matTooltip="View photo"
                      (click)="viewPhoto(row)"
                    >
                      <mat-icon>photo</mat-icon>
                    </button>
                  }
                  @if (canApprove() && row.status === 'Pending approval') {
                    <button
                      mat-flat-button
                      type="button"
                      (click)="approve(row)"
                    >
                      Approve
                    </button>
                    <button mat-button type="button" (click)="reject(row)">
                      Reject
                    </button>
                  }
                  @if (canRegister() && row.status !== 'Deleted') {
                    <button
                      mat-icon-button
                      type="button"
                      matTooltip="Delete face data"
                      (click)="remove(row)"
                    >
                      <mat-icon>delete</mat-icon>
                    </button>
                  }
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="6">
                  <div class="empty">
                    <mat-icon>face</mat-icon>
                    {{
                      loading()
                        ? 'Loading…'
                        : status() === 'Pending approval'
                          ? 'No faces are waiting for approval.'
                          : 'No face registrations match.'
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
export class FaFacesPage implements OnInit {
  private readonly api = inject(FaceAttendanceApi);
  private readonly auth = inject(AuthStore);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly severities = FACE_STATUS_SEVERITIES;
  protected readonly num = num;
  protected readonly canApprove = computed(() =>
    this.auth.hasPermission(FACE_APPROVE_PERMISSION),
  );
  protected readonly canRegister = computed(() =>
    this.auth.hasPermission(FACE_REGISTER_PERMISSION),
  );
  protected readonly canSeePhoto = computed(() =>
    this.auth.hasAnyPermission([
      FACE_PHOTO_PERMISSION,
      FACE_APPROVE_PERMISSION,
    ]),
  );
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly rows = signal<FaceRegistration[]>([]);
  protected readonly status = signal<FaceRegistrationStatus | ''>(
    'Pending approval',
  );
  protected readonly search = signal('');
  protected readonly filtered = computed(() => {
    const q = this.search().trim().toLowerCase();
    return this.rows().filter(
      (r) =>
        !q || `${r.employeeName} ${r.employeeCode}`.toLowerCase().includes(q),
    );
  });

  ngOnInit(): void {
    this.reload();
  }

  protected reload(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.listFaces(this.status()).subscribe({
      next: (rows) => {
        this.rows.set(rows);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Face registrations could not be loaded.');
        this.loading.set(false);
      },
    });
  }

  protected viewPhoto(row: FaceRegistration): void {
    const data: FaPhotoDialogData = {
      title: `${row.employeeName} (${row.employeeCode})`,
      caption: `Registered ${new Date(row.registeredAt).toLocaleString('en-IN')}`,
      load: () => this.api.facePhoto(row.id),
    };
    this.dialog.open(FaPhotoDialog, { data });
  }

  protected approve(row: FaceRegistration): void {
    confirmAction(this.dialog, {
      title: 'Approve face',
      message: `Use this photo of ${row.employeeName} to check their attendance punches? Check the photo first: it must be this employee.`,
      confirmText: 'Approve',
    }).subscribe((ok) => {
      if (!ok) return;
      this.api.approveFace(row.id).subscribe({
        next: () => {
          this.snackBar.open(
            `Face approved. ${row.employeeName} can now punch if a policy is set.`,
            'OK',
            { duration: 4000 },
          );
          this.reload();
        },
        error: (err) =>
          this.snackBar.open(
            faceAttendanceError(err, 'The face could not be approved.'),
            'OK',
            { duration: 6000 },
          ),
      });
    });
  }

  protected reject(row: FaceRegistration): void {
    askText(this.dialog, {
      title: 'Reject face',
      message: `Why is this photo of ${row.employeeName} not usable? HR will see the reason when registering again.`,
      label: 'Reason',
      confirmText: 'Reject',
      destructive: true,
    }).subscribe((reason) => {
      if (!reason) return;
      this.api.rejectFace(row.id, reason).subscribe({
        next: () => {
          this.snackBar.open('Face rejected.', 'OK', { duration: 3000 });
          this.reload();
        },
        error: (err) =>
          this.snackBar.open(
            faceAttendanceError(err, 'The face could not be rejected.'),
            'OK',
            { duration: 6000 },
          ),
      });
    });
  }

  protected remove(row: FaceRegistration): void {
    const active = row.status === 'Active';
    confirmAction(this.dialog, {
      title: 'Delete face data',
      message:
        `Delete the stored photo and face data of ${row.employeeName}? This cannot be undone.` +
        (active
          ? ' This is their active face: they cannot punch until a new face is registered and approved.'
          : ''),
      confirmText: 'Delete',
      destructive: true,
    }).subscribe((ok) => {
      if (!ok) return;
      this.api.deleteFace(row).subscribe({
        next: () => {
          this.snackBar.open('Face data deleted.', 'OK', { duration: 3000 });
          this.reload();
        },
        error: (err) =>
          this.snackBar.open(
            faceAttendanceError(err, 'The face data could not be deleted.'),
            'OK',
            { duration: 6000 },
          ),
      });
    });
  }
}
