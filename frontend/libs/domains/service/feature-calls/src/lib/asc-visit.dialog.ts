import {
  ChangeDetectionStrategy,
  Component,
  inject,
  signal,
} from '@angular/core';
import {
  FormControl,
  NonNullableFormBuilder,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { EMPTY, catchError, finalize } from 'rxjs';
import {
  AscApi,
  AscCallVisit,
  ServiceContractDetail,
} from '@trishul/service-data-access';

export interface AscVisitDialogData {
  contract: ServiceContractDetail;
  call: AscCallVisit;
}

const MAX_VISITS = 200; // as the API allows

/** Record how many visits a completed call took. Closes with the updated ASC. */
@Component({
  selector: 'trishul-asc-visit-dialog',
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>
      {{ data.call.visits ? 'Change visits' : 'Count visits' }}
    </h2>
    <mat-dialog-content>
      <p class="for">
        <b>{{ data.call.callNo }}</b> on ASC {{ data.contract.contractNo }}
      </p>
      <form [formGroup]="form" (ngSubmit)="save()" id="visit-form">
        <mat-form-field appearance="outline">
          <mat-label>Visits completed</mat-label>
          <input
            matInput
            type="number"
            min="0"
            [max]="maxVisits"
            formControlName="visits"
          />
          <mat-hint>{{ hint }}</mat-hint>
          <mat-error>Enter 0 to {{ maxVisits }}.</mat-error>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Remarks</mat-label>
          <textarea matInput rows="2" formControlName="remarks"></textarea>
          <mat-error>At most 300 characters.</mat-error>
        </mat-form-field>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close type="button">Cancel</button>
      <button
        mat-flat-button
        type="submit"
        form="visit-form"
        [disabled]="saving()"
      >
        Save
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    .for {
      margin: 0 0 1rem;
    }
    form {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      width: 24rem;
      max-width: 100%;
    }
  `,
})
export class AscVisitDialog {
  private readonly api = inject(AscApi);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly ref =
    inject<MatDialogRef<AscVisitDialog, ServiceContractDetail>>(MatDialogRef);
  protected readonly data = inject<AscVisitDialogData>(MAT_DIALOG_DATA);
  protected readonly saving = signal(false);

  /** This call's own visits are free to reuse, on top of what the ASC has left. */
  protected readonly maxVisits =
    this.data.contract.visitsRemaining === null
      ? MAX_VISITS
      : this.data.call.visits + this.data.contract.visitsRemaining;

  protected readonly hint =
    this.data.contract.visitsRemaining === null
      ? 'This ASC has no visit limit. 0 takes the call off the count.'
      : `At most ${this.maxVisits} for this call. 0 takes it off the count.`;

  protected readonly form = this.fb.group({
    // One completed call counts as one visit unless the manager says otherwise.
    visits: this.fb.control(this.data.call.visits || 1, [
      Validators.required,
      Validators.min(0),
      Validators.max(this.maxVisits),
    ]),
    remarks: new FormControl<string | null>(
      this.data.call.remarks,
      Validators.maxLength(300),
    ),
  });

  protected save(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.saving()) return;
    const v = this.form.getRawValue();
    const { contract, call } = this.data;
    this.saving.set(true);
    this.api
      .setCallVisits(contract.id, call.serviceCallId, contract.rowVersion, {
        visits: v.visits,
        remarks: v.remarks?.trim() || null,
      })
      .pipe(
        finalize(() => this.saving.set(false)),
        catchError(() => EMPTY), // the error toast has been shown
      )
      .subscribe((updated) => this.ref.close(updated));
  }
}
