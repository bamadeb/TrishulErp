/** Live working duration for attendance (Asia/Kolkata), session-aware. */

const IST = 'Asia/Kolkata';

/** Current clock reading in Asia/Kolkata as a Date (absolute instant). */
export function nowInKolkata(): Date {
  return new Date();
}

/**
 * Build the punch-in instant from a calendar day + punch clock value.
 * Accepts API `HH:mm`, `h:mm AM/PM`, or a full ISO datetime.
 */
export function punchInAt(dateIso: string | null | undefined, firstIn: string | null | undefined): Date | null {
  if (!firstIn?.trim()) return null;
  const raw = firstIn.trim();
  if (raw.includes('T') || /^\d{4}-\d{2}-\d{2}/.test(raw)) {
    const parsed = new Date(raw.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(raw) ? raw : `${raw}+05:30`);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }
  if (!dateIso) return null;
  const day = dateIso.slice(0, 10);
  const ampm = raw.match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
  let hour: number;
  let minute: number;
  if (ampm) {
    hour = Number(ampm[1]);
    minute = Number(ampm[2]);
    const meridiem = ampm[3]!.toUpperCase();
    if (meridiem === 'PM' && hour < 12) hour += 12;
    if (meridiem === 'AM' && hour === 12) hour = 0;
  } else {
    const hm = raw.match(/^(\d{1,2}):(\d{2})$/);
    if (!hm) return null;
    hour = Number(hm[1]);
    minute = Number(hm[2]);
  }
  if (hour > 23 || minute > 59) return null;
  const iso = `${day}T${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}:00+05:30`;
  const at = new Date(iso);
  return Number.isNaN(at.getTime()) ? null : at;
}

/** Format minutes as `2h 14m` / `0h 50m`, matching the attendance board. */
export function formatWorkedMinutes(minutes: number): string | null {
  if (minutes < 0) return null;
  if (minutes === 0) return '0h 00m';
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hours}h ${String(mins).padStart(2, '0')}m`;
}

/** Elapsed working duration from punch-in to `now` (default: current IST instant). */
export function liveWorkingHours(
  dateIso: string | null | undefined,
  firstIn: string | null | undefined,
  now: Date = nowInKolkata(),
): string | null {
  const start = punchInAt(dateIso, firstIn);
  if (!start) return null;
  const minutes = Math.max(0, Math.floor((now.getTime() - start.getTime()) / 60_000));
  return formatWorkedMinutes(minutes);
}

/**
 * Session-aware display: closed IN–OUT minutes + live open IN elapsed.
 * Prefer this on Daily Attendance / Punch Logs so mid-day re-IN does not count break time.
 */
export function displaySessionWorkingHours(opts: {
  closedWorkedMinutes?: number | null;
  openInAt?: string | null;
  frozenHours?: string | null;
  workingHoursDetail?: string | null;
  now?: Date;
}): { total: string; detail: string | null } {
  const now = opts.now ?? nowInKolkata();
  const closed = Math.max(0, opts.closedWorkedMinutes ?? 0);
  const openAt = opts.openInAt ? punchInAt(null, opts.openInAt) : null;
  if (openAt) {
    const live = Math.max(0, Math.floor((now.getTime() - openAt.getTime()) / 60_000));
    const totalMins = closed + live;
    const total = formatWorkedMinutes(totalMins) ?? '0h 00m';
    const closedLabel = formatWorkedMinutes(closed);
    const liveLabel = formatWorkedMinutes(live) ?? '0h 00m';
    const detail =
      closed > 0 && closedLabel ? `${closedLabel} + ${liveLabel}` : opts.workingHoursDetail ?? null;
    return { total, detail };
  }
  return {
    total: opts.frozenHours?.trim() || formatWorkedMinutes(closed) || '—',
    detail: opts.workingHoursDetail ?? null,
  };
}

/**
 * Display hours: live ticker while still punched in (legacy status In Progress,
 * or Present/Late with no last out on today); frozen after punch-out.
 */
export function displayWorkingHours(
  status: string | null | undefined,
  dateIso: string | null | undefined,
  firstIn: string | null | undefined,
  frozenHours: string | null | undefined,
  now: Date = nowInKolkata(),
  lastOut?: string | null,
): string {
  const stillIn =
    status === 'In Progress' ||
    ((status === 'Present' || status === 'Late') &&
      !lastOut?.trim() &&
      !!dateIso &&
      dateIso.slice(0, 10) === kolkataTodayIso(now));
  if (stillIn) {
    return liveWorkingHours(dateIso, firstIn, now) ?? frozenHours ?? '—';
  }
  return frozenHours?.trim() || '—';
}

/** Kolkata calendar date `YYYY-MM-DD` for "today" (for filtering In Progress rows). */
export function kolkataTodayIso(now: Date = nowInKolkata()): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: IST,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now);
}
