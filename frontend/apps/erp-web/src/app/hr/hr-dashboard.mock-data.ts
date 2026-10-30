/**
 * Demonstration source for the HR Dashboard.
 * Counts are related: attendance for a branch day adds up to that branch's headcount.
 * Nothing here is loaded from the API or the database.
 */

export const DEMO_BRANCHES = ['Bengaluru', 'Mumbai', 'Hyderabad'] as const;
export const DEMO_DEPARTMENTS = [
  'Service',
  'Sales',
  'Administration',
  'Stores',
  'Accounts',
  'Human Resources',
] as const;

export const DEMO_AS_OF = '2026-10-29';

export interface HeadcountCell {
  branch: string;
  department: string;
  active: number;
  probation: number;
  onNotice: number;
}

export interface BranchAttendance {
  date: string;
  label: string;
  branch: string;
  present: number;
  absent: number;
  onLeave: number;
}

export interface AttendanceTotals {
  present: number;
  absent: number;
  onLeave: number;
  headcount: number;
}

export type ApprovalStatus = 'Pending' | 'Approved' | 'Rejected';
export type ApprovalPriority = 'High' | 'Medium' | 'Low';

export interface ApprovalRequest {
  id: string;
  employeeName: string;
  requestType: string;
  submittedOn: string;
  submittedLabel: string;
  status: ApprovalStatus;
  priority: ApprovalPriority;
  branch: string;
  department: string;
  detail: string;
}

export interface MissingAttendance {
  id: string;
  employeeName: string;
  branch: string;
  department: string;
  date: string;
  gap: string;
}

export interface Celebration {
  employeeName: string;
  kind: 'Birthday' | 'Work anniversary';
  dateLabel: string;
  detail: string;
  branch: string;
  department: string;
}

export interface Holiday {
  name: string;
  dateLabel: string;
  type: string;
}

export interface HrActivity {
  id: string;
  whenLabel: string;
  description: string;
  branch?: string;
  department?: string;
}

export interface PayrollTask {
  label: string;
  state: string;
}

export interface QuickAction {
  label: string;
  icon: string;
  route: string;
  placeholder?: boolean;
}

/** Headcount by branch and department. Status columns add up to the department headcount. */
export const headcount: HeadcountCell[] = [
  { branch: 'Bengaluru', department: 'Service', active: 18, probation: 3, onNotice: 1 },
  { branch: 'Bengaluru', department: 'Sales', active: 10, probation: 2, onNotice: 0 },
  { branch: 'Bengaluru', department: 'Administration', active: 7, probation: 1, onNotice: 0 },
  { branch: 'Bengaluru', department: 'Stores', active: 6, probation: 1, onNotice: 0 },
  { branch: 'Bengaluru', department: 'Accounts', active: 4, probation: 1, onNotice: 0 },
  { branch: 'Bengaluru', department: 'Human Resources', active: 3, probation: 1, onNotice: 0 },
  { branch: 'Mumbai', department: 'Service', active: 12, probation: 1, onNotice: 1 },
  { branch: 'Mumbai', department: 'Sales', active: 8, probation: 1, onNotice: 1 },
  { branch: 'Mumbai', department: 'Administration', active: 5, probation: 1, onNotice: 0 },
  { branch: 'Mumbai', department: 'Stores', active: 4, probation: 1, onNotice: 0 },
  { branch: 'Mumbai', department: 'Accounts', active: 3, probation: 1, onNotice: 0 },
  { branch: 'Mumbai', department: 'Human Resources', active: 2, probation: 0, onNotice: 0 },
  { branch: 'Hyderabad', department: 'Service', active: 5, probation: 1, onNotice: 0 },
  { branch: 'Hyderabad', department: 'Sales', active: 5, probation: 1, onNotice: 0 },
  { branch: 'Hyderabad', department: 'Administration', active: 2, probation: 1, onNotice: 0 },
  { branch: 'Hyderabad', department: 'Stores', active: 3, probation: 1, onNotice: 0 },
  { branch: 'Hyderabad', department: 'Accounts', active: 4, probation: 1, onNotice: 0 },
  { branch: 'Hyderabad', department: 'Human Resources', active: 2, probation: 0, onNotice: 0 },
];

