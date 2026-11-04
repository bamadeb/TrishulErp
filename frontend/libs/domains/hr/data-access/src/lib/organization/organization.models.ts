/** Organization Management sections. Grades and hierarchy are columns, not their own tables. */
export type OrgTabId =
  | 'departments'
  | 'designations'
  | 'grades'
  | 'locations'
  | 'companies'
  | 'hierarchy';

export type OrgStatus = 'active' | 'inactive' | 'all';

/** List query shared by every organization section. Page is 1-based, matching the API. */
export interface OrgQuery {
  page: number;
  pageSize: number;
  search: string;
  status: OrgStatus;
}

/** Totals for the five dashboard cards. Companies are a tab, not a card. */
export interface OrgCounts {
  departments: number;
  designations: number;
  grades: number;
  locations: number;
  hierarchy: number;
}

/** Change organization masters. The API checks the same code. */
export const ORGANIZATION_MANAGE_PERMISSION = 'hr.organization.manage';
