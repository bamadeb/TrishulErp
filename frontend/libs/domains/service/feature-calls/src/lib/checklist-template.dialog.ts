import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import {
  FormArray,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckbox } from '@angular/material/checkbox';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatTooltip } from '@angular/material/tooltip';
import { LookupValueOut } from '@trishul/core-api';
import { AuthStore } from '@trishul/core-auth';
import { ChecklistTemplateOut, ServiceCallApi, ServiceReportApi } from '@trishul/service-data-access';

export interface ChecklistTemplateDialogData {
  /** The checklist being changed; none to add one. */
  template?: ChecklistTemplateOut;
  /** Looking only: the user may not change checklists. */
  readonly?: boolean;
}

type ResponseType = ChecklistTemplateOut['items'][number]['responseType'];

const RESPONSE_TYPES: { value: ResponseType; label: string }[] = [
  { value: 'OK Not OK', label: 'OK / Not OK' },
  { value: 'Number', label: 'Number' },
  { value: 'Text', label: 'Text' },
  { value: 'Photo', label: 'Photo' },
];

/** Add or change an inspection checklist. Questions removed here are hidden from new reports only. */
@Component({
  selector: 'trishul-checklist-template-dialog',
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatButtonModule,
    MatCheckbox,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatSelectModule,
    MatTooltip,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ data.template ? 'Edit' : 'Add' }} inspection checklist</h2>
    <mat-dialog-content>
      <form [formGroup]="form" class="form">
        <mat-form-field appearance="outline" class="full">
          <mat-label>Name</mat-label>
          <input matInput maxlength="120" formControlName="name" />
        </mat-form-field>
        <div class="row">
          <mat-form-field appearance="outline">
            <mat-label>Brand</mat-label>
            <mat-select formControlName="principalId">
              <mat-option [value]="null">All brands</mat-option>
              @for (p of principals(); track p.id) {
                <mat-option [value]="p.id">{{ p.name }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Call type</mat-label>
            <mat-select formControlName="callTypeLookupId">
              <mat-option [value]="null">All call types</mat-option>
              @for (t of callTypes(); track t.id) {
                <mat-option [value]="t.id">{{ t.name }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
        </div>
        <p class="hint">
          The most specific checklist (brand and call type) is copied into each new service report.
        </p>

        <h3>Questions</h3>
        <div formArrayName="items" class="items">
          @for (item of items.controls; track item; let i = $index) {
            <div class="item" [formGroupName]="i">
              <span class="no">{{ i + 1 }}</span>
              <mat-form-field appearance="outline" class="text">
                <mat-label>Check point</mat-label>
                <input matInput maxlength="300" formControlName="itemText" />
              </mat-form-field>
              <mat-form-field appearance="outline" class="type">
                <mat-label>Answer</mat-label>
                <mat-select formControlName="responseType">
                  @for (t of responseTypes; track t.value) {
                    <mat-option [value]="t.value">{{ t.label }}</mat-option>
                  }
                </mat-select>
              </mat-form-field>
              <mat-checkbox formControlName="isMandatory">Required</mat-checkbox>
              <button
                mat-icon-button
                type="button"
                matTooltip="Move up"
                [disabled]="i === 0"
                (click)="move(i, -1)"
              >
                <mat-icon>arrow_upward</mat-icon>
              </button>
              <button
                mat-icon-button
                type="button"
                matTooltip="Move down"
                [disabled]="i === items.length - 1"
                (click)="move(i, 1)"
              >
                <mat-icon>arrow_downward</mat-icon>
              </button>
              <button
                mat-icon-button
                type="button"
                matTooltip="Remove"
                [disabled]="items.length === 1"
                (click)="items.removeAt(i)"
              >
                <mat-icon>delete</mat-icon>
              </button>
            </div>
          }
        </div>
        <button mat-button type="button" [disabled]="!!data.readonly" (click)="addItem()">
          <mat-icon>add</mat-icon> Add question
        </button>
        @if (data.template) {
          <mat-checkbox formControlName="isActive">Active (used for new reports)</mat-checkbox>
        }
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" [disabled]="saving()" (click)="ref.close()">Cancel</button>
      <button
        mat-flat-button
        type="button"
        [disabled]="form.invalid || saving() || !!data.readonly"
        (click)="save()"
      >
        Save
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    .form {
      display: grid;
      gap: 0.25rem;
      min-width: min(52rem, 80vw);
    }
    .full {
      width: 100%;
    }
    .row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0 1rem;
    }
    .hint {
      margin: 0 0 0.5rem;
      color: var(--mat-sys-on-surface-variant);
    }
    h3 {
      margin: 0.5rem 0;
      font: var(--mat-sys-title-small);
    }
    .item {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .no {
      width: 1.5rem;
      text-align: right;
      color: var(--mat-sys-on-surface-variant);
    }
    .text {
      flex: 1 1 18rem;
    }
    .type {
      flex: 0 0 10rem;
    }
  `,
})
export class ChecklistTemplateDialog implements OnInit {
  protected readonly data = inject<ChecklistTemplateDialogData>(MAT_DIALOG_DATA);
  protected readonly ref = inject(MatDialogRef<ChecklistTemplateDialog, ChecklistTemplateOut>);
  private readonly api = inject(ServiceReportApi);
  private readonly calls = inject(ServiceCallApi);
  private readonly auth = inject(AuthStore);

  protected readonly responseTypes = RESPONSE_TYPES;
  protected readonly principals = signal(this.auth.user()?.principals ?? []);
  protected readonly callTypes = signal<LookupValueOut[]>([]);
  protected readonly saving = signal(false);

  protected readonly form = new FormGroup({
    name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.maxLength(120)] }),
    principalId: new FormControl<number | null>(null),
    callTypeLookupId: new FormControl<number | null>(null),
    isActive: new FormControl(true, { nonNullable: true }),
    items: new FormArray<FormGroup<{
      id: FormControl<number | null>;
      itemText: FormControl<string>;
      responseType: FormControl<ResponseType>;
      isMandatory: FormControl<boolean>;
    }>>([]),
  });

  protected get items() {
    return this.form.controls.items;
  }

  ngOnInit(): void {
    if (this.data.readonly) this.form.disable();
    this.calls.lookups('CALL_TYPE').subscribe((v) => this.callTypes.set(v));
    const t = this.data.template;
    if (!t) {
      this.addItem();
      return;
    }
    this.form.patchValue({
      name: t.name,
      principalId: t.principalId,
      callTypeLookupId: t.callTypeLookupId,
      isActive: t.isActive,
    });
    for (const i of t.items) this.addItem(i);
  }

  protected addItem(item?: ChecklistTemplateOut['items'][number]): void {
    this.items.push(
      new FormGroup({
        id: new FormControl<number | null>(item?.id ?? null),
        itemText: new FormControl(item?.itemText ?? '', {
          nonNullable: true,
          validators: [Validators.required, Validators.maxLength(300)],
        }),
        responseType: new FormControl<ResponseType>(item?.responseType ?? 'OK Not OK', { nonNullable: true }),
        isMandatory: new FormControl(item?.isMandatory ?? true, { nonNullable: true }),
      }),
    );
  }

  protected move(index: number, by: -1 | 1): void {
    const control = this.items.at(index);
    this.items.removeAt(index);
    this.items.insert(index + by, control);
  }

  protected save(): void {
    if (this.form.invalid || this.saving()) return;
    const v = this.form.getRawValue();
    const items = v.items.map((i) => ({
      id: i.id,
      itemText: i.itemText.trim(),
      responseType: i.responseType,
      isMandatory: i.isMandatory,
    }));
    const body = {
      name: v.name.trim(),
      principalId: v.principalId,
      callTypeLookupId: v.callTypeLookupId,
      items,
    };
    this.saving.set(true);
    const template = this.data.template;
    const request = template
      ? this.api.updateTemplate(template.id, template.rowVersion, { ...body, isActive: v.isActive })
      : this.api.createTemplate(body);
    request.subscribe({
      next: (saved) => this.ref.close(saved),
      error: () => this.saving.set(false),
    });
  }
}