/** Each row's present + absent + on leave equals that branch's headcount. */
export const branchAttendance: BranchAttendance[] = [
  { date: '2026-10-26', label: '26 Oct 2026', branch: 'Bengaluru', present: 45, absent: 7, onLeave: 6 },
  { date: '2026-10-26', label: '26 Oct 2026', branch: 'Mumbai', present: 32, absent: 5, onLeave: 4 },
  { date: '2026-10-26', label: '26 Oct 2026', branch: 'Hyderabad', present: 21, absent: 2, onLeave: 3 },
  { date: '2026-10-27', label: '27 Oct 2026', branch: 'Bengaluru', present: 48, absent: 5, onLeave: 5 },
  { date: '2026-10-27', label: '27 Oct 2026', branch: 'Mumbai', present: 34, absent: 4, onLeave: 3 },
  { date: '2026-10-27', label: '27 Oct 2026', branch: 'Hyderabad', present: 22, absent: 2, onLeave: 2 },
  { date: '2026-10-28', label: '28 Oct 2026', branch: 'Bengaluru', present: 52, absent: 3, onLeave: 3 },
  { date: '2026-10-28', label: '28 Oct 2026', branch: 'Mumbai', present: 37, absent: 2, onLeave: 2 },
  { date: '2026-10-28', label: '28 Oct 2026', branch: 'Hyderabad', present: 23, absent: 1, onLeave: 2 },
  { date: '2026-10-29', label: '29 Oct 2026', branch: 'Bengaluru', present: 50, absent: 4, onLeave: 4 },
  { date: '2026-10-29', label: '29 Oct 2026', branch: 'Mumbai', present: 36, absent: 3, onLeave: 2 },
  { date: '2026-10-29', label: '29 Oct 2026', branch: 'Hyderabad', present: 22, absent: 2, onLeave: 2 },
];

export const attendanceDates = [
  { date: '2026-10-26', label: '26 Oct 2026' },
  { date: '2026-10-27', label: '27 Oct 2026' },
  { date: '2026-10-28', label: '28 Oct 2026' },
  { date: '2026-10-29', label: '29 Oct 2026' },
] as const;

export const approvalStatusFilters = ['All', 'Pending', 'Approved', 'Rejected'] as const;

export const approvalStatusSeverity: Record<string, 'success' | 'warn' | 'danger' | 'neutral'> = {
  Pending: 'warn',
  Approved: 'success',
  Rejected: 'danger',
  High: 'danger',
  Medium: 'warn',
  Low: 'neutral',
  Open: 'warn',
  Clear: 'success',
  'Not started': 'warn',
  'On track': 'success',
  Watch: 'warn',
  Below: 'danger',
  Sample: 'neutral',
};

