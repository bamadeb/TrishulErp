import { Route } from '@angular/router';
import { permissionGuard } from '@trishul/core-auth';
import { BIOMETRIC_VIEW_PERMISSIONS } from '@trishul/hr-data-access';
import { BiometricDashboardPage } from './biometric-dashboard.page';
import { BiometricDevicesPage } from './biometric-devices.page';
import { BiometricMappingPage } from './biometric-mapping.page';
import { BiometricPunchesPage } from './biometric-punches.page';
import { BiometricShellPage } from './biometric-shell.page';
import { BiometricSyncPage } from './biometric-sync.page';

const view = { canActivate: [permissionGuard(...BIOMETRIC_VIEW_PERMISSIONS)] };

/** Biometric Management screens under /hr/biometric. */
export const biometricRoutes: Route[] = [
  {
    path: '',
    component: BiometricShellPage,
    ...view,
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      { path: 'dashboard', title: 'Biometric Dashboard', ...view, component: BiometricDashboardPage },
      { path: 'devices', title: 'Biometric Devices', ...view, component: BiometricDevicesPage },
      { path: 'mapping', title: 'Employee Mapping', ...view, component: BiometricMappingPage },
      { path: 'punches', title: 'Punch Logs', ...view, component: BiometricPunchesPage },
      { path: 'sync-history', title: 'Sync History', ...view, component: BiometricSyncPage },
    ],
  },
];
