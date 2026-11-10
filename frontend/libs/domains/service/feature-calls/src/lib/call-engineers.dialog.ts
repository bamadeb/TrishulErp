import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatDatepickerModule } from '@angular/material/datepicker';
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
  /** yyyy-mm-dd the call's visit is already planned for, if any. */
  plannedVisitDate: string | null;
  /** False for a finished call: changing who was on it plans no visit. */
  planVisit: boolean;
}
export interface CallEngineersResult {
  engineerId: number | null;
  supportEngineerIds: number[];
  /** yyyy-mm-dd of the visit for everyone on the call; null when nobody is on it or no visit is planned. */
  visitDate: string | null;
}

/** yyyy-mm-dd in the user's own time zone (toISOString would give yesterday before 05:30 in India). */
function isoDate(day: Date): string {
  const month = String(day.getMonth() + 1).padStart(2, '0');
  const date = String(day.getDate()).padStart(2, '0');
  return `${day.getFullYear()}-${month}-${date}`;
}

/** yyyy-mm-dd as a local midnight Date (new Date('yyyy-mm-dd') would be UTC). */
function fromIso(day: string): Date {
  const [year, month, date] = day.split('-').map(Number);
  return new Date(year, month - 1, date);
}

function addDays(days: number): string {
  const day = new Date();
  day.setDate(day.getDate() + days);
  return isoDate(day);
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
    MatDatepickerModule,
  ],
  providers: [provideNativeDateAdapter()],
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
      @if (data.planVisit) {
      <mat-form-field class="full visit" appearance="outline">
        <mat-label>Visit date</mat-label>
        <input
          matInput
          required
          [matDatepicker]="picker"
          [min]="minDate"
          [value]="visitDay()"
          (dateChange)="onDate($event.value)"
          (click)="picker.open()"
        />
        <mat-datepicker-toggle matSuffix [for]="picker" />
        <mat-datepicker #picker />
        @if (dateProblem(); as problem) {
        <mat-hint class="problem">{{ problem }}</mat-hint>
        } @else if (selected().length) {
        <mat-hint>Everyone ticked gets a visit on this day.</mat-hint>
        } @else {
        <mat-hint>Tick at least one engineer to plan the visit.</mat-hint>
        }
      </mat-form-field>
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <span class="count">{{ summary() }}</span>
      <button mat-button mat-dialog-close>Cancel</button>
      <button mat-flat-button (click)="save()" [disabled]="!!dateProblem()">
        Save
      </button>
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
    .visit {
      margin-top: 1rem;
    }
    .problem {
      color: var(--mat-sys-error);
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

  protected readonly today = addDays(0);
  /** The day already planned (if still ahead), otherwise tomorrow. */
  protected readonly visitDate = signal(
    this.data.plannedVisitDate && this.data.plannedVisitDate >= this.today
      ? this.data.plannedVisitDate
      : addDays(1),
  );
  /** The picker works with Date objects; the API takes yyyy-mm-dd. */
  protected readonly minDate = fromIso(this.today);
  protected readonly visitDay = computed(() =>
    this.visitDate() ? fromIso(this.visitDate()) : null,
  );

  protected onDate(day: Date | null): void {
    this.visitDate.set(day ? isoDate(day) : ''); // null: cleared or half-typed date
  }

  protected readonly dateProblem = computed(() => {
    if (!this.data.planVisit || this.selected().length === 0) return null;
    const day = this.visitDate();
    if (!day) return 'Choose the visit date.';
    return day < this.today ? 'The visit date cannot be in the past.' : null;
  });

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
    if (this.dateProblem()) return;
    const [lead, ...support] = this.selected();
    this.ref.close({
      engineerId: lead ?? null,
      supportEngineerIds: support,
      visitDate:
        lead !== undefined && this.data.planVisit ? this.visitDate() : null,
    });
  }
}
