import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialog,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { Observable } from 'rxjs';

export interface TadaConfirmLine {
  label: string;
  value: string;
}

export type TadaCommentMode = 'none' | 'approval' | 'rejection';

export interface TadaConfirmData {
  title: string;
  confirmText: string;
  lines: readonly TadaConfirmLine[];
  comments: TadaCommentMode;
  destructive?: boolean;
}

export interface TadaConfirmResult {
  reason: string;
}

/** Confirmation for a TA/DA approval, rejection, or payroll handoff. */
@Component({
  selector: 'trishul-tada-confirm-dialog',
  imports: [
    MatButton,
    MatDialogTitle,
    MatDialogContent,
    MatDialogActions,
    MatDialogClose,
    MatFormField,
    MatLabel,
    MatInput,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ data.title }}</h2>
    <mat-dialog-content>
      <dl>
        @for (line of data.lines; track line.label) {
          <div>
            <dt>{{ line.label }}</dt>
            <dd>{{ line.value }}</dd>
          </div>
        }
      </dl>
      @if (data.comments !== 'none') {
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>{{ data.comments === 'rejection' ? 'Rejection Reason' : 'Approval Comments' }}</mat-label>
          <textarea
            matInput
            rows="3"
            maxlength="500"
            [placeholder]="data.comments === 'rejection' ? 'Enter reason for rejection...' : 'Enter approval comments (optional)...'"
            [value]="reason()"
            (input)="reason.set($any($event.target).value)"
          ></textarea>
        </mat-form-field>
        @if (data.comments === 'rejection' && attempted() && !reason().trim()) {
          <p class="hint">A rejection reason is required.</p>
        }
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" mat-dialog-close>Cancel</button>
      <button
        mat-flat-button
        color="primary"
        type="button"
        [class.destructive]="data.destructive"
        (click)="confirm()"
      >
        {{ data.confirmText }}
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    mat-dialog-content {
      display: grid;
      gap: 0.85rem;
      min-width: min(26rem, 78vw);
    }
    dl {
      display: grid;
      gap: 0.55rem;
      margin: 0;
    }
    dt {
      color: var(--mat-sys-on-surface-variant);
      font: var(--mat-sys-body-small);
    }
    dd {
      margin: 0.1rem 0 0;
    }
    .hint {
      margin: 0;
      color: var(--mat-sys-error);
      font: var(--mat-sys-body-small);
    }
    .destructive {
      --mat-button-filled-container-color: var(--mat-sys-error);
      --mat-button-filled-label-text-color: var(--mat-sys-on-error);
    }
  `,
})
export class TadaConfirmDialog {
  protected readonly data = inject<TadaConfirmData>(MAT_DIALOG_DATA);
  private readonly dialogRef = inject(MatDialogRef<TadaConfirmDialog, TadaConfirmResult>);
  protected readonly reason = signal('');
  protected readonly attempted = signal(false);
  private closed = false;

  protected confirm(): void {
    const reason = this.reason().trim();
    if (this.closed) return;
    if (this.data.comments === 'rejection' && !reason) {
      this.attempted.set(true);
      return;
    }
    this.closed = true;
    this.dialogRef.close({ reason });
  }
}

export function openTadaConfirm(dialog: MatDialog, data: TadaConfirmData): Observable<TadaConfirmResult | undefined> {
  return dialog
    .open<TadaConfirmDialog, TadaConfirmData, TadaConfirmResult>(TadaConfirmDialog, {
      data,
      width: '28rem',
      autoFocus: data.comments === 'none' ? 'dialog' : 'textarea',
    })
    .afterClosed();
}
