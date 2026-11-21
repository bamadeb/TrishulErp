import { RegularizationRequest } from './attendance.models';

/**
 * Regularization tab has no backend API yet.
 * Keep a small static list for that tab only.
 */
export const REGULARIZATION_REQUESTS: RegularizationRequest[] = [
  {
    id: 1,
    employeeCode: 'TRI014',
    employeeName: 'Priya Patel',
    date: '21 Nov 2026',
    reason: 'Traffic delay — late punch-in',
    status: 'Pending',
    avatarTone: '#db2777',
  },
  {
    id: 2,
    employeeCode: 'TRI068',
    employeeName: 'Karan Mehta',
    date: '20 Nov 2026',
    reason: 'Client site visit — missing out punch',
    status: 'Pending',
    avatarTone: '#c2410c',
  },
  {
    id: 3,
    employeeCode: 'TRI027',
    employeeName: 'Rahul Verma',
    date: '19 Nov 2026',
    reason: 'Biometric device offline',
    status: 'Approved',
    avatarTone: '#ea580c',
  },
];
