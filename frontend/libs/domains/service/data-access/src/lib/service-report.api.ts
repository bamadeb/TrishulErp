import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  ApiClient,
  CallVisit,
  ChecklistTemplateInput,
  ChecklistTemplateOut,
  ChecklistTemplateUpdate,
  ServiceReportListItem,
  ServiceReportOut,
  ServiceReportSubmit,
  ServiceReportUpdate,
  createChecklistTemplate,
  getChecklistTemplate,
  getServiceReportSignature,
  getServiceVisitReport,
  listChecklistTemplates,
  listServiceCallReports,
  listServiceReports,
  listServiceCallVisits,
  signServiceReport,
  startServiceReport,
  submitServiceReport,
  updateChecklistTemplate,
  updateServiceReport,
  withRowVersion,
} from '@trishul/core-api';

export type {
  CallVisit,
  ChecklistAnswer,
  ChecklistItemOut,
  ChecklistTemplateInput,
  ChecklistTemplateOut,
  ChecklistTemplateUpdate,
  ReportAttachment,
  ServiceReportListItem,
  ServiceReportOut,
  ServiceReportSubmit,
  ServiceReportUpdate,
} from '@trishul/core-api';

/** Engineers on the call (and the team lead) write the report; the same codes as backend reports/service.py. */
export const SERVICE_REPORT_WRITE_PERMISSIONS = [
  'svc.report.submit',
  'svc.call.assign',
] as const;

/** Inspection checklists: who may open the list, and who may change them. */
export const CHECKLIST_VIEW_PERMISSIONS = [
  'svc.checklist.manage',
  'svc.call.assign',
] as const;
export const CHECKLIST_MANAGE_PERMISSION = 'svc.checklist.manage';

/** The documents module's key for an inspection checklist (reference files). */
export const CHECKLIST_ENTITY = 'svc.checklist_template';

/** The documents module's key for a service report (backend: svc.service_report), used for photos. */
export const SERVICE_REPORT_ENTITY = 'svc.service_report';

/** The inspection and service report of each visit of a call, and the checklists they start from. */
@Injectable({ providedIn: 'root' })
export class ServiceReportApi {
  private readonly api = inject(ApiClient);

  /** The visits of a call, each with the state of its report. */
  visits(callId: number): Observable<CallVisit[]> {
    return this.api.call(listServiceCallVisits, { callId });
  }

  /** Every report of a call, in full. */
  reportsOfCall(callId: number): Observable<ServiceReportOut[]> {
    return this.api.call(listServiceCallReports, { callId });
  }

  /** Search the reports by report no, call no or customer. */
  searchReports(search?: string, status?: 'Draft' | 'Submitted'): Observable<ServiceReportListItem[]> {
    return this.api.call(listServiceReports, { search: search?.trim() || undefined, status });
  }

  report(visitId: number): Observable<ServiceReportOut> {
    return this.api.call(getServiceVisitReport, { visitId });
  }

  /** Opens the report of a visit (the engineer is on site); the matching checklist is copied into it. */
  start(visitId: number): Observable<ServiceReportOut> {
    return this.api.call(startServiceReport, { visitId });
  }

  update(
    reportId: number,
    rowVersion: string,
    body: ServiceReportUpdate,
  ): Observable<ServiceReportOut> {
    return this.api.call(
      updateServiceReport,
      { reportId, body },
      withRowVersion(rowVersion),
    );
  }

  /** Closes the visit and moves the call on (done, parts required, revisit, escalate). */
  submit(
    reportId: number,
    rowVersion: string,
    body: ServiceReportSubmit,
  ): Observable<ServiceReportOut> {
    return this.api.call(
      submitServiceReport,
      { reportId, body },
      withRowVersion(rowVersion),
    );
  }

  /** The customer's signature, drawn on screen, as a PNG. */
  sign(reportId: number, png: Blob): Observable<ServiceReportOut> {
    // The generated body types the file as string (OpenAPI binary); at runtime it is sent as the Blob.
    const file = new File([png], 'signature.png', { type: 'image/png' });
    return this.api.call(signServiceReport, {
      reportId,
      body: { file: file as unknown as string },
    });
  }

  /** The customer's signature image. */
  signatureImage(reportId: number): Observable<Blob> {
    return this.api.call(getServiceReportSignature, { reportId }) as Observable<Blob>;
  }

  templates(includeInactive = false): Observable<ChecklistTemplateOut[]> {
    return this.api.call(listChecklistTemplates, { includeInactive });
  }

  template(templateId: number): Observable<ChecklistTemplateOut> {
    return this.api.call(getChecklistTemplate, { templateId });
  }

  createTemplate(
    body: ChecklistTemplateInput,
  ): Observable<ChecklistTemplateOut> {
    return this.api.call(createChecklistTemplate, { body });
  }

  updateTemplate(
    templateId: number,
    rowVersion: string,
    body: ChecklistTemplateUpdate,
  ): Observable<ChecklistTemplateOut> {
    return this.api.call(
      updateChecklistTemplate,
      { templateId, body },
      withRowVersion(rowVersion),
    );
  }
}
