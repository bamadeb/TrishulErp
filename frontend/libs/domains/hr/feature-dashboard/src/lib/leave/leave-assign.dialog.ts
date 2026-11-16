import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatDatepicker, MatDatepickerInput, MatDatepickerToggle } from '@angular/material/datepicker';
import { MAT_DIALOG_DATA, MatDialog, MatDialogActions, MatDialogContent, MatDialogRef, MatDialogTitle } from '@angular/material/dialog';
import { MatFormField, MatLabel, MatSuffix } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { AuthStore } from '@trishul/core-auth';
import { EmployeeListItem, EmployeesApi, LeaveApi, LeaveAssignmentItem, LeavePolicyItem } from '@trishul/hr-data-access';
import { confirmAction } from '@trishul/shared-ui';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

export interface LeaveAssignDialogData {
  policy: LeavePolicyItem;
  mode: 'assign' | 'assigned' | 'history';
}

@Component({
  selector: 'trishul-leave-assign-dialog',
  imports: [
    FormsModule, MatButton, MatCheckbox, MatDatepicker, MatDatepickerInput, MatDatepickerToggle,
    MatDialogActions, MatDialogContent, MatDialogTitle, MatFormField, MatInput, MatLabel, MatOption, MatSelect, MatSuffix,
  ],
  providers: [provideNativeDateAdapter()],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './leave-assign.dialog.html',
  styleUrl: './leave-assign.dialog.scss',
})
export class LeaveAssignDialog {
  private readonly api = inject(LeaveApi);
  private readonly employees = inject(EmployeesApi);
  private readonly dialog = inject(MatDialog);
  private readonly dialogRef = inject(MatDialogRef<LeaveAssignDialog, boolean>);
  private readonly auth = inject(AuthStore);
  protected readonly data = inject<LeaveAssignDialogData>(MAT_DIALOG_DATA);
  protected readonly available = signal<EmployeeListItem[]>([]);
  protected readonly assigned = signal<LeaveAssignmentItem[]>([]);
  protected readonly selected = signal<number[]>([]);
  protected readonly error = signal('');
  protected readonly search = signal('');
  protected readonly departmentId = signal('');
  protected readonly designationId = signal('');
  protected readonly branchId = signal('');
  protected readonly employeeType = signal('');
  protected readonly employmentStatus = signal('');
  protected readonly effectiveFrom = signal(this.data.policy.effectiveFrom);
  protected readonly departments = toSignal(this.employees.departments(), { initialValue: [] });
  protected readonly designations = toSignal(this.employees.designations(), { initialValue: [] });
  protected readonly branches = this.auth.user()?.branches ?? [];

  constructor() {
    this.load();
  }

  protected dateValue(value: string | null | undefined): Date | null {
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value ?? '');
    return match ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3])) : null;
  }

  protected dateText(value: Date | null): string {
    if (!(value instanceof Date) || Number.isNaN(value.getTime())) return '';
    const month = String(value.getMonth() + 1).padStart(2, '0');
    const day = String(value.getDate()).padStart(2, '0');
    return `${value.getFullYear()}-${month}-${day}`;
  }

  protected title(): string {
    if (this.data.mode === 'history') return 'Assignment history';
    return this.data.mode === 'assign' ? 'Assign employees' : 'Assigned employees';
  }

  protected load(): void {
    this.api.assignments(this.data.policy.id).subscribe({
      next: (rows) => {
        this.assigned.set(rows);
        if (this.data.mode === 'assign') this.loadEmployees(new Set(rows.map((row) => row.employeeId)));
      },
      error: () => this.error.set('Assignments could not be loaded.'),
    });
  }

  protected toggle(id: number, checked: boolean): void {
    this.selected.update((current) => checked ? [...current, id] : current.filter((item) => item !== id));
  }

  protected assignSelected(): void {
    this.save(this.selected());
  }

  protected assignAll(): void {
    const ids = this.available().map((row) => row.id);
    confirmAction(this.dialog, {
      title: 'Assign all eligible employees',
      message: `Assign ${ids.length} employees shown for this filter to ${this.data.policy.name}?`,
      confirmText: 'Assign',
    }).subscribe((confirmed) => {
      if (confirmed) this.save(ids);
    });
  }

  protected close(): void {
    this.dialogRef.close(true);
  }

  private loadEmployees(taken: Set<number>): void {
    this.employees.list({
      page: 1,
      pageSize: 100,
      status: this.employmentStatus() === 'Notice' || this.employmentStatus() === 'Exited' ? 'all' : 'active',
      search: this.search().trim() || null,
      departmentId: this.numberOrNull(this.departmentId()),
      designationId: this.numberOrNull(this.designationId()),
      branchId: this.numberOrNull(this.branchId()),
      employeeType: (this.employeeType() || null) as 'Permanent' | 'Contract' | 'Trainee' | 'Consultant' | null,
      lifecycle: this.lifecycle(),
    }).subscribe({
      next: (page) => this.available.set(page.items.filter((row) => !taken.has(row.id))),
      error: () => this.error.set('Employees could not be loaded.'),
    });
  }

  private lifecycle(): 'all' | 'notice' | 'exited' | null {
    if (this.employmentStatus() === 'Notice') return 'notice';
    if (this.employmentStatus() === 'Exited') return 'exited';
    return null;
  }

  private numberOrNull(value: string): number | null {
    return value ? Number(value) : null;
  }

  private save(ids: number[]): void {
    if (ids.length === 0) return;
    forkJoin(ids.map((employeeId) => this.api.assignEmployee(this.data.policy.id, {
      employeeId,
      effectiveFrom: this.effectiveFrom(),
    }).pipe(catchError((error: { error?: { detail?: string } }) => of(error))))).subscribe((results) => {
      const failed = results.find((row) => row && typeof row === 'object' && 'error' in row) as { error?: { detail?: string } } | undefined;
      this.selected.set([]);
      this.load();
      if (failed) this.error.set(this.detail(failed));
    });
  }

  private detail(error: { error?: { detail?: string } }): string {
    const text = error.error?.detail;
    return typeof text === 'string' && text ? text : 'The assignment could not be saved.';
  }
}
