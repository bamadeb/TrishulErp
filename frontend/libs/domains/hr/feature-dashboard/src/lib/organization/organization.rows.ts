import { OrgSnapshot } from '@trishul/hr-data-access';

const TONES = ['#7c6bf2', '#3cb58a', '#e07a3d', '#3b82c4', '#d45d8c', '#0f9f8f', '#c47b2b', '#6b5bd6'];

export interface OrgRow {
  key: string;
  id: number | string;
  code: string;
  name: string;
  head: string;
  initials: string;
  tone: string;
  employees: number;
  status: string;
  extra: string;
  active: boolean;
  /** Departments, designations, locations and companies. */
  canToggle: boolean;
}

export function toRows(snapshot: OrgSnapshot): OrgRow[] {
  switch (snapshot.tab) {
    case 'departments':
      return snapshot.items.map((row) =>
        personRow(row.id, row.code, row.name, row.headName ?? '', row.employeeCount, row.isActive, '', true),
      );
    case 'designations':
      return snapshot.items.map((row) =>
        personRow(
          row.id,
          row.code,
          row.name,
          row.grade ?? '',
          row.employeeCount,
          row.isActive,
          row.departmentName ?? '',
          true,
        ),
      );
    case 'grades':
      return snapshot.items.map((row) => ({
        key: `grade:${row.grade}`,
        id: row.grade,
        code: row.grade,
        name: `${row.designationCount} designations`,
        head: '',
        initials: '',
        tone: tone(row.grade),
        employees: row.employeeCount,
        status: '',
        extra: '',
        active: true,
        canToggle: false,
      }));
    case 'locations':
      return snapshot.items.map((row) =>
        personRow(
          row.id,
          row.code,
          row.name,
          row.stateName ?? '',
          row.employeeCount,
          row.isActive,
          row.branchType,
          true,
        ),
      );
    case 'companies':
      return snapshot.items.map((row) =>
        personRow(
          row.id,
          row.code,
          row.legalName,
          row.tradeName ?? '',
          row.employeeCount,
          row.isActive,
          '',
          true,
        ),
      );
    case 'hierarchy':
      return snapshot.items.map((row) =>
        personRow(
          row.id,
          row.employeeCode,
          row.fullName,
          row.reportingManagerName ?? '',
          row.directReportCount,
          row.isActive,
          '',
          false,
          row.isActive ? row.status : 'Inactive',
        ),
      );
  }
}

function personRow(
  id: number,
  code: string,
  name: string,
  head: string,
  employees: number,
  active: boolean,
  extra: string,
  canToggle: boolean,
  status = active ? 'Active' : 'Inactive',
): OrgRow {
  return {
    key: String(id),
    id,
    code,
    name,
    head,
    initials: initials(head),
    tone: tone(head || code),
    employees,
    status,
    extra,
    active,
    canToggle,
  };
}

function initials(value: string): string {
  const parts = value.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] ?? ''}${parts[1][0] ?? ''}`.toUpperCase();
}

function tone(value: string): string {
  let hash = 0;
  for (const char of value) hash = (hash + char.charCodeAt(0)) % TONES.length;
  return TONES[hash] ?? TONES[0];
}
