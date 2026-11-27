import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatMenu, MatMenuContent, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { catchError, finalize, of } from 'rxjs';
import { AuthStore, HasPermission } from '@trishul/core-auth';
import {
  BalanceBoard,
  BalanceEmployee,
  EmployeesApi,
  LEAVE_MANAGE_PERMISSION,
  LeaveApi,
  LeavePolicyItem,
} from '@trishul/hr-data-access';
import { PageHeader } from '@trishul/shared-ui';
import { LeaveBalanceDetailDialog } from './leave-balance-detail.dialog';
import { LeaveBalanceGenerateDialog } from './leave-balance-generate.dialog';

@Component({
  selector: 'trishul-leave-balance-page',
  imports: [
    FormsModule, HasPermission, MatButton, MatCheckbox, MatFormField, MatIcon, MatIconButton, MatInput, MatLabel,
    MatMenu, MatMenuContent, MatMenuItem, MatMenuTrigger, MatOption, MatPaginator, MatProgressBar, MatSelect, PageHeader,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './leave-balance.page.html',
  styleUrl: './leave-balance.page.scss',
})
export class LeaveBalancePage {
  private readonly api = inject(LeaveApi);
  private readonly employees = inject(EmployeesApi);
  private readonly dialog = inject(MatDialog);
  private readonly auth = inject(AuthStore);
  protected readonly manage = LEAVE_MANAGE_PERMISSION;
  protected readonly policies = signal<LeavePolicyItem[]>([]);
  protected readonly policyId = signal<number | null>(null);
  protected readonly year = signal(new Date().getFullYear());
  protected readonly departmentId = signal<number | null>(null);
  protected readonly branchId = signal<number | null>(null);
  protected readonly search = signal('');
  protected readonly pageIndex = signal(0);
  protected readonly pageSize = signal(10);
  protected readonly sort = signal('employeeCode');
  protected readonly selected = signal<number[]>([]);
  protected readonly board = signal<BalanceBoard | null>(null);
  protected readonly error = signal('');
  protected readonly loading = signal(true);
  protected readonly departments = toSignal(this.employees.departments().pipe(catchError(() => of([]))), { initialValue: [] });
  protected readonly branches = () => this.auth.user()?.branches ?? [];

  constructor() {
    this.api.policies('all').subscribe({
      next: (page) => {
        this.policies.set(page.items);
        const odisha = page.items.find((row) => row.name === 'TTPL Leave Policy')
          ?? page.items.find((row) => row.name === 'Odisha Private Company Leave Policy');
        const chosen = odisha ?? page.items[0];
        if (chosen) {
          this.policyId.set(chosen.id);
          this.year.set(Number(chosen.effectiveFrom.slice(0, 4)) || this.year());
        }
        this.load();
      },
      error: () => this.load(),
    });
  }

  protected years(): number[] {
    const policy = this.policies().find((row) => row.id === this.policyId());
    const start = policy ? Number(policy.effectiveFrom.slice(0, 4)) : this.year();
    const first = Math.min(start, new Date().getFullYear());
    const last = Math.max(start, new Date().getFullYear());
    return Array.from({ length: last - first + 1 }, (_, index) => first + index);
  }

  protected load(): void {
    const params: Record<string, string> = {
      year: String(this.year()),
      page: String(this.pageIndex() + 1),
      pageSize: String(this.pageSize()),
      sort: this.sort(),
    };
    if (this.policyId() != null) params['policyId'] = String(this.policyId());
    if (this.departmentId() != null) params['departmentId'] = String(this.departmentId());
    if (this.branchId() != null) params['branchId'] = String(this.branchId());
    if (this.search().trim()) params['search'] = this.search().trim();
    this.loading.set(true);
    this.api.balanceBoard(params).pipe(finalize(() => this.loading.set(false))).subscribe({
      next: (board) => {
        this.board.set(board);
        this.error.set('');
      },
      error: () => this.error.set('Leave balances could not be loaded.'),
    });
  }

  protected searchNow(): void {
    this.pageIndex.set(0);
    this.load();
  }

  protected clear(): void {
    const odisha = this.policies().find((row) => row.name === 'TTPL Leave Policy')
      ?? this.policies().find((row) => row.name === 'Odisha Private Company Leave Policy');
    const chosen = odisha ?? this.policies()[0];
    this.policyId.set(chosen?.id ?? null);
    this.year.set(chosen ? Number(chosen.effectiveFrom.slice(0, 4)) : new Date().getFullYear());
    this.departmentId.set(null);
    this.branchId.set(null);
    this.search.set('');
    this.pageIndex.set(0);
    this.load();
  }

  protected page(event: PageEvent): void {
    this.pageIndex.set(event.pageIndex);
    this.pageSize.set(event.pageSize);
    this.load();
  }

  protected toggleSort(column: string): void {
    this.sort.set(this.sort() === column ? `-${column}` : column);
    this.load();
  }

  protected toggle(id: number, checked: boolean): void {
    this.selected.update((current) => checked ? [...current, id] : current.filter((item) => item !== id));
  }

  protected tone(value: string): 'pos' | 'zero' | 'neg' {
    const amount = Number(value);
    if (amount > 0) return 'pos';
    if (amount < 0) return 'neg';
    return 'zero';
  }

  protected open(row: BalanceEmployee, focus: 'details' | 'transactions' | 'history' | 'adjust'): void {
    this.dialog.open(LeaveBalanceDetailDialog, {
      data: {
        employeeId: row.employeeId,
        year: this.year(),
        focus,
        canManage: this.auth.hasPermission(this.manage),
      },
      width: '52rem',
      maxWidth: '95vw',
    }).afterClosed().subscribe(() => this.load());
  }

  protected generate(): void {
    this.dialog.open(LeaveBalanceGenerateDialog, {
      data: { policies: this.policies(), policyId: this.policyId(), year: this.year() },
      width: '48rem',
      maxWidth: '95vw',
    }).afterClosed().subscribe((posted) => {
      if (posted) this.load();
    });
  }

  protected exportCsv(): void {
    const items = this.board()?.items ?? [];
    const header = ['Employee ID', 'Employee Name', 'Department', 'Designation', 'AL Balance', 'CL Balance', 'Comp-Off'];
    const lines = items.map((row) => [
      row.employeeCode, row.employeeName, row.department ?? '', row.designation ?? '',
      row.el.balance, row.cl.balance, row.compOffBalance,
    ]);
    const csv = [header, ...lines].map((line) => line.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(',')).join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `leave-balances-${this.year()}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

}
