import {
  ApplicationConfig,
  inject,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
} from '@angular/core';
import { MatIconRegistry } from '@angular/material/icon';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { provideTrishulAuth } from '@trishul/core-auth';
import { APP_CONFIG, AppConfig } from '@trishul/core-config';
import { provideTrishulHttp } from '@trishul/core-http';
import { NAV_ITEMS } from '@trishul/core-layout';
import { appRoutes } from './app.routes';
import { mockRoutes } from './mocks/mock-routes';
import { navItems } from './nav-items';

export function createAppConfig(config: AppConfig): ApplicationConfig {
  return {
    providers: [
      provideBrowserGlobalErrorListeners(),
      { provide: APP_CONFIG, useValue: config },
      provideRouter(appRoutes, withComponentInputBinding()),
      provideTrishulHttp(config, config.useMockApi ? mockRoutes : []),
      provideTrishulAuth(config),
      // <mat-icon>name</mat-icon> renders Material Symbols (loaded in index.html).
      provideAppInitializer(() => {
        inject(MatIconRegistry).setDefaultFontSetClass(
          'material-symbols-outlined',
        );
      }),
      { provide: NAV_ITEMS, useValue: navItems },
    ],
  };
}
