import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
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
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { SalaryComponentListItem } from '@trishul/core-api';
import {
  SalaryComponentsApi,
  SalaryTemplateDetail,
  SalaryTemplateSummary,
  SalaryTemplatesApi,
  SalaryTemplateWrite,
} from '@trishul/hr-data-access';

export interface SalaryTemplateDialogData {
  id: number | null;
  mode: 'view' | 'edit';
  summary: SalaryTemplateSummary;
}

interface DraftLine {
  salaryComponentId: number;
  code: string;
  name: string;
  componentType: string;
  calculationMethod: string;
  calculationBasis: string | null;
  includeInGross: boolean;
  included: boolean;
  monthlyAmount: string;
  percentage: string;
  formula: string;
}

const ASSIGNABLE = ['Earning', 'Employee Deduction', 'Employer Contribution'];

@Component({
  selector: 'trishul-salary-template-dialog',
  imports: [
    FormsModule,
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
  templateUrl: './salary-template.dialog.html',
  styleUrl: './salary-template.dialog.scss',
})
export class SalaryTemplateDialog {
  private readonly api = inject(SalaryTemplatesApi);
  private readonly componentsApi = inject(SalaryComponentsApi);
  private readonly snackBar = inject(MatSnackBar);
  private readonly dialogRef = inject(MatDialogRef<SalaryTemplateDialog, boolean>);
  protected readonly data = inject<SalaryTemplateDialogData>(MAT_DIALOG_DATA);

  protected readonly categories = ['Permanent', 'Contract', 'Trainee', 'Consultant'];
  protected readonly grades = ['E1', 'E2', 'E3', 'E4', 'E5', 'G1', 'G2', 'G3', 'G4', 'G5', 'G6'];
  protected readonly tabs = [
    { id: 'overview' as const, label: 'Overview' },
    { id: 'earnings' as const, label: 'Earnings' },
    { id: 'deductions' as const, label: 'Deductions' },
    { id: 'employer' as const, label: 'Employer contributions' },
    { id: 'employees' as const, label: 'Assigned employees' },
    { id: 'history' as const, label: 'History' },
  ];
  protected readonly groups = ASSIGNABLE;
  protected readonly step = signal(1);
  protected readonly tab = signal<'overview' | 'earnings' | 'deductions' | 'employer' | 'employees' | 'history'>('overview');
  protected readonly loading = signal(this.data.id != null);
  protected readonly saving = signal(false);
  protected readonly error = signal('');
  protected readonly detail = signal<SalaryTemplateDetail | null>(null);
  protected readonly rowVersion = signal('');
  protected readonly code = signal('');
  protected readonly name = signal('');
  protected readonly description = signal('');
  protected readonly employeeCategory = signal<string | null>(null);
  protected readonly departmentId = signal<number | null>(null);
  protected readonly designationId = signal<number | null>(null);
  protected readonly designationIds = signal<number[]>([]);
  protected readonly selectedGrades = signal<string[]>([]);
  protected readonly effectiveFrom = signal('');
  protected readonly effectiveTo = signal('');
  protected readonly isActive = signal(true);
  protected readonly lines = signal<DraftLine[]>([]);

  protected readonly selected = computed(() => this.lines().filter((line) => line.included));
  protected readonly preview = computed(() => preview(this.lines()));

  constructor() {
    this.componentsApi.list({ search: '', componentType: null, calculationMethod: null, status: 'active', page: 1, pageSize: 200 }).subscribe({
      next: (page) => {
        const drafts = page.items.filter((item) => ASSIGNABLE.includes(item.componentType)).map(toDraft);
        this.lines.update((current) => mergeDrafts(drafts, current));
        if (this.data.id == null) this.loading.set(false);
      },
      error: () => this.error.set('Active salary components could not be loaded.'),
    });
    if (this.data.id != null) {
      this.api.get(this.data.id).subscribe({
        next: (detail) => this.applyDetail(detail),
        error: () => {
          this.error.set('This salary template could not be loaded.');
          this.loading.set(false);
        },
      });
    }
  }

  protected patch(line: DraftLine, change: Partial<DraftLine>): void {
    this.lines.update((lines) => lines.map((item) => (
      item.salaryComponentId === line.salaryComponentId ? { ...item, ...change } : item
    )));
  }

  protected linesFor(type: string): DraftLine[] {
    return this.lines().filter((line) => line.componentType === type);
  }

  protected detailLines(type: string) {
    return (this.detail()?.lines ?? []).filter((line) => line.componentType === type);
  }

  protected next(): void {
    const message = this.step() === 1 ? this.basicError() : this.lineError();
    this.error.set(message);
    if (!message) this.step.update((value) => value + 1);
  }

  protected save(): void {
    const message = this.basicError() ?? this.lineError();
    if (message) {
      this.error.set(message);
      return;
    }
    this.saving.set(true);
    this.error.set('');
    const body = this.toWrite();
    const request = this.data.id == null
      ? this.api.create(body)
      : this.api.update(this.data.id, this.rowVersion(), body);
    request.subscribe({
      next: () => {
        this.snackBar.open(this.data.id == null ? 'Template added.' : 'Template saved.', 'OK', { duration: 3000 });
        this.dialogRef.close(true);
      },
      error: (error: { error?: { detail?: string } }) => {
        this.saving.set(false);
        const detail = error.error?.detail;
        this.error.set(typeof detail === 'string' && detail ? detail : 'The template could not be saved.');
      },
    });
  }

  private applyDetail(detail: SalaryTemplateDetail): void {
    this.detail.set(detail);
    this.rowVersion.set(detail.rowVersion);
    this.code.set(detail.code);
    this.name.set(detail.name);
    this.description.set(detail.description ?? '');
    this.employeeCategory.set(detail.employeeCategory);
    this.departmentId.set(detail.departmentId);
    this.designationId.set(detail.designationId);
    this.designationIds.set(detail.designationIds ?? []);
    this.selectedGrades.set(detail.grades ?? []);
    this.effectiveFrom.set(detail.effectiveFrom);
    this.effectiveTo.set(detail.effectiveTo ?? '');
    this.isActive.set(detail.isActive);
    this.lines.update((current) => mergeDrafts(current, detail.lines.map((line) => ({
      salaryComponentId: line.salaryComponentId,
      code: line.code,
      name: line.name,
      componentType: line.componentType,
      calculationMethod: line.calculationMethod,
      calculationBasis: line.calculationBasis,
      includeInGross: line.componentType === 'Earning',
      included: true,
      monthlyAmount: line.monthlyAmount ?? '',
      percentage: line.percentage ?? '',
      formula: line.formula ?? '',
    }))));
    this.loading.set(false);
  }

  private basicError(): string {
    if (!this.code().trim() || !this.name().trim() || !this.effectiveFrom()) {
      return 'Template code, name and effective from are required.';
    }
    if (this.effectiveTo() && this.effectiveTo() <= this.effectiveFrom()) {
      return 'Effective to must be after effective from.';
    }
    return '';
  }

  private lineError(): string {
    if (this.selected().length === 0) return 'Select at least one salary component.';
    for (const line of this.selected()) {
      if (line.calculationMethod === 'Fixed Amount' && !line.monthlyAmount.trim()) return `Enter the amount for ${line.name}.`;
      if (line.calculationMethod === 'Percentage' && !line.percentage.trim()) return `Enter the percentage for ${line.name}.`;
      if (line.calculationMethod === 'Formula' && !line.formula.trim()) return `Enter the formula for ${line.name}.`;
    }
    return '';
  }

  private toWrite(): SalaryTemplateWrite {
    return {
      code: this.code().trim(),
      name: this.name().trim(),
      description: this.description().trim() || null,
      templateType: 'Monthly',
      employeeCategory: this.employeeCategory(),
      departmentId: this.departmentId(),
      designationId: this.designationIds()[0] ?? this.designationId(),
      designationIds: this.designationIds(),
      grades: this.selectedGrades(),
      effectiveFrom: this.effectiveFrom(),
      effectiveTo: this.effectiveTo() || null,
      isActive: this.isActive(),
      lines: this.selected().map((line, index) => ({
        salaryComponentId: line.salaryComponentId,
        monthlyAmount: line.monthlyAmount.trim() || null,
        percentage: line.percentage.trim() || null,
        formula: line.formula.trim() || null,
        displayOrder: index + 1,
      })),
    };
  }
}

function toDraft(item: SalaryComponentListItem): DraftLine {
  return {
    salaryComponentId: item.id,
    code: item.code,
    name: item.name,
    componentType: item.componentType,
    calculationMethod: item.calculationMethod,
    calculationBasis: item.calculationBasis,
    includeInGross: item.includeInGross,
    included: false,
    monthlyAmount: '',
    percentage: '',
    formula: '',
  };
}

function mergeDrafts(catalog: DraftLine[], saved: DraftLine[]): DraftLine[] {
  const byId = new Map(saved.map((line) => [line.salaryComponentId, line]));
  const merged = catalog.map((line) => byId.get(line.salaryComponentId) ?? line);
  const known = new Set(merged.map((line) => line.salaryComponentId));
  return [...merged, ...saved.filter((line) => !known.has(line.salaryComponentId))];
}

function amount(line: DraftLine, lines: DraftLine[]): number | null {
  if (line.calculationMethod === 'Fixed Amount') {
    const value = Number(line.monthlyAmount);
    return Number.isFinite(value) ? value : null;
  }
  if (line.calculationMethod === 'Percentage' && line.calculationBasis === 'Basic Salary') {
    const basic = lines.find((item) => item.included && item.code === 'BASIC' && item.calculationMethod === 'Fixed Amount');
    const base = basic ? Number(basic.monthlyAmount) : Number.NaN;
    const rate = Number(line.percentage);
    return Number.isFinite(base) && Number.isFinite(rate) ? (base * rate) / 100 : null;
  }
  return null;
}

function preview(lines: DraftLine[]) {
  const selected = lines.filter((line) => line.included);
  const valued = selected.map((line) => ({ line, value: amount(line, lines) }));
  const sum = (type: string, grossOnly = false) => valued
    .filter((item) => item.line.componentType === type && (!grossOnly || item.line.includeInGross) && item.value != null)
    .reduce((total, item) => total + (item.value ?? 0), 0);
  const gross = sum('Earning', true);
  const deductions = sum('Employee Deduction');
  return {
    rows: valued,
    gross,
    deductions,
    net: gross - deductions,
    employer: sum('Employer Contribution'),
    annual: gross * 12,
  };
}
