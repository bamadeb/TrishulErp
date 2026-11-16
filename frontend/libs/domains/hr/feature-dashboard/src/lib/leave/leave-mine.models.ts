export type MineLeaveStatus = 'Pending' | 'Approved' | 'Rejected' | 'Cancelled';
export type MineDayPart = 'Full day' | 'First half' | 'Second half';

/** Row shape used by the existing My Leave table and dialog. */
export interface MineLeaveRequest {
  id: string;
  requestId: number;
  leaveTypeId: number;
  leaveType: string;
  from: string;
  to: string;
  days: number;
  reason: string;
  status: MineLeaveStatus;
  part: MineDayPart;
  contact: string;
  fileName: string | null;
}
