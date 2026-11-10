import { lineAmounts, rupees } from './purchases.shared';

describe('purchases helpers', () => {
  it('computes a line like the server: discount first, then GST, to the paisa', () => {
    // 10 x 1000 less 10% = 9000; 18% GST = 1620 (backend test_purchases_api uses the same order).
    expect(lineAmounts(10, 1000, 10, 18)).toEqual({ taxable: 9000, tax: 1620, total: 10620 });
    expect(lineAmounts(3, 333.33, 0, 18)).toEqual({ taxable: 999.99, tax: 180, total: 1179.99 });
    expect(lineAmounts(null, 5, null, null)).toEqual({ taxable: 0, tax: 0, total: 0 });
  });

  it('shows rupees with Indian grouping', () => {
    expect(rupees('155030.5')).toBe('₹1,55,030.50');
    expect(rupees(null)).toBe('—');
  });
});
