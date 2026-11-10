import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import {
  FormArray,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatButtonToggle, MatButtonToggleGroup } from '@angular/material/button-toggle';
import { MatError, MatFormField, MatHint, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { RouterLink } from '@angular/router';
import { EMPTY, Observable, catchError, finalize, from, of, switchMap, tap } from 'rxjs';
import { LookupValueOut } from '@trishul/core-api';
import { DocumentPanel } from '@trishul/core-documents';
import {
  CallVisit,
  SERVICE_REPORT_ENTITY,
  ServiceCallApi,
  ServiceReportApi,
  ServiceReportOut,
  ServiceReportSubmit,
} from '@trishul/service-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { SignaturePad } from './signature-pad';

type NextAction = ServiceReportSubmit['nextAction'];

const NEXT_ACTIONS: { value: NextAction; label: string; hint: string }[] = [
  { value: 'None', label: 'Work done', hint: 'The machine is fixed; nothing more to do.' },
  { value: 'Parts required', label: 'Parts required', hint: 'The call waits for parts.' },
  { value: 'Revisit', label: 'Revisit needed', hint: 'Plan another visit on a date.' },
  { value: 'Escalate', label: 'Escalate', hint: 'Needs a specialist; the team lead is told.' },
];

const VISIT_SEVERITY: Record<CallVisit['status'], StatusSeverity> = {
  Planned: 'neutral',
  'On the way': 'warn',
  'On site': 'warn',
  Completed: 'success',
  Cancelled: 'contrast',
};

/**
 * The inspection and service report of one visit (/service/calls/:callId/visits/:visitId/report).
 * Order of the work: arrive (the trip ends), inspect with the checklist, repair, record what was found and
 * done, get the customer's sign-off, then submit: that closes the visit and moves the call on.
 */
@Component({
  selector: 'trishul-service-report-page',
  imports: [
    DatePipe,
    RouterLink,
    ReactiveFormsModule,
    MatButton,
    MatButtonToggle,
    MatButtonToggleGroup,
    MatError,
    MatFormField,
    MatHint,
    MatLabel,
    MatIcon,
    MatInput,
    MatProgressBar,
    MatSelect,
    MatOption,
    PageHeader,
    StatusBadge,
    DocumentPanel,
    SignaturePad,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './service-report.page.html',
  styleUrl: './service-report.page.scss',
})
export class ServiceReportPage {
  private readonly api = inject(ServiceReportApi);
  private readonly calls = inject(ServiceCallApi);
  private readonly snackBar = inject(MatSnackBar);

  readonly callId = input<string>();
  readonly visitId = input<string>();

  protected readonly entityType = SERVICE_REPORT_ENTITY;
  protected readonly nextActions = NEXT_ACTIONS;
  protected readonly visitSeverity = VISIT_SEVERITY;
  protected readonly reportSeverity: Record<string, StatusSeverity> = { Draft: 'warn', Submitted: 'success' };
  protected readonly loading = signal(true);
  protected readonly saving = signal(false);
  protected readonly visit = signal<CallVisit | null>(null);
  protected readonly report = signal<ServiceReportOut | null>(null);
  protected readonly conditions = signal<LookupValueOut[]>([]);
  protected readonly failureCodes = signal<LookupValueOut[]>([]);
  protected readonly editable = computed(() => this.report()?.canEdit ?? false);
  protected readonly pad = viewChild(SignaturePad);

  protected readonly form = new FormGroup({
    hmrReading: new FormControl<number | null>(null, [Validators.min(0)]),
    machineConditionLookupId: new FormControl<number | null>(null),
    complaintObserved: new FormControl('', { nonNullable: true, validators: Validators.maxLength(1000) }),
    findings: new FormControl('', { nonNullable: true, validators: Validators.maxLength(2000) }),
    failureCodeLookupId: new FormControl<number | null>(null),
    actionTaken: new FormControl('', { nonNullable: true, validators: Validators.maxLength(2000) }),
    labourHours: new FormControl<number | null>(null, [Validators.min(0), Validators.max(999)]),
    recommendations: new FormControl('', { nonNullable: true, validators: Validators.maxLength(1000) }),
    customerSignedName: new FormControl('', { nonNullable: true, validators: Validators.maxLength(100) }),
    customerSignedMobile: new FormControl('', {
      nonNullable: true,
      validators: Validators.pattern(/^(\+91)?[6-9]\d{9}$|^$/),
    }),
    checklist: new FormArray<
      FormGroup<{
        id: FormControl<number>;
        isOk: FormControl<boolean | null>;
        responseValue: FormControl<string>;
        remarks: FormControl<string>;
      }>
    >([]),
  });

  protected readonly finish = new FormGroup({
    nextAction: new FormControl<NextAction>('None', { nonNullable: true }),
    nextVisitDate: new FormControl<string>('', { nonNullable: true }),
    customerUnavailableReason: new FormControl('', { nonNullable: true, validators: Validators.maxLength(300) }),
  });

  protected readonly today = new Date().toISOString().slice(0, 10);

  constructor() {
    this.calls.lookups('MACHINE_CONDITION').subscribe((v) => this.conditions.set(v));
    this.calls.lookups('FAILURE_CODE').subscribe((v) => this.failureCodes.set(v));
    effect(() => {
      const call = this.callId();
      const visit = this.visitId();
      untracked(() => {
        if (call && visit) this.load(Number(call), Number(visit));
      });
    });
  }

  protected get checklist() {
    return this.form.controls.checklist;
  }

  protected questionOf(index: number): ServiceReportOut['checklist'][number] {
    return this.report()!.checklist[index];
  }

  protected startReport(): void {
    const visit = this.visit();
    if (!visit || this.saving()) return;
    this.saving.set(true);
    this.api
      .start(visit.id)
      .pipe(finalize(() => this.saving.set(false)))
      .subscribe((report) => this.show(report));
  }

  /** Saves the draft, then the signature if one was drawn. */
  protected saveDraft(): void {
    if (this.form.invalid || this.saving()) return;
    this.saving.set(true);
    this.persist()
      .pipe(finalize(() => this.saving.set(false)))
      .subscribe((report) => {
        this.show(report);
        this.snackBar.open('Report saved', 'OK', { duration: 3000 });
      });
  }

  protected submit(): void {
    if (this.form.invalid || this.finish.invalid || this.saving()) return;
    const { nextAction, nextVisitDate, customerUnavailableReason } = this.finish.getRawValue();
    this.saving.set(true);
    this.persist()
      .pipe(
        switchMap((report) =>
          this.api.submit(report.id, report.rowVersion, {
            nextAction,
            nextVisitDate: nextAction === 'Revisit' && nextVisitDate ? nextVisitDate : null,
            customerUnavailableReason: customerUnavailableReason.trim() || null,
          }),
        ),
        finalize(() => this.saving.set(false)),
      )
      .subscribe((report) => {
        this.show(report);
        this.snackBar.open('Report submitted. The visit is closed.', 'OK', { duration: 5000 });
      });
  }

  protected viewSignature(): void {
    const report = this.report();
    if (!report?.customerSignatureDocumentId) return;
    const tab = window.open('', '_blank');
    this.api.signatureImage(report.id).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        if (tab) tab.location.href = url;
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
      },
      error: () => tab?.close(),
    });
  }

  private persist(): Observable<ServiceReportOut> {
    const report = this.report();
    if (!report) return EMPTY;
    const v = this.form.getRawValue();
    return this.api
      .update(report.id, report.rowVersion, {
        hmrReading: v.hmrReading,
        machineConditionLookupId: v.machineConditionLookupId,
        complaintObserved: v.complaintObserved.trim() || null,
        findings: v.findings.trim() || null,
        failureCodeLookupId: v.failureCodeLookupId,
        actionTaken: v.actionTaken.trim() || null,
        labourHours: v.labourHours,
        recommendations: v.recommendations.trim() || null,
        customerSignedName: v.customerSignedName.trim() || null,
        customerSignedMobile: v.customerSignedMobile.trim() || null,
        checklist: v.checklist.map((a) => ({
          id: a.id,
          isOk: a.isOk,
          responseValue: a.responseValue.trim() || null,
          remarks: a.remarks.trim() || null,
        })),
      })
      .pipe(
        switchMap((saved) => {
          const pad = this.pad();
          if (!pad?.hasInk()) return of(saved);
          return from(pad.toPng()).pipe(
            switchMap((png) => (png ? this.api.sign(saved.id, png) : of(saved))),
            tap(() => pad.clear()),
          );
        }),
      );
  }

  private load(callId: number, visitId: number): void {
    this.loading.set(true);
    this.api
      .visits(callId)
      .pipe(
        finalize(() => this.loading.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe((visits) => {
        const visit = visits.find((x) => x.id === visitId) ?? null;
        this.visit.set(visit);
        if (visit?.report) {
          this.api.report(visitId).subscribe((report) => this.show(report));
        }
      });
  }

  private show(report: ServiceReportOut): void {
    this.report.set(report);
    this.form.patchValue(
      {
        hmrReading: report.hmrReading === null ? null : Number(report.hmrReading),
        machineConditionLookupId: report.machineConditionLookupId,
        complaintObserved: report.complaintObserved ?? '',
        findings: report.findings ?? '',
        failureCodeLookupId: report.failureCodeLookupId,
        actionTaken: report.actionTaken ?? '',
        labourHours: report.labourHours === null ? null : Number(report.labourHours),
        recommendations: report.recommendations ?? '',
        customerSignedName: report.customerSignedName ?? '',
        customerSignedMobile: report.customerSignedMobile ?? '',
      },
      { emitEvent: false },
    );
    this.checklist.clear();
    for (const q of report.checklist) {
      this.checklist.push(
        new FormGroup({
          id: new FormControl(q.id, { nonNullable: true }),
          isOk: new FormControl<boolean | null>(q.isOk),
          responseValue: new FormControl(q.responseValue ?? '', { nonNullable: true }),
          remarks: new FormControl(q.remarks ?? '', { nonNullable: true }),
        }),
      );
    }
    if (report.canEdit) this.form.enable({ emitEvent: false });
    else this.form.disable({ emitEvent: false });
    // The visit's own state moved on when the report was submitted.
    const visit = this.visit();
    if (visit) {
      this.visit.set({
        ...visit,
        status: report.visitStatus,
        report: { id: report.id, reportNo: report.reportNo, status: report.status, submittedAt: report.submittedAt },
        canStartReport: false,
      });
    }
  }

  protected progress(): { done: number; total: number } {
    const rows = this.checklist.getRawValue();
    const report = this.report();
    if (!report) return { done: 0, total: 0 };
    return {
      total: rows.length,
      done: rows.filter((r) => r.isOk !== null || !!r.responseValue?.trim()).length,
    };
  }
}
