import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialog,
  MatDialogModule,
} from '@angular/material/dialog';
import { MatFormField, MatHint, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { Observable } from 'rxjs';

export interface FaTextDialogData {
  title: string;
  message: string;
  label: string;
  confirmText: string;
  destructive?: boolean;
}

/** Asks for a short reason or remark (3–300 characters); closes with the text, or undefined. */
@Component({
  selector: 'trishul-fa-text-dialog',
  imports: [
    ReactiveFormsModule,
    MatButton,
    MatDialogModule,
    MatFormField,
    MatHint,
    MatInput,
    MatLabel,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ data.title }}</h2>
    <mat-dialog-content>
      <p>{{ data.message }}</p>
      <mat-form-field appearance="outline" class="full">
        <mat-label>{{ data.label }}</mat-label>
        <textarea
          matInput
          rows="3"
          maxlength="300"
          [formControl]="text"
        ></textarea>
        <mat-hint align="end">{{ text.value.length }}/300</mat-hint>
      </mat-form-field>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" mat-dialog-close>Cancel</button>
      <button
        mat-flat-button
        type="button"
        [class.destructive]="data.destructive"
        [disabled]="text.invalid"
        [mat-dialog-close]="text.value.trim()"
      >
        {{ data.confirmText }}
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    .full {
      width: min(26rem, 80vw);
    }
    p {
      margin-top: 0;
    }
    .destructive {
      --mat-button-filled-container-color: var(--mat-sys-error);
      --mat-button-filled-label-text-color: var(--mat-sys-on-error);
    }
  `,
})
export class FaTextDialog {
  protected readonly data = inject<FaTextDialogData>(MAT_DIALOG_DATA);
  protected readonly text = new FormControl('', {
    nonNullable: true,
    validators: [
      Validators.required,
      Validators.minLength(3),
      Validators.maxLength(300),
    ],
  });
}

export function askText(
  dialog: MatDialog,
  data: FaTextDialogData,
): Observable<string | undefined> {
  return dialog
    .open<FaTextDialog, FaTextDialogData, string>(FaTextDialog, { data })
    .afterClosed();
}
