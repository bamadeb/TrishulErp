import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { WarehouseApi, WarehouseCompany, WarehouseOut } from '@trishul/admin-data-access';

export interface WarehouseEditData {
  /** The warehouse being changed; none to add one. */
  warehouse?: WarehouseOut;
  /** The companies a warehouse can belong to. */
  companies: WarehouseCompany[];
}

/** Add a warehouse or change its code and name. */
@Component({
  selector: 'trishul-warehouse-edit-dialog',
  imports: [
    MatDialogModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ data.warehouse ? 'Edit' : 'Add' }} warehouse</h2>
    <mat-dialog-content>
      <mat-form-field appearance="outline">
        <mat-label>Code</mat-label>
        <input
          matInput
          [attr.maxlength]="10"
          [value]="code()"
          (input)="code.set($any($event.target).value)"
        />
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Name</mat-label>
        <input
          matInput
          [attr.maxlength]="120"
          [value]="name()"
          (input)="name.set($any($event.target).value)"
        />
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
      <button
        mat-button
        type="button"
        [disabled]="saving()"
        (click)="dialogRef.close(false)"
      >
        Cancel
      </button>
      <button
        mat-flat-button
        type="button"
        [disabled]="!valid() || saving()"
        (click)="save()"
      >
        Save
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    mat-form-field {
      width: 100%;
    }
  `,
})
export class WarehouseEditDialog {
  protected readonly data = inject<WarehouseEditData>(MAT_DIALOG_DATA);
  protected readonly dialogRef =
    inject<MatDialogRef<WarehouseEditDialog, boolean>>(MatDialogRef);
  private readonly api = inject(WarehouseApi);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly code = signal(this.data.warehouse?.code ?? '');
  protected readonly name = signal(this.data.warehouse?.name ?? '');
  protected readonly companyId = signal<number | null>(
    this.data.warehouse?.companyId ?? this.data.companies[0]?.id ?? null,
  );
  protected readonly saving = signal(false);
  protected readonly valid = computed(
    () =>
      this.code().trim().length > 0 &&
      this.name().trim().length > 0 &&
      this.companyId() !== null,
  );

  protected save(): void {
    const code = this.code().trim();
    const name = this.name().trim();
    const { warehouse } = this.data;
    const companyId = this.companyId();
    const request = warehouse
      ? this.api.update(warehouse, { code, name, companyId })
      : this.api.create({ code, name, companyId });
    this.saving.set(true);
    request.subscribe({
      next: () => {
        this.snackBar.open('Warehouse saved', 'OK', { duration: 4000 });
        this.dialogRef.close(true);
      },
      // The global interceptor shows the server's message.
      error: () => this.saving.set(false),
    });
  }
}
