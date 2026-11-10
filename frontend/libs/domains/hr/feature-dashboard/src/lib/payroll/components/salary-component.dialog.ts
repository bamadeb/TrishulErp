import { DatePipe } from '@angular/common';
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
import { MatCheckbox } from '@angular/material/checkbox';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { SalaryComponentDetail, SalaryComponentUpdate, SalaryComponentWrite } from '@trishul/core-api';
import {
  BASIS_FOR_METHOD,
  CALCULATION_METHODS,
  COMPONENT_TYPES,
  CalculationBasis,
  CalculationMethod,
  ComponentType,
  SalaryComponentsApi,
} from '@trishul/hr-data-access';
import { evaluateFormula } from './salary-component.model';

export type SalaryComponentDialogMode = 'create' | 'edit' | 'view';

export interface SalaryComponentDialogData {
  mode: SalaryComponentDialogMode;
  id?: number;
}

interface ComponentForm {
  code: string;
  name: string;
  componentType: ComponentType;
  description: string;
  displayOrder: number;
  calculationMethod: CalculationMethod;
  calculationBasis: CalculationBasis | null;
  fixedAmount: string;
  percentage: string;
  formula: string;
  isProrated: boolean;
  allowManualOverride: boolean;
  includeInGross: boolean;
  isTaxable: boolean;
  isPfApplicable: boolean;
  isEsiApplicable: boolean;
  includeInNetPay: boolean;
  allowReversal: boolean;
  displayInStatement: boolean;
  displayInPayslip: boolean;
  effectiveFrom: string;
  effectiveTo: string;
  isActive: boolean;
}

const EMPTY: ComponentForm = {
  code: '',
  name: '',
  componentType: 'Earning',
  description: '',
  displayOrder: 0,
  calculationMethod: 'Fixed Amount',
  calculationBasis: 'Fixed Monthly Amount',
  fixedAmount: '',
  percentage: '',
  formula: '',
  isProrated: false,
  allowManualOverride: false,
  includeInGross: true,
  isTaxable: false,
  isPfApplicable: false,
  isEsiApplicable: false,
  includeInNetPay: true,
  allowReversal: false,
  displayInStatement: true,
  displayInPayslip: true,
  effectiveFrom: new Date().toISOString().slice(0, 10),
  effectiveTo: '',
  isActive: true,
};

