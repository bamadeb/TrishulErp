import { StatusSeverity } from '@trishul/shared-ui';
import { PayrollStatus } from './payroll.mock';

const money = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
});

const moneyPrecise = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function inr(value: number, digits = 0): string {
  return (digits === 0 ? money : moneyPrecise).format(value);
}

export const PAYROLL_STATUS: Record<PayrollStatus, StatusSeverity> = {
  Active: 'success',
  Inactive: 'neutral',
  Pending: 'warn',
  Approved: 'success',
  Rejected: 'danger',
  Draft: 'neutral',
  Processed: 'info',
  Paid: 'success',
  Filed: 'success',
  Due: 'warn',
  Imported: 'success',
  Failed: 'danger',
};

export function netOf(gross: number, deductions: number): number {
  return gross - deductions;
}
