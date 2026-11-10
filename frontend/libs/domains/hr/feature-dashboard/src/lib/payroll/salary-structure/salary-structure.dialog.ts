import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
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
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { SalaryStructureLineItem, SalaryStructureWrite } from '@trishul/core-api';
import { COMPONENT_TYPES, ComponentType, SalaryStructuresApi } from '@trishul/hr-data-access';

export interface SalaryStructureDialogData {
  mode: 'view' | 'edit';
  employeeId: number;
}

interface LineDraft {
  salaryComponentId: number;
  code: string;
  name: string;
  componentType: ComponentType;
  calculationMethod: SalaryStructureLineItem['calculationMethod'];
  calculationBasis: string | null;
  included: boolean;
  monthlyAmount: string;
  percentage: string;
  formula: string;
  includeInNetPay: boolean;
}

interface StructureForm {
  employeeCode: string;
  fullName: string;
  department: string;
  designation: string;
  structureId: number | null;
  rowVersion: string | null;
  effectiveFrom: string;
  effectiveTo: string;
  annualCtc: string;
  monthlyGross: string;
  lines: LineDraft[];
}

const STRUCTURE_DATE_FORMATS = {
  ...MAT_NATIVE_DATE_FORMATS,
  parse: { ...MAT_NATIVE_DATE_FORMATS.parse, dateInput: 'DD-MM-YYYY' },
  display: {
    ...MAT_NATIVE_DATE_FORMATS.display,
    dateInput: { day: '2-digit', month: '2-digit', year: 'numeric' },
  },
};

