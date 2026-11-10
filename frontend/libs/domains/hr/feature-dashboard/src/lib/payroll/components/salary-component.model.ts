/**
 * Salary component master used by the Salary Components screen.
 *
 * Database mapping (hr.salary_component). The live table is empty; these eight
 * records are the screen master. Payroll processing does not read this model.
 *
 * Stored today on hr.salary_component:
 * - code, name
 * - component_type: Earning | Deduction | Employer contribution
 * - calculation_type: Fixed | Percent of basic | Formula | Statutory
 * - is_taxable, is_pf_wage, is_esi_wage
 * - is_active, created_by_user_id, updated_by_user_id, created_at, updated_at
 *
 * Not on that table, so they stay with this screen record:
 * - Reimbursement and Non-payable categories (the check constraint does not allow them)
 * - calculation basis other than basic, amount, percentage, formula text
 * - rounding, minimum, maximum
 * - include in gross, include in CTC, recurring, proration, LOP
 * - Professional tax and TDS mapping (no rate is stored here)
 * - applicability, effective dates, version history
 *
 * Amount, percentage and formula on an employee live on hr.salary_structure_line.
 * This master does not write that table.
 */

export type ComponentType =
  | 'Earning'
  | 'Deduction'
  | 'Employer contribution'
  | 'Reimbursement'
  | 'Non-payable';

export type CalculationMethod = 'Fixed' | 'Percentage' | 'Formula';

export type CalculationBasis = 'Basic salary' | 'Gross salary' | 'CTC' | 'Component' | 'Formula';

export type RoundingMode = 'None' | 'Nearest rupee' | 'Round up' | 'Round down';

export type Recurrence = 'Recurring' | 'One-time';

export type LopTreatment = 'None' | 'Deduct' | 'Do not deduct';

export type StatutoryHead = 'None' | 'PF' | 'ESI' | 'Professional tax' | 'TDS';

export interface ApplicabilityRules {
  departments: string[];
  designations: string[];
  grades: string[];
  locations: string[];
  categories: string[];
  employees: string[];
}

export interface ComponentChange {
  at: string;
  by: string;
  action: 'Created' | 'Updated' | 'Duplicated' | 'Deactivated' | 'Activated';
  summary: string;
}

export interface ComponentVersion {
  version: number;
  calculation: CalculationMethod;
  basis: CalculationBasis;
  basisComponent: string;
  value: number;
  formula: string;
  rounding: RoundingMode;
  minimum: number | null;
  maximum: number | null;
  effectiveFrom: string;
  effectiveTo: string;
  changedAt: string;
  changedBy: string;
}

export interface SalaryComponentRow {
  id: number;
  code: string;
  name: string;
  type: ComponentType;
  calculation: CalculationMethod;
  basis: CalculationBasis;
  basisComponent: string;
  value: number;
  formula: string;
  rounding: RoundingMode;
  minimum: number | null;
  maximum: number | null;
  applicability: string;
  rules: ApplicabilityRules;
  effectiveFrom: string;
  effectiveTo: string;
  active: boolean;
  includeInGross: boolean;
  includeInCtc: boolean;
  taxable: boolean;
  recurrence: Recurrence;
  prorateAttendance: boolean;
  lopTreatment: LopTreatment;
  includeInPfWages: boolean;
  includeInEsiWages: boolean;
  statutoryHead: StatutoryHead;
  createdBy: string;
  modifiedBy: string;
  history: ComponentChange[];
  versions: ComponentVersion[];
}

export interface ComponentDraft {
  code: string;
  name: string;
  type: ComponentType;
  calculation: CalculationMethod;
  basis: CalculationBasis;
  basisComponent: string;
  value: number;
  formula: string;
  rounding: RoundingMode;
  minimum: number | null;
  maximum: number | null;
  applicability: string;
  rules: ApplicabilityRules;
  effectiveFrom: string;
  effectiveTo: string;
  active: boolean;
  includeInGross: boolean;
  includeInCtc: boolean;
  taxable: boolean;
  recurrence: Recurrence;
  prorateAttendance: boolean;
  lopTreatment: LopTreatment;
  includeInPfWages: boolean;
  includeInEsiWages: boolean;
  statutoryHead: StatutoryHead;
}

