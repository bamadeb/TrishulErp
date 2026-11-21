/** Shared Daily Attendance view models (display strings for times). */

export type AttendanceStatus =
  | 'Present'
  | 'Late'
  | 'Missing Punch'
  | 'Absent'
  | 'On Leave'
  | 'Off Day'
  | 'Holiday';

export type PunchKind = 'IN' | 'OUT';
export type StatusTab = 'all' | 'present' | 'absent' | 'leave' | 'offDay';

export interface AttendancePunch {
  kind: PunchKind;
  at: string;
  device: string;
}

export interface AttendanceHistoryItem {
  date: string;
  status: AttendanceStatus;
  firstIn: string | null;
  lastOut: string | null;
  workingHours: string | null;
}

export interface DailyAttendanceRow {
  id: number;
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  department: string;
  location: string;
  shift: string;
  employeeType: string;
  reportingManager: string;
  firstIn: string | null;
  lastOut: string | null;
  firstInLate: boolean;
  workingHours: string | null;
  status: AttendanceStatus;
  remarks: string;
  punches: AttendancePunch[];
  history: AttendanceHistoryItem[];
}

export interface AttendanceKpi {
  total: number;
  present: number;
  absent: number;
  onLeave: number;
  offDay: number;
  holiday: number;
  late: number;
  missingPunch: number;
}

export const ATTENDANCE_STATUSES: AttendanceStatus[] = [
  'Present',
  'Late',
  'Missing Punch',
  'Absent',
  'On Leave',
  'Off Day',
  'Holiday',
];
