import {
  RegularizationKpi,
  RegularizationListRow,
  RegularizationRequestType,
  RegularizationStatus,
} from './attendance.models';

/** Static sample data for Attendance Regularization UI (no API). */

const TONES = [
  '#2563eb',
  '#db2777',
  '#ea580c',
  '#7c3aed',
  '#0891b2',
  '#059669',
  '#c2410c',
  '#4f46e5',
  '#be123c',
  '#0d9488',
];

const PEOPLE: Array<{
  code: string;
  name: string;
  department: string;
  location: string;
}> = [
  { code: 'TRI001', name: 'Amit Sharma', department: 'IT', location: 'Head Office' },
  { code: 'TRI014', name: 'Priya Patel', department: 'HR', location: 'Head Office' },
  { code: 'TRI027', name: 'Rahul Verma', department: 'Operations', location: 'Bhadrak' },
  { code: 'TRI033', name: 'Sneha Reddy', department: 'Finance', location: 'Head Office' },
  { code: 'TRI041', name: 'Vikram Singh', department: 'Sales', location: 'Cuttack' },
  { code: 'TRI055', name: 'Ananya Das', department: 'IT', location: 'Head Office' },
  { code: 'TRI062', name: 'Karan Mehta', department: 'Operations', location: 'Angul-MCL' },
  { code: 'TRI068', name: 'Neha Gupta', department: 'HR', location: 'Head Office' },
  { code: 'TRI074', name: 'Arjun Nair', department: 'Service', location: 'Bhadrak' },
  { code: 'TRI081', name: 'Meera Iyer', department: 'Finance', location: 'Head Office' },
  { code: 'TRI088', name: 'Suresh Patra', department: 'Sales', location: 'Cuttack' },
  { code: 'TRI095', name: 'Divya Rao', department: 'IT', location: 'Head Office' },
];

const TYPES: RegularizationRequestType[] = [
  'Missed Punch',
  'Wrong Attendance',
  'Early Exit',
  'WFH Correction',
  'Late Arrival',
];

const REASONS = [
  'Missed IN punch due to client visit.',
  'Biometric device offline at gate.',
  'Left early for medical appointment.',
  'Worked from home — attendance not captured.',
  'Late arrival due to traffic delay.',
  'Wrong OUT punch recorded by device.',
  'Forgot to punch after returning from site.',
  'Network issue at office entry.',
];

function pad(n: number): string {
  return String(n).padStart(2, '0');
}

function buildRow(
  id: number,
  status: RegularizationStatus,
  day: number,
  typeIndex: number,
): RegularizationListRow {
  const person = PEOPLE[(id - 1) % PEOPLE.length]!;
  const type = TYPES[typeIndex % TYPES.length]!;
  const reason = REASONS[(id + typeIndex) % REASONS.length]!;
  const attendanceDateIso = `2026-11-${pad(Math.min(28, Math.max(1, day)))}`;
  const submittedDay = Math.min(30, day + 1);
  const originalIn =
    type === 'Missed Punch' && id % 3 === 1
      ? null
      : type === 'Late Arrival'
        ? '09:48 AM'
        : '09:12 AM';
  const originalOut =
    type === 'Missed Punch' && id % 2 === 0
      ? null
      : type === 'Early Exit'
        ? '04:10 PM'
        : '06:05 PM';

  return {
    id,
    employeeCode: person.code,
    employeeName: person.name,
    department: person.department,
    location: person.location,
    attendanceDate: `${pad(day)} Nov 2026`,
    attendanceDateIso,
    requestType: type,
    originalIn,
    originalOut,
    requestedIn: '09:30 AM',
    requestedOut: '06:30 PM',
    reason,
    submittedOn: `${pad(submittedDay)} Nov 2026, ${pad(9 + (id % 8))}:${pad((id * 7) % 60)} ${id % 2 ? 'AM' : 'PM'}`,
    status,
    avatarTone: TONES[(id - 1) % TONES.length]!,
    attachmentName: id % 4 === 0 ? 'supporting_note.pdf' : null,
    rejectionReason: status === 'Rejected' ? 'Insufficient evidence provided.' : null,
    reviewedBy: status === 'Pending' ? null : 'HR Admin',
    reviewedOn: status === 'Pending' ? null : `${pad(Math.min(30, submittedDay + 1))} Nov 2026`,
  };
}

