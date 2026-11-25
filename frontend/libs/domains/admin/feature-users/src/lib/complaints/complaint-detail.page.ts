import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  effect,
  inject,
  input,
  numberAttribute,
  signal,
  untracked,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatFormField, MatHint, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { RouterLink } from '@angular/router';
import {
  COMPLAINT_ENTITY_TYPE,
  ComplaintDetail,
  ComplaintHistoryItem,
  ComplaintStatus,
  ComplaintsApi,
} from '@trishul/admin-data-access';
import { DocumentPanel } from '@trishul/core-documents';
import { PageHeader, StatusBadge } from '@trishul/shared-ui';
import { COMPLAINT_STATUS_SEVERITY } from './complaint-table';

/**
 * One complaint: what was raised, by whom, its attachments and full history. The department's leaders
 * change the status or add a note here; the person who raised it sees the same history.
 */
@Component({
  selector: 'trishul-complaint-detail-page',
  imports: [
    DatePipe,
    FormsModule,
    RouterLink,
    MatButton,
    MatIcon,
    MatFormField,
    MatLabel,
    MatHint,
    MatInput,
    MatSelect,
    MatOption,
    MatProgressBar,
    PageHeader,
    StatusBadge,
    DocumentPanel,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './complaints.scss',
  styles: `
    .layout {
      display: grid;
      grid-template-columns: minmax(0, 2fr) minmax(18rem, 1fr);
      gap: 1rem;
      align-items: start;
    }
    @media (max-width: 960px) {
      .layout {
        grid-template-columns: minmax(0, 1fr);
      }
    }
    .stack {
      display: grid;
      gap: 1rem;
    }
    dl {
      display: grid;
      grid-template-columns: max-content 1fr;
      gap: 0.4rem 1rem;
      margin: 0;
    }
    dt {
      color: var(--mat-sys-on-surface-variant);
      font: var(--mat-sys-body-small);
      align-self: center;
    }
    dd {
      margin: 0;
      overflow-wrap: anywhere;
    }
    .description {
      white-space: pre-wrap;
      margin: 0;
    }
    .update {
      display: grid;
      gap: 0.75rem;
    }
    .update .buttons {
      display: flex;
      justify-content: flex-end;
    }
    .timeline {
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .timeline li {
      position: relative;
      padding: 0 0 1rem 1.5rem;
      border-left: 2px solid var(--mat-sys-outline-variant);
      margin-left: 0.5rem;
    }
    .timeline li:last-child {
      border-left-color: transparent;
    }
    .timeline li::before {
      content: '';
      position: absolute;
      left: -0.45rem;
      top: 0.15rem;
      width: 0.8rem;
      height: 0.8rem;
      border-radius: 50%;
      background: var(--mat-sys-primary);
    }
    .timeline .what {
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
      align-items: center;
      font-weight: 500;
    }
    .timeline .note {
      margin: 0.35rem 0 0;
      padding: 0.5rem 0.75rem;
      border-radius: var(--mat-sys-corner-small);
      background: var(--mat-sys-surface-container);
      white-space: pre-wrap;
    }
    .head {
      display: flex;
      gap: 0.75rem;
      align-items: center;
    }
  `,
  template: `
    @if (complaint(); as c) {
      <trishul-page-header
        [title]="'Complaint ' + c.complaintNo"
        [subtitle]="c.departmentName + ' · ' + c.issueTypeName"
      >
        <trishul-status-badge [status]="c.status" [severities]="severity" />
        <a mat-button [routerLink]="backLink()">
          <mat-icon>arrow_back</mat-icon> Back
        </a>
      </trishul-page-header>

      <div class="layout">
        <div class="stack">
          <section class="card" aria-label="Complaint">
            <h3>What was raised</h3>
            <p class="description">{{ c.description }}</p>
          </section>

          @if (c.canManage && c.allowedStatuses.length) {
            <section class="card" aria-label="Update the complaint">
              <h3>Update status</h3>
              <form class="update" (ngSubmit)="save()">
                <mat-form-field appearance="outline" subscriptSizing="dynamic">
                  <mat-label>Status</mat-label>
                  <mat-select
                    name="status"
                    [ngModel]="newStatus()"
                    (ngModelChange)="newStatus.set($event)"
                  >
                    <mat-option [value]="c.status"
                      >{{ c.status }} (no change, note only)</mat-option
                    >
                    @for (s of c.allowedStatuses; track s) {
                      <mat-option [value]="s">{{ s }}</mat-option>
                    }
                  </mat-select>
                </mat-form-field>
                <mat-form-field appearance="outline">
                  <mat-label>Note (optional)</mat-label>
                  <textarea
                    matInput
                    name="note"
                    rows="3"
                    maxlength="1000"
                    [ngModel]="note()"
                    (ngModelChange)="note.set($event)"
                  ></textarea>
                  <mat-hint
                    >The person who raised it sees this note in the
                    history.</mat-hint
                  >
                </mat-form-field>
                @if (saving()) {
                  <mat-progress-bar mode="indeterminate" />
                }
                <div class="buttons">
                  <button
                    mat-flat-button
                    type="submit"
                    [disabled]="saving() || !canSave(c)"
                  >
                    <mat-icon>check</mat-icon>
                    {{ newStatus() === c.status ? 'Add note' : 'Save status' }}
                  </button>
                </div>
              </form>
            </section>
          }

          <section class="card" aria-label="Attachments">
            <trishul-document-panel
              title="Attachments"
              [entityType]="entityType"
              [entityId]="c.id"
              [readonly]="!c.canAttach"
            />
          </section>

          <section class="card" aria-label="History">
            <h3>History</h3>
            <ol class="timeline">
              @for (h of historyNewestFirst(c); track h.id) {
                <li>
                  <div class="what">
                    @switch (h.action) {
                      @case ('Raised') {
                        Raised
                      }
                      @case ('Note') {
                        Note added
                      }
                      @default {
                        {{ h.fromStatus }}
                        <mat-icon inline aria-label="to">arrow_forward</mat-icon>
                        <trishul-status-badge
                          [status]="h.toStatus"
                          [severities]="severity"
                        />
                      }
                    }
                  </div>
                  <div class="muted">
                    {{ h.changedByName }} ·
                    {{ h.changedAt | date: 'dd MMM yyyy, hh:mm a' }}
                  </div>
                  @if (h.note) {
                    <p class="note">{{ h.note }}</p>
                  }
                </li>
              }
            </ol>
          </section>
        </div>

        <div class="stack">
          <section class="card" aria-label="Details">
            <h3>Details</h3>
            <dl>
              <dt>Complaint ID</dt>
              <dd>{{ c.complaintNo }}</dd>
              <dt>Department</dt>
              <dd>{{ c.departmentName }}</dd>
              <dt>Issue type</dt>
              <dd>{{ c.issueTypeName }}</dd>
              <dt>Raised</dt>
              <dd>{{ c.raisedAt | date: 'dd MMM yyyy, hh:mm a' }}</dd>
              @if (c.raisedVia) {
                <dt>From</dt>
                <dd>{{ c.raisedVia === 'Web' ? 'Web' : 'Mobile app' }}</dd>
              }
              @if (c.resolvedAt) {
                <dt>Resolved</dt>
                <dd>{{ c.resolvedAt | date: 'dd MMM yyyy, hh:mm a' }}</dd>
              }
              @if (c.closedAt) {
                <dt>Closed</dt>
                <dd>{{ c.closedAt | date: 'dd MMM yyyy, hh:mm a' }}</dd>
              }
            </dl>
          </section>
          <section class="card" aria-label="Raised by">
            <h3>Raised by</h3>
            <dl>
              <dt>Name</dt>
              <dd>{{ c.raisedBy.name }}</dd>
              @if (c.raisedBy.employeeCode) {
                <dt>Employee</dt>
                <dd>{{ c.raisedBy.employeeCode }}</dd>
              }
              @if (c.raisedBy.designationName) {
                <dt>Designation</dt>
                <dd>{{ c.raisedBy.designationName }}</dd>
              }
              @if (c.raisedBy.departmentName) {
                <dt>Department</dt>
                <dd>{{ c.raisedBy.departmentName }}</dd>
              }
              @if (c.raisedBy.branchName) {
                <dt>Branch</dt>
                <dd>{{ c.raisedBy.branchName }}</dd>
              }
              @if (c.raisedBy.mobile) {
                <dt>Mobile</dt>
                <dd>
                  <a [href]="'tel:' + c.raisedBy.mobile">{{
                    c.raisedBy.mobile
                  }}</a>
                </dd>
              }
              @if (c.raisedBy.email) {
                <dt>Email</dt>
                <dd>
                  <a [href]="'mailto:' + c.raisedBy.email">{{
                    c.raisedBy.email
                  }}</a>
                </dd>
              }
            </dl>
          </section>
        </div>
      </div>
    } @else if (failed()) {
      <p class="error" role="alert">
        This complaint could not be opened. It may not exist, or you may not
        have access to it.
        <a mat-button routerLink="/complaints/mine">My complaints</a>
      </p>
    } @else {
      <mat-progress-bar mode="indeterminate" />
    }
  `,
})
export class ComplaintDetailPage {
  /** From the route, /complaints/:complaintId. */
  readonly complaintId = input.required({ transform: numberAttribute });

  private readonly api = inject(ComplaintsApi);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly entityType = COMPLAINT_ENTITY_TYPE;
  protected readonly severity = COMPLAINT_STATUS_SEVERITY;
  protected readonly complaint = signal<ComplaintDetail | null>(null);
  protected readonly failed = signal(false);
  protected readonly saving = signal(false);
  protected readonly newStatus = signal<ComplaintStatus>('Open');
  protected readonly note = signal('');

  constructor() {
    // Reload when the route moves to another complaint (e.g. from an alert) without leaving the page.
    effect(() => {
      const id = this.complaintId();
      untracked(() => {
        this.complaint.set(null);
        this.failed.set(false);
        this.load(id);
      });
    });
  }

  protected backLink(): string {
    return this.complaint()?.canManage
      ? '/complaints/department'
      : '/complaints/mine';
  }

  protected historyNewestFirst(c: ComplaintDetail): ComplaintHistoryItem[] {
    return [...c.history].reverse();
  }

  protected canSave(c: ComplaintDetail): boolean {
    return this.newStatus() !== c.status || this.note().trim().length > 0;
  }

  private load(id = this.complaintId()): void {
    this.api
      .get(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (c) => this.show(c),
        error: () => this.failed.set(true),
      });
  }

  private show(c: ComplaintDetail): void {
    this.complaint.set(c);
    this.newStatus.set(c.allowedStatuses[0] ?? c.status);
    this.note.set('');
  }

  protected save(): void {
    const c = this.complaint();
    if (!c || !this.canSave(c)) return;
    this.saving.set(true);
    const note = this.note().trim();
    this.api
      .changeStatus(c.id, {
        status: this.newStatus(),
        note: note || null,
        rowVersion: c.rowVersion,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (updated) => {
          this.saving.set(false);
          this.snackBar.open(
            updated.status === c.status
              ? 'Note added.'
              : `Status changed to ${updated.status}.`,
            'OK',
            { duration: 3000 },
          );
          this.show(updated);
        },
        error: () => {
          // 409: someone else updated it meanwhile; show the latest.
          this.saving.set(false);
          this.load();
        },
      });
  }
}
