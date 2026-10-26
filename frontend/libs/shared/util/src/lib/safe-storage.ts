/**
 * localStorage / sessionStorage that never throws. Storage can be blocked (private windows,
 * site-data settings); callers then simply don't remember the value.
 */
export type StorageKind = 'local' | 'session';

function storage(kind: StorageKind): Storage {
  return kind === 'local' ? localStorage : sessionStorage;
}

export function readStorage(kind: StorageKind, key: string): string | null {
  try {
    return storage(kind).getItem(key);
  } catch {
    return null;
  }
}

/** Stores the value; null removes the key. */
export function writeStorage(
  kind: StorageKind,
  key: string,
  value: string | null,
): void {
  try {
    if (value === null) storage(kind).removeItem(key);
    else storage(kind).setItem(key, value);
  } catch {
    // Not remembered; nothing else to do.
  }
}
