import {
  EnvironmentProviders,
  inject,
  makeEnvironmentProviders,
  provideAppInitializer,
} from '@angular/core';
import { AppConfig } from '@trishul/core-config';
import { AuthSession } from './auth-session';
import { AuthService } from './auth.service';
import { CognitoAuthSession } from './sessions/cognito-auth-session';
import { DevAuthSession } from './sessions/dev-auth-session';

/**
 * Sign-in for the ERP apps. Before the first route renders, resumes a session from earlier in the
 * tab and loads the user, so guards know who is signed in.
 */
export function provideTrishulAuth(config: AppConfig): EnvironmentProviders {
  return makeEnvironmentProviders([
    {
      provide: AuthSession,
      useClass:
        config.auth.mode === 'cognito' ? CognitoAuthSession : DevAuthSession,
    },
    provideAppInitializer(() => inject(AuthService).restore()),
  ]);
}
