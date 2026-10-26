import {
  HttpErrorResponse,
  HttpInterceptorFn,
  HttpRequest,
  HttpResponse,
} from '@angular/common/http';
import { InjectionToken, inject } from '@angular/core';
import { delay, of, throwError } from 'rxjs';
import { APP_CONFIG } from '@trishul/core-config';

/** A fake endpoint. `path` is relative to apiBaseUrl and may contain :params. */
export interface MockRoute {
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  path: string;
  /** Returns the response body; throw an HttpErrorResponse to simulate a failure. */
  handle: (
    req: HttpRequest<unknown>,
    params: Record<string, string>,
  ) => unknown;
}

export const MOCK_API_ROUTES = new InjectionToken<MockRoute[][]>(
  'MOCK_API_ROUTES',
);

const LATENCY_MS = 250;

/** Answers API calls from MOCK_API_ROUTES when useMockApi is on. Must be the last interceptor. */
export const mockApiInterceptor: HttpInterceptorFn = (req, next) => {
  const config = inject(APP_CONFIG);
  if (!config.useMockApi || !req.url.startsWith(config.apiBaseUrl))
    return next(req);

  const path = req.url.slice(config.apiBaseUrl.length).split('?')[0];
  const routes = (inject(MOCK_API_ROUTES, { optional: true }) ?? []).flat();
  for (const route of routes) {
    const params =
      route.method === req.method ? matchPath(route.path, path) : null;
    if (!params) continue;
    try {
      const body = route.handle(req, params);
      return of(new HttpResponse({ status: 200, body })).pipe(
        delay(LATENCY_MS),
      );
    } catch (error) {
      return throwError(() => error).pipe(delay(LATENCY_MS));
    }
  }
  return throwError(
    () =>
      new HttpErrorResponse({
        status: 404,
        url: req.url,
        error: {
          title: 'No mock',
          detail: `No mock route for ${req.method} ${path}`,
        },
      }),
  );
};

function matchPath(
  pattern: string,
  path: string,
): Record<string, string> | null {
  const patternParts = pattern.split('/').filter(Boolean);
  const pathParts = path.split('/').filter(Boolean);
  if (patternParts.length !== pathParts.length) return null;
  const params: Record<string, string> = {};
  for (let i = 0; i < patternParts.length; i++) {
    if (patternParts[i].startsWith(':')) {
      params[patternParts[i].slice(1)] = decodeURIComponent(pathParts[i]);
    } else if (patternParts[i] !== pathParts[i]) {
      return null;
    }
  }
  return params;
}
