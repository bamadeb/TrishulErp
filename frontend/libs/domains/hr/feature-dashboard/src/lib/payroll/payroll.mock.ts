/** Hardcoded Payroll Management prototype. Nothing here is loaded from an API. */

export type PayrollStatus =
  | 'Active'
  | 'Inactive'
  | 'Pending'
  | 'Approved'
  | 'Rejected'
  | 'Draft'
  | 'Processed'
  | 'Paid'
  | 'Filed'
  | 'Due'
  | 'Imported'
  | 'Failed';

export interface SalaryRow {
  id: number;
  employeeCode: string;
  name: string;
  department: string;
  designation: string;
  ctc: number;
  gross: number;
  basic: number;
  hra: number;
  allowances: number;
  deductions: number;
}

export type { SalaryComponentRow } from './components/salary-component.model';
export { SALARY_COMPONENTS } from './components/salary-component.model';

export interface PayrollRun {
  id: number;
  month: string;
  employees: number;
  gross: number;
  deductions: number;
  net: number;
  status: 'Draft' | 'Processed' | 'Approved' | 'Paid';
}

export interface PayrollApproval {
  id: number;
  employee: string;
  month: string;
  net: number;
  submittedBy: string;
  status: 'Pending' | 'Approved' | 'Rejected';
}

export interface PayslipRow {
  id: number;
  name: string;
  code: string;
  month: string;
  gross: number;
  deductions: number;
  net: number;
}

export interface ClaimRow {
  id: number;
  employee: string;
  type: string;
  date: string;
  amount: number;
  status: 'Pending' | 'Approved' | 'Rejected';
}

export type VehicleType = 'Bike' | 'Car';

export interface TadaRow {
  id: number;
  code: string;
  name: string;
  designation: string;
  serviceDate: string;
  ticket: string;
  from: string;
  to: string;
  vehicle: VehicleType;
  km: number;
  hra: number;
  specialAllowance: number;
  otherAllowance: number;
  conveyance: number;
  promotion: number;
  status: 'Pending' | 'Approved' | 'Rejected';
}

export interface ImportBatch {
  id: number;
  fileName: string;
  importedAt: string;
  rows: number;
  status: 'Imported' | 'Failed';
}

export interface StatutoryRow {
  code: string;
  name: string;
  employeeShare: number;
  employerShare: number;
}

export interface StatutoryScheme {
  id: 'pf' | 'esi' | 'pt' | 'tds';
  name: string;
  period: string;
  status: 'Filed' | 'Due' | 'Draft';
  rows: StatutoryRow[];
}

export interface ActivityRow {
  when: string;
  text: string;
  status: PayrollStatus;
}

export interface TrendPoint {
  month: string;
  net: number;
}

export interface PayrollSettings {
  period: 'Monthly';
  cutoffDay: number;
  payDay: number;
  workingDays: number;
  lopProRata: boolean;
  attendanceIntegration: boolean;
  workflow: string;
  bikePerKm: number;
  carPerKm: number;
}

export const SALARIES: SalaryRow[] = [
  { id: 1, employeeCode: 'EMP-0142', name: 'Ananya Rao', department: 'Administration', designation: 'Manager', ctc: 960000, gross: 72000, basic: 36000, hra: 14400, allowances: 21600, deductions: 8400 },
  { id: 2, employeeCode: 'EMP-0208', name: 'Karthik Menon', department: 'Human Resources', designation: 'Executive', ctc: 540000, gross: 42000, basic: 21000, hra: 8400, allowances: 12600, deductions: 3900 },
  { id: 3, employeeCode: 'EMP-0116', name: 'Meera Singh', department: 'Finance', designation: 'Assistant Vice President', ctc: 1440000, gross: 110000, basic: 55000, hra: 22000, allowances: 33000, deductions: 16800 },
  { id: 4, employeeCode: 'EMP-0331', name: 'Rohan Deshmukh', department: 'Information Technology', designation: 'Team Lead', ctc: 840000, gross: 64000, basic: 32000, hra: 12800, allowances: 19200, deductions: 7200 },
  { id: 5, employeeCode: 'EMP-0274', name: 'Priya Nair', department: 'Operations', designation: 'Manager', ctc: 780000, gross: 60000, basic: 30000, hra: 12000, allowances: 18000, deductions: 6100 },
  { id: 6, employeeCode: 'EMP-0419', name: 'Neha Sharma', department: 'Service', designation: 'Service Engineer', ctc: 420000, gross: 32000, basic: 16000, hra: 6400, allowances: 9600, deductions: 2400 },
];

