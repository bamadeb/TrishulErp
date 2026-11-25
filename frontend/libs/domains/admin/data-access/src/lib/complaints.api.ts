import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  changeComplaintStatus,
  createComplaint,
  createComplaintIssueType,
  getComplaint,
  getComplaintAccess,
  listComplaintDepartments,
  listComplaintIssueTypes,
  listComplaints,
  listMyComplaints,
  updateComplaintIssueType,
  withRowVersion,
} from '@trishul/core-api';
import {
  ComplaintAccessOut,
  ComplaintCreate,
  ComplaintDepartmentOption,
  ComplaintDetail,
  ComplaintIssueTypeCreate,
  ComplaintIssueTypeItem,
  ComplaintIssueTypeUpdate,
  ComplaintQuery,
  ComplaintStatusChange,
  MyComplaintQuery,
  PageComplaintListItem,
} from './complaints.models';

/** /core/complaints and friends, through ApiClient and the generated functions. */
@Injectable({ providedIn: 'root' })
export class ComplaintsApi {
  private readonly api = inject(ApiClient);

  access(): Observable<ComplaintAccessOut> {
    return this.api.call(getComplaintAccess);
  }

  departments(): Observable<ComplaintDepartmentOption[]> {
    return this.api.call(listComplaintDepartments);
  }

  create(body: ComplaintCreate): Observable<ComplaintDetail> {
    return this.api.call(createComplaint, { body });
  }

  mine(query: MyComplaintQuery): Observable<PageComplaintListItem> {
    return this.api.call(listMyComplaints, query);
  }

  /** The departments the user leads; all of them for a Super Admin. */
  list(query: ComplaintQuery): Observable<PageComplaintListItem> {
    return this.api.call(listComplaints, query);
  }

  get(complaintId: number): Observable<ComplaintDetail> {
    return this.api.call(getComplaint, { complaintId });
  }

  /** A new status, a note, or both. rowVersion from the loaded complaint; a newer change gives 409. */
  changeStatus(
    complaintId: number,
    body: ComplaintStatusChange,
  ): Observable<ComplaintDetail> {
    return this.api.call(changeComplaintStatus, { complaintId, body });
  }

  issueTypes(
    departmentId?: number,
    status: 'active' | 'inactive' | 'all' = 'all',
  ): Observable<ComplaintIssueTypeItem[]> {
    return this.api.call(listComplaintIssueTypes, { departmentId, status });
  }

  createIssueType(
    body: ComplaintIssueTypeCreate,
  ): Observable<ComplaintIssueTypeItem> {
    return this.api.call(createComplaintIssueType, { body });
  }

  updateIssueType(
    item: ComplaintIssueTypeItem,
    body: ComplaintIssueTypeUpdate,
  ): Observable<ComplaintIssueTypeItem> {
    return this.api.call(
      updateComplaintIssueType,
      { issueTypeId: item.id, body },
      withRowVersion(item.rowVersion),
    );
  }
}
