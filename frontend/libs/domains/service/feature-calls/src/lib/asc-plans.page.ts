import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { RouterLink } from '@angular/router';
import { EMPTY, catchError, filter, finalize } from 'rxjs';
import { AuthStore, HasPermission } from '@trishul/core-auth';
import {
  ASC_MANAGE_PERMISSION,
  AscApi,
  ContractPlanItem,
} from '@trishul/service-data-access';
import { PageHeader, StatusBadge, StatusSeverity } from '@trishul/shared-ui';
import { AscPlanDialog } from './asc-plan.dialog';

type PlanFilter = 'active' | 'inactive' | 'all';
const ACTIVE_SEVERITY: Record<string, StatusSeverity> = {
  Active: 'success',
  Inactive: 'neutral',
};

/** The ASC price list: plans by machine class and duration. Admins add and change them. */
@Component({
  selector: 'trishul-asc-plans-page',
  imports: [
    DecimalPipe,
    RouterLink,
    MatTableModule,
    MatProgressBar,
    MatFormField,
    MatLabel,
    MatSelect,
    MatOption,
    MatButton,
    MatIconButton,
    MatIcon,
    MatMenu,
    MatMenuItem,
    MatMenuTrigger,
    HasPermission,
    PageHeader,
    StatusBadge,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './asc-plans.page.html',
  styleUrl: './machine-list.page.scss',
})
export class AscPlansPage {
  private readonly api = inject(AscApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  protected readonly canManage = inject(AuthStore).hasPermission(
    ASC_MANAGE_PERMISSION,
  );
  protected readonly managePermission = ASC_MANAGE_PERMISSION;
  protected readonly activeSeverity = ACTIVE_SEVERITY;

  protected readonly status = signal<PlanFilter>('active');
  protected readonly plans = signal<ContractPlanItem[]>([]);
  protected readonly loading = signal(false);
  protected readonly columns = [
    'name',
    'machineClass',
    'duration',
    'price',
    'total',
    'benefits',
    'status',
    'actions',
  ];

  constructor() {
    this.load();
  }

  protected setStatus(status: PlanFilter): void {
    this.status.set(status);
    this.load();
  }

  protected edit(plan: ContractPlanItem | null): void {
    this.dialog
      .open(AscPlanDialog, { data: plan, autoFocus: 'first-tabbable' })
      .afterClosed()
      .pipe(filter((saved): saved is ContractPlanItem => !!saved))
      .subscribe((saved) => {
        this.notify(plan ? 'Plan saved' : `Plan ${saved.code} added`);
        this.load();
      });
  }

  protected setActive(plan: ContractPlanItem, active: boolean): void {
    this.api
      .setPlanActive(plan.id, active)
      .pipe(catchError(() => EMPTY))
      .subscribe(() => {
        this.notify(active ? `${plan.code} offered again` : `${plan.code} no longer offered`);
        this.load();
      });
  }

  private load(): void {
    this.loading.set(true);
    this.api
      .plans(this.status())
      .pipe(
        finalize(() => this.loading.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe((plans) => this.plans.set(plans));
  }

  private notify(message: string): void {
    this.snackBar.open(message, 'OK', { duration: 5000 });
  }
}