export interface FormulaSuccess {
  ok: true;
  value: number;
}

export interface FormulaFailure {
  ok: false;
  error: string;
}

export type FormulaResult = FormulaSuccess | FormulaFailure;

export const COMPONENT_TYPES: readonly ComponentType[] = [
  'Earning',
  'Deduction',
  'Employer contribution',
  'Reimbursement',
  'Non-payable',
];

export const COMPONENT_TYPE_LABEL: Record<ComponentType, string> = {
  Earning: 'Earning',
  Deduction: 'Employee deduction',
  'Employer contribution': 'Employer contribution',
  Reimbursement: 'Reimbursement',
  'Non-payable': 'Non-payable',
};

export const CALCULATION_METHODS: readonly CalculationMethod[] = ['Fixed', 'Percentage', 'Formula'];

export const CALCULATION_LABEL: Record<CalculationMethod, string> = {
  Fixed: 'Fixed amount',
  Percentage: 'Percentage',
  Formula: 'Formula',
};

export const CALCULATION_BASES: readonly CalculationBasis[] = [
  'Basic salary',
  'Gross salary',
  'CTC',
  'Component',
  'Formula',
];

export const ROUNDING_MODES: readonly RoundingMode[] = ['None', 'Nearest rupee', 'Round up', 'Round down'];

export const RECURRENCE: readonly Recurrence[] = ['Recurring', 'One-time'];

export const LOP_TREATMENTS: readonly LopTreatment[] = ['None', 'Deduct', 'Do not deduct'];

export const STATUTORY_HEADS: readonly StatutoryHead[] = ['None', 'PF', 'ESI', 'Professional tax', 'TDS'];

export const DEPARTMENTS = ['Administration', 'Human Resources', 'Finance', 'Information Technology', 'Operations', 'Service'];

export const DESIGNATIONS = ['Manager', 'Executive', 'Assistant Vice President', 'Team Lead', 'Service Engineer'];

export const GRADES = ['L1', 'L2', 'L3', 'L4'];

export const LOCATIONS = ['Head office', 'Field', 'Karnataka'];

export const EMPLOYMENT_CATEGORIES = ['Permanent', 'Contract', 'Trainee', 'Consultant'];

export const EMPLOYEES = ['Ananya Rao', 'Karthik Menon', 'Meera Singh', 'Rohan Deshmukh', 'Priya Nair', 'Neha Sharma'];

const ACTOR = 'Payroll admin';
const OPENED = '2026-04-01T00:00:00.000Z';

export function emptyRules(): ApplicabilityRules {
  return { departments: [], designations: [], grades: [], locations: [], categories: [], employees: [] };
}

export function cloneComponent(row: SalaryComponentRow): SalaryComponentRow {
  return {
    ...row,
    rules: {
      departments: [...row.rules.departments],
      designations: [...row.rules.designations],
      grades: [...row.rules.grades],
      locations: [...row.rules.locations],
      categories: [...row.rules.categories],
      employees: [...row.rules.employees],
    },
    history: row.history.map((item) => ({ ...item })),
    versions: row.versions.map((item) => ({ ...item })),
  };
}

function opened(summary: string): ComponentChange {
  return { at: OPENED, by: 'System', action: 'Created', summary };
}

function seed(row: Omit<SalaryComponentRow, 'history' | 'versions' | 'rules' | 'createdBy' | 'modifiedBy'> & {
  rules?: ApplicabilityRules;
}): SalaryComponentRow {
  return {
    ...row,
    rules: row.rules ?? emptyRules(),
    createdBy: 'System',
    modifiedBy: 'System',
    history: [opened('Opening component')],
    versions: [],
  };
}

