import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, DestroyRef, inject, Injectable, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { DateAdapter, MAT_DATE_FORMATS, MAT_NATIVE_DATE_FORMATS, NativeDateAdapter } from '@angular/material/core';
import { MatDatepickerToggle, MatDateRangeInput, MatDateRangePicker, MatEndDate, MatStartDate } from '@angular/material/datepicker';
import { MatDialog, MatDialogActions, MatDialogClose, MatDialogContent, MatDialogRef, MatDialogTitle } from '@angular/material/dialog';
import { MatFormField, MatLabel, MatPrefix, MatSuffix } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatDrawer, MatDrawerContainer, MatDrawerContent } from '@angular/material/sidenav';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltip } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import {
  LeaveApi,
  LeaveOption,
  LeaveRequestDetail,
  LeaveRequestFilterQuery,
  LeaveRequestRow,
} from '@trishul/hr-data-access';
import { confirmAction, PageHeader, StatusBadge } from '@trishul/shared-ui';

const REQUEST_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const REQUEST_DATE_FORMATS = {
  ...MAT_NATIVE_DATE_FORMATS,
  parse: { ...MAT_NATIVE_DATE_FORMATS.parse, dateInput: 'DD-MMM-YYYY' },
  display: { ...MAT_NATIVE_DATE_FORMATS.display, dateInput: { day: '2-digit', month: 'short', year: 'numeric' } },
};
const AVATAR_COLORS = ['#7C4DFF', '#2E7D32', '#EF6C00', '#C2185B', '#1565C0', '#00838F', '#6A1B9A', '#455A64'];

type RequestStatus = 'Pending' | 'Approved' | 'Rejected' | 'All';

interface RequestView {
  requestId: number;
  id: string;
  employee: {
    code: string;
    name: string;
    initials: string;
    department: string;
    designation: string;
    manager: string;
    color: string;
  };
  leaveType: string;
  leaveCode: string;
  fromDate: string;
  toDate: string;
  days: number;
  reason: string;
  appliedOn: string;
  status: string;
  balance: number | null;
  canApprove: boolean;
  attachments: { id: string; name: string }[];
  history: { id: string; action: string; actor: string; at: string; remarks: string }[];
  comments: string[];
}

@Injectable()
class RequestDateAdapter extends NativeDateAdapter {
  override format(date: Date, displayFormat: object): string {
    if (displayFormat === REQUEST_DATE_FORMATS.display.dateInput) {
      return `${String(date.getDate()).padStart(2, '0')}-${REQUEST_MONTHS[date.getMonth()]}-${date.getFullYear()}`;
    }
    return super.format(date, displayFormat);
  }
}

