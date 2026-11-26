import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import { ShiftItem, ShiftWrite } from '@trishul/hr-data-access';

export interface ShiftFormData {
  mode: 'add' | 'edit';
  shift: ShiftItem | null;
}

@Component({
  selector: 'trishul-shift-form-dialog',
  imports: [FormsModule, MatButton, MatDialogModule, MatFormField, MatInput, MatLabel, MatSlideToggle],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ data.mode === 'add' ? 'Add Shift' : 'Edit Shift' }}</h2>
    <mat-dialog-content>
      @if (error()) {
        <p class="err">{{ error() }}</p>
      }
      <div class="grid">
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Code</mat-label>
          <input matInput maxlength="10" [(ngModel)]="form.code" name="code" required />
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Name</mat-label>
          <input matInput maxlength="60" [(ngModel)]="form.name" name="name" required />
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>In time</mat-label>
          <input matInput type="time" [(ngModel)]="form.startTime" name="startTime" required />
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Out time</mat-label>
          <input matInput type="time" [(ngModel)]="form.endTime" name="endTime" required />
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Grace (minutes)</mat-label>
          <input matInput type="number" min="0" max="240" [(ngModel)]="form.graceMinutes" name="grace" />
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Half-day hours</mat-label>
          <input
            matInput
            type="number"
            min="0"
            max="24"
            step="0.25"
            [(ngModel)]="form.halfDayHours"
            name="halfDay"
          />
        </mat-form-field>
      </div>
      <mat-slide-toggle [(ngModel)]="form.isActive" name="active">Active</mat-slide-toggle>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" mat-dialog-close>Cancel</button>
      <button mat-flat-button color="primary" type="button" (click)="save()">Save</button>
    </mat-dialog-actions>
  `,
  styles: `
    :host {
      display: block;
      width: 100%;
      max-width: 100%;
    }

    h2[mat-dialog-title] {
      margin: 0;
      padding: 12px 16px 0;
      font-size: 1.05rem;
      line-height: 1.3;
    }

    :host mat-dialog-content.mat-mdc-dialog-content {
      display: block;
      width: 100%;
      max-width: 100%;
      max-height: none;
      box-sizing: border-box;
      overflow: visible;
      padding: 10px 16px 4px;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 0.5rem 0.65rem;
      width: 100%;
      min-width: 0;
      margin-bottom: 0.45rem;
    }

    mat-form-field {
      width: 100%;
      min-width: 0;
    }

    :host ::ng-deep .mdc-floating-label--float-above {
      background: #fff;
      padding: 0 4px;
      overflow: visible;
      z-index: 1;
    }

    mat-slide-toggle {
      --mat-slide-toggle-track-height: 20px;
      --mat-slide-toggle-track-width: 36px;
      --mat-slide-toggle-track-shape: 10px;
      --mat-slide-toggle-with-icon-handle-size: 16px;
      --mat-slide-toggle-pressed-handle-size: 16px;
      --mat-slide-toggle-unselected-handle-size: 16px;
      --mat-slide-toggle-selected-handle-size: 16px;
      font-size: 13px;
    }

    :host ::ng-deep .mdc-switch__icons {
      display: none;
    }

    .err {
      margin: 0 0 0.4rem;
      color: #b3261e;
      font-size: 0.75rem;
    }

    mat-dialog-actions {
      justify-content: flex-end;
      gap: 0.35rem;
      min-height: 0;
      margin: 0;
      padding: 4px 16px 12px;
    }

    mat-dialog-actions button {
      min-width: 0;
      height: 32px;
      padding: 0 12px;
      font-size: 13px;
      line-height: 32px;
    }
  `,
})
export class ShiftFormDialog {
  private readonly ref = inject(MatDialogRef<ShiftFormDialog, ShiftWrite | null>);
  protected readonly data = inject<ShiftFormData>(MAT_DIALOG_DATA);
  protected readonly error = signal('');

  protected form: {
    code: string;
    name: string;
    startTime: string;
    endTime: string;
    graceMinutes: number;
    halfDayHours: number | null;
    isActive: boolean;
  } = {
    code: this.data.shift?.code ?? '',
    name: this.data.shift?.name ?? '',
    startTime: toInputTime(this.data.shift?.startTime),
    endTime: toInputTime(this.data.shift?.endTime),
    graceMinutes: this.data.shift?.graceMinutes ?? 10,
    halfDayHours: this.data.shift?.halfDayHours ?? null,
    isActive: this.data.shift?.isActive ?? true,
  };

  protected save(): void {
    const code = this.form.code.trim().toUpperCase();
    const name = this.form.name.trim();
    if (!code || !name || !this.form.startTime || !this.form.endTime) {
      this.error.set('Code, name, in time and out time are required.');
      return;
    }
    if (this.form.startTime === this.form.endTime) {
      this.error.set('In time and out time must differ.');
      return;
    }
    this.ref.close({
      code,
      name,
      startTime: normalizeTime(this.form.startTime),
      endTime: normalizeTime(this.form.endTime),
      graceMinutes: Number(this.form.graceMinutes) || 0,
      halfDayHours:
        this.form.halfDayHours === null || this.form.halfDayHours === ('' as unknown)
          ? null
          : Number(this.form.halfDayHours),
      isActive: this.form.isActive,
    });
  }
}

function toInputTime(value: string | undefined): string {
  if (!value) return '09:30';
  return value.slice(0, 5);
}

function normalizeTime(value: string): string {
  const parts = value.split(':');
  const hh = (parts[0] ?? '00').padStart(2, '0');
  const mm = (parts[1] ?? '00').padStart(2, '0');
  const ss = (parts[2] ?? '00').padStart(2, '0');
  return `${hh}:${mm}:${ss}`;
}