/** The original eight components. Identity, amount and applicability text are unchanged. */
export const SALARY_COMPONENTS: SalaryComponentRow[] = [
  seed({
    id: 1, code: 'BASIC', name: 'Basic', type: 'Earning', calculation: 'Percentage', basis: 'CTC',
    basisComponent: '', value: 50, formula: '', rounding: 'Nearest rupee', minimum: null, maximum: null,
    applicability: 'All employees', effectiveFrom: '', effectiveTo: '', active: true,
    includeInGross: true, includeInCtc: true, taxable: true, recurrence: 'Recurring', prorateAttendance: true,
    lopTreatment: 'Deduct', includeInPfWages: true, includeInEsiWages: true, statutoryHead: 'None',
  }),
  seed({
    id: 2, code: 'HRA', name: 'HRA', type: 'Earning', calculation: 'Percentage', basis: 'Basic salary',
    basisComponent: '', value: 40, formula: '', rounding: 'Nearest rupee', minimum: null, maximum: null,
    applicability: 'All employees', effectiveFrom: '', effectiveTo: '', active: true,
    includeInGross: true, includeInCtc: true, taxable: true, recurrence: 'Recurring', prorateAttendance: true,
    lopTreatment: 'Deduct', includeInPfWages: false, includeInEsiWages: true, statutoryHead: 'None',
  }),
  seed({
    id: 3, code: 'SPECIAL', name: 'Special allowance', type: 'Earning', calculation: 'Fixed', basis: 'Basic salary',
    basisComponent: '', value: 5000, formula: '', rounding: 'None', minimum: null, maximum: null,
    applicability: 'Grade L2 and above', effectiveFrom: '', effectiveTo: '', active: true,
    includeInGross: true, includeInCtc: true, taxable: true, recurrence: 'Recurring', prorateAttendance: true,
    lopTreatment: 'Deduct', includeInPfWages: false, includeInEsiWages: false, statutoryHead: 'None',
  }),
  seed({
    id: 4, code: 'CONVEY', name: 'Conveyance', type: 'Earning', calculation: 'Fixed', basis: 'Basic salary',
    basisComponent: '', value: 1600, formula: '', rounding: 'None', minimum: null, maximum: null,
    applicability: 'Field staff', effectiveFrom: '', effectiveTo: '', active: true,
    includeInGross: true, includeInCtc: true, taxable: true, recurrence: 'Recurring', prorateAttendance: true,
    lopTreatment: 'Deduct', includeInPfWages: false, includeInEsiWages: false, statutoryHead: 'None',
  }),
  seed({
    id: 5, code: 'PF_EE', name: 'Provident fund', type: 'Deduction', calculation: 'Percentage', basis: 'Basic salary',
    basisComponent: '', value: 12, formula: '', rounding: 'Nearest rupee', minimum: null, maximum: null,
    applicability: 'Basic, eligible staff', effectiveFrom: '', effectiveTo: '', active: true,
    includeInGross: false, includeInCtc: true, taxable: false, recurrence: 'Recurring', prorateAttendance: true,
    lopTreatment: 'Deduct', includeInPfWages: false, includeInEsiWages: false, statutoryHead: 'PF',
  }),
  seed({
    id: 6, code: 'ESI_EE', name: 'ESI', type: 'Deduction', calculation: 'Percentage', basis: 'Gross salary',
    basisComponent: '', value: 0.75, formula: '', rounding: 'Nearest rupee', minimum: null, maximum: null,
    applicability: 'Gross up to 21,000', effectiveFrom: '', effectiveTo: '', active: true,
    includeInGross: false, includeInCtc: true, taxable: false, recurrence: 'Recurring', prorateAttendance: true,
    lopTreatment: 'Deduct', includeInPfWages: false, includeInEsiWages: false, statutoryHead: 'ESI',
  }),
  seed({
    id: 7, code: 'PT', name: 'Professional tax', type: 'Deduction', calculation: 'Fixed', basis: 'Basic salary',
    basisComponent: '', value: 200, formula: '', rounding: 'None', minimum: null, maximum: null,
    applicability: 'Karnataka payroll', effectiveFrom: '', effectiveTo: '', active: true,
    includeInGross: false, includeInCtc: false, taxable: false, recurrence: 'Recurring', prorateAttendance: false,
    lopTreatment: 'None', includeInPfWages: false, includeInEsiWages: false, statutoryHead: 'Professional tax',
  }),
  seed({
    id: 8, code: 'MEAL', name: 'Meal coupon', type: 'Earning', calculation: 'Fixed', basis: 'Basic salary',
    basisComponent: '', value: 2200, formula: '', rounding: 'None', minimum: null, maximum: null,
    applicability: 'Head office', effectiveFrom: '', effectiveTo: '', active: false,
    includeInGross: true, includeInCtc: true, taxable: false, recurrence: 'Recurring', prorateAttendance: false,
    lopTreatment: 'None', includeInPfWages: false, includeInEsiWages: false, statutoryHead: 'None',
  }),
];

