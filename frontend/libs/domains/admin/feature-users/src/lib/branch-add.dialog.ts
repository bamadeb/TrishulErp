import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { WarehouseApi, WarehouseCompany, WarehouseOut } from '@trishul/admin-data-access';

export interface BranchAddData {
  /** The active warehouses to choose from. */
  warehouses: WarehouseOut[];
  companies: WarehouseCompany[];
  /** Pre-selected when the dialog is opened from a warehouse. */
  warehouseId?: number;
}

type BranchType = 'Branch' | 'Service point';

/** Add a branch or service point and put it under a warehouse (the warehouse can also be set later). */
@Component({
  selector: 'trishul-branch-add-dialog',
  imports: [MatDialogModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSelectModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Add branch</h2>
    <mat-dialog-content>
      <mat-form-field appearance="outline">
        <mat-label>Code</mat-label>
        <input matInput [attr.maxlength]="10" [value]="code()" (input)="code.set($any($event.target).value)" />
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Name</mat-label>
        <input matInput [attr.maxlength]="120" [value]="name()" (input)="name.set($any($event.target).value)" />
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Type</mat-label>
        <mat-select [value]="type()" (valueChange)="type.set($event)">
          <mat-option value="Branch">Branch</mat-option>
          <mat-option value="Service point">Service point</mat-option>
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Warehouse</mat-label>
        <mat-select [value]="warehouseId()" (valueChange)="chooseWarehouse($event)">
          <mat-option [value]="0">No warehouse yet</mat-option>
          @for (w of data.warehouses; track w.id) {
            <mat-option [value]="w.id">{{ w.name }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Company</mat-label>
        <mat-select [value]="companyId()" (valueChange)="companyId.set($event)">
          @for (c of data.companies; track c.id) {
            <mat-option [value]="c.id">{{ c.name }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" [disabled]="saving()" (click)="dialogRef.close(false)">Cancel</button>
      <button mat-flat-button type="button" [disabled]="!valid() || saving()" (click)="save()">Add branch</button>
    </mat-dialog-actions>
  `,
  styles: `
    mat-form-field {
      width: 100%;
    }
  `,
})
export class BranchAddDialog {
  protected readonly data = inject<BranchAddData>(MAT_DIALOG_DATA);
  protected readonly dialogRef = inject<MatDialogRef<BranchAddDialog, boolean>>(MatDialogRef);
  private readonly api = inject(WarehouseApi);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly code = signal('');
  protected readonly name = signal('');
  protected readonly type = signal<BranchType>('Branch');
  protected readonly warehouseId = signal(this.data.warehouseId ?? 0); // 0 = none; mat-select shows null as blank
  protected readonly companyId = signal<number | null>(this.companyOf(this.data.warehouseId));
  protected readonly saving = signal(false);
  protected readonly valid = computed(() => this.code().trim().length > 0 && this.name().trim().length > 0);

  /** Picking a warehouse proposes its company; it can still be changed. */
  protected chooseWarehouse(id: number): void {
    this.warehouseId.set(id);
    if (id) this.companyId.set(this.companyOf(id));
  }

  private companyOf(warehouseId: number | undefined): number | null {
    const warehouse = this.data.warehouses.find((w) => w.id === warehouseId);
    return warehouse?.companyId ?? this.data.companies[0]?.id ?? null;
  }

  protected save(): void {
    this.saving.set(true);
    this.api
      .createBranch({
        code: this.code().trim(),
        name: this.name().trim(),
        branchType: this.type(),
        warehouseId: this.warehouseId() || null,
        companyId: this.companyId(),
      })
      .subscribe({
        next: (branch) => {
          this.snackBar.open(`${branch.name} added`, 'OK', { duration: 4000 });
          this.dialogRef.close(true);
        },
        // The global interceptor shows the server's message (e.g. the code is already used).
        error: () => this.saving.set(false),
      });
  }
}
