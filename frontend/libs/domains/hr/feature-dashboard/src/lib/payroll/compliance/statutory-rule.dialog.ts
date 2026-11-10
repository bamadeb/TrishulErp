import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { DateAdapter, MAT_DATE_FORMATS, MAT_NATIVE_DATE_FORMATS, NativeDateAdapter } from '@angular/material/core';
import { MatDatepicker, MatDatepickerInput, MatDatepickerToggle } from '@angular/material/datepicker';
import {
  MAT_DIALOG_DATA,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatFormField, MatLabel, MatSuffix } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import {
  StatutoryApi,
  StatutoryChoice,
  StatutoryRule,
  StatutoryRuleWrite,
  StatutoryScheme,
} from '@trishul/hr-data-access';

export interface StatutoryRuleDialogData {
  scheme: StatutoryScheme;
  schemeName: string;
  month: string;
  states: StatutoryChoice[];
  rules: StatutoryRule[];
  rule: StatutoryRule | null;
}

const DATE_FORMATS = {
  ...MAT_NATIVE_DATE_FORMATS,
  parse: { ...MAT_NATIVE_DATE_FORMATS.parse, dateInput: 'DD-MM-YYYY' },
  display: {
    ...MAT_NATIVE_DATE_FORMATS.display,
    dateInput: { day: '2-digit', month: '2-digit', year: 'numeric' },
  },
};

class StatutoryDateAdapter extends NativeDateAdapter {
  override format(date: Date, displayFormat: object): string {
    if (displayFormat === DATE_FORMATS.display.dateInput) {
      const day = String(date.getDate()).padStart(2, '0');
      const month = String(date.getMonth() + 1).padStart(2, '0');
      return `${day}-${month}-${date.getFullYear()}`;
    }
    return super.format(date, displayFormat);
  }

  override parse(value: unknown): Date | null {
    if (typeof value !== 'string') return value ? super.parse(value) : null;
    const match = /^(\d{1,2})-(\d{1,2})-(\d{4})$/.exec(value.trim());
    if (!match) return null;
    const day = Number(match[1]);
    const month = Number(match[2]);
    const year = Number(match[3]);
    const date = new Date(year, month - 1, day);
    if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null;
    return date;
  }
}

@Component({
  selector: 'trishul-statutory-rule-dialog',
  imports: [
    DatePipe,
    ReactiveFormsModule,
    MatButton,
    MatCheckbox,
    MatDatepicker,
    MatDatepickerInput,
    MatDatepickerToggle,
    MatDialogActions,
    MatDialogClose,
    MatDialogContent,
    MatDialogTitle,
    MatFormField,
    MatInput,
    MatLabel,
    MatOption,
    MatSelect,
    MatSuffix,
  ],
  providers: [
    { provide: DateAdapter, useClass: StatutoryDateAdapter },
    { provide: MAT_DATE_FORMATS, useValue: DATE_FORMATS },
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './statutory-rule.dialog.html',
  styleUrl: './statutory-rule.dialog.scss',
})
export class StatutoryRuleDialog {
  private readonly api = inject(StatutoryApi);
  private readonly snackBar = inject(MatSnackBar);
  private readonly dialogRef = inject(MatDialogRef<StatutoryRuleDialog, boolean>);
  protected readonly data = inject<StatutoryRuleDialogData>(MAT_DIALOG_DATA);

  protected readonly saving = signal(false);
  protected readonly error = signal('');
  protected readonly editing = signal<StatutoryRule | null>(this.data.rule);
  protected readonly effectiveFrom = new FormControl<Date | null>(initialDate(this.data));
  protected readonly stateId = signal<number | null>(this.data.rule?.stateId ?? null);
  protected readonly employeeRate = signal(this.data.rule?.employeeRate ?? '');
  protected readonly employerRate = signal(this.data.rule?.employerRate ?? '');
  protected readonly wageCeiling = signal(this.data.rule?.wageCeiling ?? '');
  protected readonly slabs = signal(this.data.rule?.slabJson ?? '');
  protected readonly active = signal(this.data.rule?.isActive ?? true);

  protected edit(rule: StatutoryRule): void {
    this.editing.set(rule);
    this.effectiveFrom.setValue(parseIso(rule.effectiveFrom));
    this.stateId.set(rule.stateId);
    this.employeeRate.set(rule.employeeRate ?? '');
    this.employerRate.set(rule.employerRate ?? '');
    this.wageCeiling.set(rule.wageCeiling ?? '');
    this.slabs.set(rule.slabJson ?? '');
    this.active.set(rule.isActive);
    this.error.set('');
  }

  protected save(): void {
    if (this.effectiveFrom.hasError('matDatepickerParse')) {
      this.error.set('Enter the date as DD-MM-YYYY.');
      return;
    }
    const effectiveFrom = toIso(this.effectiveFrom.value);
    if (!effectiveFrom) {
      this.error.set('Choose the date this rule starts.');
      return;
    }
    if (this.data.scheme === 'PT' && this.stateId() == null) {
      this.error.set('Professional tax needs a state.');
      return;
    }
    const body: StatutoryRuleWrite = {
      configType: this.data.scheme,
      stateId: this.stateId(),
      effectiveFrom,
      employeeRate: blank(this.employeeRate()),
      employerRate: blank(this.employerRate()),
      wageCeiling: blank(this.wageCeiling()),
      slabJson: blank(this.slabs()),
      isActive: this.active(),
    };
    if (!body.employeeRate && !body.employerRate && !body.wageCeiling && !body.slabJson) {
      this.error.set('Enter a rate, a ceiling, or the slabs. A rate is not filled in for you.');
      return;
    }
    this.error.set('');
    this.saving.set(true);
    const current = this.editing();
    const request = current
      ? this.api.update(current.id, current.rowVersion, body)
      : this.api.create(body);
    request.subscribe({
      next: () => {
        this.snackBar.open('Statutory rule saved.', 'OK', { duration: 4000 });
        this.dialogRef.close(true);
      },
      error: (error: { error?: { detail?: string } }) => {
        const detail = error.error?.detail;
        this.error.set(typeof detail === 'string' && detail ? detail : 'The statutory rule could not be saved.');
        this.saving.set(false);
      },
    });
  }
}

function initialDate(data: StatutoryRuleDialogData): Date | null {
  if (data.rule) return parseIso(data.rule.effectiveFrom);
  return parseIso(data.month);
}

function parseIso(value: string | null): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value ?? '');
  return match ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3])) : null;
}

function toIso(value: Date | null): string {
  if (!value || Number.isNaN(value.getTime())) return '';
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${value.getFullYear()}-${month}-${day}`;
}

function blank(value: string): string | null {
  const text = value.trim();
  return text || null;
}
