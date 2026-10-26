import { Observable } from 'rxjs';

/** What the user must do next to finish signing in. */
export type SignInStep = 'done' | 'new-password' | 'mfa-code';

/** A sign-in problem with a message that can be shown to the user as it is. */
export class AuthError extends Error {
  override readonly name = 'AuthError';
}

/**
 * Credentials and tokens for one identity provider. The app uses AuthService, which adds loading
 * the ERP user and navigation; only AuthService and the HTTP interceptor talk to a session.
 */
export abstract class AuthSession {
  /** False for development sign-in, which needs only a username. */
  abstract readonly usesPassword: boolean;

  /** Resumes a session kept from earlier in this browser tab; true if one is still valid. */
  abstract restore(): Promise<boolean>;

  /** The access token for API calls, refreshed when needed; null when signed out. */
  abstract accessToken(): Observable<string | null>;

  abstract signIn(username: string, password: string): Promise<SignInStep>;

  /** First sign-in with a temporary password: choose the permanent one. */
  abstract completeNewPassword(newPassword: string): Promise<SignInStep>;

  abstract confirmMfaCode(code: string): Promise<SignInStep>;

  /** Sends a reset code; resolves to where it went, e.g. "r***@t***.com". */
  abstract sendPasswordResetCode(username: string): Promise<string>;

  abstract resetPassword(
    username: string,
    code: string,
    newPassword: string,
  ): Promise<void>;

  abstract signOut(): Promise<void>;
}
