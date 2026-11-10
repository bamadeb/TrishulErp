/** One list drives the Salary Components chooser and the table. */

export type SalaryColumnKey =
  | 'index'
  | 'code'
  | 'name'
  | 'type'
  | 'calculation'
  | 'basis'
  | 'amount'
  | 'applicability'
  | 'effectiveFrom'
  | 'effectiveTo'
  | 'tax'
  | 'statutory'
  | 'recurrence'
  | 'gross'
  | 'ctc'
  | 'pf'
  | 'esi'
  | 'proration'
  | 'lastModified'
  | 'status'
  | 'actions';

export interface SalaryListColumn {
  key: SalaryColumnKey;
  label: string;
  chooser: string;
  fixed: boolean;
  defaultVisible: boolean;
}

export const SALARY_LIST_COLUMNS: readonly SalaryListColumn[] = [
  { key: 'index', label: '#', chooser: 'Row number', fixed: true, defaultVisible: true },
  { key: 'code', label: 'Component code', chooser: 'Component code', fixed: true, defaultVisible: true },
  { key: 'name', label: 'Component name', chooser: 'Component name', fixed: true, defaultVisible: true },
  { key: 'type', label: 'Component type', chooser: 'Component type', fixed: false, defaultVisible: true },
  { key: 'calculation', label: 'Calculation method', chooser: 'Calculation method', fixed: false, defaultVisible: true },
  { key: 'basis', label: 'Calculation basis', chooser: 'Calculation basis', fixed: false, defaultVisible: true },
  { key: 'amount', label: 'Amount / percentage', chooser: 'Amount / percentage', fixed: false, defaultVisible: true },
  { key: 'applicability', label: 'Applicability', chooser: 'Applicability', fixed: false, defaultVisible: true },
  { key: 'effectiveFrom', label: 'Effective from', chooser: 'Effective from', fixed: false, defaultVisible: false },
  { key: 'effectiveTo', label: 'Effective to', chooser: 'Effective to', fixed: false, defaultVisible: false },
  { key: 'tax', label: 'Tax treatment', chooser: 'Tax treatment', fixed: false, defaultVisible: false },
  { key: 'statutory', label: 'Statutory head', chooser: 'Statutory head', fixed: false, defaultVisible: false },
  { key: 'recurrence', label: 'Recurrence', chooser: 'Recurrence', fixed: false, defaultVisible: false },
  { key: 'gross', label: 'Include in gross', chooser: 'Include in gross', fixed: false, defaultVisible: false },
  { key: 'ctc', label: 'Include in CTC', chooser: 'Include in CTC', fixed: false, defaultVisible: false },
  { key: 'pf', label: 'PF applicability', chooser: 'PF applicability', fixed: false, defaultVisible: false },
  { key: 'esi', label: 'ESI applicability', chooser: 'ESI applicability', fixed: false, defaultVisible: false },
  { key: 'proration', label: 'Proration', chooser: 'Proration', fixed: false, defaultVisible: false },
  { key: 'lastModified', label: 'Last modified', chooser: 'Last modified', fixed: false, defaultVisible: false },
  { key: 'status', label: 'Status', chooser: 'Status', fixed: true, defaultVisible: true },
  { key: 'actions', label: 'Actions', chooser: 'Actions', fixed: true, defaultVisible: true },
];

const OPTIONAL = new Set(SALARY_LIST_COLUMNS.filter((column) => !column.fixed).map((column) => column.key));
const FIXED: readonly SalaryColumnKey[] = ['index', 'code', 'name', 'status', 'actions'];

export function defaultHiddenColumns(): SalaryColumnKey[] {
  return SALARY_LIST_COLUMNS.filter((column) => !column.fixed && !column.defaultVisible).map((column) => column.key);
}

export function visibleSalaryColumns(hidden: readonly SalaryColumnKey[]): SalaryListColumn[] {
  const hiddenKeys = new Set(hidden);
  return SALARY_LIST_COLUMNS.filter((column) => column.fixed || !hiddenKeys.has(column.key));
}

/** Checked shows the column. Unchecked hides it. Fixed columns are ignored. */
export function setSalaryColumnVisible(
  hidden: readonly SalaryColumnKey[],
  key: SalaryColumnKey,
  visible: boolean,
): SalaryColumnKey[] {
  if (!OPTIONAL.has(key)) return [...hidden];
  const next = hidden.filter((item) => item !== key);
  if (!visible) next.push(key);
  return next;
}

export function isFixedSalaryColumn(key: SalaryColumnKey): boolean {
  return FIXED.includes(key);
}

export function salaryColumnKeys(columns: readonly { key: SalaryColumnKey }[]): SalaryColumnKey[] {
  return columns.map((column) => column.key);
}
