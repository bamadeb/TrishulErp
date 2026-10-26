import { InjectionToken } from '@angular/core';

/**
 * Runtime configuration, read from /config.json before bootstrap so one build
 * can be deployed to every environment (dev, UAT, prod) unchanged.
 */
export interface AppConfig {
  /** Base URL of the Trishul REST API, e.g. https://api.trishul.example.com/api/v1 */
  apiBaseUrl: string;
  /** Answer API calls from in-browser fixtures instead of the real API. */
  useMockApi: boolean;
  auth: {
    /**
     * cognito: username + password against the Cognito user pool (UAT, production).
     * dev: sign in as any ERP username without a password. Local development only; the API must
     *      run with TRISHUL_AUTH_MODE=dev, which it refuses in UAT and production.
     */
    mode: 'cognito' | 'dev';
    /** Cognito user pool id, e.g. ap-south-1_AbCdEf123 (the region is part of it). */
    userPoolId: string;
    /** Cognito app client id: public client, no secret, ALLOW_USER_SRP_AUTH + ALLOW_REFRESH_TOKEN_AUTH. */
    userPoolClientId: string;
  };
}

export const APP_CONFIG = new InjectionToken<AppConfig>('APP_CONFIG');

export async function loadAppConfig(url = '/config.json'): Promise<AppConfig> {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`Cannot load ${url} (HTTP ${response.status})`);
  }
  return (await response.json()) as AppConfig;
}
