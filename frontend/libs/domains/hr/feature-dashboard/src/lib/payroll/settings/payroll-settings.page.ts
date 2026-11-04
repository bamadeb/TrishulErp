import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatSnackBar } from '@angular/material/snack-bar';
import { PageHeader } from '@trishul/shared-ui';
import { PayrollSettings } from '../payroll.mock';
import { PayrollPrototype } from '../payroll.prototype';

/** Payroll period, calculation, attendance, workflow and allowance rates. */
@Component({
  selector: 'trishul-payroll-settings-page',
  imports: [MatButton, MatFormField, MatLabel, MatInput, PageHeader],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './payroll-settings.page.html',
  styleUrl: '../payroll.shared.scss',
})
export class PayrollSettingsPage {
  private readonly payroll = inject(PayrollPrototype);
  private readonly snackBar = inject(MatSnackBar);
  protected readonly draft = signal<PayrollSettings>({ ...this.payroll.settings() });

  protected setNumber(key: 'cutoffDay' | 'payDay' | 'workingDays' | 'bikePerKm' | 'carPerKm', event: Event): void {
    const value = Number((event.target as HTMLInputElement).value);
    this.draft.update((current) => ({ ...current, [key]: value }));
  }

  protected setText(event: Event): void {
    const workflow = (event.target as HTMLInputElement).value;
    this.draft.update((current) => ({ ...current, workflow }));
  }

  protected setFlag(key: 'lopProRata' | 'attendanceIntegration', event: Event): void {
    const checked = (event.target as HTMLInputElement).checked;
    this.draft.update((current) => ({ ...current, [key]: checked }));
  }

  protected save(): void {
    const draft = this.draft();
    this.payroll.settings.set({
      ...draft,
      cutoffDay: clamp(draft.cutoffDay, 1, 28),
      payDay: clamp(draft.payDay, 1, 28),
      workingDays: clamp(draft.workingDays, 1, 31),
      bikePerKm: Math.max(0, draft.bikePerKm),
      carPerKm: Math.max(0, draft.carPerKm),
    });
    this.draft.set({ ...this.payroll.settings() });
    this.snackBar.open('Payroll settings saved', 'OK', { duration: 4000 });
  }
}

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.min(max, Math.max(min, Math.round(value)));
}