export function blankDraft(today: string): ComponentDraft {
  return {
    code: '',
    name: '',
    type: 'Earning',
    calculation: 'Fixed',
    basis: 'Basic salary',
    basisComponent: '',
    value: 0,
    formula: '',
    rounding: 'Nearest rupee',
    minimum: null,
    maximum: null,
    applicability: 'All employees',
    rules: emptyRules(),
    effectiveFrom: today,
    effectiveTo: '',
    active: true,
    includeInGross: true,
    includeInCtc: true,
    taxable: true,
    recurrence: 'Recurring',
    prorateAttendance: true,
    lopTreatment: 'Deduct',
    includeInPfWages: false,
    includeInEsiWages: false,
    statutoryHead: 'None',
  };
}

export function draftFrom(row: SalaryComponentRow): ComponentDraft {
  return {
    code: row.code,
    name: row.name,
    type: row.type,
    calculation: row.calculation,
    basis: row.basis,
    basisComponent: row.basisComponent,
    value: row.value,
    formula: row.formula,
    rounding: row.rounding,
    minimum: row.minimum,
    maximum: row.maximum,
    applicability: row.applicability,
    rules: {
      departments: [...row.rules.departments],
      designations: [...row.rules.designations],
      grades: [...row.rules.grades],
      locations: [...row.rules.locations],
      categories: [...row.rules.categories],
      employees: [...row.rules.employees],
    },
    effectiveFrom: row.effectiveFrom,
    effectiveTo: row.effectiveTo,
    active: row.active,
    includeInGross: row.includeInGross,
    includeInCtc: row.includeInCtc,
    taxable: row.taxable,
    recurrence: row.recurrence,
    prorateAttendance: row.prorateAttendance,
    lopTreatment: row.lopTreatment,
    includeInPfWages: row.includeInPfWages,
    includeInEsiWages: row.includeInEsiWages,
    statutoryHead: row.statutoryHead,
  };
}

export function applicabilityLabel(rules: ApplicabilityRules, note: string): string {
  const parts: string[] = [];
  if (rules.departments.length) parts.push(`Department: ${rules.departments.join(', ')}`);
  if (rules.designations.length) parts.push(`Designation: ${rules.designations.join(', ')}`);
  if (rules.grades.length) parts.push(`Grade: ${rules.grades.join(', ')}`);
  if (rules.locations.length) parts.push(`Location: ${rules.locations.join(', ')}`);
  if (rules.categories.length) parts.push(`Category: ${rules.categories.join(', ')}`);
  if (rules.employees.length) parts.push(`Employee: ${rules.employees.join(', ')}`);
  if (parts.length) return parts.join(' · ');
  const text = note.trim();
  return text || 'All employees';
}

export function basisLabel(row: Pick<SalaryComponentRow, 'calculation' | 'basis' | 'basisComponent'>): string {
  if (row.calculation === 'Fixed') return '—';
  if (row.calculation === 'Formula') return 'Formula';
  if (row.basis === 'Component') return row.basisComponent || 'Component';
  return row.basis;
}

export function trimNumber(value: number): string {
  if (Number.isInteger(value)) return String(value);
  return String(value);
}

function versionOf(row: SalaryComponentRow, version: number, at: string, by: string): ComponentVersion {
  return {
    version,
    calculation: row.calculation,
    basis: row.basis,
    basisComponent: row.basisComponent,
    value: row.value,
    formula: row.formula,
    rounding: row.rounding,
    minimum: row.minimum,
    maximum: row.maximum,
    effectiveFrom: row.effectiveFrom,
    effectiveTo: row.effectiveTo,
    changedAt: at,
    changedBy: by,
  };
}

