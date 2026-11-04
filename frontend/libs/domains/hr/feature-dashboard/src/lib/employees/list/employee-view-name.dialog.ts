import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';

export interface EmployeeViewNameData {
  title: string;
  name: string;
}

/** Asks for a saved-view name. The dialog result is the trimmed name. */
@Component({
  selector: 'trishul-employee-view-name-dialog',
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
      <mat-form-field appearance="outline" subscriptSizing="dynamic" class="name">
        <mat-label>View name</mat-label>
        <input
          matInput
          maxlength="60"
          [value]="name()"
          (input)="name.set($any($event.target).value)"
        />
      </mat-form-field>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" mat-dialog-close>Cancel</button>
      <button
        mat-flat-button
        color="primary"
        type="button"
        [disabled]="!name().trim()"
        [mat-dialog-close]="name().trim()"
      >
        Save
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    .name {
      width: 100%;
      min-width: 16rem;
    }
  `,
})
export class EmployeeViewNameDialog {
  protected readonly data = inject<EmployeeViewNameData>(MAT_DIALOG_DATA);
  protected readonly name = signal(this.data.name);
}