export const pendingApprovals: ApprovalRequest[] = [
  { id: 'apr-01', employeeName: 'Ananya Rao', requestType: 'Leave', submittedOn: '2026-10-27', submittedLabel: '27 Oct 2026', status: 'Pending', priority: 'High', branch: 'Bengaluru', department: 'Service', detail: 'Sample casual leave for 3 Nov 2026. One day, Service desk cover is already named.' },
  { id: 'apr-02', employeeName: 'Karthik Menon', requestType: 'Attendance regularisation', submittedOn: '2026-10-27', submittedLabel: '27 Oct 2026', status: 'Pending', priority: 'Medium', branch: 'Bengaluru', department: 'Stores', detail: 'Sample request to mark 27 Oct 2026 present. The punch device at the stores gate did not record an in-time.' },
  { id: 'apr-03', employeeName: 'Priya Nair', requestType: 'Leave', submittedOn: '2026-10-26', submittedLabel: '26 Oct 2026', status: 'Pending', priority: 'High', branch: 'Mumbai', department: 'Sales', detail: 'Sample earned leave from 10 Nov 2026 to 12 Nov 2026.' },
  { id: 'apr-04', employeeName: 'Rohan Deshmukh', requestType: 'Work from home', submittedOn: '2026-10-26', submittedLabel: '26 Oct 2026', status: 'Pending', priority: 'Low', branch: 'Mumbai', department: 'Service', detail: 'Sample work-from-home request for 30 Oct 2026.' },
  { id: 'apr-05', employeeName: 'Meera Iyer', requestType: 'Leave', submittedOn: '2026-10-25', submittedLabel: '25 Oct 2026', status: 'Pending', priority: 'Medium', branch: 'Hyderabad', department: 'Accounts', detail: 'Sample leave on 3 Nov 2026 for a family function.' },
  { id: 'apr-06', employeeName: 'Arjun Patel', requestType: 'Compensatory off', submittedOn: '2026-10-25', submittedLabel: '25 Oct 2026', status: 'Pending', priority: 'Low', branch: 'Hyderabad', department: 'Sales', detail: 'Sample compensatory off on 6 Nov 2026 against duty on 18 Oct 2026.' },
  { id: 'apr-07', employeeName: 'Sneha Kulkarni', requestType: 'Attendance regularisation', submittedOn: '2026-10-24', submittedLabel: '24 Oct 2026', status: 'Pending', priority: 'High', branch: 'Bengaluru', department: 'Administration', detail: 'Sample request to correct 24 Oct 2026 from absent to present.' },
  { id: 'apr-08', employeeName: 'Vikram Singh', requestType: 'Leave', submittedOn: '2026-10-24', submittedLabel: '24 Oct 2026', status: 'Pending', priority: 'Medium', branch: 'Mumbai', department: 'Stores', detail: 'Sample sick leave for 31 Oct 2026.' },
  { id: 'apr-09', employeeName: 'Divya Krishnan', requestType: 'Profile change', submittedOn: '2026-10-23', submittedLabel: '23 Oct 2026', status: 'Pending', priority: 'Low', branch: 'Bengaluru', department: 'Human Resources', detail: 'Sample request to update the emergency contact number.' },
  { id: 'apr-10', employeeName: 'Harish Reddy', requestType: 'Leave', submittedOn: '2026-10-23', submittedLabel: '23 Oct 2026', status: 'Pending', priority: 'Medium', branch: 'Hyderabad', department: 'Service', detail: 'Sample leave on 7 Nov 2026.' },
  { id: 'apr-11', employeeName: 'Lakshmi Venkatesh', requestType: 'Work from home', submittedOn: '2026-10-22', submittedLabel: '22 Oct 2026', status: 'Pending', priority: 'Low', branch: 'Mumbai', department: 'Accounts', detail: 'Sample work-from-home request for 5 Nov 2026.' },
  { id: 'apr-12', employeeName: 'Imran Qureshi', requestType: 'Compensatory off', submittedOn: '2026-10-22', submittedLabel: '22 Oct 2026', status: 'Pending', priority: 'High', branch: 'Hyderabad', department: 'Stores', detail: 'Sample compensatory off on 2 Nov 2026 against the stock-count Sunday.' },
];

export const missingAttendance: MissingAttendance[] = [
  { id: 'gap-01', employeeName: 'Neha Sharma', branch: 'Bengaluru', department: 'Service', date: '2026-10-29', gap: 'No punch in' },
  { id: 'gap-02', employeeName: 'Suresh Babu', branch: 'Mumbai', department: 'Sales', date: '2026-10-29', gap: 'No punch in' },
  { id: 'gap-03', employeeName: 'Fatima Khan', branch: 'Hyderabad', department: 'Accounts', date: '2026-10-29', gap: 'No punch out' },
  { id: 'gap-04', employeeName: 'Ravi Chandra', branch: 'Bengaluru', department: 'Stores', date: '2026-10-28', gap: 'No punch in' },
  { id: 'gap-05', employeeName: 'Pooja Joshi', branch: 'Mumbai', department: 'Service', date: '2026-10-28', gap: 'No punch in' },
  { id: 'gap-06', employeeName: 'Amit Verma', branch: 'Hyderabad', department: 'Sales', date: '2026-10-27', gap: 'No punch in' },
  { id: 'gap-07', employeeName: 'Kavita Shenoy', branch: 'Bengaluru', department: 'Administration', date: '2026-10-26', gap: 'No punch out' },
  { id: 'gap-08', employeeName: 'Nandita Shah', branch: 'Mumbai', department: 'Human Resources', date: '2026-10-26', gap: 'No punch in' },
];