function sameVersion(row: SalaryComponentRow, draft: ComponentDraft): boolean {
  return row.calculation === draft.calculation
    && row.basis === draft.basis
    && row.basisComponent === draft.basisComponent
    && row.value === draft.value
    && row.formula === draft.formula
    && row.rounding === draft.rounding
    && row.minimum === draft.minimum
    && row.maximum === draft.maximum
    && row.effectiveFrom === draft.effectiveFrom
    && row.effectiveTo === draft.effectiveTo;
}

export function validateDraft(
  draft: ComponentDraft,
  codes: readonly string[],
  ignoreCode = '',
): string | null {
  const code = draft.code.trim().toUpperCase();
  if (!/^[A-Z][A-Z0-9_-]{0,19}$/.test(code)) {
    return 'Component code must start with a letter and use only letters, numbers, underscores and hyphens (20 characters).';
  }
  if (code !== ignoreCode.toUpperCase() && codes.some((item) => item.toUpperCase() === code)) {
    return 'Component code is already used.';
  }
  const name = draft.name.trim();
  if (!name || name.length > 80) return 'Component name is required (80 characters).';
  if (draft.calculation === 'Formula') {
    const formula = draft.formula.trim();
    if (!formula) return 'Enter a formula.';
    if (formula.length > 300) return 'Formula must be 300 characters or less.';
    const checked = evaluateFormula(formula, { BASIC: 1, GROSS: 1, CTC: 1, [draft.basisComponent.trim().toUpperCase() || 'COMPONENT']: 1 });
    if (!checked.ok && !checked.error.startsWith('Unknown name')) return checked.error;
  } else if (draft.value < 0 || !Number.isFinite(draft.value)) {
    return 'Amount / percentage must be zero or more.';
  }
  if (draft.calculation === 'Percentage' && draft.basis === 'Formula') {
    return 'Choose a calculation basis for a percentage.';
  }
  if (draft.calculation === 'Percentage' && draft.basis === 'Component' && !draft.basisComponent.trim()) {
    return 'Choose the salary component this percentage uses.';
  }
  if (draft.minimum != null && !Number.isFinite(draft.minimum)) return 'Minimum must be a number.';
  if (draft.maximum != null && !Number.isFinite(draft.maximum)) return 'Maximum must be a number.';
  if (draft.minimum != null && draft.maximum != null && draft.minimum > draft.maximum) {
    return 'Minimum cannot be above maximum.';
  }
  if (draft.effectiveFrom && draft.effectiveTo && draft.effectiveTo < draft.effectiveFrom) {
    return 'Effective to cannot be before effective from.';
  }
  return null;
}

function applyDraft(
  row: Pick<SalaryComponentRow, 'id' | 'createdBy' | 'modifiedBy' | 'history' | 'versions'>,
  draft: ComponentDraft,
): SalaryComponentRow {
  const rules = {
    departments: [...draft.rules.departments],
    designations: [...draft.rules.designations],
    grades: [...draft.rules.grades],
    locations: [...draft.rules.locations],
    categories: [...draft.rules.categories],
    employees: [...draft.rules.employees],
  };
  return {
    id: row.id,
    createdBy: row.createdBy,
    modifiedBy: row.modifiedBy,
    history: row.history,
    versions: row.versions,
    code: draft.code.trim().toUpperCase(),
    name: draft.name.trim(),
    type: draft.type,
    calculation: draft.calculation,
    basis: draft.calculation === 'Formula' ? 'Formula' : draft.basis,
    basisComponent: draft.basis === 'Component' ? draft.basisComponent.trim().toUpperCase() : '',
    value: draft.calculation === 'Formula' ? 0 : draft.value,
    formula: draft.calculation === 'Formula' ? draft.formula.trim() : '',
    rounding: draft.rounding,
    minimum: draft.minimum,
    maximum: draft.maximum,
    rules,
    applicability: applicabilityLabel(rules, draft.applicability),
    effectiveFrom: draft.effectiveFrom,
    effectiveTo: draft.effectiveTo,
    active: draft.active,
    includeInGross: draft.includeInGross,
    includeInCtc: draft.includeInCtc,
    taxable: draft.taxable,
    recurrence: draft.recurrence,
    prorateAttendance: draft.prorateAttendance,
    lopTreatment: draft.lopTreatment,
    includeInPfWages: draft.includeInPfWages,
    includeInEsiWages: draft.includeInEsiWages,
    statutoryHead: draft.statutoryHead,
  };
}

