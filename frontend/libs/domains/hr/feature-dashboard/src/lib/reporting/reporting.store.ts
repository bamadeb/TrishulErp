import { Injectable, signal } from '@angular/core';
import { ReportingPerson } from '@trishul/hr-data-access';

/** Employees loaded from the reporting API. Assignments are saved on the server. */
@Injectable({ providedIn: 'root' })
export class ReportingDemoStore {
  readonly people = signal<ReportingPerson[]>([]);

  replace(rows: ReportingPerson[]): void {
    this.people.set(rows.map((person) => ({ ...person })));
  }
}

/** Direct-report count at which a manager card is marked. */
export const WIDE_SPAN = 8;

/** True when a date-only value is after the local calendar day. */
export function laterThanToday(value: string | null | undefined): boolean {
  if (!value) return false;
  const today = new Date();
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');
  return value.slice(0, 10) > `${today.getFullYear()}-${month}-${day}`;
}

/** True when walking upward from `startId` reaches `targetId`. */
export function reportsThrough(rows: readonly ReportingPerson[], startId: number, targetId: number): boolean {
  const seen = new Set<number>();
  let current: number | null = startId;
  while (current !== null) {
    if (current === targetId) return true;
    if (seen.has(current)) return true;
    seen.add(current);
    current = rows.find((person) => person.id === current)?.managerId ?? null;
  }
  return false;
}
