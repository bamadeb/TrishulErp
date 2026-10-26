import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router } from '@angular/router';
import { catchError, switchMap, take, throwError } from 'rxjs';
import {
  ProblemDetails,
  ROW_VERSION,
  SKIP_ERROR_TOAST,
} from '@trishul/core-api';
import { AuthService, AuthSession, AuthStore } from '@trishul/core-auth';
import { APP_CONFIG } from '@trishul/core-config';

function isApiCall(url: string): boolean {
  return url.startsWith(inject(APP_CONFIG).apiBaseUrl);
}

/** Adds the Cognito access token to API calls. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  if (!isApiCall(req.url)) return next(req);
  return inject(AuthSession)
    .accessToken()
    .pipe(
      take(1),
      switchMap((token) =>
        next(
          token
            ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
            : req,
        ),
      ),
    );
};

/**
 * Sends the selected branch and brand. The API turns these into SESSION_CONTEXT
 * values, which the row-level security policy filters on.
 */
export const contextInterceptor: HttpInterceptorFn = (req, next) => {
  if (!isApiCall(req.url)) return next(req);
  const store = inject(AuthStore);
  const headers: Record<string, string> = {};
  const branchId = store.branchId();
  const principalId = store.principalId();
  if (branchId !== null) headers['X-Branch-Id'] = String(branchId);
  if (principalId !== null) headers['X-Principal-Id'] = String(principalId);
  return next(req.clone({ setHeaders: headers }));
};

/** Optimistic concurrency: forwards the record's row_version as If-Match. */
export const rowVersionInterceptor: HttpInterceptorFn = (req, next) => {
  const rowVersion = req.context.get(ROW_VERSION);
  return next(
    rowVersion
      ? req.clone({ setHeaders: { 'If-Match': `"${rowVersion}"` } })
      : req,
  );
};

/** Shows API errors as toasts, and sends the user to sign in again when the session has ended. */
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const snackBar = inject(MatSnackBar);
  const auth = inject(AuthService);
  const router = inject(Router);
  return next(req).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse) {
        if (error.status === 401) {
          // Expired or revoked: sign in again, then come back to this page.
          if (!router.url.startsWith('/login')) void auth.expire(router.url);
        } else if (!req.context.get(SKIP_ERROR_TOAST)) {
          const { summary, detail } = describeError(error);
          snackBar.open(`${summary}: ${detail}`, 'Dismiss', {
            duration: 8000,
            panelClass: 'trishul-snack-error',
            politeness: 'assertive',
          });
        }
      }
      return throwError(() => error);
    }),
  );
};

function describeError(error: HttpErrorResponse): {
  summary: string;
  detail: string;
} {
  const problem = (error.error ?? {}) as ProblemDetails;
  switch (error.status) {
    case 0:
      return {
        summary: 'Network error',
        detail: 'The server could not be reached. Check your connection.',
      };
    case 403:
      return {
        summary: 'Not allowed',
        detail: problem.detail ?? 'You do not have permission for this action.',
      };
    case 409:
    case 412:
      // The API's message is the single source; this only covers a missing body.
      return {
        summary: problem.title ?? 'Record changed',
        detail:
          problem.detail ??
          'Another user changed this record. Reload it and try again.',
      };
    case 400:
    case 422: {
      const fieldErrors = Object.values(problem.errors ?? {}).flat();
      return {
        summary: problem.title ?? 'Please check the form',
        detail:
          fieldErrors.join(' ') ||
          problem.detail ||
          'Some values are not valid.',
      };
    }
    default:
      return {
        summary: problem.title ?? `Error ${error.status}`,
        detail: problem.detail ?? 'Something went wrong. Please try again.',
      };
  }
}
