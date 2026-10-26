import { Injectable, inject } from '@angular/core';
import { Amplify } from 'aws-amplify';
import {
  confirmResetPassword,
  confirmSignIn,
  fetchAuthSession,
  getCurrentUser,
  resetPassword,
  signIn,
  signOut,
  type SignInOutput,
} from 'aws-amplify/auth';
import { cognitoUserPoolsTokenProvider } from 'aws-amplify/auth/cognito';
import { sessionStorage } from 'aws-amplify/utils';
import { Observable, catchError, from, map, of } from 'rxjs';
import { APP_CONFIG } from '@trishul/core-config';
import { AuthError, AuthSession, SignInStep } from '../auth-session';

/**
 * Cognito user pool through AWS Amplify. Passwords are checked with SRP, so the password itself
 * is never sent. Tokens live in sessionStorage: closing the tab signs the user out.
 */
@Injectable()
export class CognitoAuthSession extends AuthSession {
  readonly usesPassword = true;

  constructor() {
    super();
    const { auth } = inject(APP_CONFIG);
    Amplify.configure({
      Auth: {
        Cognito: {
          userPoolId: auth.userPoolId,
          userPoolClientId: auth.userPoolClientId,
          loginWith: { username: true, email: true },
        },
      },
    });
    cognitoUserPoolsTokenProvider.setKeyValueStorage(sessionStorage);
  }

  async restore(): Promise<boolean> {
    try {
      await getCurrentUser();
      return true;
    } catch {
      return false;
    }
  }

  accessToken(): Observable<string | null> {
    // fetchAuthSession refreshes an expired access token with the refresh token.
    return from(fetchAuthSession()).pipe(
      map((session) => session.tokens?.accessToken.toString() ?? null),
      catchError(() => of(null)),
    );
  }

  signIn(username: string, password: string): Promise<SignInStep> {
    return attempt(async () =>
      nextStep(
        await signIn({
          username: username.trim(),
          password,
          options: { authFlowType: 'USER_SRP_AUTH' },
        }),
      ),
    );
  }

  completeNewPassword(newPassword: string): Promise<SignInStep> {
    return attempt(async () =>
      nextStep(await confirmSignIn({ challengeResponse: newPassword })),
    );
  }

  confirmMfaCode(code: string): Promise<SignInStep> {
    return attempt(async () =>
      nextStep(await confirmSignIn({ challengeResponse: code.trim() })),
    );
  }

  sendPasswordResetCode(username: string): Promise<string> {
    return attempt(async () => {
      const result = await resetPassword({ username: username.trim() });
      return (
        result.nextStep.codeDeliveryDetails.destination ??
        'your registered contact'
      );
    });
  }

  resetPassword(
    username: string,
    code: string,
    newPassword: string,
  ): Promise<void> {
    return attempt(() =>
      confirmResetPassword({
        username: username.trim(),
        confirmationCode: code.trim(),
        newPassword,
      }),
    );
  }

  async signOut(): Promise<void> {
    await signOut();
  }
}

function nextStep(output: SignInOutput): SignInStep {
  const step = output.nextStep.signInStep;
  switch (step) {
    case 'DONE':
      return 'done';
    case 'CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED':
      return 'new-password';
    case 'CONFIRM_SIGN_IN_WITH_TOTP_CODE':
    case 'CONFIRM_SIGN_IN_WITH_SMS_CODE':
    case 'CONFIRM_SIGN_IN_WITH_EMAIL_CODE':
      return 'mfa-code';
    default:
      throw new AuthError(
        `This account needs a sign-in step the ERP doesn't support yet (${step}). Contact your administrator.`,
      );
  }
}

async function attempt<T>(action: () => Promise<T>): Promise<T> {
  try {
    return await action();
  } catch (error) {
    throw toAuthError(error);
  }
}

/** Cognito errors as messages for the login page. Unknown users get the same message as a wrong
 * password, so the page doesn't reveal which usernames exist. */
export function toAuthError(error: unknown): AuthError {
  if (error instanceof AuthError) return error;
  const { name, message } = (error ?? {}) as {
    name?: string;
    message?: string;
  };
  switch (name) {
    case 'NotAuthorizedException':
      return new AuthError(
        message?.toLowerCase().includes('attempts exceeded')
          ? 'Too many failed attempts. Wait a few minutes, then try again.'
          : 'Incorrect username or password.',
      );
    case 'UserNotFoundException':
      return new AuthError('Incorrect username or password.');
    case 'PasswordResetRequiredException':
      return new AuthError(
        'Your password has to be reset. Use "Forgot password?" below.',
      );
    case 'UserNotConfirmedException':
      return new AuthError(
        'Your account is not activated yet. Contact your administrator.',
      );
    case 'CodeMismatchException':
      return new AuthError('That code is not correct. Check it and try again.');
    case 'ExpiredCodeException':
      return new AuthError('That code has expired. Request a new one.');
    case 'InvalidPasswordException':
      return new AuthError(
        message ?? 'The new password does not meet the password rules.',
      );
    case 'LimitExceededException':
    case 'TooManyRequestsException':
      return new AuthError(
        'Too many attempts. Wait a few minutes, then try again.',
      );
    default:
      return new AuthError(
        'Sign-in failed. Check your connection and try again.',
      );
  }
}
