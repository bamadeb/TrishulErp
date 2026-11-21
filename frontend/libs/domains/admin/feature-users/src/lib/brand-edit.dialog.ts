import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { BrandApi, BrandItem, CompanyChoice } from '@trishul/admin-data-access';

export interface BrandEditData {
  /** The brand being changed; none to add one. */
  brand?: BrandItem;
}

/** Add a brand or change its name, company and what the company does with it. */
@Component({
  selector: 'trishul-brand-edit-dialog',
  imports: [
    MatDialogModule,
    MatButtonModule,
    MatCheckboxModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ data.brand ? 'Edit' : 'Add' }} brand</h2>
    <mat-dialog-content>
      <mat-form-field appearance="outline">
        <mat-label>Brand code</mat-label>
        <input
          matInput
          [attr.maxlength]="20"
          [value]="code()"
          (input)="code.set($any($event.target).value)"
        />
        <mat-hint>Short and unique, e.g. TATA_HITACHI</mat-hint>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Brand name</mat-label>
        <input
          matInput
          [attr.maxlength]="120"
          [value]="name()"
          (input)="name.set($any($event.target).value)"
        />
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Company</mat-label>
        <mat-select
          [value]="companyId()"
          (valueChange)="companyId.set($event)"
        >
          <mat-option [value]="null">No company</mat-option>
          @for (c of companies(); track c.id) {
            <mat-option [value]="c.id">{{ c.name }}</mat-option>
          }
        </mat-select>
        <mat-hint>Shown beside the brand name in every brand dropdown</mat-hint>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Website</mat-label>
        <input
          matInput
          [attr.maxlength]="200"
          [value]="website()"
          (input)="website.set($any($event.target).value)"
        />
      </mat-form-field>
      <div class="handles">
        <mat-checkbox
          [checked]="handlesSales()"
          (change)="handlesSales.set($event.checked)"
          >Sales</mat-checkbox
        >
        <mat-checkbox
          [checked]="handlesService()"
          (change)="handlesService.set($event.checked)"
          >Service</mat-checkbox
        >
        <mat-checkbox
          [checked]="handlesParts()"
          (change)="handlesParts.set($event.checked)"
          >Parts</mat-checkbox
        >
      </div>
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
    .handles {
      display: flex;
      gap: 1rem;
    }
  `,
})
export class BrandEditDialog {
  protected readonly data = inject<BrandEditData>(MAT_DIALOG_DATA);
  protected readonly dialogRef =
    inject<MatDialogRef<BrandEditDialog, boolean>>(MatDialogRef);
  private readonly api = inject(BrandApi);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly code = signal(this.data.brand?.code ?? '');
  protected readonly name = signal(this.data.brand?.name ?? '');
  protected readonly companyId = signal<number | null>(
    this.data.brand?.companyId ?? null,
  );
  protected readonly companies = signal<CompanyChoice[]>([]);
  protected readonly website = signal(this.data.brand?.website ?? '');
  protected readonly handlesSales = signal(
    this.data.brand?.handlesSales ?? true,
  );
  protected readonly handlesService = signal(
    this.data.brand?.handlesService ?? true,
  );
  protected readonly handlesParts = signal(
    this.data.brand?.handlesParts ?? true,
  );
  protected readonly saving = signal(false);
  protected readonly valid = computed(
    () => this.code().trim().length > 0 && this.name().trim().length > 0,
  );

  constructor() {
    this.api.formOptions().subscribe((o) => this.companies.set(o.companies));
  }

  protected save(): void {
    const body = {
      code: this.code().trim(),
      name: this.name().trim(),
      companyId: this.companyId(),
      website: this.website().trim() || null,
      handlesSales: this.handlesSales(),
      handlesService: this.handlesService(),
      handlesParts: this.handlesParts(),
    };
    const { brand } = this.data;
    const request = brand
      ? this.api.update(brand, body)
      : this.api.create(body);
    this.saving.set(true);
    request.subscribe({
      next: () => {
        this.snackBar.open('Brand saved', 'OK', { duration: 4000 });
        this.dialogRef.close(true);
      },
      // The global interceptor shows the server's message.
      error: () => this.saving.set(false),
    });
  }
}
