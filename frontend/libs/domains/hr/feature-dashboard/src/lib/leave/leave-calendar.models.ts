/** Shapes for the Leave Calendar screen. Phase 2 can return these from the API. */

export type LeaveCalendarStatus = 'Approved' | 'Pending' | 'Rejected' | 'Cancelled';

export type CalendarViewMode = 'month' | 'week' | 'day';

export interface EmployeeCalendarInfo {
  employeeId: number;
  code: string;
  name: string;
  department: string;
  designation: string;
  location: string;
  initials: string;
  color: string;
}

export interface CalendarLeaveEntry {
  id: string;
  employeeId: number;
  leaveCode: string;
  leaveType: string;
  fromDate: string;
  toDate: string;
  days: number;
  status: string;
  reason: string;
  approvedBy: string | null;
}

export interface CalendarHoliday {
  date: string;
  name: string;
}

export interface LeaveCalendarFilters {
  departmentId: number | null;
  designationId: number | null;
  branchId: number | null;
  leaveTypeId: number | null;
  search: string;
}

export interface LeaveCalendarSummary {
  totalEmployees: number;
  onLeaveToday: number;
  onLeavePercent: number;
  pendingApproval: number;
  approvedMtd: number;
  rejectedMtd: number;
  upcomingLeaves: number;
}