@Component({
  selector: 'trishul-leave-reject-dialog',
  imports: [FormsModule, MatButton, MatDialogActions, MatDialogClose, MatDialogContent, MatDialogTitle, MatFormField, MatInput, MatLabel],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Reject leave</h2>
    <mat-dialog-content>
      <p>Remarks are required. The leave balance is not changed.</p>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Remarks</mat-label>
        <textarea matInput rows="3" [ngModel]="remarks" (ngModelChange)="remarks = $event"></textarea>
      </mat-form-field>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" [mat-dialog-close]="undefined">Cancel</button>
      <button mat-flat-button type="button" color="warn" [disabled]="remarks.trim().length < 3" (click)="close()">Reject</button>
    </mat-dialog-actions>
  `,
})
class LeaveRejectDialog {
  private readonly ref = inject(MatDialogRef<LeaveRejectDialog, string>);
  protected remarks = '';

  protected close(): void {
    this.ref.close(this.remarks.trim());
  }
}

@Component({
  selector: 'trishul-leave-requests-page',
  imports: [
    FormsModule, MatButton, MatCheckbox, MatDateRangeInput, MatDateRangePicker, MatDatepickerToggle,
    MatDrawer, MatDrawerContainer, MatDrawerContent, MatEndDate, MatFormField, MatIcon, MatIconButton, MatInput,
    MatLabel, MatMenu, MatMenuItem, MatMenuTrigger, MatOption, MatPrefix, MatSelect, MatStartDate, MatSuffix,
    MatTooltip, PageHeader, RouterLink, StatusBadge,
  ],
  providers: [
    { provide: DateAdapter, useClass: RequestDateAdapter },
    { provide: MAT_DATE_FORMATS, useValue: REQUEST_DATE_FORMATS },
    DatePipe,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './leave-requests.page.html',
  styleUrl: './leave-requests.page.scss',
})
export class LeaveRequestsPage {
  private readonly api = inject(LeaveApi);
  private readonly dialog = inject(MatDialog);
  private readonly snack = inject(MatSnackBar);
  private readonly dates = inject(DatePipe);
  private readonly drawer = viewChild.required<MatDrawer>('drawer');
  private readonly destroyRef = inject(DestroyRef);
  private loadToken = 0;

  protected readonly months = monthChoices();
  protected readonly severities = { Pending: 'warn', Approved: 'success', Rejected: 'danger' } as const;
  protected readonly pageSize = 5;

  protected readonly rows = signal<RequestView[]>([]);
  protected readonly total = signal(0);
  protected readonly counts = signal({ pending: 0, approved: 0, rejected: 0, total: 0 });
  protected readonly departments = signal<LeaveOption[]>([]);
  protected readonly leaveTypes = signal<LeaveOption[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal('');
  protected readonly tab = signal<RequestStatus>('Pending');
  protected readonly department = signal<number | null>(null);
  protected readonly leaveType = signal<number | null>(null);
  protected readonly search = signal('');
  protected readonly month = signal(currentMonth());
  protected readonly rangeStart = signal<Date | null>(monthStart(currentMonth()));
  protected readonly rangeEnd = signal<Date | null>(monthEnd(currentMonth()));
  protected readonly pageIndex = signal(0);
  protected readonly selected = signal<number[]>([]);
  protected readonly openRequest = signal<RequestView | null>(null);
  protected readonly commentDraft = signal('');

  protected readonly pageCount = computed(() => Math.max(1, Math.ceil(this.total() / this.pageSize)));
  protected readonly pageRows = computed(() => this.rows());
  protected readonly pageNumbers = computed(() => {
    const count = Math.ceil(this.total() / this.pageSize);
    const current = this.pageIndex();
    const start = Math.max(0, Math.min(current - 2, count - 5));
    return Array.from({ length: Math.min(5, count) }, (_, index) => start + index);
  });
  protected readonly pageAllSelected = computed(() => {
    const page = this.pageRows();
    return page.length > 0 && page.every((row) => this.selected().includes(row.requestId));
  });
  protected readonly pagePartSelected = computed(() => {
    const page = this.pageRows();
    const count = page.filter((row) => this.selected().includes(row.requestId)).length;
    return count > 0 && count < page.length;
  });

  constructor() {
    this.reload();
    this.destroyRef.onDestroy(() => this.loadToken++);
  }

  protected setTab(tab: RequestStatus): void {
    this.tab.set(tab);
    this.pageIndex.set(0);
    this.selected.set([]);
    this.reload();
  }

  protected setDepartment(value: number | null): void {
    this.department.set(value);
    this.pageIndex.set(0);
    this.reload();
  }

  protected setLeaveType(value: number | null): void {
    this.leaveType.set(value);
    this.pageIndex.set(0);
    this.reload();
  }

  protected setSearch(value: string): void {
    this.search.set(value);
    this.pageIndex.set(0);
    this.reload();
  }

  protected setMonth(value: string): void {
    this.month.set(value);
    this.rangeStart.set(monthStart(value));
    this.rangeEnd.set(monthEnd(value));
    this.pageIndex.set(0);
    this.reload();
  }

  protected setRangeStart(value: Date | null): void {
    this.rangeStart.set(value);
    this.pageIndex.set(0);
    this.reload();
  }

  protected setRangeEnd(value: Date | null): void {
    this.rangeEnd.set(value);
    this.pageIndex.set(0);
    this.reload();
  }

  protected reset(): void {
    const month = currentMonth();
    this.department.set(null);
    this.leaveType.set(null);
    this.search.set('');
    this.month.set(month);
    this.rangeStart.set(monthStart(month));
    this.rangeEnd.set(monthEnd(month));
    this.tab.set('Pending');
    this.pageIndex.set(0);
    this.selected.set([]);
    this.reload();
  }

  protected togglePage(checked: boolean): void {
    const pageIds = this.pageRows().map((row) => row.requestId);
    this.selected.update((ids) => (checked ? [...new Set([...ids, ...pageIds])] : ids.filter((id) => !pageIds.includes(id))));
  }

  protected toggleRow(id: number, checked: boolean): void {
    this.selected.update((ids) => (checked ? [...ids, id] : ids.filter((item) => item !== id)));
  }

  protected isSelected(id: number): boolean {
    return this.selected().includes(id);
  }

  protected view(row: RequestView): void {
    this.commentDraft.set('');
    this.drawer().open();
    this.api.leaveRequest(row.requestId).subscribe({
      next: (detail) => this.openRequest.set(toView(detail)),
      error: (error: unknown) => this.snack.open(problemDetail(error, 'The leave request could not be opened.'), 'Dismiss', { duration: 3000 }),
    });
  }

  protected closeDrawer(): void {
    this.drawer().close();
  }

  protected decide(ids: number[], status: 'Approved' | 'Rejected'): void {
    const pending = this.rows().filter((row) => ids.includes(row.requestId) && row.canApprove);
    if (!pending.length) {
      this.snack.open('Only pending requests you can decide are updated.', 'Dismiss', { duration: 2500 });
      return;
    }
    if (status === 'Rejected') {
      this.dialog.open<LeaveRejectDialog, void, string>(LeaveRejectDialog, { width: '28rem' }).afterClosed().subscribe((remarks) => {
        if (!remarks) return;
        this.commit(pending.map((row) => row.requestId), 'Rejected', remarks);
      });
      return;
    }
    const label = pending.length === 1 ? pending[0].id : `${pending.length} requests`;
    confirmAction(this.dialog, {
      title: 'Approve leave',
      message: `Approve ${label}? The leave balance is deducted when approval succeeds.`,
      confirmText: 'Approve',
    }).subscribe((confirmed) => {
      if (confirmed) this.commit(pending.map((row) => row.requestId), 'Approved');
    });
  }

  protected addComment(): void {
    const text = this.commentDraft().trim();
    const request = this.openRequest();
    if (!text || !request) return;
    this.api.commentLeaveRequest(request.requestId, text).subscribe({
      next: (detail) => {
        this.openRequest.set(toView(detail));
        this.commentDraft.set('');
      },
      error: (error: unknown) => this.snack.open(problemDetail(error, 'The comment could not be saved.'), 'Dismiss', { duration: 3000 }),
    });
  }

  protected preview(_name?: string): void {
    this.snack.open('This request has no stored attachment.', 'Dismiss', { duration: 2500 });
  }

  protected copyId(id: string): void {
    void navigator.clipboard?.writeText(id);
    this.snack.open(`${id} copied.`, 'Dismiss', { duration: 2000 });
  }

  protected exportRows(): void {
    const query = { ...this.filters(), status: this.statusFilter(), page: 1, pageSize: 200 };
    this.api.leaveRequests(query).subscribe({
      next: (page) => download(page.items.map(toView)),
      error: (error: unknown) => this.snack.open(problemDetail(error, 'The list could not be exported.'), 'Dismiss', { duration: 3000 }),
    });
  }

  protected showing(): string {
    const total = this.total();
    if (!total) return 'Showing 0 requests';
    const start = this.pageIndex() * this.pageSize + 1;
    const end = Math.min(total, start + this.pageSize - 1);
    return `Showing ${start} – ${end} of ${total} requests`;
  }

  protected when(value: string): string {
    return this.dates.transform(value, 'dd-MMM-yyyy') ?? value;
  }

  protected goTo(page: number): void {
    this.pageIndex.set(Math.min(Math.max(page, 0), this.pageCount() - 1));
    this.reload();
  }

  private reload(): void {
    const token = ++this.loadToken;
    this.loading.set(true);
    this.error.set('');
    const filters = this.filters();
    forkJoin({
      summary: this.api.leaveRequestSummary(filters),
      page: this.api.leaveRequests({
        ...filters,
        status: this.statusFilter(),
        page: this.pageIndex() + 1,
        pageSize: this.pageSize,
      }),
    }).subscribe({
      next: (result) => {
        if (token !== this.loadToken) return;
        this.counts.set({
          pending: result.summary.pending,
          approved: result.summary.approved,
          rejected: result.summary.rejected,
          total: result.summary.total,
        });
        this.departments.set(result.summary.departments);
        this.leaveTypes.set(result.summary.leaveTypes);
        this.rows.set(result.page.items.map(toView));
        this.total.set(result.page.total);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        if (token !== this.loadToken) return;
        this.rows.set([]);
        this.total.set(0);
        this.error.set(problemDetail(error, 'Leave requests could not be loaded.'));
        this.loading.set(false);
      },
    });
  }

  private commit(ids: number[], status: 'Approved' | 'Rejected', remarks?: string): void {
    forkJoin(ids.map((id) => (
      status === 'Approved' ? this.api.approveLeaveRequest(id) : this.api.rejectLeaveRequest(id, remarks ?? '')
    ))).subscribe({
      next: () => {
        this.selected.set([]);
        this.snack.open(`${ids.length} request${ids.length === 1 ? '' : 's'} ${status.toLowerCase()}.`, 'Dismiss', { duration: 2500 });
        const open = this.openRequest();
        if (open && ids.includes(open.requestId)) this.view(open);
        this.reload();
      },
      error: (error: unknown) => {
        this.snack.open(problemDetail(error, 'The leave request could not be updated.'), 'Dismiss', { duration: 4000 });
        this.reload();
      },
    });
  }

  private statusFilter(): 'Pending' | 'Approved' | 'Rejected' | undefined {
    const tab = this.tab();
    return tab === 'All' ? undefined : tab;
  }

  private filters(): LeaveRequestFilterQuery {
    return {
      departmentId: this.department(),
      leaveTypeId: this.leaveType(),
      fromDate: this.iso(this.rangeStart()),
      toDate: this.iso(this.rangeEnd()),
      search: this.search().trim() || null,
    };
  }

  private iso(value: Date | null): string | null {
    if (!value || Number.isNaN(value.getTime())) return null;
    return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
  }
}

function toView(row: LeaveRequestRow | LeaveRequestDetail): RequestView {
  const detail = 'history' in row ? row : null;
  return {
    requestId: row.requestId,
    id: row.displayId,
    employee: {
      code: row.employee.code,
      name: row.employee.name,
      initials: initials(row.employee.name),
      department: row.employee.department ?? '—',
      designation: row.employee.designation ?? '—',
      manager: row.employee.manager ?? '—',
      color: colorFor(row.employee.code),
    },
    leaveType: row.leaveType,
    leaveCode: row.leaveCode,
    fromDate: row.fromDate,
    toDate: row.toDate,
    days: Number(row.days),
    reason: row.reason ?? '',
    appliedOn: row.appliedOn,
    status: row.status,
    balance: row.balance == null ? null : Number(row.balance),
    canApprove: row.canApprove,
    attachments: [],
    history: detail?.history.map((item) => ({
      id: String(item.id),
      action: item.action,
      actor: item.actor,
      at: item.at,
      remarks: item.remarks,
    })) ?? [],
    comments: detail?.comments ?? [],
  };
}

function initials(name: string): string {
  const parts = name.split(' ').filter(Boolean);
  return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase();
}

function colorFor(code: string): string {
  const total = [...code].reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return AVATAR_COLORS[total % AVATAR_COLORS.length];
}

function currentMonth(): string {
  const today = new Date();
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;
}

function monthChoices(): { id: string; label: string }[] {
  const start = new Date(2026, 0, 1);
  return Array.from({ length: 24 }, (_, index) => {
    const date = new Date(start.getFullYear(), start.getMonth() + index, 1);
    const id = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
    return { id, label: date.toLocaleString('en-GB', { month: 'long', year: 'numeric' }) };
  });
}

function monthStart(value: string): Date {
  const [year, month] = value.split('-').map(Number);
  return new Date(year, month - 1, 1);
}

function monthEnd(value: string): Date {
  const [year, month] = value.split('-').map(Number);
  return new Date(year, month, 0);
}

function download(rows: RequestView[]): void {
  const header = ['Request ID', 'Employee', 'Employee ID', 'Department', 'Leave Type', 'From', 'To', 'Days', 'Reason', 'Applied On', 'Status'];
  const lines = rows.map((row) => [
    row.id, row.employee.name, row.employee.code, row.employee.department, row.leaveType,
    row.fromDate, row.toDate, String(row.days), row.reason, row.appliedOn, row.status,
  ].map((value) => `"${value.replaceAll('"', '""')}"`).join(','));
  const blob = new Blob([[header.join(','), ...lines].join('\n')], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'leave-requests.csv';
  link.click();
  URL.revokeObjectURL(url);
}

function problemDetail(error: unknown, fallback: string): string {
  const detail = (error as { error?: { detail?: string } }).error?.detail;
  return typeof detail === 'string' && detail ? detail : fallback;
}
