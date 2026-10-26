import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthStore } from './auth.store';

/** Signed-in users only; others go to the login page and come back afterwards. */
export const authGuard: CanActivateFn = (_route, state) =>
  inject(AuthStore).isLoggedIn() ||
  inject(Router).createUrlTree(['/login'], {
    queryParams: { returnUrl: state.url },
  });

/** The login page: a signed-in user goes straight to the app. */
export const guestGuard: CanActivateFn = () =>
  !inject(AuthStore).isLoggedIn() || inject(Router).createUrlTree(['/']);

/**
 * Allows the route when the user holds any of the given permission codes.
 * The UI check is a convenience only; the API enforces every permission.
 */
export function permissionGuard(...codes: string[]): CanActivateFn {
  return () =>
    inject(AuthStore).hasAnyPermission(codes) ||
    inject(Router).createUrlTree(['/forbidden']);
}
