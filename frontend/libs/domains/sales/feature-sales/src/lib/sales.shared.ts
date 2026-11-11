import { FormControl, FormGroup, Validators } from '@angular/forms';
import { ItemListItem } from '@trishul/core-api';
import { num } from '@trishul/inventory-data-access';
import { StatusSeverity } from '@trishul/shared-ui';

export const QUOTATION_STATE: Record<string, StatusSeverity> = {
  Draft: 'neutral',
  'Pending approval': 'warn',
  Submitted: 'info',
  Accepted: 'success',
  Rejected: 'danger',
  Expired: 'contrast',
  Converted: 'success',
};
export const QUOTATION_STATES = [
  'Draft',
  'Pending approval',
  'Submitted',
  'Accepted',
  'Rejected',
  'Expired',
  'Converted',
] as const;

export const ORDER_STATUS: Record<string, StatusSeverity> = {
  Draft: 'neutral',
  'Pending approval': 'warn',
  Approved: 'info',
  'Part delivered': 'warn',
  Delivered: 'info',
  'Part invoiced': 'warn',
  Invoiced: 'success',
  Closed: 'contrast',
  Cancelled: 'contrast',
};
export const ORDER_STATUSES = [
  'Draft',
  'Pending approval',
  'Approved',
  'Part delivered',
  'Delivered',
  'Part invoiced',
  'Invoiced',
  'Closed',
  'Cancelled',
] as const;

export const DELIVERY_STATUS: Record<string, StatusSeverity> = {
  Dispatched: 'info',
  Delivered: 'success',
  Cancelled: 'contrast',
};

export const INVOICE_STATE: Record<string, StatusSeverity> = {
  Unpaid: 'info',
  'Partially paid': 'warn',
  Paid: 'success',
  Overdue: 'danger',
  Cancelled: 'contrast',
};

export type PaymentMode =
  'NEFT' | 'RTGS' | 'Cheque' | 'UPI' | 'Cash' | 'Finance disbursement';
export const PAYMENT_MODES: { value: PaymentMode; label: string }[] = [
  { value: 'NEFT', label: 'Bank transfer (NEFT)' },
  { value: 'RTGS', label: 'Bank transfer (RTGS)' },
  { value: 'Cheque', label: 'Cheque' },
  { value: 'UPI', label: 'UPI' },
  { value: 'Cash', label: 'Cash' },
  { value: 'Finance disbursement', label: 'Finance disbursement' },
];

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

/** One priced line of a quotation or order form. */
export function saleLine() {
  return new FormGroup({
    item: new FormControl<ItemListItem | null>(null),
    description: new FormControl<string | null>(
      null,
      Validators.maxLength(300),
    ),
    quantity: new FormControl<number | null>(1, [
      Validators.required,
      Validators.min(0.001),
    ]),
    unitPrice: new FormControl<number | null>(null, [
      Validators.required,
      Validators.min(0),
    ]),
    discountPct: new FormControl<number | null>(0, [
      Validators.min(0),
      Validators.max(100),
    ]),
    gstPct: new FormControl<number | null>(18, [
      Validators.required,
      Validators.min(0),
      Validators.max(100),
    ]),
  });
}
export type SaleLineForm = ReturnType<typeof saleLine>;

export function saleLineAmounts(line: SaleLineForm) {
  const v = line.getRawValue();
  return lineAmounts(v.quantity, v.unitPrice, v.discountPct, v.gstPct);
}

export function saleLinesTotals(lines: SaleLineForm[], other: number) {
  let taxable = 0;
  let tax = 0;
  for (const line of lines) {
    const a = saleLineAmounts(line);
    taxable += a.taxable;
    tax += a.tax;
  }
  return { taxable, tax, other, total: taxable + tax + other };
}

/** The API shape of a line (item optional only where allowText). */
export function saleLineBody(line: SaleLineForm) {
  const v = line.getRawValue();
  return {
    itemId: v.item?.id ?? null,
    description: v.description?.trim() || null,
    quantity: v.quantity as number,
    unitPrice: v.unitPrice as number,
    discountPct: v.discountPct ?? 0,
    gstPct: v.gstPct ?? 0,
  };
}

/** Lines are valid, and each has an item (or, where text lines are allowed, a description). */
export function saleLinesValid(lines: SaleLineForm[], allowText: boolean) {
  return lines.every(
    (l) =>
      l.valid &&
      (!!l.controls.item.value ||
        (allowText && !!l.controls.description.value?.trim())),
  );
}
