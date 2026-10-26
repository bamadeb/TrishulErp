import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';
import { readStorage, writeStorage } from '@trishul/shared-util';
import { AuthError, AuthSession, SignInStep } from '../auth-session';

const TOKEN_KEY = 'trishul.devToken';

/**
 * Local development: sign in as any ERP username, without a password. The token "dev:<username>"
 * is accepted only by an API running with TRISHUL_AUTH_MODE=dev (refused in UAT and production).
 */
@Injectable()
export class DevAuthSession extends AuthSession {
  readonly usesPassword = false;

  async restore(): Promise<boolean> {
    return readStorage('session', TOKEN_KEY) !== null;
  }

  accessToken(): Observable<string | null> {
    return of(readStorage('session', TOKEN_KEY));
  }

  async signIn(username: string): Promise<SignInStep> {
    const name = username.trim();
    if (!name) throw new AuthError('Enter a username.');
    writeStorage('session', TOKEN_KEY, `dev:${name}`);
    return 'done';
  }

  async completeNewPassword(): Promise<SignInStep> {
    throw new AuthError('Development sign-in has no passwords.');
  }

  async confirmMfaCode(): Promise<SignInStep> {
    throw new AuthError('Development sign-in has no MFA.');
  }

  async sendPasswordResetCode(): Promise<string> {
    throw new AuthError('Development sign-in has no passwords.');
  }

  async resetPassword(): Promise<void> {
    throw new AuthError('Development sign-in has no passwords.');
  }

  async signOut(): Promise<void> {
    writeStorage('session', TOKEN_KEY, null);
  }
}