/** Material calendar that shows and accepts DD-MM-YYYY. Used only on this dialog. */
class SalaryStructureDateAdapter extends NativeDateAdapter {
  override format(date: Date, displayFormat: object): string {
    if (displayFormat === STRUCTURE_DATE_FORMATS.display.dateInput) {
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
  selector: 'trishul-salary-structure-dialog',
  imports: [
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
    MatSuffix,
    MatProgressBar,
  ],
  providers: [
    { provide: DateAdapter, useClass: SalaryStructureDateAdapter },
    { provide: MAT_DATE_FORMATS, useValue: STRUCTURE_DATE_FORMATS },
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './salary-structure.dialog.html',
  styleUrl: './salary-structure.dialog.scss',
})
export class SalaryStructureDialog {
  private readonly api = inject(SalaryStructuresApi);
  private readonly snackBar = inject(MatSnackBar);
  private readonly dialogRef = inject(MatDialogRef<SalaryStructureDialog, boolean>);
  protected readonly data = inject<SalaryStructureDialogData>(MAT_DIALOG_DATA);

  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly error = signal('');
  protected readonly form = signal<StructureForm | null>(null);
  protected readonly effectiveFrom = new FormControl<Date | null>(null);
  protected readonly effectiveTo = new FormControl<Date | null>(null);
  protected readonly fromDate = signal<Date | null>(null);
  protected readonly readOnly = this.data.mode === 'view';
  protected readonly groups = computed(() => {
    const form = this.form();
    if (!form) return [];
    return COMPONENT_TYPES.map((type) => ({
      type,
      lines: form.lines.filter((line) => line.componentType === type),
    })).filter((group) => group.lines.length > 0);
  });

  constructor() {
    this.api.get(this.data.employeeId).subscribe({
      next: (detail) => {
        const savedFrom = parseIso(detail.effectiveFrom);
        const from = savedFrom ?? (detail.structureId == null ? today() : null);
        const to = parseIso(detail.effectiveTo);
        this.effectiveFrom.setValue(from);
        this.effectiveTo.setValue(to);
        this.fromDate.set(from);
        if (this.readOnly) {
          this.effectiveFrom.disable();
          this.effectiveTo.disable();
        }
        this.form.set({
          employeeCode: detail.employeeCode,
          fullName: detail.fullName,
          department: detail.department ?? '',
          designation: detail.designation ?? '',
          structureId: detail.structureId,
          rowVersion: detail.rowVersion,
          effectiveFrom: toIso(from),
          effectiveTo: toIso(to),
          annualCtc: detail.annualCtc ?? '',
          monthlyGross: detail.monthlyGross ?? '',
          lines: detail.lines.map(toDraft),
        });
        this.loading.set(false);
      },
      error: () => {
        this.error.set('This salary structure could not be loaded.');
        this.loading.set(false);
      },
    });
  }

  protected patch(change: Partial<StructureForm>): void {
    this.form.update((current) => (current ? { ...current, ...change } : current));
  }

  protected onFrom(value: Date | null): void {
    this.fromDate.set(value);
    this.patch({ effectiveFrom: toIso(value) });
  }

  protected onTo(value: Date | null): void {
    this.patch({ effectiveTo: toIso(value) });
  }

  protected nextDay(value: Date | null): Date | null {
    if (!value) return null;
    return new Date(value.getFullYear(), value.getMonth(), value.getDate() + 1);
  }

  protected patchLine(componentId: number, change: Partial<LineDraft>): void {
    this.form.update((current) => {
      if (!current) return current;
      return {
        ...current,
        lines: current.lines.map((line) => (line.salaryComponentId === componentId ? { ...line, ...change } : line)),
      };
    });
  }

  protected save(): void {
    const form = this.form();
    if (!form) return;
    if (this.effectiveFrom.hasError('matDatepickerParse') || this.effectiveTo.hasError('matDatepickerParse')) {
      this.error.set('Enter the date as DD-MM-YYYY.');
      return;
    }
    const current = {
      ...form,
      effectiveFrom: toIso(this.effectiveFrom.value),
      effectiveTo: toIso(this.effectiveTo.value),
    };
    this.form.set(current);
    const message = validate(current);
    if (message) {
      this.error.set(message);
      return;
    }
    this.error.set('');
    this.saving.set(true);
    const body = toWrite(current);
    const request =
      current.structureId == null
        ? this.api.create(this.data.employeeId, body)
        : this.api.update(this.data.employeeId, current.rowVersion ?? '', body);
    request.subscribe({
      next: () => {
        this.snackBar.open('Salary structure saved.', 'OK', { duration: 4000 });
        this.dialogRef.close(true);
      },
      error: (error: { error?: { detail?: string } }) => {
        const detail = error.error?.detail;
        this.error.set(typeof detail === 'string' && detail ? detail : 'The salary structure could not be saved.');
        this.saving.set(false);
      },
    });
  }
}

function toDraft(line: SalaryStructureLineItem): LineDraft {
  return {
    salaryComponentId: line.salaryComponentId,
    code: line.code,
    name: line.name,
    componentType: line.componentType,
    calculationMethod: line.calculationMethod,
    calculationBasis: line.calculationBasis,
    included: line.included,
    monthlyAmount: line.monthlyAmount ?? '',
    percentage: line.percentage ?? '',
    formula: line.formula ?? '',
    includeInNetPay: line.includeInNetPay,
  };
}

function validate(form: StructureForm): string {
  if (!form.effectiveFrom) return 'Choose the date this structure starts.';
  if (form.effectiveTo && form.effectiveTo <= form.effectiveFrom) {
    return 'Effective to must be later than effective from.';
  }
  if (!form.annualCtc.trim()) return 'Enter the annual CTC.';
  if (!form.monthlyGross.trim()) return 'Enter the monthly gross.';
  return '';
}

function toWrite(form: StructureForm): SalaryStructureWrite {
  return {
    effectiveFrom: form.effectiveFrom,
    effectiveTo: form.effectiveTo || null,
    annualCtc: form.annualCtc.trim(),
    monthlyGross: form.monthlyGross.trim(),
    lines: form.lines.map((line) => ({
      salaryComponentId: line.salaryComponentId,
      included: line.included,
      monthlyAmount: blank(line.monthlyAmount),
      percentage: blank(line.percentage),
      formula: blank(line.formula),
    })),
  };
}

function blank(value: string): string | null {
  const text = value.trim();
  return text || null;
}

function today(): Date {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
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
