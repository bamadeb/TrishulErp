import { InjectionToken } from '@angular/core';

/** A side-menu entry. Hidden unless the user holds one of `permissions` (when given). */
export interface NavItem {
  label: string;
  /** Material Symbols name, e.g. 'build'. Shown for top-level entries. */
  icon?: string;
  route?: string;
  permissions?: string[];
  children?: NavItem[];
}

export const NAV_ITEMS = new InjectionToken<NavItem[]>('NAV_ITEMS');
