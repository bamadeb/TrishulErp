import { ChangeDetectionStrategy, Component, ElementRef, computed, inject, signal, viewChild } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatDatepicker, MatDatepickerInput, MatDatepickerToggle } from '@angular/material/datepicker';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatHint, MatLabel, MatSuffix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatMenu, MatMenuContent, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import { MatSnackBar } from '@angular/material/snack-bar';
import { catchError, finalize, forkJoin, map, of } from 'rxjs';
import { HasPermission, AuthStore } from '@trishul/core-auth';
import {
  EmployeesApi,
  LEAVE_MANAGE_PERMISSION,
  LeaveApi,
  LeaveBenefitClass,
  LeaveCalculationMethod,
  LeaveCompensatoryBasis,
  LeavePolicyItem,
  LeavePolicyLineWrite,
  LeavePolicyWrite,
  LeaveTypeItem,
  OrganizationApi,
} from '@trishul/hr-data-access';
import { PageHeader, StatusBadge, confirmAction } from '@trishul/shared-ui';
import { LeaveAssignDialog } from './leave-assign.dialog';
import { LeavePolicyDetailsDialog } from './leave-policy-details.dialog';

type Frequency = 'None' | 'Monthly' | 'Yearly';

@Component({
  selector: 'trishul-leave-policies-page',
  imports: [
    FormsModule, HasPermission, MatButton, MatCheckbox, MatDatepicker, MatDatepickerInput, MatDatepickerToggle,
    MatFormField, MatHint, MatIcon, MatIconButton, MatInput, MatLabel, MatSuffix,
    MatMenu, MatMenuContent, MatMenuItem, MatMenuTrigger, MatOption, MatProgressBar, MatSelect, MatSlideToggle, PageHeader, StatusBadge,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './leave-policies.page.html',
  styleUrls: ['./leave-policies.page.scss'],
})
export class LeavePoliciesPage {
  private readonly api = inject(LeaveApi);
  private readonly employees = inject(EmployeesApi);
  private readonly organization = inject(OrganizationApi);
  private readonly snackBar = inject(MatSnackBar);
  private readonly dialog = inject(MatDialog);
  private readonly auth = inject(AuthStore);

  protected readonly manage = LEAVE_MANAGE_PERMISSION;
  protected readonly frequencies: Frequency[] = ['None', 'Monthly', 'Yearly'];
  protected readonly categories = ['Permanent', 'Contract', 'Trainee', 'Consultant'];
  protected readonly methods: { value: LeaveCalculationMethod; label: string }[] = [
    { value: 'FIXED', label: 'Fixed entitlement' },
    { value: 'FORMULA', label: 'Formula (days worked)' },
    { value: 'ELIGIBILITY', label: 'Eligibility' },
  ];
  protected readonly benefits: { value: LeaveBenefitClass; label: string }[] = [
    { value: 'STANDARD', label: 'Standard' },
    { value: 'STATUTORY', label: 'Statutory (Odisha)' },
    { value: 'COMPANY', label: 'Company benefit' },
  ];
  protected readonly compensatory: { value: LeaveCompensatoryBasis; label: string }[] = [
    { value: 'NONE', label: 'None' },
    { value: 'STATUTORY_WEEKLY_REST', label: 'Statutory weekly holiday' },
    { value: 'COMPANY_COMP_OFF', label: 'Company Comp-Off' },
  ];
  private readonly policyForm = viewChild<ElementRef<HTMLElement>>('policyForm');
  protected readonly rows = signal<LeavePolicyItem[]>([]);
  protected readonly counts = signal<Record<number, number>>({});
  protected readonly types = signal<LeaveTypeItem[]>([]);
  protected readonly error = signal('');
  protected readonly loading = signal(true);
  protected readonly editing = signal<LeavePolicyItem | null>(null);
  protected readonly form = signal<LeavePolicyWrite>(blankPolicy());
  protected readonly formVersion = signal(1);
  protected readonly selected = signal(0);
  protected readonly statusFilter = signal('all');
  protected readonly search = signal('');
  protected readonly visible = computed(() => {
    const term = this.search().trim().toLowerCase();
    return this.rows().filter((row) => !term || row.name.toLowerCase().includes(term));
  });
  protected readonly statusTone = { Active: 'success', Inactive: 'neutral' } as const;
  protected readonly attendanceReady = signal(false);
  protected readonly departments = toSignal(this.employees.departments().pipe(catchError(() => of([]))), { initialValue: [] });
  protected readonly states = toSignal(this.organization.stateOptions().pipe(catchError(() => of([]))), { initialValue: [] });
  protected readonly branches = () => this.auth.user()?.branches ?? [];

  constructor() {
    this.reload();
    this.api.types().subscribe({ next: (page) => this.types.set(page.items), error: () => undefined });
    this.api.attendanceClasses().subscribe({
      next: (rows) => this.attendanceReady.set(rows.some((row) => row.configured)),
      error: () => this.attendanceReady.set(false),
    });
  }

  protected addPolicy(): void {
    this.reset();
    this.scrollToForm();
  }

  protected editPolicy(row: LeavePolicyItem): void {
    this.edit(row);
    this.scrollToForm();
  }

  protected viewDetails(row: LeavePolicyItem): void {
    this.dialog.open(LeavePolicyDetailsDialog, { data: row, width: '36rem', maxWidth: '95vw' });
  }

  protected openAssign(row: LeavePolicyItem, mode: 'assign' | 'assigned' | 'history'): void {
    this.dialog
      .open(LeaveAssignDialog, { data: { policy: row, mode }, width: '64rem', maxWidth: '95vw' })
      .afterClosed()
      .subscribe(() => this.reload());
  }

  protected confirmStatus(row: LeavePolicyItem): void {
    const turningOn = !row.isActive;
    confirmAction(this.dialog, {
      title: turningOn ? 'Activate policy' : 'Deactivate policy',
      message: turningOn
        ? `Activate ${row.name}?`
        : `Deactivate ${row.name}? Existing assignment records stay saved.`,
      confirmText: turningOn ? 'Activate' : 'Deactivate',
      destructive: !turningOn,
    }).subscribe((confirmed) => {
      if (confirmed) this.toggleActive(row);
    });
  }

  protected formatDate(value: string | null): string {
    if (!value) return '—';
    const [year, month, day] = value.slice(0, 10).split('-');
    const names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${day}-${names[Number(month) - 1]}-${year}`;
  }

  protected edit(row: LeavePolicyItem): void {
    this.editing.set(row);
    this.selected.set(0);
    this.form.set({
      name: row.name,
      employeeType: row.employeeType,
      departmentId: row.departmentId,
      branchId: row.branchId,
      stateId: row.stateId,
      yearBasis: row.yearBasis,
      assignmentMode: row.assignmentMode,
      appliesDuringProbation: row.appliesDuringProbation,
      negativeBalanceAllowed: row.negativeBalanceAllowed,
      effectiveFrom: row.effectiveFrom,
      effectiveTo: row.effectiveTo,
      isActive: row.isActive,
      lines: row.lines.map((line) => ({
        leaveTypeId: line.leaveTypeId,
        annualEntitlement: line.annualEntitlement,
        accrualFrequency: line.accrualFrequency,
        carryForward: line.carryForward,
        maxAccumulation: line.maxAccumulation,
        encashmentEligible: line.encashmentEligible,
        calculationMethod: line.calculationMethod,
        creditDays: line.creditDays,
        qualifyingDaysPerCredit: line.qualifyingDaysPerCredit,
        minimumQualifyingDays: line.minimumQualifyingDays,
        joiningYearRule: line.joiningYearRule,
        minimumServiceMonths: line.minimumServiceMonths,
        adolescentMaxAccumulation: line.adolescentMaxAccumulation,
        excludeBoundaryHolidays: line.excludeBoundaryHolidays,
        documentRequired: line.documentRequired,
        benefitClass: line.benefitClass,
        compensatoryBasis: line.compensatoryBasis,
        compensatoryExpiryMonths: line.compensatoryExpiryMonths,
        maxBackdateDays: line.maxBackdateDays,
        backdateRequiresAuthorization: line.backdateRequiresAuthorization,
      })),
    });
    this.formVersion.update((version) => version + 1);
  }

  protected reset(): void {
    this.editing.set(null);
    this.selected.set(0);
    this.form.set(blankPolicy());
    this.error.set('');
    this.formVersion.update((version) => version + 1);
  }

  private readonly dates = new Map<string, Date>();

  protected patch(change: Partial<LeavePolicyWrite>): void {
    this.form.update((current) => ({ ...current, ...change }));
  }

  protected setEffective(field: 'effectiveFrom' | 'effectiveTo', value: Date | null): void {
    const next = this.dateText(value);
    const stored = field === 'effectiveFrom' ? (next ?? '') : next;
    if (this.form()[field] === stored) return;
    this.patch({ [field]: stored });
  }

  protected dateValue(value: string | null | undefined): Date | null {
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value ?? '');
    if (!match) return null;
    const cached = this.dates.get(match[0]);
    if (cached) return cached;
    const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
    this.dates.set(match[0], date);
    return date;
  }

  protected dateText(value: Date | null): string | null {
    if (!(value instanceof Date) || Number.isNaN(value.getTime())) return null;
    const month = String(value.getMonth() + 1).padStart(2, '0');
    const day = String(value.getDate()).padStart(2, '0');
    return `${value.getFullYear()}-${month}-${day}`;
  }

  protected addLine(): void {
    const first = this.types()[0];
    if (!first) return;
    this.form.update((current) => ({ ...current, lines: [...current.lines, blankLine(first.id)] }));
    this.selected.set(this.form().lines.length - 1);
  }

  protected removeLine(index: number): void {
    this.form.update((current) => ({ ...current, lines: current.lines.filter((_, item) => item !== index) }));
    this.selected.set(Math.max(0, Math.min(this.selected(), this.form().lines.length - 1)));
  }

  protected patchLine(index: number, change: Partial<LeavePolicyLineWrite>): void {
    this.form.update((current) => ({
      ...current,
      lines: current.lines.map((line, item) => item === index ? { ...line, ...change } : line),
    }));
  }

  protected backdateDays(value: number | string | null): number | null {
    if (value === '' || value == null) return null;
    const days = Number(value);
    return Number.isInteger(days) && days >= 0 ? days : null;
  }

  protected chooseMethod(index: number, method: LeaveCalculationMethod): void {
    const change: Partial<LeavePolicyLineWrite> = { calculationMethod: method };
    if (method === 'FORMULA') change.annualEntitlement = '0';
    this.patchLine(index, change);
  }

  protected lineTitle(line: LeavePolicyLineWrite): string {
    const type = this.types().find((item) => item.id === line.leaveTypeId);
    return type ? `${type.code} ${type.name}` : 'Leave type';
  }

  protected summary(line: LeavePolicyLineWrite): string[] {
    const sentences: string[] = [];
    if (line.benefitClass === 'COMPANY') sentences.push('Company benefit. This is not an Odisha statutory entitlement.');
    if (line.benefitClass === 'STATUTORY') sentences.push('Statutory entitlement for a covered Odisha private establishment.');
    if (line.calculationMethod === 'FORMULA') {
      sentences.push(`Eligible when at least ${line.minimumQualifyingDays ?? 0} qualifying days are counted in the preceding year.`);
      sentences.push(`Entitlement: ${line.creditDays || 0} day for every ${line.qualifyingDaysPerCredit ?? 0} days actually worked.`);
      sentences.push('Deemed-work days can count toward eligibility and do not earn extra leave.');
      if (line.joiningYearRule === 'TWO_THIRDS_REMAINDER') {
        sentences.push('Joining after 1 January uses two-thirds of the remaining calendar year.');
      }
      if (!this.attendanceReady()) {
        sentences.push('Attendance classification is not configured, so this formula cannot be calculated yet.');
      }
    }
    if (line.calculationMethod === 'ELIGIBILITY') {
      sentences.push(`Maximum ${line.annualEntitlement || 0} days in the policy year.`);
      if (line.minimumServiceMonths) {
        sentences.push(`Available after ${line.minimumServiceMonths} months of continuous employment from the joining date.`);
      }
    }
    if (line.carryForward && line.maxAccumulation) sentences.push(`Carry forward up to ${line.maxAccumulation} days for adult employees.`);
    if (line.adolescentMaxAccumulation) sentences.push(`Carry forward up to ${line.adolescentMaxAccumulation} days for employees under 18.`);
    if (line.excludeBoundaryHolidays) sentences.push('Holidays during or at either end of leave are not counted.');
    if (line.compensatoryBasis === 'STATUTORY_WEEKLY_REST') {
      sentences.push(`If the weekly holiday is denied, compensatory leave is due within ${line.compensatoryExpiryMonths ?? 0} calendar months of that weekly holiday.`);
    }
    if (line.compensatoryBasis === 'COMPANY_COMP_OFF') {
      sentences.push('Company Comp-Off is separate from statutory weekly-rest compensation.');
    }
    if (line.backdateRequiresAuthorization) sentences.push('Past dates require HR authorization.');
    if (line.maxBackdateDays === 0) sentences.push('Past dates are not allowed.');
    else if (line.maxBackdateDays != null && line.maxBackdateDays > 0) {
      sentences.push(`Past dates are allowed up to ${line.maxBackdateDays} calendar days.`);
    }
    return sentences;
  }

  protected save(): void {
    const body = this.form();
    const current = this.editing();
    const request = current ? this.api.updatePolicy(current.id, current.rowVersion, body) : this.api.createPolicy(body);
    request.subscribe({
      next: () => {
        this.snackBar.open(current ? 'Leave policy saved.' : 'Leave policy added.', 'OK', { duration: 3000 });
        this.reset();
        this.reload();
      },
      error: (error: { error?: { detail?: string } }) => {
        const detail = error.error?.detail;
        this.error.set(typeof detail === 'string' && detail ? detail : 'The leave policy could not be saved.');
      },
    });
  }

  protected toggleActive(row: LeavePolicyItem): void {
    this.api.updatePolicy(row.id, row.rowVersion, {
      name: row.name,
      employeeType: row.employeeType,
      departmentId: row.departmentId,
      branchId: row.branchId,
      stateId: row.stateId,
      yearBasis: row.yearBasis,
      assignmentMode: row.assignmentMode,
      appliesDuringProbation: row.appliesDuringProbation,
      negativeBalanceAllowed: row.negativeBalanceAllowed,
      effectiveFrom: row.effectiveFrom,
      effectiveTo: row.effectiveTo,
      isActive: !row.isActive,
      lines: row.lines.map((line) => ({
        leaveTypeId: line.leaveTypeId,
        annualEntitlement: line.annualEntitlement,
        accrualFrequency: line.accrualFrequency,
        carryForward: line.carryForward,
        maxAccumulation: line.maxAccumulation,
        encashmentEligible: line.encashmentEligible,
        calculationMethod: line.calculationMethod,
        creditDays: line.creditDays,
        qualifyingDaysPerCredit: line.qualifyingDaysPerCredit,
        minimumQualifyingDays: line.minimumQualifyingDays,
        joiningYearRule: line.joiningYearRule,
        minimumServiceMonths: line.minimumServiceMonths,
        adolescentMaxAccumulation: line.adolescentMaxAccumulation,
        excludeBoundaryHolidays: line.excludeBoundaryHolidays,
        documentRequired: line.documentRequired,
        benefitClass: line.benefitClass,
        compensatoryBasis: line.compensatoryBasis,
        compensatoryExpiryMonths: line.compensatoryExpiryMonths,
        maxBackdateDays: line.maxBackdateDays,
        backdateRequiresAuthorization: line.backdateRequiresAuthorization,
      })),
    }).subscribe({
      next: (saved) => {
        this.snackBar.open(saved.isActive ? 'Leave policy activated.' : 'Leave policy deactivated.', 'OK', { duration: 3000 });
        if (this.editing()?.id === saved.id) this.edit(saved);
        this.reload();
      },
      error: () => this.error.set('The leave policy could not be updated.'),
    });
  }

  protected filterStatus(status: string): void {
    this.statusFilter.set(status);
    this.reload();
  }

  private scrollToForm(): void {
    queueMicrotask(() => this.policyForm()?.nativeElement.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  }

  private reload(): void {
    this.loading.set(true);
    this.api.policies(this.statusFilter()).pipe(finalize(() => this.loading.set(false))).subscribe({
      next: (page) => {
        this.rows.set(page.items);
        this.error.set('');
        if (page.items.length === 0) {
          this.counts.set({});
          return;
        }
        forkJoin(
          page.items.map((row) =>
            this.api.assignments(row.id).pipe(
              map((assigned) => [row.id, assigned.length] as const),
              catchError(() => of([row.id, 0] as const)),
            ),
          ),
        ).subscribe((pairs) => this.counts.set(Object.fromEntries(pairs)));
      },
      error: () => this.error.set('Leave policies could not be loaded.'),
    });
  }
}

function blankPolicy(): LeavePolicyWrite {
  return {
    name: '',
    employeeType: null,
    departmentId: null,
    branchId: null,
    stateId: null,
    yearBasis: 'FINANCIAL',
    assignmentMode: 'AUTOMATIC',
    appliesDuringProbation: false,
    negativeBalanceAllowed: false,
    effectiveFrom: '',
    effectiveTo: null,
    isActive: true,
    lines: [],
  };
}

function blankLine(leaveTypeId: number): LeavePolicyLineWrite {
  return {
    leaveTypeId,
    annualEntitlement: '0',
    accrualFrequency: 'None',
    carryForward: false,
    maxAccumulation: null,
    encashmentEligible: false,
    calculationMethod: 'FIXED',
    creditDays: '1',
    qualifyingDaysPerCredit: 20,
    minimumQualifyingDays: 240,
    joiningYearRule: 'NONE',
    minimumServiceMonths: null,
    adolescentMaxAccumulation: null,
    excludeBoundaryHolidays: false,
    documentRequired: false,
    benefitClass: 'STANDARD',
    compensatoryBasis: 'NONE',
    compensatoryExpiryMonths: null,
    maxBackdateDays: null,
    backdateRequiresAuthorization: false,
  };
}
