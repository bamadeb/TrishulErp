import { HttpContext, HttpContextToken } from '@angular/common/http';

/** The record's row_version (base64), sent as If-Match so the API can reject stale updates. */
export const ROW_VERSION = new HttpContextToken<string | null>(() => null);

/** Set when the caller shows its own error message instead of the global toast. */
export const SKIP_ERROR_TOAST = new HttpContextToken<boolean>(() => false);

/** Context for an update of a record loaded with the given row_version. */
export function withRowVersion(
  rowVersion: string,
  context = new HttpContext(),
): HttpContext {
  return context.set(ROW_VERSION, rowVersion);
}

/** Context for a call whose errors the caller reports itself. */
export function withoutErrorToast(context = new HttpContext()): HttpContext {
  return context.set(SKIP_ERROR_TOAST, true);
}
