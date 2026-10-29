/**
 * Demonstration figures for the HR Dashboard only.
 * Nothing in this file is loaded from the API or the database.
 */

export interface HrSummary {
  totalEmployees: number;
  presentToday: number;
  absentToday: number;
  onLeave: number;
  pendingApprovals: number;
  payrollStatus: string;
  asOfLabel: string;
}

export interface HrSummaryCard {
  label: string;
  value: string;
  route: string;
  fragment?: string;
}

export interface AttendanceDay {
  date: string;
  label: string;
  present: number;
  absent: number;
  onLeave: number;
}

export interface DepartmentCount {
  department: string;
  employees: number;
}

export interface ApprovalRequest {
  employeeName: string;
  requestType: string;
  dateLabel: string;
  status: string;
}

export interface Celebration {
  employeeName: string;
  kind: 'Birthday' | 'Work anniversary';
  dateLabel: string;
  detail: string;
}

export interface Holiday {
  name: string;
  dateLabel: string;
  type: string;
}

export interface HrActivity {
  whenLabel: string;
  description: string;
}

export interface QuickAction {
  label: string;
  icon: string;
  route: string;
  /** Set when the destination is a labelled placeholder, not a built screen. */
  placeholder?: boolean;
}

export const hrSummary: HrSummary = {
  totalEmployees: 125,
  presentToday: 108,
  absentToday: 9,
  onLeave: 8,
  pendingApprovals: 12,
  payrollStatus: 'Not Started',
  asOfLabel: '29 Oct 2026',
};

export const summaryCards: HrSummaryCard[] = [
  {
    label: 'Total Employees',
    value: String(hrSummary.totalEmployees),
    route: '/admin/employees',
  },
  {
    label: 'Present Today',
    value: String(hrSummary.presentToday),
    route: '/hr/attendance',
  },
  {
    label: 'Absent Today',
    value: String(hrSummary.absentToday),
    route: '/hr/attendance',
  },
  {
    label: 'On Leave',
    value: String(hrSummary.onLeave),
    route: '/hr/leave',
  },
  {
    label: 'Pending Approvals',
    value: String(hrSummary.pendingApprovals),
    route: '/hr/dashboard',
    fragment: 'approvals',
  },
  {
    label: 'Payroll Status',
    value: hrSummary.payrollStatus,
    route: '/hr/payroll',
  },
];

/** Default day matches the summary cards. Other days show the date filter working. */
export const attendanceDays: AttendanceDay[] = [
  { date: '2026-10-29', label: '29 Oct 2026', present: 108, absent: 9, onLeave: 8 },
  { date: '2026-10-28', label: '28 Oct 2026', present: 112, absent: 6, onLeave: 7 },
  { date: '2026-10-27', label: '27 Oct 2026', present: 104, absent: 11, onLeave: 10 },
  { date: '2026-10-26', label: '26 Oct 2026', present: 98, absent: 14, onLeave: 13 },
];

/** Counts add up to the sample headcount of 125. */
export const departmentDistribution: DepartmentCount[] = [
  { department: 'Service', employees: 42 },
  { department: 'Sales', employees: 28 },
  { department: 'Administration', employees: 17 },
  { department: 'Stores', employees: 16 },
  { department: 'Accounts', employees: 14 },
  { department: 'Human Resources', employees: 8 },
];

export const approvalStatusFilters = [
  'All',
  'Pending',
  'Approved',
  'Rejected',
] as const;