export const PAYROLL_RUNS: PayrollRun[] = [
  { id: 1, month: 'Oct 2026', employees: 186, gross: 9240000, deductions: 1462000, net: 7778000, status: 'Paid' },
  { id: 2, month: 'Nov 2026', employees: 188, gross: 9315000, deductions: 1488000, net: 7827000, status: 'Approved' },
  { id: 3, month: 'Dec 2026', employees: 190, gross: 9480000, deductions: 1510000, net: 7970000, status: 'Processed' },
  { id: 4, month: 'Jan 2027', employees: 192, gross: 9564000, deductions: 1526000, net: 8038000, status: 'Draft' },
];

export const PAYROLL_APPROVALS: PayrollApproval[] = [
  { id: 1, employee: 'Ananya Rao', month: 'Jan 2027', net: 63600, submittedBy: 'Payroll Officer', status: 'Pending' },
  { id: 2, employee: 'Karthik Menon', month: 'Jan 2027', net: 38100, submittedBy: 'Payroll Officer', status: 'Pending' },
  { id: 3, employee: 'Meera Singh', month: 'Jan 2027', net: 93200, submittedBy: 'Payroll Officer', status: 'Approved' },
  { id: 4, employee: 'Rohan Deshmukh', month: 'Dec 2026', net: 56800, submittedBy: 'HR Executive', status: 'Rejected' },
  { id: 5, employee: 'Priya Nair', month: 'Jan 2027', net: 53900, submittedBy: 'Payroll Officer', status: 'Pending' },
];

export const PAYSLIPS: PayslipRow[] = SALARIES.map((row) => ({
  id: row.id,
  name: row.name,
  code: row.employeeCode,
  month: 'Dec 2026',
  gross: row.gross,
  deductions: row.deductions,
  net: row.gross - row.deductions,
}));

export const CLAIMS: ClaimRow[] = [
  { id: 1, employee: 'Neha Sharma', type: 'Travel', date: '12 Jan 2027', amount: 2450, status: 'Pending' },
  { id: 2, employee: 'Rohan Deshmukh', type: 'Medical', date: '08 Jan 2027', amount: 6800, status: 'Approved' },
  { id: 3, employee: 'Priya Nair', type: 'Mobile', date: '04 Jan 2027', amount: 999, status: 'Pending' },
  { id: 4, employee: 'Karthik Menon', type: 'Travel', date: '28 Dec 2026', amount: 1760, status: 'Rejected' },
  { id: 5, employee: 'Ananya Rao', type: 'Training', date: '18 Dec 2026', amount: 4500, status: 'Approved' },
];

export const TADA_ROWS: TadaRow[] = [
  { id: 1, code: 'SE-1104', name: 'Arjun Patel', designation: 'Service Engineer', serviceDate: '06 Jan 2027', ticket: 'SC-24081', from: 'Bengaluru', to: 'Tumkur', vehicle: 'Bike', km: 140, hra: 400, specialAllowance: 150, otherAllowance: 0, conveyance: 80, promotion: 0, status: 'Pending' },
  { id: 2, code: 'SE-1188', name: 'Divya Krishnan', designation: 'Senior Service Engineer', serviceDate: '06 Jan 2027', ticket: 'SC-24090', from: 'Mysuru', to: 'Mandya', vehicle: 'Car', km: 96, hra: 500, specialAllowance: 200, otherAllowance: 100, conveyance: 0, promotion: 250, status: 'Approved' },
  { id: 3, code: 'SE-1210', name: 'Imran Qureshi', designation: 'Service Engineer', serviceDate: '07 Jan 2027', ticket: 'SC-24102', from: 'Hubballi', to: 'Dharwad', vehicle: 'Bike', km: 42, hra: 400, specialAllowance: 0, otherAllowance: 50, conveyance: 60, promotion: 0, status: 'Pending' },
  { id: 4, code: 'SE-1092', name: 'Suresh Babu', designation: 'Service Engineer', serviceDate: '07 Jan 2027', ticket: 'SC-24115', from: 'Mangaluru', to: 'Udupi', vehicle: 'Car', km: 118, hra: 450, specialAllowance: 180, otherAllowance: 0, conveyance: 120, promotion: 0, status: 'Pending' },
  { id: 5, code: 'SE-1304', name: 'Pooja Joshi', designation: 'Service Engineer', serviceDate: '08 Jan 2027', ticket: 'SC-24128', from: 'Belagavi', to: 'Gokak', vehicle: 'Bike', km: 76, hra: 400, specialAllowance: 100, otherAllowance: 0, conveyance: 40, promotion: 0, status: 'Rejected' },
];

