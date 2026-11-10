import { Injectable, computed, signal } from '@angular/core';
import {
  ACTIVITIES,
  CLAIMS,
  DEFAULT_SETTINGS,
  IMPORT_HISTORY,
  PAYROLL_APPROVALS,
  PAYROLL_RUNS,
  PAYSLIPS,
  SALARIES,
  SALARY_COMPONENTS,
  STATUTORY,
  TADA_ROWS,
  TREND,
  ClaimRow,
  ImportBatch,
  PayrollApproval,
  PayrollRun,
  PayrollSettings,
  PayslipRow,
  SalaryComponentRow,
  SalaryRow,
  TadaRow,
  VehicleType,
} from './payroll.mock';
import { cloneComponent } from './components/salary-component.model';

function nextId(rows: readonly { id: number }[]): number {
  return rows.reduce((max, row) => Math.max(max, row.id), 0) + 1;
}

/** In-memory payroll prototype. Screens read and update these signals. */
@Injectable({ providedIn: 'root' })
export class PayrollPrototype {
  readonly salaries = signal<SalaryRow[]>(SALARIES.map((row) => ({ ...row })));
  readonly components = signal<SalaryComponentRow[]>(SALARY_COMPONENTS.map((row) => cloneComponent(row)));
  readonly runs = signal<PayrollRun[]>(PAYROLL_RUNS.map((row) => ({ ...row })));
  readonly approvals = signal<PayrollApproval[]>(PAYROLL_APPROVALS.map((row) => ({ ...row })));
  readonly payslips = signal<PayslipRow[]>(PAYSLIPS.map((row) => ({ ...row })));
  readonly claims = signal<ClaimRow[]>(CLAIMS.map((row) => ({ ...row })));
  readonly tada = signal<TadaRow[]>(TADA_ROWS.map((row) => ({ ...row })));
  readonly imports = signal<ImportBatch[]>(IMPORT_HISTORY.map((row) => ({ ...row })));
  readonly statutory = STATUTORY;
  readonly activities = ACTIVITIES;
  readonly trend = TREND;
  readonly settings = signal<PayrollSettings>({ ...DEFAULT_SETTINGS });

  readonly totals = computed(() => {
    const rows = this.salaries();
    const gross = rows.reduce((sum, row) => sum + row.gross, 0);
    const deductions = rows.reduce((sum, row) => sum + row.deductions, 0);
    return {
      employees: rows.length,
      gross,
      deductions,
      net: gross - deductions,
      pendingApprovals: this.approvals().filter((row) => row.status === 'Pending').length,
    };
  });

  readonly departments = computed(() => {
    const buckets = new Map<string, number>();
    for (const row of this.salaries()) {
      buckets.set(row.department, (buckets.get(row.department) ?? 0) + row.gross);
    }
    return [...buckets.entries()].map(([name, gross]) => ({ name, gross }));
  });

  rateFor(vehicle: VehicleType): number {
    const settings = this.settings();
    return vehicle === 'Bike' ? settings.bikePerKm : settings.carPerKm;
  }

  taAmount(row: Pick<TadaRow, 'vehicle' | 'km'>): number {
    return Math.round(row.km * this.rateFor(row.vehicle) * 100) / 100;
  }

  tadaPayable(row: TadaRow): number {
    return (
      this.taAmount(row) +
      row.hra +
      row.specialAllowance +
      row.otherAllowance +
      row.conveyance +
      row.promotion
    );
  }

  saveSalary(row: SalaryRow): void {
    this.salaries.update((rows) => {
      const index = rows.findIndex((item) => item.id === row.id);
      if (index < 0) return [...rows, row];
      return rows.map((item) => (item.id === row.id ? row : item));
    });
  }

  saveComponent(row: SalaryComponentRow): void {
    this.components.update((rows) => {
      const exists = rows.some((item) => item.id === row.id);
      return exists ? rows.map((item) => (item.id === row.id ? row : item)) : [...rows, row];
    });
  }

  setRunStatus(id: number, status: PayrollRun['status']): void {
    this.runs.update((rows) => rows.map((row) => (row.id === id ? { ...row, status } : row)));
  }

  setApproval(id: number, status: PayrollApproval['status']): void {
    this.approvals.update((rows) => rows.map((row) => (row.id === id ? { ...row, status } : row)));
  }

  setClaim(id: number, status: ClaimRow['status']): void {
    this.claims.update((rows) => rows.map((row) => (row.id === id ? { ...row, status } : row)));
  }

  setTada(id: number, status: TadaRow['status']): void {
    this.tada.update((rows) => rows.map((row) => (row.id === id ? { ...row, status } : row)));
  }

  addTada(rows: TadaRow[], fileName: string): void {
    this.tada.update((current) => [...rows, ...current]);
    this.imports.update((current) => [
      {
        id: nextId(current),
        fileName,
        importedAt: new Intl.DateTimeFormat('en-IN', {
          day: '2-digit',
          month: 'short',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        }).format(new Date()),
        rows: rows.length,
        status: 'Imported',
      },
      ...current,
    ]);
  }

  nextSalaryId(): number {
    return nextId(this.salaries());
  }

  nextComponentId(): number {
    return nextId(this.components());
  }

  nextTadaId(): number {
    return nextId(this.tada());
  }
}
