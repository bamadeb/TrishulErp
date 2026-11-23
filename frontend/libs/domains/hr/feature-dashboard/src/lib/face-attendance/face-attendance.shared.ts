import { StatusSeverity } from '@trishul/shared-ui';

export const FACE_STATUS_SEVERITIES: Partial<Record<string, StatusSeverity>> = {
  Active: 'success',
  'Pending approval': 'warn',
  Rejected: 'danger',
  'Not registered': 'neutral',
  Superseded: 'neutral',
  Deleted: 'neutral',
};

export const PUNCH_STATUS_SEVERITIES: Partial<Record<string, StatusSeverity>> =
  {
    Present: 'success',
    Pending: 'warn',
    Rejected: 'danger',
  };

/** Today's date in India as yyyy-mm-dd (attendance days are Indian days). */
export function indiaToday(): string {
  return new Date(Date.now() + 5.5 * 3600 * 1000).toISOString().slice(0, 10);
}

/** A Google Maps link to a point. */
export function mapLink(
  lat: number | string | null,
  lng: number | string | null,
): string | null {
  return lat == null || lng == null || lat === '' || lng === ''
    ? null
    : `https://www.google.com/maps?q=${lat},${lng}`;
}
