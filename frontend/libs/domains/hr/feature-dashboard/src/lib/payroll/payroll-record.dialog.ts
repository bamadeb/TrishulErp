import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect, MatSelectChange } from '@angular/material/select';

export interface PayrollDialogField {
  key: string;
  label: string;
  value: string;
  kind?: 'text' | 'number' | 'select';
  options?: readonly string[];
  required?: boolean;
}

export interface PayrollDialogData {
  title: string;
  mode: 'view' | 'edit' | 'create';
  fields: PayrollDialogField[];
}

/** Small add / edit / view form used by the payroll prototype screens. */
@Component({
  selector: 'trishul-payroll-record-dialog',
  imports: [
    MatButton,
    MatDialogTitle,
    MatDialogContent,
    MatDialogActions,
    MatDialogClose,
    MatFormField,
    MatLabel,
    MatInput,
    MatSelect,
    MatOption,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ data.title }}</h2>
    <mat-dialog-content>
      @if (data.mode === 'view') {
        <dl>
          @for (field of data.fields; track field.key) {
            <div>
              <dt>{{ field.label }}</dt>
              <dd>{{ field.value || '—' }}</dd>
            </div>
          }
        </dl>
      } @else {
        <div class="fields">
          @for (field of data.fields; track field.key) {
            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>{{ field.label }}</mat-label>
              @if (field.kind === 'select') {
                <mat-select
                  [value]="values()[field.key]"
                  (selectionChange)="setValue(field.key, $event)"
                >
                  @for (option of field.options ?? []; track option) {
                    <mat-option [value]="option">{{ option }}</mat-option>
                  }
                </mat-select>
              } @else {
                <input
                  matInput
                  [type]="field.kind === 'number' ? 'number' : 'text'"
                  [value]="values()[field.key]"
                  (input)="setText(field.key, $event)"
                />
              }
            </mat-form-field>
          }
        </div>
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" mat-dialog-close>
        {{ data.mode === 'view' ? 'Close' : 'Cancel' }}
      </button>
      @if (data.mode !== 'view') {
        <button mat-flat-button color="primary" type="button" [disabled]="!canSave()" (click)="save()">
          Save
        </button>
      }
    </mat-dialog-actions>
  `,
  styles: `
    .fields {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      min-width: min(28rem, 78vw);
      padding-top: 0.25rem;
    }
    dl {
      display: grid;
      gap: 0.65rem;
      margin: 0;
    }
    dt {
      color: var(--mat-sys-on-surface-variant);
      font: var(--mat-sys-body-small);
    }
    dd {
      margin: 0.1rem 0 0;
    }
  `,
})
export class PayrollRecordDialog {
  protected readonly data = inject<PayrollDialogData>(MAT_DIALOG_DATA);
  private readonly dialogRef = inject(MatDialogRef<PayrollRecordDialog, Record<string, string>>);
  protected readonly values = signal<Record<string, string>>(
    Object.fromEntries(this.data.fields.map((field) => [field.key, field.value])),
  );

  protected readonly canSave = computed(() =>
    this.data.fields
      .filter((field) => field.required)
      .every((field) => (this.values()[field.key] ?? '').trim().length > 0),
  );

  protected setText(key: string, event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.values.update((current) => ({ ...current, [key]: value }));
  }

  protected setValue(key: string, event: MatSelectChange): void {
    this.values.update((current) => ({ ...current, [key]: String(event.value ?? '') }));
  }

  protected save(): void {
    this.dialogRef.close(this.values());
  }
}
