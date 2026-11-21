import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSnackBar } from '@angular/material/snack-bar';
import { BrandApi } from '@trishul/admin-data-access';

/** Add a company, so a brand can be placed under it. */
@Component({
  selector: 'trishul-company-add-dialog',
  imports: [
    MatDialogModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Add company</h2>
    <mat-dialog-content>
      <mat-form-field appearance="outline">
        <mat-label>Company code</mat-label>
        <input
          matInput
          [attr.maxlength]="10"
          [value]="code()"
          (input)="code.set($any($event.target).value)"
        />
        <mat-hint>Short and unique, e.g. KASI</mat-hint>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Legal name</mat-label>
        <input
          matInput
          [attr.maxlength]="200"
          [value]="legalName()"
          (input)="legalName.set($any($event.target).value)"
        />
        <mat-hint>As registered</mat-hint>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Name shown beside brands</mat-label>
        <input
          matInput
          [attr.maxlength]="200"
          [value]="tradeName()"
          (input)="tradeName.set($any($event.target).value)"
        />
        <mat-hint>Leave blank to use the legal name</mat-hint>
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
export class CompanyAddDialog {
  protected readonly dialogRef =
    inject<MatDialogRef<CompanyAddDialog, boolean>>(MatDialogRef);
  private readonly api = inject(BrandApi);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly code = signal('');
  protected readonly legalName = signal('');
  protected readonly tradeName = signal('');
  protected readonly saving = signal(false);
  protected readonly valid = computed(
    () => this.code().trim().length > 0 && this.legalName().trim().length > 0,
  );

  protected save(): void {
    this.saving.set(true);
    this.api
      .createCompany({
        code: this.code().trim(),
        legalName: this.legalName().trim(),
        tradeName: this.tradeName().trim() || null,
      })
      .subscribe({
        next: (company) => {
          this.snackBar.open(`Company ${company.name} added`, 'OK', {
            duration: 4000,
          });
          this.dialogRef.close(true);
        },
        // The global interceptor shows the server's message.
        error: () => this.saving.set(false),
      });
  }
}
