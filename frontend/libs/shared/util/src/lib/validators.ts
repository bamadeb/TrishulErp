import { AbstractControl, ValidationErrors, ValidatorFn } from '@angular/forms';

function pattern(name: string, regex: RegExp): ValidatorFn {
  return (control: AbstractControl): ValidationErrors | null => {
    const value = control.value as string | null;
    return !value || regex.test(value.trim().toUpperCase())
      ? null
      : { [name]: true };
  };
}

/** Indian validators for master-data forms. Empty values pass; combine with Validators.required. */
export const TrishulValidators = {
  /** 15 characters: state code, PAN, entity number, 'Z', check digit. */
  gstin: pattern('gstin', /^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/),
  pan: pattern('pan', /^[A-Z]{5}\d{4}[A-Z]$/),
  pincode: pattern('pincode', /^[1-9]\d{5}$/),
  /** 10-digit Indian mobile number, optionally prefixed with +91 or 0. */
  mobile: pattern('mobile', /^(\+91|0)?[6-9]\d{9}$/),
} as const;
