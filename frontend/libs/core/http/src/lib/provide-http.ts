import {
  provideHttpClient,
  withFetch,
  withInterceptors,
} from '@angular/common/http';
import { EnvironmentProviders, makeEnvironmentProviders } from '@angular/core';
import { provideApiConfiguration } from '@trishul/core-api';
import { AppConfig } from '@trishul/core-config';
import {
  authInterceptor,
  contextInterceptor,
  errorInterceptor,
  rowVersionInterceptor,
} from './interceptors';
import { MOCK_API_ROUTES, MockRoute, mockApiInterceptor } from './mock-api';

/**
 * HttpClient with the Trishul interceptor chain, and the generated API client pointed at
 * config.apiBaseUrl. Pass mock routes for local development.
 */
export function provideTrishulHttp(
  config: AppConfig,
  mockRoutes: MockRoute[] = [],
): EnvironmentProviders {
  return makeEnvironmentProviders([
    provideApiConfiguration(config.apiBaseUrl),
    { provide: MOCK_API_ROUTES, useValue: mockRoutes, multi: true },
    provideHttpClient(
      withFetch(),
      withInterceptors([
        authInterceptor,
        contextInterceptor,
        rowVersionInterceptor,
        errorInterceptor,
        mockApiInterceptor,
      ]),
    ),
  ]);
}
