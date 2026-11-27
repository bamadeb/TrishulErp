import { InjectionToken } from '@angular/core';

/** A side-menu entry. Hidden unless the user holds one of `permissions` (when given). */
export interface NavItem {
  label: string;
  /** Material Symbols name, e.g. 'build'. Shown beside the label (group header or item). */
  icon?: string;
  route?: string;
  permissions?: string[];
  /** Hide this entry when the user already has one of these (a wider role). */
  excludePermissions?: string[];
  children?: NavItem[];
}

export const NAV_ITEMS = new InjectionToken<NavItem[]>('NAV_ITEMS');
