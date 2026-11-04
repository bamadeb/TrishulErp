import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import {
  FormControl,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
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
import { EMPTY, catchError, finalize } from 'rxjs';
import { AscApi, ContractPlanItem } from '@trishul/service-data-access';
import { amount } from './asc-form.page';

const PRIORITIES = ['Critical', 'High', 'Normal', 'Low'] as const;

/** Add an ASC plan or change one (null = add). Closes with the saved plan. */
@Component({
  selector: 'trishul-asc-plan-dialog',
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatCheckboxModule,
    MatButtonModule,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ plan ? 'Edit plan' : 'Add plan' }}</h2>
    <mat-dialog-content>
      <form class="grid" [formGroup]="form" (ngSubmit)="save()" id="plan-form">
        <mat-form-field appearance="outline">
          <mat-label>Code</mat-label>
          <input matInput formControlName="code" autocomplete="off" />
          <mat-error>Required, at most 20 characters.</mat-error>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Machine class</mat-label>
          <input matInput formControlName="machineClass" placeholder="e.g. 20 Ton (ZX)" />
        </mat-form-field>
        <mat-form-field appearance="outline" class="wide">
          <mat-label>Name</mat-label>
          <input matInput formControlName="name" />
          <mat-error>Required.</mat-error>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Months</mat-label>
          <input matInput type="number" min="1" max="60" formControlName="durationMonths" />
          <mat-error>1 to 60.</mat-error>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Visits</mat-label>
          <input matInput type="number" min="0" formControlName="visitsIncluded" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Price before GST (₹)</mat-label>
          <input matInput type="number" min="0" formControlName="price" />
          <mat-error>Required.</mat-error>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>GST %</mat-label>
          <input matInput type="number" min="0" max="100" formControlName="gstPct" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Parts discount %</mat-label>
          <input matInput type="number" min="0" max="100" formControlName="partsDiscountPct" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Call priority</mat-label>
          <mat-select formControlName="servicePriority">
            @for (p of priorities; track p) {
              <mat-option [value]="p">{{ p }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
        <div class="wide checks">
          <mat-checkbox formControlName="coversLabour">Labour covered</mat-checkbox>
          <mat-checkbox formControlName="coversTravel">Travel covered</mat-checkbox>
          <mat-checkbox formControlName="coversParts">Parts covered</mat-checkbox>
        </div>
        <mat-form-field appearance="outline" class="wide">
          <mat-label>Terms</mat-label>
          <textarea matInput rows="2" formControlName="terms"></textarea>
        </mat-form-field>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close type="button">Cancel</button>
      <button mat-flat-button type="submit" form="plan-form" [disabled]="saving()">
        {{ plan ? 'Save' : 'Add plan' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 0.25rem 0.75rem;
      width: 34rem;
      max-width: 100%;
      padding-top: 0.25rem;
    }
    .wide {
      grid-column: 1 / -1;
    }
    .checks {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem 1rem;
      margin-bottom: 0.75rem;
    }
    @media (max-width: 600px) {
      .grid {
        grid-template-columns: 1fr;
      }
    }
  `,
})
export class AscPlanDialog {
  private readonly api = inject(AscApi);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly ref =
    inject<MatDialogRef<AscPlanDialog, ContractPlanItem>>(MatDialogRef);
  protected readonly plan = inject<ContractPlanItem | null>(MAT_DIALOG_DATA);
  protected readonly priorities = PRIORITIES;
  protected readonly saving = signal(false);

  protected readonly form = this.fb.group({
    code: this.fb.control(this.plan?.code ?? '', [
      Validators.required,
      Validators.maxLength(20),
    ]),
    name: this.fb.control(this.plan?.name ?? '', [
      Validators.required,
      Validators.maxLength(100),
    ]),
    machineClass: new FormControl<string | null>(
      this.plan?.machineClass ?? null,
      Validators.maxLength(40),
    ),
    durationMonths: this.fb.control(this.plan?.durationMonths ?? 12, [
      Validators.required,
      Validators.min(1),
      Validators.max(60),
    ]),
    visitsIncluded: new FormControl<number | null>(
      this.plan?.visitsIncluded ?? 12,
      Validators.min(0),
    ),
    price: new FormControl<number | null>(amount(this.plan?.price ?? null), [
      Validators.required,
      Validators.min(0),
    ]),
    gstPct: this.fb.control(amount(this.plan?.gstPct ?? null) ?? 18, [
      Validators.min(0),
      Validators.max(100),
    ]),
    partsDiscountPct: new FormControl<number | null>(
      this.plan ? amount(this.plan.partsDiscountPct) : 5,
      [Validators.min(0), Validators.max(100)],
    ),
    servicePriority: this.fb.control<(typeof PRIORITIES)[number]>(
      this.plan?.servicePriority ?? 'High',
    ),
    coversLabour: this.fb.control(this.plan?.coversLabour ?? true),
    coversTravel: this.fb.control(this.plan?.coversTravel ?? true),
    coversParts: this.fb.control(this.plan?.coversParts ?? false),
    terms: new FormControl<string | null>(
      this.plan?.terms ?? null,
      Validators.maxLength(2000),
    ),
  });

  protected save(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.saving()) return;
    const v = this.form.getRawValue();
    const body = {
      code: v.code.trim(),
      name: v.name.trim(),
      machineClass: v.machineClass?.trim() || null,
      durationMonths: v.durationMonths,
      visitsIncluded: v.visitsIncluded,
      price: v.price as number,
      gstPct: v.gstPct,
      partsDiscountPct: v.partsDiscountPct,
      servicePriority: v.servicePriority,
      coversLabour: v.coversLabour,
      coversTravel: v.coversTravel,
      coversParts: v.coversParts,
      terms: v.terms?.trim() || null,
    };
    this.saving.set(true);
    const request = this.plan
      ? this.api.updatePlan(this.plan.id, this.plan.rowVersion, body)
      : this.api.createPlan(body);
    request
      .pipe(
        finalize(() => this.saving.set(false)),
        catchError(() => EMPTY),
      )
      .subscribe((saved) => this.ref.close(saved));
  }
}
