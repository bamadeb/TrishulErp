import { TestBed } from '@angular/core/testing';
import { MatDialog } from '@angular/material/dialog';
import { Router } from '@angular/router';
import { APP_CONFIG, AppConfig } from '@trishul/core-config';
import { Subject } from 'rxjs';
import { AuthService } from '../auth.service';
import { IdleTimeout } from './idle-timeout';
import { readLastActivity, recordActivity } from './last-activity';

const MINUTE = 60_000;

describe('IdleTimeout', () => {
  let auth: { expire: ReturnType<typeof vi.fn>; signOut: ReturnType<typeof vi.fn> };
  let dialog: { open: ReturnType<typeof vi.fn> };
  let closed: Subject<boolean | undefined>;
  let close: ReturnType<typeof vi.fn>;
  let stop: () => void;

  function startWith(idleTimeoutMinutes?: number): void {
    const config = {
      auth: { mode: 'dev', userPoolId: '', userPoolClientId: '', idleTimeoutMinutes },
    } as AppConfig;
    TestBed.configureTestingModule({
      providers: [
        { provide: APP_CONFIG, useValue: config },
        { provide: AuthService, useValue: auth },
        { provide: MatDialog, useValue: dialog },
        { provide: Router, useValue: { url: '/service/calls' } },
      ],
    });
    stop = TestBed.inject(IdleTimeout).start();
  }

  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
    auth = { expire: vi.fn().mockResolvedValue(undefined), signOut: vi.fn() };
    closed = new Subject();
    close = vi.fn(() => closed.next(undefined));
    dialog = {
      open: vi.fn(() => ({ afterClosed: () => closed, close })),
    };
  });

  afterEach(() => {
    stop();
    vi.useRealTimers();
  });

  it('warns a minute before the limit and signs out at the limit', () => {
    startWith(30);
    vi.advanceTimersByTime(28 * MINUTE);
    expect(dialog.open).not.toHaveBeenCalled();

    vi.advanceTimersByTime(MINUTE + 1000);
    expect(dialog.open).toHaveBeenCalledTimes(1);
    expect(auth.expire).not.toHaveBeenCalled();

    vi.advanceTimersByTime(MINUTE);
    expect(auth.expire).toHaveBeenCalledWith('/service/calls', 'idle');
  });

  it('keeps the session while the user is active', () => {
    startWith(30);
    for (let i = 0; i < 4; i++) {
      vi.advanceTimersByTime(20 * MINUTE);
      document.dispatchEvent(new KeyboardEvent('keydown'));
    }
    vi.advanceTimersByTime(20 * MINUTE);
    expect(auth.expire).not.toHaveBeenCalled();
    expect(readLastActivity()).toBeGreaterThan(0);
  });

  it('"Stay signed in" restarts the clock', () => {
    startWith(30);
    vi.advanceTimersByTime(29.5 * MINUTE);
    expect(dialog.open).toHaveBeenCalledTimes(1);

    closed.next(true);
    vi.advanceTimersByTime(20 * MINUTE);
    expect(auth.expire).not.toHaveBeenCalled();
  });

  it('activity in another tab closes the warning', () => {
    startWith(30);
    vi.advanceTimersByTime(29.5 * MINUTE);
    recordActivity(Date.now());
    vi.advanceTimersByTime(1000);
    expect(close).toHaveBeenCalled();
    expect(auth.expire).not.toHaveBeenCalled();
  });

  it('ends a session resumed after the limit straight away', () => {
    recordActivity(Date.now() - 2 * 60 * MINUTE);
    startWith(30);
    expect(auth.expire).toHaveBeenCalledWith('/service/calls', 'idle');
  });

  it('does nothing when turned off', () => {
    startWith(0);
    vi.advanceTimersByTime(24 * 60 * MINUTE);
    expect(dialog.open).not.toHaveBeenCalled();
    expect(auth.expire).not.toHaveBeenCalled();
  });
});