export const celebrations: Celebration[] = [
  { employeeName: 'Neha Sharma', kind: 'Birthday', dateLabel: '31 Oct 2026', detail: 'Turns 34', branch: 'Bengaluru', department: 'Service' },
  { employeeName: 'Ravi Chandra', kind: 'Work anniversary', dateLabel: '1 Nov 2026', detail: '6 years', branch: 'Bengaluru', department: 'Stores' },
  { employeeName: 'Suresh Babu', kind: 'Birthday', dateLabel: '2 Nov 2026', detail: 'Turns 41', branch: 'Mumbai', department: 'Sales' },
  { employeeName: 'Pooja Joshi', kind: 'Work anniversary', dateLabel: '4 Nov 2026', detail: '3 years', branch: 'Mumbai', department: 'Service' },
  { employeeName: 'Fatima Khan', kind: 'Birthday', dateLabel: '5 Nov 2026', detail: 'Turns 29', branch: 'Hyderabad', department: 'Accounts' },
  { employeeName: 'Amit Verma', kind: 'Work anniversary', dateLabel: '8 Nov 2026', detail: '10 years', branch: 'Hyderabad', department: 'Sales' },
];

export const holidays: Holiday[] = [
  { name: 'Kannada Rajyotsava', dateLabel: '1 Nov 2026', type: 'Regional' },
  { name: 'Diwali', dateLabel: '8 Nov 2026', type: 'Festival' },
  { name: 'Christmas', dateLabel: '25 Dec 2026', type: 'Festival' },
];

export const recentActivities: HrActivity[] = [
  { id: 'act-01', whenLabel: '29 Oct 2026, 09:15', description: 'Meera Iyer submitted a sample leave request for 3 Nov 2026.', branch: 'Hyderabad', department: 'Accounts' },
  { id: 'act-02', whenLabel: '29 Oct 2026, 08:40', description: 'October payroll is still Not Started in this sample.' },
  { id: 'act-03', whenLabel: '28 Oct 2026, 17:20', description: 'Karthik Menon requested sample attendance regularisation for 27 Oct 2026.', branch: 'Bengaluru', department: 'Stores' },
  { id: 'act-04', whenLabel: '28 Oct 2026, 11:05', description: 'Ananya Rao was marked present in the Bengaluru service sample.', branch: 'Bengaluru', department: 'Service' },
  { id: 'act-05', whenLabel: '27 Oct 2026, 16:30', description: 'Rohan Deshmukh asked to work from home on 30 Oct 2026 in this sample.', branch: 'Mumbai', department: 'Service' },
];

export const payrollOverview = {
  period: 'October 2026',
  from: '1 Oct 2026',
  to: '31 Oct 2026',
  status: 'Not Started',
  note: 'Payroll has not been processed. This sample does not include salary totals.',
  tasks: [
    { label: 'Lock attendance for October', state: 'Open' },
    { label: 'Clear pending leave requests', state: 'Open' },
    { label: 'Confirm joiners and exits for the period', state: 'Open' },
    { label: 'Start the payroll run', state: 'Open' },
  ] satisfies PayrollTask[],
};

export const quickActions: QuickAction[] = [
  { label: 'Add Employee', icon: 'person_add', route: '/admin/employees/new' },
  { label: 'Attendance', icon: 'fact_check', route: '/hr/attendance', placeholder: true },
  { label: 'Leave Requests', icon: 'event_busy', route: '/hr/leave', placeholder: true },
  { label: 'Payroll', icon: 'payments', route: '/hr/payroll', placeholder: true },
];