export function createComponent(
  rows: readonly SalaryComponentRow[],
  draft: ComponentDraft,
  now = new Date(),
): FormulaResult & { row?: SalaryComponentRow } {
  const error = validateDraft(draft, rows.map((row) => row.code));
  if (error) return { ok: false, error };
  const at = now.toISOString();
  const row = applyDraft({
    id: rows.reduce((max, item) => Math.max(max, item.id), 0) + 1,
    createdBy: ACTOR,
    modifiedBy: ACTOR,
    history: [],
    versions: [],
  }, draft);
  row.history = [{ at, by: ACTOR, action: 'Created', summary: 'Component created' }];
  return { ok: true, value: 0, row };
}

export function updateComponent(
  current: SalaryComponentRow,
  draft: ComponentDraft,
  codes: readonly string[],
  now = new Date(),
): FormulaResult & { row?: SalaryComponentRow } {
  const error = validateDraft(draft, codes, current.code);
  if (error) return { ok: false, error };
  const at = now.toISOString();
  const next = applyDraft(cloneComponent(current), draft);
  next.modifiedBy = ACTOR;
  const action = current.active && !next.active
    ? 'Deactivated'
    : !current.active && next.active
      ? 'Activated'
      : 'Updated';
  next.history = [...current.history.map((item) => ({ ...item })), { at, by: ACTOR, action, summary: 'Component updated' }];
  next.versions = current.versions.map((item) => ({ ...item }));
  if (!sameVersion(current, draft)) {
    next.versions = [...next.versions, versionOf(current, current.versions.length + 1, at, ACTOR)];
  }
  return { ok: true, value: 0, row: next };
}

export function duplicateCode(rows: readonly { code: string }[], code: string): string {
  const base = code.toUpperCase().replace(/-COPY\d*$/, '');
  const used = new Set(rows.map((row) => row.code.toUpperCase()));
  let candidate = `${base}-COPY`.slice(0, 20);
  let n = 1;
  while (used.has(candidate)) {
    n += 1;
    const suffix = `-COPY${n}`;
    candidate = `${base.slice(0, Math.max(1, 20 - suffix.length))}${suffix}`;
  }
  return candidate;
}

export function duplicateComponent(
  rows: readonly SalaryComponentRow[],
  source: SalaryComponentRow,
  draft: ComponentDraft,
  now = new Date(),
): FormulaResult & { row?: SalaryComponentRow } {
  const error = validateDraft(draft, rows.map((row) => row.code));
  if (error) return { ok: false, error };
  const at = now.toISOString();
  const row = applyDraft({
    id: rows.reduce((max, item) => Math.max(max, item.id), 0) + 1,
    createdBy: ACTOR,
    modifiedBy: ACTOR,
    history: [],
    versions: [],
  }, draft);
  row.history = [{
    at,
    by: ACTOR,
    action: 'Duplicated',
    summary: `Duplicated from ${source.code}`,
  }];
  row.versions = [];
  return { ok: true, value: 0, row };
}

export function setComponentActive(
  current: SalaryComponentRow,
  active: boolean,
  now = new Date(),
): SalaryComponentRow {
  const next = cloneComponent(current);
  next.active = active;
  next.modifiedBy = ACTOR;
  next.history = [
    ...next.history,
    {
      at: now.toISOString(),
      by: ACTOR,
      action: active ? 'Activated' : 'Deactivated',
      summary: active ? 'Component activated' : 'Component deactivated',
    },
  ];
  return next;
}

