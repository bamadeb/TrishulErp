import {
  DashboardDepartmentRow,
  DashboardExceptionItem,
  DashboardKpiCard,
  DashboardOverviewSlice,
  DashboardQuickAction,
  DashboardTrendPoint,
} from './attendance.models';

/** Static sample data for Attendance Dashboard UI (no API). */

export const DASHBOARD_DATE_LABEL = '21 Nov 2026 (Today)';

export const DASHBOARD_KPI: DashboardKpiCard[] = [
  {
    id: 'total',
    label: 'Total Employees',
    value: 800,
    icon: 'groups',
    tone: 'total',
  },
  {
    id: 'present',
    label: 'Present',
    value: 742,
    percent: 92.8,
    icon: 'check_circle',
    tone: 'present',
  },
  {
    id: 'absent',
    label: 'Absent',
    value: 20,
    percent: 2.5,
    icon: 'person_off',
    tone: 'absent',
  },
  {
    id: 'late',
    label: 'Late Arrival',
    value: 18,
    percent: 2.3,
    icon: 'schedule',
    tone: 'late',
  },
  {
    id: 'early',
    label: 'Early Exit',
    value: 8,
    percent: 1.0,
    icon: 'logout',
    tone: 'early',
  },
  {
    id: 'short',
    label: 'Short Hours',
    value: 12,
    percent: 1.5,
    icon: 'timer',
    tone: 'short',
  },
];

export const DASHBOARD_ATTENDANCE_RATE = 92.8;

export const DASHBOARD_OVERVIEW: DashboardOverviewSlice[] = [
  { label: 'Present', count: 742, percent: 92.8, color: '#22c55e' },
  { label: 'Absent', count: 20, percent: 2.5, color: '#ef4444' },
  { label: 'Late Arrival', count: 18, percent: 2.3, color: '#f59e0b' },
  { label: 'Early Exit', count: 8, percent: 1.0, color: '#8b5cf6' },
  { label: 'Short Hours', count: 12, percent: 1.5, color: '#0ea5e9' },
];

export const DASHBOARD_TREND: DashboardTrendPoint[] = [
  { label: '15 Nov', percent: 91.6 },
  { label: '16 Nov', percent: 92.1 },
  { label: '17 Nov', percent: 91.8 },
  { label: '18 Nov', percent: 92.4 },
  { label: '19 Nov', percent: 93.0 },
  { label: '20 Nov', percent: 92.6 },
  { label: '21 Nov', percent: 92.8 },
];

export const DASHBOARD_DEPARTMENTS: DashboardDepartmentRow[] = [
  { id: 1, department: 'IT', employees: 120, present: 113, absent: 4, attendancePct: 94.2 },
  { id: 2, department: 'Operations', employees: 210, present: 188, absent: 12, attendancePct: 89.5 },
  { id: 3, department: 'Sales', employees: 96, present: 88, absent: 5, attendancePct: 91.7 },
  { id: 4, department: 'Finance', employees: 64, present: 60, absent: 1, attendancePct: 93.8 },
  { id: 5, department: 'HR', employees: 48, present: 45, absent: 1, attendancePct: 93.8 },
  { id: 6, department: 'Field Service', employees: 140, present: 126, absent: 6, attendancePct: 90.0 },
  { id: 7, department: 'Admin', employees: 50, present: 47, absent: 1, attendancePct: 94.0 },
  { id: 8, department: 'Management', employees: 72, present: 68, absent: 2, attendancePct: 94.4 },
];

export const DASHBOARD_EXCEPTIONS_TOTAL = 46;

export const DASHBOARD_EXCEPTIONS: DashboardExceptionItem[] = [
  {
    id: 'missing',
    label: 'Missing Punch',
    count: 26,
    tone: 'missing',
    icon: 'fingerprint',
    route: '/hr/attendance/exceptions',
  },
  {
    id: 'late',
    label: 'Late Arrival',
    count: 18,
    tone: 'late',
    icon: 'schedule',
    route: '/hr/attendance/exceptions',
  },
  {
    id: 'early',
    label: 'Early Exit',
    count: 8,
    tone: 'early',
    icon: 'logout',
    route: '/hr/attendance/exceptions',
  },
  {
    id: 'short',
    label: 'Short Hours',
    count: 12,
    tone: 'short',
    icon: 'timer',
    route: '/hr/attendance/exceptions',
  },
];

export const DASHBOARD_ACTIONS: DashboardQuickAction[] = [
  {
    id: 'regularize',
    label: 'Regularize Attendance',
    icon: 'add',
    route: '/hr/attendance/regularization',
  },
  {
    id: 'rules',
    label: 'Manage Shifts & Rules',
    icon: 'rule',
    route: '/hr/attendance/rules',
  },
  {
    id: 'finalize',
    label: 'Finalize Attendance',
    icon: 'event_available',
    route: '/hr/attendance/finalization',
  },
  {
    id: 'reports',
    label: 'Attendance Reports',
    icon: 'download',
    route: '/hr/attendance/monthly-muster',
  },
];
