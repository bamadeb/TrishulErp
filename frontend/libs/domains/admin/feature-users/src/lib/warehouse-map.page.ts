import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltip } from '@angular/material/tooltip';
import { Observable, filter } from 'rxjs';
import {
  WAREHOUSE_MANAGE_PERMISSION,
  WarehouseApi,
  WarehouseBranch,
  WarehouseMap,
  WarehouseOut,
} from '@trishul/admin-data-access';
import { AuthStore, HasPermission } from '@trishul/core-auth';
import { PageHeader, confirmAction } from '@trishul/shared-ui';
import { BranchAddData, BranchAddDialog } from './branch-add.dialog';
import {
  WarehouseEditData,
  WarehouseEditDialog,
} from './warehouse-edit.dialog';

interface WarehouseNode {
  warehouse: WarehouseOut;
  branches: WarehouseBranch[];
}

const NO_WAREHOUSE = 0; // mat-select shows null as blank, so "No warehouse" uses this id

/**
 * Administration > Warehouses: each warehouse with the branches it supplies, and the branches no
 * warehouse supplies yet. Admin adds and edits warehouses and moves branches between them.
 */
@Component({
  selector: 'trishul-warehouse-map-page',
  imports: [
    MatButton,
    MatIconButton,
    MatIcon,
    MatProgressBar,
    MatSelect,
    MatOption,
    MatTooltip,
    PageHeader,
    HasPermission,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './warehouse-map.page.html',
  styleUrl: './warehouse-map.page.scss',
})
export class WarehouseMapPage {
  private readonly api = inject(WarehouseApi);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  private readonly auth = inject(AuthStore);

  protected readonly managePermission = WAREHOUSE_MANAGE_PERMISSION;
  protected readonly canManage = this.auth.hasPermission(
    WAREHOUSE_MANAGE_PERMISSION,
  );
  protected readonly NO_WAREHOUSE = NO_WAREHOUSE;
  protected readonly loading = signal(true);
  protected readonly failed = signal(false);
  private readonly map = signal<WarehouseMap>({
    warehouses: [],
    branches: [],
    companies: [],
  });

  protected readonly activeWarehouses = computed(() =>
    this.map().warehouses.filter((w) => w.isActive),
  );

  private readonly companies = computed(() => this.map().companies);

  protected readonly nodes = computed((): WarehouseNode[] => {
    const { warehouses, branches } = this.map();
    const live = branches.filter((b) => b.isActive);
    return warehouses.map((warehouse) => ({
      warehouse,
      branches: live.filter((b) => b.warehouseId === warehouse.id),
    }));
  });

  protected readonly unmapped = computed(() =>
    this.map().branches.filter(
      (b) => b.isActive && b.warehouseId === null,
    ),
  );

  constructor() {
    this.reload();
  }

  protected reload(): void {
    this.loading.set(true);
    this.api.load().subscribe({
      next: (map) => {
        this.map.set(map);
        this.failed.set(false);
        this.loading.set(false);
      },
      error: () => {
        this.failed.set(true);
        this.loading.set(false);
      },
    });
  }

  protected addWarehouse(): void {
    this.edit({ companies: this.companies() });
  }

  /** Add a branch, optionally already under the given warehouse. */
  protected addBranch(warehouseId?: number): void {
    const data: BranchAddData = {
      warehouses: this.activeWarehouses(),
      companies: this.companies(),
      warehouseId,
    };
    this.dialog
      .open(BranchAddDialog, { data, width: '28rem', autoFocus: 'dialog' })
      .afterClosed()
      .subscribe((saved) => {
        if (saved) this.reload();
      });
  }

  protected editWarehouse(warehouse: WarehouseOut): void {
    this.edit({ warehouse, companies: this.companies() });
  }

  protected assign(branch: WarehouseBranch, warehouseId: number): void {
    this.run(
      this.api.assign(branch, warehouseId === NO_WAREHOUSE ? null : warehouseId),
      `${branch.name} moved`,
    );
  }

  protected toggleWarehouse(warehouse: WarehouseOut): void {
    const change = (): Observable<unknown> =>
      this.api.update(warehouse, { isActive: !warehouse.isActive });
    const done = (): void =>
      this.run(
        change(),
        `${warehouse.name} ${warehouse.isActive ? 'deactivated' : 'activated'}`,
      );
    if (!warehouse.isActive) {
      done();
      return;
    }
    confirmAction(this.dialog, {
      title: `Deactivate ${warehouse.name}?`,
      message: `${warehouse.code} will be hidden from active lists. Its branches must be moved first. You can activate it again later.`,
      confirmText: 'Deactivate',
      destructive: true,
    })
      .pipe(filter(Boolean))
      .subscribe(done);
  }

  private edit(data: WarehouseEditData): void {
    this.dialog
      .open(WarehouseEditDialog, { data, width: '28rem', autoFocus: 'dialog' })
      .afterClosed()
      .subscribe((saved) => {
        if (saved) this.reload();
      });
  }

  /** The server rejects unsafe moves (e.g. closing a warehouse that still supplies branches). */
  private run(request: Observable<unknown>, done: string): void {
    this.loading.set(true);
    request.subscribe({
      next: () => {
        this.snackBar.open(done, 'OK', { duration: 4000 });
        this.reload();
      },
      error: () => this.reload(),
    });
  }
}