export interface PreviewSamples {
  basic: number;
  gross: number;
  ctc: number;
  other: number;
}

export function previewAmount(draft: ComponentDraft, samples: PreviewSamples): FormulaResult {
  let result: FormulaResult;
  if (draft.calculation === 'Formula') {
    const variables: Record<string, number> = {
      BASIC: samples.basic,
      GROSS: samples.gross,
      CTC: samples.ctc,
    };
    const reserved = new Set(['BASIC', 'GROSS', 'CTC', 'MIN', 'MAX', 'ROUND']);
    for (const name of formulaNames(draft.formula)) {
      if (!reserved.has(name)) variables[name] = samples.other;
    }
    result = evaluateFormula(draft.formula, variables);
  } else if (draft.calculation === 'Percentage') {
    const base = draft.basis === 'Gross salary'
      ? samples.gross
      : draft.basis === 'CTC'
        ? samples.ctc
        : draft.basis === 'Component'
          ? samples.other
          : samples.basic;
    result = { ok: true, value: (base * draft.value) / 100 };
  } else {
    result = { ok: true, value: draft.value };
  }
  if (!result.ok) return result;
  const limited = applyLimits(result.value, draft.rounding, draft.minimum, draft.maximum);
  if (!Number.isFinite(limited)) return { ok: false, error: 'Amount / percentage must be a number.' };
  return { ok: true, value: limited };
}

export function applyLimits(
  value: number,
  rounding: RoundingMode,
  minimum: number | null,
  maximum: number | null,
): number {
  let next = value;
  if (rounding === 'Nearest rupee') next = Math.round(next);
  if (rounding === 'Round up') next = Math.ceil(next);
  if (rounding === 'Round down') next = Math.floor(next);
  if (minimum != null && next < minimum) next = minimum;
  if (maximum != null && next > maximum) next = maximum;
  return next;
}

type Token =
  | { kind: 'num'; value: number }
  | { kind: 'id'; value: string }
  | { kind: 'op'; value: '+' | '-' | '*' | '/' | '(' | ')' | ',' };

function formulaNames(source: string): string[] {
  const tokens = tokenize(source);
  if (!Array.isArray(tokens)) return [];
  return tokens.filter((token) => token.kind === 'id').map((token) => token.value);
}

function tokenize(source: string): Token[] | FormulaFailure {
  const tokens: Token[] = [];
  let index = 0;
  while (index < source.length) {
    const char = source[index];
    if (char === ' ' || char === '\n' || char === '\r' || char === '\t') {
      index += 1;
      continue;
    }
    if (char === '+' || char === '-' || char === '*' || char === '/' || char === '(' || char === ')' || char === ',') {
      tokens.push({ kind: 'op', value: char });
      index += 1;
      continue;
    }
    if (char >= '0' && char <= '9') {
      let end = index + 1;
      while (end < source.length && source[end] >= '0' && source[end] <= '9') end += 1;
      if (source[end] === '.') {
        end += 1;
        if (end >= source.length || source[end] < '0' || source[end] > '9') {
          return { ok: false, error: 'A number is incomplete.' };
        }
        while (end < source.length && source[end] >= '0' && source[end] <= '9') end += 1;
      }
      tokens.push({ kind: 'num', value: Number(source.slice(index, end)) });
      index = end;
      continue;
    }
    if ((char >= 'A' && char <= 'Z') || (char >= 'a' && char <= 'z') || char === '_') {
      let end = index + 1;
      while (end < source.length) {
        const next = source[end];
        const ok = (next >= 'A' && next <= 'Z') || (next >= 'a' && next <= 'z') || (next >= '0' && next <= '9') || next === '_';
        if (!ok) break;
        end += 1;
      }
      tokens.push({ kind: 'id', value: source.slice(index, end).toUpperCase() });
      index = end;
      continue;
    }
    return { ok: false, error: 'The formula contains a character that is not allowed.' };
  }
  return tokens;
}

/**
 * Arithmetic only: numbers, names, + - * /, parentheses, and MIN, MAX, ROUND.
 * Names are read from the supplied map. Nothing is compiled or executed.
 */
