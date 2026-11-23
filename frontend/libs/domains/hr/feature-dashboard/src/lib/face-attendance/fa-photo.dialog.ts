import {
  ChangeDetectionStrategy,
  Component,
  OnDestroy,
  inject,
  signal,
} from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatProgressSpinner } from '@angular/material/progress-spinner';
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';
import { Observable } from 'rxjs';

export interface FaPhotoDialogData {
  title: string;
  caption?: string;
  /** Loads the photo; the server writes each view to the attendance audit log. */
  load: () => Observable<Blob>;
}

/** Shows a stored face or punch photo (fetched with the user's token; never cached). */
@Component({
  selector: 'trishul-fa-photo-dialog',
  imports: [MatButton, MatDialogModule, MatProgressSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ data.title }}</h2>
    <mat-dialog-content>
      @if (url(); as src) {
        <img [src]="src" alt="Face photo" />
      } @else if (error()) {
        <p class="error">{{ error() }}</p>
      } @else {
        <mat-progress-spinner mode="indeterminate" diameter="40" />
      }
      @if (data.caption) {
        <p class="caption">{{ data.caption }}</p>
      }
      <p class="note">
        Viewing this photo is recorded in the attendance audit log.
      </p>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" mat-dialog-close>Close</button>
    </mat-dialog-actions>
  `,
  styles: `
    mat-dialog-content {
      display: grid;
      justify-items: center;
      gap: 0.5rem;
      min-width: min(22rem, 80vw);
    }
    img {
      max-width: min(26rem, 80vw);
      max-height: 60vh;
      border-radius: var(--mat-sys-corner-medium);
    }
    .caption,
    .note {
      margin: 0;
      color: var(--mat-sys-on-surface-variant);
      font: var(--mat-sys-body-small);
    }
    .error {
      color: var(--mat-sys-error);
    }
  `,
})
export class FaPhotoDialog implements OnDestroy {
  protected readonly data = inject<FaPhotoDialogData>(MAT_DIALOG_DATA);
  private readonly sanitizer = inject(DomSanitizer);
  protected readonly url = signal<SafeUrl | null>(null);
  protected readonly error = signal<string | null>(null);
  private objectUrl: string | null = null;

  constructor() {
    this.data.load().subscribe({
      next: (blob) => {
        this.objectUrl = URL.createObjectURL(blob);
        this.url.set(this.sanitizer.bypassSecurityTrustUrl(this.objectUrl));
      },
      error: () =>
        this.error.set(
          'The photo could not be loaded (it may have been deleted).',
        ),
    });
  }

  ngOnDestroy(): void {
    if (this.objectUrl) URL.revokeObjectURL(this.objectUrl);
  }
}