export const IMPORT_HISTORY: ImportBatch[] = [
  { id: 1, fileName: 'tada-dec-2026.csv', importedAt: '02 Jan 2027, 11:20', rows: 48, status: 'Imported' },
  { id: 2, fileName: 'tada-week-1.csv', importedAt: '09 Jan 2027, 16:05', rows: 12, status: 'Imported' },
];

export const STATUTORY: StatutoryScheme[] = [
  {
    id: 'pf',
    name: 'PF',
    period: 'Dec 2026',
    status: 'Filed',
    rows: [
      { code: 'EMP-0142', name: 'Ananya Rao', employeeShare: 4320, employerShare: 4320 },
      { code: 'EMP-0116', name: 'Meera Singh', employeeShare: 6600, employerShare: 6600 },
      { code: 'EMP-0331', name: 'Rohan Deshmukh', employeeShare: 3840, employerShare: 3840 },
    ],
  },
  {
    id: 'esi',
    name: 'ESI',
    period: 'Dec 2026',
    status: 'Due',
    rows: [
      { code: 'EMP-0419', name: 'Neha Sharma', employeeShare: 240, employerShare: 1040 },
      { code: 'SE-1104', name: 'Arjun Patel', employeeShare: 210, employerShare: 910 },
    ],
  },
  {
    id: 'pt',
    name: 'Professional Tax',
    period: 'Dec 2026',
    status: 'Filed',
    rows: [
      { code: 'EMP-0142', name: 'Ananya Rao', employeeShare: 200, employerShare: 0 },
      { code: 'EMP-0208', name: 'Karthik Menon', employeeShare: 200, employerShare: 0 },
      { code: 'EMP-0116', name: 'Meera Singh', employeeShare: 200, employerShare: 0 },
    ],
  },
  {
    id: 'tds',
    name: 'TDS',
    period: 'Dec 2026',
    status: 'Draft',
    rows: [
      { code: 'EMP-0116', name: 'Meera Singh', employeeShare: 8400, employerShare: 0 },
      { code: 'EMP-0142', name: 'Ananya Rao', employeeShare: 2100, employerShare: 0 },
    ],
  },
];

export const ACTIVITIES: ActivityRow[] = [
  { when: 'Today, 09:40', text: 'January payroll submitted for approval', status: 'Pending' },
  { when: 'Today, 08:15', text: 'TA/DA import tada-week-1.csv completed', status: 'Imported' },
  { when: 'Yesterday, 17:05', text: 'Meera Singh January payroll approved', status: 'Approved' },
  { when: 'Yesterday, 11:30', text: 'Rohan Deshmukh December payroll rejected', status: 'Rejected' },
  { when: '08 Jan 2027', text: 'December payroll marked paid', status: 'Paid' },
];

export const TREND: TrendPoint[] = [
  { month: 'Aug', net: 7420000 },
  { month: 'Sep', net: 7580000 },
  { month: 'Oct', net: 7778000 },
  { month: 'Nov', net: 7827000 },
  { month: 'Dec', net: 7970000 },
  { month: 'Jan', net: 8038000 },
];

export const DEFAULT_SETTINGS: PayrollSettings = {
  period: 'Monthly',
  cutoffDay: 25,
  payDay: 1,
  workingDays: 30,
  lopProRata: true,
  attendanceIntegration: true,
  workflow: 'HR review, then Finance approval',
  bikePerKm: 2.5,
  carPerKm: 5.5,
};

export const TADA_COLUMNS = [
  'Employee Code',
  'Employee Name',
  'Designation',
  'Service Date',
  'Service Call',
  'Travel From',
  'Travel To',
  'Vehicle Type',
  'Total KM',
  'HRA',
  'Special Allowance',
  'Other Allowance',
  'Conveyance',
  'Promotion',
] as const;

export const REPORTS = [
  { id: 'register', label: 'Monthly Payroll Register' },
  { id: 'employee', label: 'Employee Salary Report' },
  { id: 'department', label: 'Department-wise Payroll' },
  { id: 'deduction', label: 'Deduction Report' },
  { id: 'tada', label: 'TA/DA Report' },
] as const;

export type ReportId = (typeof REPORTS)[number]['id'];
