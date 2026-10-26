import { HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Router } from '@angular/router';
import { AuthError, AuthSession, SignInStep } from './auth-session';
import { AuthStore } from './auth.store';

/**
 * Sign-in flows for the app: the identity provider (AuthSession), then the ERP user (AuthStore),
 * then navigation. The login page, the shell and the HTTP interceptor use this.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly session = inject(AuthSession);
  private readonly store = inject(AuthStore);
  private readonly router = inject(Router);

  /** False for development sign-in (username only). */
  readonly usesPassword = this.session.usesPassword;

  /** At startup: resume a session from earlier in this tab, if it is still valid. */
  async restore(): Promise<void> {
    if (!(await this.session.restore())) return;
    try {
      await this.store.loadCurrentUser();
    } catch {
      await this.discard(); // the login page will explain on the next attempt
    }
  }

  async signIn(username: string, password: string): Promise<SignInStep> {
    return this.finish(await this.session.signIn(username, password));
  }

  async completeNewPassword(newPassword: string): Promise<SignInStep> {
    return this.finish(await this.session.completeNewPassword(newPassword));
  }

  async confirmMfaCode(code: string): Promise<SignInStep> {
    return this.finish(await this.session.confirmMfaCode(code));
  }

  sendPasswordResetCode(username: string): Promise<string> {
    return this.session.sendPasswordResetCode(username);
  }

  resetPassword(
    username: string,
    code: string,
    newPassword: string,
  ): Promise<void> {
    return this.session.resetPassword(username, code, newPassword);
  }

  async signOut(): Promise<void> {
    await this.discard();
    await this.router.navigateByUrl('/login');
  }

  /** The API rejected the session (401): sign in again, then return to returnUrl. */
  async expire(returnUrl: string): Promise<void> {
    await this.discard();
    await this.router.navigate(['/login'], {
      queryParams: { returnUrl, expired: 1 },
    });
  }

  private async finish(step: SignInStep): Promise<SignInStep> {
    if (step !== 'done') return step;
    try {
      await this.store.loadCurrentUser();
    } catch (error) {
      await this.discard();
      throw describeUserLoadError(error);
    }
    return step;
  }

  private async discard(): Promise<void> {
    try {
      await this.session.signOut();
    } finally {
      this.store.clear();
    }
  }
}

function describeUserLoadError(error: unknown): AuthError {
  if (error instanceof HttpErrorResponse && error.status === 403) {
    return new AuthError(
      'Your account is not set up in Trishul ERP, or it is locked. Contact your administrator.',
    );
  }
  if (error instanceof HttpErrorResponse && error.status === 0) {
    return new AuthError(
      'The server could not be reached. Check your connection.',
    );
  }
  return new AuthError('Your account could not be loaded. Try again.');
}
