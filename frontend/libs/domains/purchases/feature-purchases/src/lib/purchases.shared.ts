import { StatusSeverity } from '@trishul/shared-ui';
import { num } from '@trishul/inventory-data-access';

export const PO_STATUS: Record<string, StatusSeverity> = {
  Draft: 'neutral',
  'Pending approval': 'warn',
  Approved: 'info',
  Sent: 'info',
  'Part received': 'warn',
  Received: 'success',
  Closed: 'contrast',
  Cancelled: 'contrast',
};

export const INVOICE_STATE: Record<string, StatusSeverity> = {
  Unpaid: 'info',
  'Partially paid': 'warn',
  Paid: 'success',
  Overdue: 'danger',
  Cancelled: 'contrast',
};

export const PO_STATUSES = [
  'Draft',
  'Pending approval',
  'Approved',
  'Part received',
  'Received',
  'Closed',
  'Cancelled',
] as const;

/** ₹1,23,456.78 (Indian grouping); a dash when empty. */
export function rupees(
  value: string | number | null | undefined,
  digits = 2,
): string {
  const amount = num(value);
  if (amount === null) return '—';
  return `₹${amount.toLocaleString('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
}

/** Line amounts as the server computes them: taxable after discount, GST on it. */
export function lineAmounts(
  quantity: number | null,
  unitPrice: number | null,
  discountPct: number | null,
  gstPct: number | null,
): { taxable: number; tax: number; total: number } {
  const round = (v: number) => Math.round(v * 100) / 100;
  const taxable = round(
    (quantity ?? 0) * (unitPrice ?? 0) * (1 - (discountPct ?? 0) / 100),
  );
  const tax = round((taxable * (gstPct ?? 0)) / 100);
  return { taxable, tax, total: round(taxable + tax) };
}