@Component({
  selector: 'trishul-salary-component-dialog',
  imports: [
    DatePipe,
    MatButton,
    MatCheckbox,
    MatDialogActions,
    MatDialogClose,
    MatDialogContent,
    MatDialogTitle,
    MatFormField,
    MatInput,
    MatLabel,
    MatOption,
    MatProgressBar,
    MatSelect,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './salary-component.dialog.html',
  styleUrl: './salary-component.dialog.scss',
})
export class SalaryComponentDialog {
  private readonly api = inject(SalaryComponentsApi);
  private readonly snackBar = inject(MatSnackBar);
  private readonly dialogRef = inject(MatDialogRef<SalaryComponentDialog, boolean>);
  protected readonly data = inject<SalaryComponentDialogData>(MAT_DIALOG_DATA);

  protected readonly types = COMPONENT_TYPES;
  protected readonly methods = CALCULATION_METHODS;
  protected readonly formulaTokens = ['BASIC', 'GROSS', 'PF_WAGES', 'ESI_WAGES', 'CTC', '+', '-', '*', '/', '(', ')', 'MIN(', 'MAX(', 'ROUND('] as const;
  protected readonly sampleNames = ['BASIC', 'GROSS', 'PF_WAGES', 'ESI_WAGES', 'CTC'] as const;
  protected readonly samples = signal<Record<string, string>>({
    BASIC: '',
    GROSS: '',
    PF_WAGES: '',
    ESI_WAGES: '',
    CTC: '',
  });
  protected readonly formulaPreview = computed(() => {
    if (this.form().calculationMethod !== 'Formula' || !this.form().formula.trim()) return '';
    const variables: Record<string, number> = {};
    for (const [name, raw] of Object.entries(this.samples())) {
      if (raw.trim() === '') continue;
      const value = Number(raw);
      if (Number.isFinite(value)) variables[name] = value;
    }
    const result = evaluateFormula(this.form().formula, variables);
    return result.ok ? result.value.toLocaleString('en-IN', { maximumFractionDigits: 2 }) : result.error;
  });
  protected readonly form = signal<ComponentForm>({ ...EMPTY });
  protected readonly detail = signal<SalaryComponentDetail | null>(null);
  protected readonly loading = signal(this.data.mode !== 'create');
  protected readonly saving = signal(false);
  protected readonly error = signal('');
  protected readonly bases = computed(() => BASIS_FOR_METHOD[this.form().calculationMethod]);
  protected readonly readOnly = computed(() => this.data.mode === 'view');
  protected readonly rulesLocked = computed(() => this.detail()?.rulesLocked === true);
  protected readonly inUse = computed(() => this.detail()?.inUse === true);

  constructor() {
    if (this.data.id != null) {
      this.api.get(this.data.id).subscribe({
        next: (row) => {
          this.detail.set(row);
          this.form.set(formFrom(row));
          this.loading.set(false);
        },
        error: () => {
          this.error.set('This component could not be loaded.');
          this.loading.set(false);
        },
      });
    }
  }

  protected patch(change: Partial<ComponentForm>): void {
    this.form.update((current) => ({ ...current, ...change }));
  }

  protected onType(componentType: ComponentType): void {
    const employerOrInfo = componentType === 'Employer Contribution' || componentType === 'Informational';
    this.patch({
      componentType,
      allowReversal: componentType === 'Earning' ? this.form().allowReversal : false,
      includeInGross: componentType === 'Informational' ? false : componentType === 'Earning' || componentType === 'Reimbursement',
      includeInNetPay: employerOrInfo ? false : this.form().includeInNetPay,
    });
  }

  protected insertToken(token: string): void {
    const formula = this.form().formula;
    const spacer = formula && !formula.endsWith(' ') && !formula.endsWith('(') ? ' ' : '';
    this.patch({ formula: `${formula}${spacer}${token}` });
  }

  protected setSample(name: string, value: string): void {
    this.samples.update((current) => ({ ...current, [name]: value }));
  }

  protected onMethod(calculationMethod: CalculationMethod): void {
    const bases = BASIS_FOR_METHOD[calculationMethod];
    const current = this.form().calculationBasis;
    this.patch({
      calculationMethod,
      calculationBasis: current && bases.includes(current) ? current : (bases[0] ?? null),
      allowManualOverride: calculationMethod === 'Manual Entry' ? true : this.form().allowManualOverride,
    });
  }

  protected save(): void {
    const message = validate(this.form());
    if (message) {
      this.error.set(message);
      return;
    }
    this.error.set('');
    this.saving.set(true);
    const request =
      this.data.mode === 'create' || this.detail() == null
        ? this.api.create(toWrite(this.form()))
        : this.api.update(this.detail()!.id, this.detail()!.rowVersion, toUpdate(this.form()));
    request.subscribe({
      next: () => {
        this.snackBar.open(this.data.mode === 'create' ? 'Component added.' : 'Component saved.', 'OK', {
          duration: 4000,
        });
        this.dialogRef.close(true);
      },
      error: () => this.saving.set(false),
    });
  }
}

function formFrom(row: SalaryComponentDetail): ComponentForm {
  return {
    code: row.code,
    name: row.name,
    componentType: row.componentType,
    description: row.description ?? '',
    displayOrder: row.displayOrder,
    calculationMethod: row.calculationMethod,
    calculationBasis: row.calculationBasis,
    fixedAmount: row.fixedAmount ?? '',
    percentage: row.percentage ?? '',
    formula: row.formula ?? '',
    isProrated: row.isProrated,
    allowManualOverride: row.allowManualOverride,
    includeInGross: row.includeInGross,
    isTaxable: row.isTaxable,
    isPfApplicable: row.isPfApplicable,
    isEsiApplicable: row.isEsiApplicable,
    includeInNetPay: row.includeInNetPay,
    allowReversal: row.allowReversal,
    displayInStatement: row.displayInStatement,
    displayInPayslip: row.displayInPayslip,
    effectiveFrom: row.effectiveFrom,
    effectiveTo: row.effectiveTo ?? '',
    isActive: row.isActive,
  };
}

function validate(form: ComponentForm): string {
  if (!/^[A-Za-z][A-Za-z0-9_]{0,19}$/.test(form.code.trim())) {
    return 'Component code starts with a letter and uses letters, digits and underscores.';
  }
  if (!form.name.trim()) {
    return 'Component name is required.';
  }
  if (form.calculationMethod !== 'Manual Entry' && !form.calculationBasis) {
    return 'Choose a calculation basis.';
  }
  if (form.percentage.trim() && !/^\d+(\.\d+)?$/.test(form.percentage.trim())) {
    return 'Percentage must be a number from 0 to 100.';
  }
  if (form.fixedAmount.trim() && !/^\d+(\.\d+)?$/.test(form.fixedAmount.trim())) {
    return 'Fixed amount must be a number.';
  }
  if (!form.effectiveFrom) {
    return 'Effective from is required.';
  }
  if (form.effectiveTo && form.effectiveTo < form.effectiveFrom) {
    return 'Effective to cannot be earlier than effective from.';
  }
  return '';
}

function amounts(form: ComponentForm): Pick<SalaryComponentWrite, 'fixedAmount' | 'percentage' | 'formula' | 'calculationBasis'> {
  return {
    calculationBasis: form.calculationMethod === 'Manual Entry' ? null : form.calculationBasis,
    fixedAmount: form.calculationMethod === 'Fixed Amount' ? blank(form.fixedAmount) : null,
    percentage: form.calculationMethod === 'Percentage' ? blank(form.percentage) : null,
    formula: form.calculationMethod === 'Formula' ? blank(form.formula) : null,
  };
}

function blank(value: string): string | null {
  const text = value.trim();
  return text || null;
}

function toWrite(form: ComponentForm): SalaryComponentWrite {
  return {
    code: form.code.trim().toUpperCase(),
    name: form.name.trim(),
    componentType: form.componentType,
    description: blank(form.description),
    displayOrder: form.displayOrder,
    calculationMethod: form.calculationMethod,
    ...amounts(form),
    isProrated: form.isProrated,
    allowManualOverride: form.calculationMethod === 'Manual Entry' ? true : form.allowManualOverride,
    includeInGross: form.componentType === 'Informational' ? false : form.includeInGross,
    isTaxable: form.isTaxable,
    isPfApplicable: form.isPfApplicable,
    isEsiApplicable: form.isEsiApplicable,
    includeInNetPay:
      form.componentType === 'Employer Contribution' || form.componentType === 'Informational'
        ? false
        : form.includeInNetPay,
    allowReversal: form.componentType === 'Earning' ? form.allowReversal : false,
    displayInStatement: form.displayInStatement,
    displayInPayslip: form.displayInPayslip,
    effectiveFrom: form.effectiveFrom,
    effectiveTo: form.effectiveTo || null,
    isActive: form.isActive,
  };
}

function toUpdate(form: ComponentForm): SalaryComponentUpdate {
  return toWrite(form);
}
