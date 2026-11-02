import { Injectable, inject, signal } from '@angular/core';
import { MatDialog, MatDialogRef } from '@angular/material/dialog';
import { Router } from '@angular/router';
import { APP_CONFIG } from '@trishul/core-config';
import { AuthService } from '../auth.service';
import { IdleWarningData, IdleWarningDialog } from './idle-warning.dialog';
import { readLastActivity, recordActivity } from './last-activity';

const DEFAULT_IDLE_MINUTES = 30;
const WARNING_MS = 60_000;
const CHECK_MS = 1_000;
/** Writing to storage on every mouse move would be wasteful; a few seconds of slack is fine. */
const RECORD_EVERY_MS = 5_000;
const ACTIVITY_EVENTS = [
  'pointerdown',
  'pointermove',
  'keydown',
  'wheel',
  'touchstart',
  'scroll',
] as const;

/**
 * Signs the user out after a spell with no mouse, keyboard or touch input (config
 * auth.idleTimeoutMinutes), with a one-minute warning first. Background requests such as the
 * alert bell's polling do not count as activity. Started by the shell while someone is signed in.
 */
@Injectable({ providedIn: 'root' })
export class IdleTimeout {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly dialog = inject(MatDialog);
  private readonly limitMs =
    (inject(APP_CONFIG).auth.idleTimeoutMinutes ?? DEFAULT_IDLE_MINUTES) *
    60_000;

  private readonly secondsLeft = signal(0);
  private lastActivity = 0;
  private lastRecorded = 0;
  private warning: MatDialogRef<IdleWarningDialog, boolean> | null = null;
  private timer: ReturnType<typeof setInterval> | undefined;

  /** Starts watching; returns the function that stops it. */
  start(): () => void {
    if (this.limitMs <= 0 || this.timer) return () => undefined;
    // A session resumed from storage (browser reopened, laptop woken) after the limit ends at once.
    // No stored time means a session from before this feature: count from now.
    const stored = readLastActivity();
    this.lastActivity = stored ?? Date.now();
    if (!stored) recordActivity(this.lastActivity);
    this.lastRecorded = this.lastActivity;

    const options = { capture: true, passive: true };
    for (const type of ACTIVITY_EVENTS) {
      document.addEventListener(type, this.onActivity, options);
    }
    this.timer = setInterval(() => this.check(), CHECK_MS);
    this.check();
    return () => this.stop();
  }

  private stop(): void {
    clearInterval(this.timer);
    this.timer = undefined;
    for (const type of ACTIVITY_EVENTS) {
      document.removeEventListener(type, this.onActivity, { capture: true });
    }
    this.warning?.close();
    this.warning = null;
  }

  private readonly onActivity = (): void => {
    // Once the warning is up, only "Stay signed in" counts: a stray mouse move should not
    // silently cancel it.
    if (this.warning) return;
    this.markActive(Date.now());
  };

  private markActive(now: number): void {
    this.lastActivity = now;
    if (now - this.lastRecorded >= RECORD_EVERY_MS) {
      this.lastRecorded = now;
      recordActivity(now);
    }
  }

  private check(): void {
    const now = Date.now();
    const last = Math.max(this.lastActivity, readLastActivity() ?? 0);
    const remaining = this.limitMs - (now - last);
    if (remaining <= 0) {
      this.stop();
      void this.auth.expire(this.router.url, 'idle');
      return;
    }
    this.secondsLeft.set(Math.ceil(remaining / 1000));
    if (remaining <= WARNING_MS) {
      this.openWarning();
    } else if (this.warning) {
      // Activity in another tab.
      this.lastActivity = last;
      this.warning.close();
    }
  }

  private openWarning(): void {
    if (this.warning) return;
    const ref = this.dialog.open<IdleWarningDialog, IdleWarningData, boolean>(
      IdleWarningDialog,
      {
        data: { secondsLeft: this.secondsLeft.asReadonly() },
        width: '26rem',
        disableClose: true,
        autoFocus: 'dialog',
      },
    );
    this.warning = ref;
    ref.afterClosed().subscribe((stay) => {
      if (this.warning === ref) this.warning = null;
      if (stay) {
        this.lastRecorded = 0;
        this.markActive(Date.now());
      } else if (stay === false) {
        this.stop();
        void this.auth.signOut();
      }
    });
  }
}
