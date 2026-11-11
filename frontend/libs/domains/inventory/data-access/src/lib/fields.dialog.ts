import {
  ChangeDetectionStrategy,
  Component,
  inject,
  signal,
} from '@angular/core';
import {
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  ValidatorFn,
  Validators,
} from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { provideNativeDateAdapter } from '@angular/material/core';
import {
  MatDatepicker,
  MatDatepickerInput,
  MatDatepickerToggle,
} from '@angular/material/datepicker';
import {
  MAT_DIALOG_DATA,
  MatDialog,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import {
  MatError,
  MatFormField,
  MatHint,
  MatLabel,
  MatSuffix,
} from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { EMPTY, Observable, catchError, finalize } from 'rxjs';
import { fromIso, isoDate } from './inventory.shared';

export interface FieldOption {
  value: string | number | boolean | null;
  label: string;
}

export interface FieldDef {
  key: string;
  label: string;
  type?: 'text' | 'number' | 'select' | 'date' | 'checkbox' | 'textarea';
  required?: boolean;
  options?: FieldOption[];
  hint?: string;
  min?: number;
  max?: number;
  maxLength?: number;
  pattern?: string;
  /** Spans both columns. */
  wide?: boolean;
  /** Shown but not editable (e.g. a code that can't change). */
  readonly?: boolean;
}

export interface FieldsDialogData<R> {
  title: string;
  submitText: string;
  fields: FieldDef[];
  /** Starting values by key; dates as yyyy-mm-dd. */
  value?: Record<string, unknown>;
  /** Saves the values (dates as yyyy-mm-dd, empty text as null); the dialog closes with the result. */
  save: (value: Record<string, unknown>) => Observable<R>;
}

/** Opens a form of the given fields; resolves with what save() returned, or undefined if cancelled. */
export function openFieldsDialog<R>(
  dialog: MatDialog,
  data: FieldsDialogData<R>,
): Observable<R | undefined> {
  return dialog
    .open<FieldsDialog, FieldsDialogData<unknown>, R>(FieldsDialog, {
      data: data as FieldsDialogData<unknown>,
      autoFocus: 'first-tabbable',
      maxWidth: '95vw',
    })
    .afterClosed();
}

/** A small add / edit form for a master record (unit, rack, supplier, price, ...). */
@Component({
  selector: 'trishul-fields-dialog',
  imports: [
    ReactiveFormsModule,
    MatDialogTitle,
    MatDialogContent,
    MatDialogActions,
    MatDialogClose,
    MatFormField,
    MatLabel,
    MatHint,
    MatError,
    MatSuffix,
    MatInput,
    MatSelect,
    MatOption,
    MatCheckbox,
    MatDatepicker,
    MatDatepickerInput,
    MatDatepickerToggle,
    MatButton,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ data.title }}</h2>
    <mat-dialog-content>
      <form
        class="grid"
        [formGroup]="form"
        (ngSubmit)="save()"
        id="fields-form"
      >
        @for (f of data.fields; track f.key) {
          @switch (f.type ?? 'text') {
            @case ('checkbox') {
              <mat-checkbox class="wide" [formControlName]="f.key">{{
                f.label
              }}</mat-checkbox>
            }
            @case ('select') {
              <mat-form-field appearance="outline" [class.wide]="f.wide">
                <mat-label>{{ f.label }}</mat-label>
                <mat-select [formControlName]="f.key">
                  @for (o of f.options ?? []; track o.value) {
                    <mat-option [value]="o.value">{{ o.label }}</mat-option>
                  }
                </mat-select>
                @if (f.hint) {
                  <mat-hint>{{ f.hint }}</mat-hint>
                }
                <mat-error>Required.</mat-error>
              </mat-form-field>
            }
            @case ('date') {
              <mat-form-field appearance="outline" [class.wide]="f.wide">
                <mat-label>{{ f.label }}</mat-label>
                <input
                  matInput
                  [matDatepicker]="picker"
                  [formControlName]="f.key"
                />
                <mat-datepicker-toggle matSuffix [for]="picker" />
                <mat-datepicker #picker />
                @if (f.hint) {
                  <mat-hint>{{ f.hint }}</mat-hint>
                }
                <mat-error>Enter a valid date.</mat-error>
              </mat-form-field>
            }
            @case ('textarea') {
              <mat-form-field appearance="outline" class="wide">
                <mat-label>{{ f.label }}</mat-label>
                <textarea
                  matInput
                  rows="2"
                  [formControlName]="f.key"
                ></textarea>
              </mat-form-field>
            }
            @default {
              <mat-form-field appearance="outline" [class.wide]="f.wide">
                <mat-label>{{ f.label }}</mat-label>
                <input
                  matInput
                  [type]="f.type === 'number' ? 'number' : 'text'"
                  [formControlName]="f.key"
                  [readonly]="f.readonly"
                  [attr.min]="f.min ?? null"
                  [attr.max]="f.max ?? null"
                  autocomplete="off"
                />
                @if (f.hint) {
                  <mat-hint>{{ f.hint }}</mat-hint>
                }
                <mat-error>{{ errorText(f) }}</mat-error>
              </mat-form-field>
            }
          }
        }
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close type="button">Cancel</button>
      <button
        mat-flat-button
        type="submit"
        form="fields-form"
        [disabled]="saving()"
      >
        {{ data.submitText }}
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 0.25rem 0.75rem;
      width: 34rem;
      max-width: 100%;
      padding-top: 0.25rem;
    }
    .wide {
      grid-column: 1 / -1;
    }
    mat-checkbox {
      margin-bottom: 0.5rem;
    }
    @media (max-width: 600px) {
      .grid {
        grid-template-columns: 1fr;
      }
    }
  `,
})
export class FieldsDialog {
  protected readonly data = inject<FieldsDialogData<unknown>>(MAT_DIALOG_DATA);
  private readonly ref =
    inject<MatDialogRef<FieldsDialog, unknown>>(MatDialogRef);
  protected readonly saving = signal(false);
  protected readonly form = new FormGroup<Record<string, FormControl<unknown>>>(
    {},
  );

  constructor() {
    for (const field of this.data.fields) {
      const start = this.data.value?.[field.key];
      const value =
        field.type === 'date'
          ? fromIso(start as string | null)
          : field.type === 'checkbox'
            ? Boolean(start ?? false)
            : (start ?? null);
      const control = new FormControl<unknown>(value, this.validators(field));
      if (field.readonly) control.disable();
      this.form.addControl(field.key, control);
    }
  }

  private validators(field: FieldDef): ValidatorFn[] {
    const validators: ValidatorFn[] = [];
    if (field.required) validators.push(Validators.required);
    if (field.min !== undefined) validators.push(Validators.min(field.min));
    if (field.max !== undefined) validators.push(Validators.max(field.max));
    if (field.maxLength !== undefined)
      validators.push(Validators.maxLength(field.maxLength));
    if (field.pattern) validators.push(Validators.pattern(field.pattern));
    return validators;
  }

  protected errorText(field: FieldDef): string {
    const errors = this.form.controls[field.key]?.errors ?? {};
    if (errors['required']) return 'Required.';
    if (errors['min']) return `At least ${field.min}.`;
    if (errors['max']) return `At most ${field.max}.`;
    if (errors['maxlength']) return `At most ${field.maxLength} characters.`;
    if (errors['pattern']) return 'Not in the expected format.';
    return 'Check this value.';
  }

  protected save(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.saving()) return;
    const raw = this.form.getRawValue();
    const value: Record<string, unknown> = {};
    for (const field of this.data.fields) {
      let v = raw[field.key];
      if (v instanceof Date) v = isoDate(v);
      if (typeof v === 'string') v = v.trim() || null;
      value[field.key] = v;
    }
    this.saving.set(true);
    this.data
      .save(value)
      .pipe(
        finalize(() => this.saving.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe((result) => this.ref.close(result));
  }
}