export function cellHeadcount(cell: HeadcountCell): number {
  return cell.active + cell.probation + cell.onNotice;
}

export function scopeHeadcount(branch: string, department: string): number {
  return headcount
    .filter((cell) => matchesScope(cell.branch, cell.department, branch, department))
    .reduce((sum, cell) => sum + cellHeadcount(cell), 0);
}

/** Largest-remainder split. `total` must not exceed the sum of `weights`. */
export function allocateCounts(total: number, weights: number[]): number[] {
  if (weights.length === 0 || total <= 0) return weights.map(() => 0);
  const weightSum = weights.reduce((sum, weight) => sum + weight, 0);
  if (weightSum <= 0) return weights.map(() => 0);
  const exact = weights.map((weight) => (total * weight) / weightSum);
  const result = exact.map((value) => Math.floor(value));
  let remainder = total - result.reduce((sum, value) => sum + value, 0);
  const order = exact
    .map((value, index) => ({ index, fraction: value - Math.floor(value) }))
    .sort((a, b) => b.fraction - a.fraction || a.index - b.index);
  for (let step = 0; step < remainder; step++) {
    result[order[step].index] += 1;
  }
  return result;
}

/**
 * Attendance for the selected date, branch, and department.
 * A department slice is allocated from that branch's day so the parts still add up.
 */
export function attendanceForScope(
  date: string,
  branch: string,
  department: string,
): AttendanceTotals | null {
  const slices = branchAttendance.filter(
    (row) => row.date === date && (branch === 'All' || row.branch === branch),
  );
  if (slices.length === 0) return null;
  let present = 0;
  let absent = 0;
  let onLeave = 0;
  for (const slice of slices) {
    const cells = headcount.filter((cell) => cell.branch === slice.branch);
    const weights = cells.map(cellHeadcount);
    const leave = allocateCounts(slice.onLeave, weights);
    const capacity = weights.map((weight, index) => weight - leave[index]);
    const absentParts = allocateCounts(slice.absent, capacity);
    cells.forEach((cell, index) => {
      if (department !== 'All' && cell.department !== department) return;
      present += weights[index] - leave[index] - absentParts[index];
      absent += absentParts[index];
      onLeave += leave[index];
    });
  }
  return { present, absent, onLeave, headcount: present + absent + onLeave };
}

export function formatShare(part: number, whole: number): string {
  if (whole <= 0) return '0%';
  const rounded = Math.round((part / whole) * 1000) / 10;
  return `${Number.isInteger(rounded) ? rounded.toFixed(0) : rounded.toFixed(1)}%`;
}

export function matchesScope(
  rowBranch: string,
  rowDepartment: string,
  branch: string,
  department: string,
): boolean {
  return (
    (branch === 'All' || rowBranch === branch) &&
    (department === 'All' || rowDepartment === department)
  );
}

/** Returns a message when the sample contradicts itself, otherwise null. */
export function validateSample(): string | null {
  if (scopeHeadcount('All', 'All') !== 125) {
    return 'Sample headcount is inconsistent.';
  }
  const dates = [...new Set(branchAttendance.map((row) => row.date))];
  for (const date of dates) {
    for (const branch of DEMO_BRANCHES) {
      const slice = branchAttendance.find(
        (row) => row.date === date && row.branch === branch,
      );
      const expected = scopeHeadcount(branch, 'All');
      if (!slice) return `Missing sample attendance for ${branch} on ${date}.`;
      const marked = slice.present + slice.absent + slice.onLeave;
      if (marked !== expected) {
        return `${branch} attendance on ${date} does not match its headcount.`;
      }
    }
  }
  const today = attendanceForScope(DEMO_AS_OF, 'All', 'All');
  if (!today || today.present !== 108 || today.absent !== 9 || today.onLeave !== 8) {
    return 'The 29 Oct 2026 sample does not add up to 108 present, 9 absent, and 8 on leave.';
  }
  if (pendingApprovals.length !== 12 || pendingApprovals.some((row) => row.status !== 'Pending')) {
    return 'The sample approval list must start with 12 pending requests.';
  }
  return null;
}
