import { Route } from '@angular/router';
import { permissionGuard } from '@trishul/core-auth';
import { BIOMETRIC_MANAGE_PERMISSION } from '@trishul/hr-data-access';
import { BiometricDashboardPage } from './biometric-dashboard.page';
import { BiometricDevicesPage } from './biometric-devices.page';
import { BiometricMappingPage } from './biometric-mapping.page';
import { BiometricPunchesPage } from './biometric-punches.page';
import { BiometricShellPage } from './biometric-shell.page';
import { BiometricSyncPage } from './biometric-sync.page';

/** Admin / HR only — employees use My Attendance, not biometric admin screens. */
const manage = { canActivate: [permissionGuard(BIOMETRIC_MANAGE_PERMISSION)] };

/** Biometric Management screens under /hr/biometric. */
export const biometricRoutes: Route[] = [
  {
    path: '',
    component: BiometricShellPage,
    ...manage,
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      { path: 'dashboard', title: 'Biometric Dashboard', ...manage, component: BiometricDashboardPage },
      { path: 'devices', title: 'Biometric Devices', ...manage, component: BiometricDevicesPage },
      { path: 'mapping', title: 'Employee Mapping', ...manage, component: BiometricMappingPage },
      { path: 'punches', title: 'Punch Logs', ...manage, component: BiometricPunchesPage },
      { path: 'sync-history', title: 'Sync History', ...manage, component: BiometricSyncPage },
    ],
  },
];
