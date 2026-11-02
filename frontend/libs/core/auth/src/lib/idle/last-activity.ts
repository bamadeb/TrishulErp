/**
 * Time of the user's last input, shared by every tab through localStorage, so working in one tab
 * keeps the others signed in too. Storage can be blocked (private windows); then each tab keeps
 * its own time.
 */
const STORAGE_KEY = 'trishul.lastActivity';

export function readLastActivity(): number | null {
  try {
    const value = Number(localStorage.getItem(STORAGE_KEY));
    return value > 0 ? value : null;
  } catch {
    return null;
  }
}

export function recordActivity(at = Date.now()): void {
  try {
    localStorage.setItem(STORAGE_KEY, String(at));
  } catch {
    // storage blocked: this tab still tracks its own time
  }
}

export function clearLastActivity(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // nothing stored
  }
}