/** Seed rows matching the reference layout, then expand for KPI/tab counts. */
const SEED: RegularizationListRow[] = [
  {
    id: 1,
    employeeCode: 'TRI001',
    employeeName: 'Amit Sharma',
    department: 'IT',
    location: 'Head Office',
    attendanceDate: '20 Nov 2026',
    attendanceDateIso: '2026-11-20',
    requestType: 'Missed Punch',
    originalIn: null,
    originalOut: '06:02 PM',
    requestedIn: '09:30 AM',
    requestedOut: '06:02 PM',
    reason: 'Missed IN punch due to client visit.',
    submittedOn: '21 Nov 2026, 10:14 AM',
    status: 'Pending',
    avatarTone: '#2563eb',
    attachmentName: null,
  },
  {
    id: 2,
    employeeCode: 'TRI014',
    employeeName: 'Priya Patel',
    department: 'HR',
    location: 'Head Office',
    attendanceDate: '19 Nov 2026',
    attendanceDateIso: '2026-11-19',
    requestType: 'Wrong Attendance',
    originalIn: '10:05 AM',
    originalOut: '05:40 PM',
    requestedIn: '09:15 AM',
    requestedOut: '06:10 PM',
    reason: 'Wrong OUT punch recorded by device.',
    submittedOn: '20 Nov 2026, 09:02 AM',
    status: 'Pending',
    avatarTone: '#db2777',
  },
  {
    id: 3,
    employeeCode: 'TRI027',
    employeeName: 'Rahul Verma',
    department: 'Operations',
    location: 'Bhadrak',
    attendanceDate: '18 Nov 2026',
    attendanceDateIso: '2026-11-18',
    requestType: 'Early Exit',
    originalIn: '09:05 AM',
    originalOut: '03:45 PM',
    requestedIn: '09:05 AM',
    requestedOut: '06:00 PM',
    reason: 'Left early for medical appointment.',
    submittedOn: '19 Nov 2026, 11:28 AM',
    status: 'Pending',
    avatarTone: '#ea580c',
    attachmentName: 'doctor_note.pdf',
  },
  {
    id: 4,
    employeeCode: 'TRI033',
    employeeName: 'Sneha Reddy',
    department: 'Finance',
    location: 'Head Office',
    attendanceDate: '17 Nov 2026',
    attendanceDateIso: '2026-11-17',
    requestType: 'WFH Correction',
    originalIn: null,
    originalOut: null,
    requestedIn: '09:30 AM',
    requestedOut: '06:30 PM',
    reason: 'Worked from home — attendance not captured.',
    submittedOn: '18 Nov 2026, 08:45 AM',
    status: 'Approved',
    avatarTone: '#7c3aed',
    reviewedBy: 'HR Admin',
    reviewedOn: '18 Nov 2026',
  },
  {
    id: 5,
    employeeCode: 'TRI041',
    employeeName: 'Vikram Singh',
    department: 'Sales',
    location: 'Cuttack',
    attendanceDate: '16 Nov 2026',
    attendanceDateIso: '2026-11-16',
    requestType: 'Missed Punch',
    originalIn: '09:20 AM',
    originalOut: null,
    requestedIn: '09:20 AM',
    requestedOut: '06:15 PM',
    reason: 'Forgot to punch after returning from site.',
    submittedOn: '17 Nov 2026, 04:12 PM',
    status: 'Rejected',
    avatarTone: '#0891b2',
    rejectionReason: 'Insufficient evidence provided.',
    reviewedBy: 'HR Admin',
    reviewedOn: '18 Nov 2026',
  },
  {
    id: 6,
    employeeCode: 'TRI055',
    employeeName: 'Ananya Das',
    department: 'IT',
    location: 'Head Office',
    attendanceDate: '15 Nov 2026',
    attendanceDateIso: '2026-11-15',
    requestType: 'Late Arrival',
    originalIn: '09:52 AM',
    originalOut: '06:20 PM',
    requestedIn: '09:10 AM',
    requestedOut: '06:20 PM',
    reason: 'Late arrival due to traffic delay.',
    submittedOn: '16 Nov 2026, 09:30 AM',
    status: 'Pending',
    avatarTone: '#059669',
  },
];

const generated: RegularizationListRow[] = [];
let nextId = 7;
// Seed already has 4 Pending, 1 Approved, 1 Rejected → target 18 / 96 / 10.
for (let i = 0; i < 14; i++) {
  generated.push(buildRow(nextId++, 'Pending', 3 + (i % 20), i));
}
for (let i = 0; i < 95; i++) {
  generated.push(buildRow(nextId++, 'Approved', 1 + (i % 25), i + 1));
}
for (let i = 0; i < 9; i++) {
  generated.push(buildRow(nextId++, 'Rejected', 2 + (i % 22), i + 2));
}

export const REGULARIZATION_ROWS: RegularizationListRow[] = [...SEED, ...generated];

export const REGULARIZATION_KPI: RegularizationKpi = {
  total: REGULARIZATION_ROWS.length,
  pending: REGULARIZATION_ROWS.filter((r) => r.status === 'Pending').length,
  approved: REGULARIZATION_ROWS.filter((r) => r.status === 'Approved').length,
  rejected: REGULARIZATION_ROWS.filter((r) => r.status === 'Rejected').length,
};

export const REGULARIZATION_EMPLOYEE_OPTIONS = PEOPLE.map((person, index) => ({
  id: index + 1,
  employeeCode: person.code,
  employeeName: person.name,
  department: person.department,
  location: person.location,
  avatarTone: TONES[index % TONES.length]!,
  firstIn: '09:12 AM' as string | null,
  lastOut: '06:05 PM' as string | null,
  status: 'Present' as const,
}));