export const pendingApprovals: ApprovalRequest[] = [
  { employeeName: 'Ananya Rao', requestType: 'Leave', dateLabel: '27 Oct 2026', status: 'Pending' },
  { employeeName: 'Karthik Menon', requestType: 'Attendance regularisation', dateLabel: '27 Oct 2026', status: 'Pending' },
  { employeeName: 'Priya Nair', requestType: 'Leave', dateLabel: '26 Oct 2026', status: 'Pending' },
  { employeeName: 'Rohan Deshmukh', requestType: 'Work from home', dateLabel: '26 Oct 2026', status: 'Pending' },
  { employeeName: 'Meera Iyer', requestType: 'Leave', dateLabel: '25 Oct 2026', status: 'Pending' },
  { employeeName: 'Arjun Patel', requestType: 'Compensatory off', dateLabel: '25 Oct 2026', status: 'Pending' },
  { employeeName: 'Sneha Kulkarni', requestType: 'Attendance regularisation', dateLabel: '24 Oct 2026', status: 'Pending' },
  { employeeName: 'Vikram Singh', requestType: 'Leave', dateLabel: '24 Oct 2026', status: 'Pending' },
  { employeeName: 'Divya Krishnan', requestType: 'Profile change', dateLabel: '23 Oct 2026', status: 'Pending' },
  { employeeName: 'Harish Reddy', requestType: 'Leave', dateLabel: '23 Oct 2026', status: 'Pending' },
  { employeeName: 'Lakshmi Venkatesh', requestType: 'Work from home', dateLabel: '22 Oct 2026', status: 'Pending' },
  { employeeName: 'Imran Qureshi', requestType: 'Compensatory off', dateLabel: '22 Oct 2026', status: 'Pending' },
];

export const celebrations: Celebration[] = [
  { employeeName: 'Neha Sharma', kind: 'Birthday', dateLabel: '31 Oct 2026', detail: 'Turns 34' },
  { employeeName: 'Ravi Chandra', kind: 'Work anniversary', dateLabel: '1 Nov 2026', detail: '6 years' },
  { employeeName: 'Suresh Babu', kind: 'Birthday', dateLabel: '2 Nov 2026', detail: 'Turns 41' },
  { employeeName: 'Pooja Joshi', kind: 'Work anniversary', dateLabel: '4 Nov 2026', detail: '3 years' },
  { employeeName: 'Fatima Khan', kind: 'Birthday', dateLabel: '5 Nov 2026', detail: 'Turns 29' },
  { employeeName: 'Amit Verma', kind: 'Work anniversary', dateLabel: '8 Nov 2026', detail: '10 years' },
];

export const holidays: Holiday[] = [
  { name: 'Kannada Rajyotsava', dateLabel: '1 Nov 2026', type: 'Regional' },
  { name: 'Diwali', dateLabel: '8 Nov 2026', type: 'Festival' },
  { name: 'Christmas', dateLabel: '25 Dec 2026', type: 'Festival' },
];

export const recentActivities: HrActivity[] = [
  { whenLabel: '29 Oct 2026, 09:15', description: 'Meera Iyer submitted a leave request for 3 Nov 2026.' },
  { whenLabel: '29 Oct 2026, 08:40', description: 'October payroll remains Not Started.' },
  { whenLabel: '28 Oct 2026, 17:20', description: 'Karthik Menon requested attendance regularisation for 27 Oct 2026.' },
  { whenLabel: '28 Oct 2026, 11:05', description: 'Ananya Rao was marked present at the Bengaluru service branch.' },
  { whenLabel: '27 Oct 2026, 16:30', description: 'Rohan Deshmukh asked to work from home on 30 Oct 2026.' },
];

export const quickActions: QuickAction[] = [
  { label: 'Add Employee', icon: 'person_add', route: '/admin/employees/new' },
  { label: 'Attendance', icon: 'fact_check', route: '/hr/attendance', placeholder: true },
  { label: 'Leave Requests', icon: 'event_busy', route: '/hr/leave', placeholder: true },
  { label: 'Payroll', icon: 'payments', route: '/hr/payroll', placeholder: true },
];

export const approvalStatusSeverity: Record<string, 'success' | 'warn' | 'danger' | 'neutral'> = {
  Pending: 'warn',
  Approved: 'success',
  Rejected: 'danger',
};
