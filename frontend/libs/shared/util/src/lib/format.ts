import { Pipe, PipeTransform } from '@angular/core';

const inr = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
});

/** 1234567.5 -> "₹12,34,567.50" (Indian digit grouping). */
export function formatInr(amount: number | null | undefined): string {
  return amount === null || amount === undefined ? '' : inr.format(amount);
}

@Pipe({ name: 'inr' })
export class InrPipe implements PipeTransform {
  transform(amount: number | null | undefined): string {
    return formatInr(amount);
  }
}
