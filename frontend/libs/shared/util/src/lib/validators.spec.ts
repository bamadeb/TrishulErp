import { FormControl } from '@angular/forms';
import { TrishulValidators } from './validators';

describe('TrishulValidators', () => {
  const check = (validator: keyof typeof TrishulValidators, value: string) =>
    TrishulValidators[validator](new FormControl(value));

  it('accepts valid Indian identifiers', () => {
    expect(check('gstin', '27AAPFU0939F1ZV')).toBeNull();
    expect(check('pan', 'aapfu0939f')).toBeNull();
    expect(check('pincode', '411001')).toBeNull();
    expect(check('mobile', '+919876543210')).toBeNull();
  });

  it('rejects malformed values', () => {
    expect(check('gstin', '27AAPFU0939F1V')).toEqual({ gstin: true });
    expect(check('pincode', '011001')).toEqual({ pincode: true });
    expect(check('mobile', '5876543210')).toEqual({ mobile: true });
  });

  it('leaves empty values to Validators.required', () => {
    expect(check('pan', '')).toBeNull();
  });
});