export function evaluateFormula(
  source: string,
  variables: Readonly<Record<string, number>>,
): FormulaResult {
  const tokens = tokenize(source.trim());
  if (!Array.isArray(tokens)) return tokens;
  if (!tokens.length) return { ok: false, error: 'Enter a formula.' };
  let cursor = 0;

  const peek = (): Token | undefined => tokens[cursor];
  const take = (): Token | undefined => tokens[cursor++];

  function fail(error: string): FormulaFailure {
    return { ok: false, error };
  }

  function parseExpression(): FormulaResult {
    let left = parseTerm();
    if (!left.ok) return left;
    while (peek()?.kind === 'op' && (peek()?.value === '+' || peek()?.value === '-')) {
      const op = take();
      const right = parseTerm();
      if (!right.ok) return right;
      left = { ok: true, value: op?.value === '+' ? left.value + right.value : left.value - right.value };
    }
    return left;
  }

  function parseTerm(): FormulaResult {
    let left = parseUnary();
    if (!left.ok) return left;
    while (peek()?.kind === 'op' && (peek()?.value === '*' || peek()?.value === '/')) {
      const op = take();
      const right = parseUnary();
      if (!right.ok) return right;
      if (op?.value === '/' && right.value === 0) return fail('Division by zero.');
      left = { ok: true, value: op?.value === '*' ? left.value * right.value : left.value / right.value };
    }
    return left;
  }

  function parseUnary(): FormulaResult {
    if (peek()?.kind === 'op' && peek()?.value === '-') {
      take();
      const inner = parseUnary();
      if (!inner.ok) return inner;
      return { ok: true, value: -inner.value };
    }
    return parsePrimary();
  }

  function parsePrimary(): FormulaResult {
    const token = take();
    if (!token) return fail('The formula ended early.');
    if (token.kind === 'num') return { ok: true, value: token.value };
    if (token.kind === 'op' && token.value === '(') {
      const inner = parseExpression();
      if (!inner.ok) return inner;
      const close = take();
      if (close?.kind !== 'op' || close.value !== ')') return fail('A closing parenthesis is missing.');
      return inner;
    }
    if (token.kind === 'id') {
      const next = peek();
      if (next?.kind === 'op' && next.value === '(') {
        return parseCall(token.value);
      }
      if (!(token.value in variables) || !Number.isFinite(variables[token.value])) {
        return fail(`Unknown name ${token.value}.`);
      }
      return { ok: true, value: variables[token.value] };
    }
    return fail('The formula could not be read.');
  }

  function parseCall(name: string): FormulaResult {
    take();
    const args: number[] = [];
    if (!(peek()?.kind === 'op' && peek()?.value === ')')) {
      while (true) {
        const arg = parseExpression();
        if (!arg.ok) return arg;
        args.push(arg.value);
        const sep = peek();
        if (sep?.kind === 'op' && sep.value === ',') {
          take();
          continue;
        }
        break;
      }
    }
    const close = take();
    if (close?.kind !== 'op' || close.value !== ')') return fail('A closing parenthesis is missing.');
    if (name === 'MIN' || name === 'MAX') {
      if (args.length < 2) return fail(`${name} needs at least two values.`);
      return { ok: true, value: name === 'MIN' ? Math.min(...args) : Math.max(...args) };
    }
    if (name === 'ROUND') {
      if (args.length < 1 || args.length > 2) return fail('ROUND needs one value, or a value and decimal places.');
      const places = args.length === 2 ? args[1] : 0;
      if (!Number.isInteger(places) || places < 0 || places > 4) {
        return fail('ROUND decimal places must be a whole number from 0 to 4.');
      }
      const factor = 10 ** places;
      return { ok: true, value: Math.round(args[0] * factor) / factor };
    }
    return fail(`Unknown function ${name}.`);
  }

  const result = parseExpression();
  if (!result.ok) return result;
  if (cursor !== tokens.length) return fail('The formula has an extra part.');
  if (!Number.isFinite(result.value)) return fail('The formula did not produce a number.');
  return result;
}
