import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, Injectable, inject, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { DateAdapter, MAT_DATE_FORMATS, MAT_NATIVE_DATE_FORMATS, NativeDateAdapter } from '@angular/material/core';
import { MatDatepicker, MatDatepickerInput, MatDatepickerToggle } from '@angular/material/datepicker';
import {
  MAT_DIALOG_DATA,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatAutocomplete, MatAutocompleteTrigger, MatOption } from '@angular/material/autocomplete';
import { MatFormField, MatLabel, MatSuffix } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { ReportingApi, ReportingPerson } from '@trishul/hr-data-access';
import { ReportingDemoStore, reportsThrough } from './reporting.store';

export interface ReportingAssignData {
  employeeId?: number;
  employeeIds?: readonly number[];
}

const REPORTING_DATE_FORMATS = {
  ...MAT_NATIVE_DATE_FORMATS,
  parse: { ...MAT_NATIVE_DATE_FORMATS.parse, dateInput: 'DD-MM-YYYY' },
  display: { ...MAT_NATIVE_DATE_FORMATS.display, dateInput: 'DD-MM-YYYY' },
};

/** Shows 16-11-2026, matching the other HR date fields. */
@Injectable()
class ReportingDateAdapter extends NativeDateAdapter {
  override format(date: Date, displayFormat: object): string {
    if (String(displayFormat) !== 'DD-MM-YYYY') return super.format(date, displayFormat);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    return `${day}-${month}-${date.getFullYear()}`;
  }

  override parse(value: unknown): Date | null {
    if (typeof value !== 'string') return super.parse(value);
    const match = /^(\d{2})-(\d{2})-(\d{4})$/.exec(value.trim());
    if (!match) return null;
    const day = Number(match[1]);
    const month = Number(match[2]);
    const year = Number(match[3]);
    const date = new Date(year, month - 1, day);
    if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null;
    return date;
  }
}

@Component({
  selector: 'trishul-reporting-assign-dialog',
  imports: [
    ReactiveFormsModule,
    MatButton,
    MatDialogTitle,
    MatDialogContent,
    MatDialogActions,
    MatDialogClose,
    MatAutocomplete,
    MatAutocompleteTrigger,
    MatFormField,
    MatLabel,
    MatSuffix,
    MatInput,
    MatOption,
    MatDatepicker,
    MatDatepickerInput,
    MatDatepickerToggle,
  ],
  providers: [
    { provide: DateAdapter, useClass: ReportingDateAdapter },
    { provide: MAT_DATE_FORMATS, useValue: REPORTING_DATE_FORMATS },
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './reporting-assign.dialog.html',
  styleUrl: './reporting-assign.dialog.scss',
})
export class ReportingAssignDialog {
  private readonly store = inject(ReportingDemoStore);
  private readonly api = inject(ReportingApi);
  private readonly dialogRef = inject(MatDialogRef<ReportingAssignDialog, boolean>);
  private readonly data = inject<ReportingAssignData>(MAT_DIALOG_DATA);

  protected readonly managerId = signal<number | null>(null);
  protected readonly managerQuery = signal('');
  protected readonly effective = new FormControl<Date | null>(new Date());
  protected readonly remarks = signal('');
  protected readonly error = signal('');
  protected readonly saving = signal(false);
  protected readonly employees = signal(this.selectedPeople());
  protected readonly choices = this.store.people().filter((person) => this.canLead(person));

  protected currentManager(): ReportingPerson | null {
    const row = this.employees().length === 1 ? this.employees()[0] : null;
    if (!row || row.managerId == null) return null;
    return this.person(row.managerId) ?? null;
  }

  protected shown(name: string): string {
    const trimmed = name.trim();
    if (trimmed !== trimmed.toUpperCase()) return trimmed;
    return trimmed
      .toLowerCase()
      .replace(/(^|[\s'-])([a-z])/g, (_, lead: string, letter: string) => `${lead}${letter.toUpperCase()}`);
  }

  protected initials(name: string): string {
    const parts = this.shown(name).split(' ').filter(Boolean);
    return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase();
  }

  protected onRemarks(event: Event): void {
    this.remarks.set((event.target as HTMLInputElement).value);
  }

  protected save(): void {
    const managerId = this.managerId();
    const effective = this.effective.value;
    if (managerId == null) {
      this.error.set('Choose a new reporting manager.');
      return;
    }
    if (!effective) {
      this.error.set('Choose the effective date.');
      return;
    }
    if (!this.remarks().trim()) {
      this.error.set('Enter the reason for this change.');
      return;
    }
    const ids = this.employees().map((person) => person.id);
    if (!ids.length || this.saving()) return;
    this.saving.set(true);
    this.error.set('');
    this.saveAt(ids, 0, managerId, isoDay(effective), this.remarks().trim());
  }

  private saveAt(ids: number[], index: number, managerId: number, effective: string, remarks: string): void {
    if (index >= ids.length) {
      this.dialogRef.close(true);
      return;
    }
    this.api
      .assign({ employeeId: ids[index], reportingManagerId: managerId, effectiveFrom: effective, remarks })
      .subscribe({
        next: () => this.saveAt(ids, index + 1, managerId, effective, remarks),
        error: (error: HttpErrorResponse) => {
          this.saving.set(false);
          const failed = this.person(ids[index]);
          const name = failed ? this.shown(failed.name) : 'An employee';
          this.employees.set(this.employees().filter((person) => !ids.slice(0, index).includes(person.id)));
          this.error.set(index ? `${index} saved. ${name}: ${problemText(error)}` : `${name}: ${problemText(error)}`);
        },
      });
  }

  private person(id: number): ReportingPerson | undefined {
    return this.store.people().find((person) => person.id === id);
  }

  protected readonly managerLabel = (id: number | null): string => {
    if (id == null) return '';
    const person = this.choices.find((row) => row.id === id);
    return person ? `${this.shown(person.name)} · ${person.code} · ${person.designation}` : '';
  };

  protected filtered(): ReportingPerson[] {
    const term = this.managerQuery().trim().toLowerCase();
    if (!term) return this.choices;
    return this.choices.filter((person) => `${person.code} ${person.name} ${person.designation}`.toLowerCase().includes(term));
  }

  protected onQuery(event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.managerQuery.set(value);
    if (this.managerLabel(this.managerId()) !== value) this.managerId.set(null);
  }

  private selectedPeople(): ReportingPerson[] {
    const ids = this.data.employeeIds?.length ? this.data.employeeIds : this.data.employeeId == null ? [] : [this.data.employeeId];
    return ids.flatMap((id) => {
      const person = this.person(id);
      return person ? [person] : [];
    });
  }

  private canLead(person: ReportingPerson): boolean {
    const rows = this.employees();
    if (!rows.length || person.status !== 'Active' || rows.some((employee) => employee.id === person.id)) return false;
    return rows.every((employee) => !reportsThrough(this.store.people(), person.id, employee.id));
  }
}

function isoDay(value: Date): string {
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${value.getFullYear()}-${month}-${day}`;
}

function problemText(error: HttpErrorResponse): string {
  const problem = (error.error ?? {}) as { detail?: string; errors?: Record<string, string[]> };
  const fields = Object.values(problem.errors ?? {}).flat();
  return fields.join(' ') || problem.detail || 'The assignment could not be saved.';
}
