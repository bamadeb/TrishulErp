import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnDestroy,
  inject,
  signal,
  viewChild,
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

/**
 * Registers an employee's face from an uploaded photo or one taken now, with their consent; a second
 * HR user approves it afterwards.
 *
 * Taking a photo: browsers allow the webcam (getUserMedia) only on HTTPS pages. Where it isn't
 * available (the ERP on plain HTTP), "Take photo" opens the device camera through a file input with
 * capture="user": a phone or tablet opens its front camera; a laptop shows the file picker.
 */
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
        <li>JPEG or PNG, up to 8 MB. A photo taken now is best.</li>
      </ul>

      <input
        #file
        type="file"
        accept="image/jpeg,image/png"
        hidden
        (change)="pick(file.files); file.value = ''"
      />
      <input
        #shot
        type="file"
        accept="image/*"
        capture="user"
        hidden
        (change)="pick(shot.files); shot.value = ''"
      />

      @if (cameraOn()) {
        <div class="camera">
          <video #video autoplay playsinline muted></video>
          <div class="camera-actions">
            <button mat-flat-button type="button" (click)="capture()">
              <mat-icon>photo_camera</mat-icon>
              Capture
            </button>
            <button mat-button type="button" (click)="stopCamera()">
              Cancel
            </button>
          </div>
        </div>
      } @else {
        <div class="sources">
          <button
            mat-stroked-button
            type="button"
            (click)="takePhoto(shot)"
            [disabled]="saving()"
          >
            <mat-icon>photo_camera</mat-icon>
            Take photo
          </button>
          <button
            mat-stroked-button
            type="button"
            (click)="file.click()"
            [disabled]="saving()"
          >
            <mat-icon>upload</mat-icon>
            Upload photo
          </button>
        </div>
      }
      @if (cameraNote()) {
        <p class="muted">{{ cameraNote() }}</p>
      }

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
        [disabled]="!photo() || !consent || saving() || cameraOn()"
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
    .sources,
    .camera-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
    }
    .camera {
      display: grid;
      gap: 0.5rem;
      justify-self: center;
    }
    video {
      width: min(22rem, 75vw);
      border-radius: var(--mat-sys-corner-medium);
      background: #000;
      transform: scaleX(
        -1
      ); /* a mirror, as people expect from a front camera */
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
  private readonly video = viewChild<ElementRef<HTMLVideoElement>>('video');

  protected readonly photo = signal<File | null>(null);
  protected readonly preview = signal<SafeUrl | null>(null);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly cameraOn = signal(false);
  protected readonly cameraNote = signal<string | null>(null);
  protected consent = false;
  private objectUrl: string | null = null;
  private stream: MediaStream | null = null;

  /** Webcam on HTTPS; otherwise the device camera through the file input (phones open it directly). */
  protected async takePhoto(fallback: HTMLInputElement): Promise<void> {
    this.error.set(null);
    this.cameraNote.set(null);
    const media = navigator.mediaDevices;
    if (!window.isSecureContext || !media?.getUserMedia) {
      if (!isTouchDevice()) {
        this.cameraNote.set(
          'This browser allows the laptop camera only on a secure (https) address. ' +
            'Use Upload photo, or open this screen on a phone or tablet to take the photo there.',
        );
      }
      fallback.click();
      return;
    }
    try {
      this.stream = await media.getUserMedia({
        video: {
          facingMode: 'user',
          width: { ideal: 1280 },
          height: { ideal: 960 },
        },
        audio: false,
      });
      this.cameraOn.set(true);
      // The <video> appears with cameraOn; attach the stream once it exists.
      setTimeout(() => {
        const el = this.video()?.nativeElement;
        if (el && this.stream) el.srcObject = this.stream;
      });
    } catch {
      this.stopCamera();
      this.cameraNote.set(
        'The camera could not be opened (permission refused or no camera). Use Upload photo.',
      );
    }
  }

  protected capture(): void {
    const el = this.video()?.nativeElement;
    if (!el || !el.videoWidth) return;
    const canvas = document.createElement('canvas');
    canvas.width = el.videoWidth;
    canvas.height = el.videoHeight;
    // Stored the way the camera sees it (not mirrored), like a photo from a phone.
    canvas.getContext('2d')?.drawImage(el, 0, 0);
    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const name = `${this.data.employee.employeeCode}-${Date.now()}.jpg`;
        this.setPhoto(new File([blob], name, { type: 'image/jpeg' }));
        this.stopCamera();
      },
      'image/jpeg',
      0.92,
    );
  }

  protected stopCamera(): void {
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    this.cameraOn.set(false);
  }

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
    this.setPhoto(file);
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
    this.stopCamera();
    this.revoke();
  }

  private setPhoto(file: File): void {
    this.revoke();
    this.objectUrl = URL.createObjectURL(file);
    this.preview.set(this.sanitizer.bypassSecurityTrustUrl(this.objectUrl));
    this.photo.set(file);
  }

  private revoke(): void {
    if (this.objectUrl) URL.revokeObjectURL(this.objectUrl);
    this.objectUrl = null;
  }
}

function isTouchDevice(): boolean {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia('(pointer: coarse)').matches
  );
}
