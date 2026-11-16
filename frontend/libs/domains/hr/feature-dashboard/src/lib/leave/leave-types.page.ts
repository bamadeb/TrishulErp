import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HasPermission } from '@trishul/core-auth';
import { LEAVE_MANAGE_PERMISSION, LeaveApi, LeaveTypeItem, LeaveTypeWrite } from '@trishul/hr-data-access';
import { PageHeader } from '@trishul/shared-ui';

@Component({
  selector: 'trishul-leave-types-page',
  imports: [FormsModule, HasPermission, MatButton, MatCheckbox, MatFormField, MatIcon, MatIconButton, MatInput, MatLabel, PageHeader],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './leave-types.page.html',
  styleUrl: './leave-master.scss',
})
export class LeaveTypesPage {
  private readonly api = inject(LeaveApi);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly manage = LEAVE_MANAGE_PERMISSION;
  protected readonly rows = signal<LeaveTypeItem[]>([]);
  protected readonly error = signal('');
  protected readonly editing = signal<LeaveTypeItem | null>(null);
  protected readonly form = signal<LeaveTypeWrite>(blank());

  constructor() {
    this.reload();
  }

  protected edit(row: LeaveTypeItem): void {
    this.editing.set(row);
    this.form.set({
      code: row.code,
      name: row.name,
      description: row.description,
      annualQuota: row.annualQuota,
      carryForwardMax: row.carryForwardMax,
      isPaid: row.isPaid,
      isEncashable: row.isEncashable,
      accrualApplicable: row.accrualApplicable,
      halfDayAllowed: row.halfDayAllowed,
      attachmentRequired: row.attachmentRequired,
      maxConsecutiveDays: row.maxConsecutiveDays,
      isActive: row.isActive,
    });
  }

  protected reset(): void {
    this.editing.set(null);
    this.form.set(blank());
    this.error.set('');
  }

  protected patch(change: Partial<LeaveTypeWrite>): void {
    this.form.update((current) => ({ ...current, ...change }));
  }

  protected save(): void {
    const body = this.form();
    const current = this.editing();
    const request = current
      ? this.api.updateType(current.id, current.rowVersion, body)
      : this.api.createType(body);
    request.subscribe({
      next: () => {
        this.snackBar.open(current ? 'Leave type saved.' : 'Leave type added.', 'OK', { duration: 3000 });
        this.reset();
        this.reload();
      },
      error: (error: { error?: { detail?: string } }) => {
        const detail = error.error?.detail;
        this.error.set(typeof detail === 'string' && detail ? detail : 'The leave type could not be saved.');
      },
    });
  }

  private reload(): void {
    this.api.types().subscribe({
      next: (page) => this.rows.set(page.items),
      error: () => this.error.set('Leave types could not be loaded.'),
    });
  }
}

function blank(): LeaveTypeWrite {
  return {
    code: '',
    name: '',
    description: '',
    annualQuota: null,
    carryForwardMax: null,
    isPaid: true,
    isEncashable: false,
    accrualApplicable: false,
    halfDayAllowed: true,
    attachmentRequired: false,
    maxConsecutiveDays: null,
    isActive: true,
  };
}
