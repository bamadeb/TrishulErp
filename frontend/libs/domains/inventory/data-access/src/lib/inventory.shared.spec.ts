import {
  ageClass,
  ageText,
  fromIso,
  isoDate,
  n0,
  num,
} from './inventory.shared';

describe('inventory helpers', () => {
  it('colours ages in the same buckets as the ageing report', () => {
    // 0-30, 31-60, 61-90, 91-180, above 180 days (backend: stock_schemas.AGEING_BUCKETS).
    expect([0, 30, 31, 60, 61, 90, 91, 180, 181, 900].map(ageClass)).toEqual([
      'b0',
      'b0',
      'b1',
      'b1',
      'b2',
      'b2',
      'b3',
      'b3',
      'b4',
      'b4',
    ]);
  });

  it('reads API decimals sent as strings', () => {
    expect(num('12.500')).toBe(12.5);
    expect(num(null)).toBeNull();
    expect(num('')).toBeNull();
    expect(n0(undefined)).toBe(0);
    expect(n0('-2.000')).toBe(-2);
  });

  it('round-trips local dates as yyyy-mm-dd', () => {
    const day = fromIso('2026-03-09');
    expect(day?.getDate()).toBe(9);
    expect(isoDate(day as Date)).toBe('2026-03-09');
    expect(fromIso(null)).toBeNull();
  });
});

describe('ageText', () => {
  it('counts whole years, then months, then days from the GRN date', () => {
    expect(ageText('2025-10-15', new Date(2026, 10, 27))).toBe(
      '1 year 1 month 12 days',
    );
    expect(ageText('2024-11-27', new Date(2026, 10, 27))).toBe('2 years');
    expect(ageText('2026-11-10', new Date(2026, 10, 27))).toBe('17 days');
    expect(ageText('2026-11-27', new Date(2026, 10, 27))).toBe('0 days');
  });

  it('caps the day at the end of a shorter month', () => {
    expect(ageText('2025-01-31', new Date(2025, 1, 28))).toBe('1 month');
    expect(ageText('2025-01-31', new Date(2025, 2, 1))).toBe('1 month 1 day');
    expect(ageText('2024-02-29', new Date(2025, 1, 28))).toBe('1 year');
  });
});
