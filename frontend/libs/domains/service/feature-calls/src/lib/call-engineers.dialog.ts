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
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatTooltipModule } from '@angular/material/tooltip';
import { EngineerOption } from '@trishul/service-data-access';

export interface CallEngineersData {
  callNo: string;
  /** The engineers on offer, including anyone already on the call. */
  engineers: EngineerOption[];
  leadId: number | null;
  supportIds: number[];
}
export interface CallEngineersResult {
  engineerId: number | null;
  supportEngineerIds: number[];
}

/** Choose everyone on a call. The first one ticked leads; the star moves the lead to someone else. */
@Component({
  selector: 'trishul-call-engineers-dialog',
  imports: [
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatCheckboxModule,
    MatButtonModule,
    MatIconModule,
    MatTooltipModule,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Assign engineers</h2>
    <mat-dialog-content>
      <p class="sub">
        Call {{ data.callNo }} — everyone ticked sees the call and can work it.
      </p>
      <mat-form-field
        class="full"
        appearance="outline"
        subscriptSizing="dynamic"
      >
        <mat-icon matPrefix>search</mat-icon>
        <input
          matInput
          placeholder="Search by name or code"
          aria-label="Search engineers"
          (input)="search.set($any($event.target).value)"
        />
      </mat-form-field>
      <div class="list">
        @for (e of visible(); track e.id) {
        <div class="row">
          <mat-checkbox
            [checked]="selected().includes(e.id)"
            (change)="toggle(e.id)"
          >
            {{ e.name }} <span class="muted">· {{ e.employeeCode }}</span>
          </mat-checkbox>
          @if (selected()[0] === e.id) {
          <span class="lead"><mat-icon inline>star</mat-icon> Lead</span>
          } @else if (selected().includes(e.id)) {
          <button
            mat-icon-button
            type="button"
            class="make-lead"
            (click)="makeLead(e.id)"
            matTooltip="Make lead"
            [attr.aria-label]="'Make ' + e.name + ' the lead'"
          >
            <mat-icon>star_border</mat-icon>
          </button>
          }
        </div>
        } @empty {
        <p class="sub">No engineers found</p>
        }
      </div>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <span class="count">{{ summary() }}</span>
      <button mat-button mat-dialog-close>Cancel</button>
      <button mat-flat-button (click)="save()">Save</button>
    </mat-dialog-actions>
  `,
  styles: `
    .sub {
      margin: 0 0 1rem;
      color: var(--mat-sys-on-surface-variant);
    }
    .full {
      width: 26rem;
      max-width: 100%;
    }
    .list {
      margin-top: 0.5rem;
      max-height: 20rem;
      overflow-y: auto;
    }
    .row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 2.75rem;
    }
    .muted {
      color: var(--mat-sys-on-surface-variant);
      font-size: 0.8rem;
    }
    .lead {
      display: inline-flex;
      align-items: center;
      gap: 0.25rem;
      padding-right: 0.75rem;
      font: var(--mat-sys-label-medium);
      color: var(--mat-sys-primary);
    }
    .make-lead {
      color: var(--mat-sys-on-surface-variant);
    }
    .count {
      margin-right: auto;
      padding-left: 0.5rem;
      font: var(--mat-sys-body-small);
      color: var(--mat-sys-on-surface-variant);
    }
  `,
})
export class CallEngineersDialog {
  private readonly ref =
    inject<MatDialogRef<CallEngineersDialog, CallEngineersResult>>(
      MatDialogRef,
    );
  protected readonly data = inject<CallEngineersData>(MAT_DIALOG_DATA);

  protected readonly search = signal('');
  /** Everyone ticked; the first is the lead. */
  protected readonly selected = signal<number[]>(
    this.data.leadId === null
      ? []
      : [this.data.leadId, ...this.data.supportIds],
  );

  protected readonly visible = computed(() => {
    const term = this.search().trim().toLowerCase();
    return this.data.engineers.filter(
      (e) =>
        !term ||
        e.name.toLowerCase().includes(term) ||
        e.employeeCode.toLowerCase().includes(term),
    );
  });

  protected readonly summary = computed(() => {
    const count = this.selected().length;
    if (count === 0) return 'Unassigned';
    return count === 1 ? '1 engineer' : `${count} engineers`;
  });

  protected toggle(id: number): void {
    this.selected.update((ids) =>
      ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id],
    );
  }

  protected makeLead(id: number): void {
    this.selected.update((ids) => [id, ...ids.filter((x) => x !== id)]);
  }

  protected save(): void {
    const [lead, ...support] = this.selected();
    this.ref.close({ engineerId: lead ?? null, supportEngineerIds: support });
  }
}
