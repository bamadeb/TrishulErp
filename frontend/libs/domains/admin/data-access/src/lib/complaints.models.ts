import {
  ComplaintDetail,
  ListComplaints$Params,
  ListMyComplaints$Params,
} from '@trishul/core-api';

export type {
  ComplaintAccessOut,
  ComplaintCreate,
  ComplaintDepartmentOption,
  ComplaintDepartmentRef,
  ComplaintDetail,
  ComplaintHistoryItem,
  ComplaintIssueTypeCreate,
  ComplaintIssueTypeItem,
  ComplaintIssueTypeOption,
  ComplaintIssueTypeUpdate,
  ComplaintListItem,
  ComplaintRaisedBy,
  ComplaintStatusChange,
  PageComplaintListItem,
} from '@trishul/core-api';

export type ComplaintStatus = ComplaintDetail['status'];
export type ComplaintQuery = ListComplaints$Params;
export type MyComplaintQuery = ListMyComplaints$Params;

/** The workflow, in order. Closed is final. */
export const COMPLAINT_STATUSES: readonly ComplaintStatus[] = [
  'Open',
  'In Progress',
  'On Hold',
  'Resolved',
  'Closed',
];

/** Attachments are documents of the record 'core.complaint' (the shared document service). */
export const COMPLAINT_ENTITY_TYPE = 'core.complaint';

/**
 * Codes the API checks (modules/core/complaints). A department head works the department's complaints
 * without a role permission; /me then reports core.complaint.manage so the menu shows the page.
 */
export const COMPLAINT_RAISE_PERMISSION = 'core.complaint.raise';
export const COMPLAINT_MANAGE_PERMISSIONS = [
  'core.complaint.manage',
  'core.complaint.manage_all',
] as const;
export const COMPLAINT_MANAGE_ALL_PERMISSION = 'core.complaint.manage_all';
