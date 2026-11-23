import {
  ChangeDetectionStrategy,
  Component,
  OnDestroy,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';
import {
  AttendanceEmployee,
  FaceAttendanceApi,
  faceAttendanceError,
} from '@trishul/hr-data-access';

export interface FaRegisterFaceDialogData {
  employee: AttendanceEmployee;
}

const MAX_BYTES = 8 * 1024 * 1024;

/** Uploads an employee's face photo with their consent; a second HR user approves it afterwards. */
@Component({
  selector: 'trishul-fa-register-face-dialog',
  imports: [
    FormsModule,
    MatButton,
    MatCheckbox,
    MatDialogModule,
    MatIcon,
    MatProgressBar,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Register face</h2>
    <mat-dialog-content>
      <p class="who">
        {{ data.employee.employeeName }} ({{ data.employee.employeeCode }})
      </p>
      <ul class="tips">
        <li>
          Only the employee in the photo, facing the camera, in good light.
        </li>
        <li>
          No cap, mask or sunglasses. The face should fill a good part of the
          photo.
        </li>
        <li>JPEG or PNG, up to 8 MB. A phone photo taken now is best.</li>
      </ul>
      <input
        #file
        type="file"
        accept="image/jpeg,image/png"
        hidden
        (change)="pick(file.files)"
      />
      <button
        mat-stroked-button
        type="button"
        (click)="file.click()"
        [disabled]="saving()"
      >
        <mat-icon>add_a_photo</mat-icon>
        {{ photo() ? 'Choose another photo' : 'Choose photo' }}
      </button>
      @if (preview(); as src) {
        <img [src]="src" alt="Selected photo" />
      }
      <mat-checkbox [(ngModel)]="consent" [disabled]="saving()">
        The employee agrees to their face being stored and used for attendance.
      </mat-checkbox>
      @if (saving()) {
        <mat-progress-bar mode="indeterminate" />
        <p class="muted">Checking the photo…</p>
      }
      @if (error()) {
        <p class="error">{{ error() }}</p>
      }
      <p class="muted">
        After saving, a different HR user must approve the face before the
        employee can punch.
      </p>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" mat-dialog-close [disabled]="saving()">
        Cancel
      </button>
      <button
        mat-flat-button
        type="button"
        [disabled]="!photo() || !consent || saving()"
        (click)="save()"
      >
        Register
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    mat-dialog-content {
      display: grid;
      gap: 0.6rem;
      justify-items: start;
      min-width: min(28rem, 90vw);
    }
    .who {
      margin: 0;
      font: var(--mat-sys-title-small);
    }
    .tips {
      margin: 0;
      padding-left: 1.1rem;
      color: var(--mat-sys-on-surface-variant);
      font: var(--mat-sys-body-small);
    }
    img {
      max-width: 14rem;
      max-height: 14rem;
      border-radius: var(--mat-sys-corner-medium);
      justify-self: center;
    }
    mat-progress-bar {
      width: 100%;
    }
    .error {
      margin: 0;
      color: var(--mat-sys-error);
      font-size: 0.82rem;
    }
    .muted {
      margin: 0;
      color: var(--mat-sys-on-surface-variant);
      font-size: 0.82rem;
    }
  `,
})
export class FaRegisterFaceDialog implements OnDestroy {
  private readonly api = inject(FaceAttendanceApi);
  private readonly ref = inject(MatDialogRef<FaRegisterFaceDialog, boolean>);
  private readonly sanitizer = inject(DomSanitizer);
  protected readonly data = inject<FaRegisterFaceDialogData>(MAT_DIALOG_DATA);
  protected readonly photo = signal<File | null>(null);
  protected readonly preview = signal<SafeUrl | null>(null);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected consent = false;
  private objectUrl: string | null = null;

  protected pick(files: FileList | null): void {
    const file = files?.[0];
    if (!file) return;
    this.error.set(null);
    if (!['image/jpeg', 'image/png'].includes(file.type)) {
      this.error.set('Choose a JPEG or PNG photo.');
      return;
    }
    if (file.size > MAX_BYTES) {
      this.error.set('The photo must be 8 MB or smaller.');
      return;
    }
    this.revoke();
    this.objectUrl = URL.createObjectURL(file);
    this.preview.set(this.sanitizer.bypassSecurityTrustUrl(this.objectUrl));
    this.photo.set(file);
  }

  protected save(): void {
    const file = this.photo();
    if (!file || !this.consent) return;
    this.saving.set(true);
    this.error.set(null);
    this.api.registerFace(this.data.employee.employeeId, file, true).subscribe({
      next: () => this.ref.close(true),
      error: (err) => {
        this.saving.set(false);
        this.error.set(
          faceAttendanceError(err, 'The face could not be registered.'),
        );
      },
    });
  }

  ngOnDestroy(): void {
    this.revoke();
  }

  private revoke(): void {
    if (this.objectUrl) URL.revokeObjectURL(this.objectUrl);
    this.objectUrl = null;
  }
}
