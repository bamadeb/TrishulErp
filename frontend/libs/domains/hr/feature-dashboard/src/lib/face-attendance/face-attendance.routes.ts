import { Route } from '@angular/router';
import { permissionGuard } from '@trishul/core-auth';
import {
  FACE_APPROVE_PERMISSION,
  FACE_ATTENDANCE_VIEW_PERMISSIONS,
  FACE_PUNCH_VIEW_PERMISSIONS,
  FACE_REGISTER_PERMISSION,
} from '@trishul/hr-data-access';
import { FaEmployeesPage } from './fa-employees.page';
import { FaFacesPage } from './fa-faces.page';
import { FaLocationsPage } from './fa-locations.page';
import { FaPoliciesPage } from './fa-policies.page';
import { FaPunchesPage } from './fa-punches.page';
import { FaceAttendanceShellPage } from './face-attendance-shell.page';

const view = {
  canActivate: [permissionGuard(...FACE_ATTENDANCE_VIEW_PERMISSIONS)],
};

/** Face Attendance (mobile app check-in with a face check) under /hr/face-attendance. */
export const faceAttendanceRoutes: Route[] = [
  {
    path: '',
    component: FaceAttendanceShellPage,
    ...view,
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'employees' },
      {
        path: 'employees',
        title: 'Face Attendance — Employees',
        ...view,
        component: FaEmployeesPage,
      },
      {
        path: 'faces',
        title: 'Face Attendance — Face approvals',
        canActivate: [
          permissionGuard(FACE_REGISTER_PERMISSION, FACE_APPROVE_PERMISSION),
        ],
        component: FaFacesPage,
      },
      {
        path: 'punches',
        title: 'Face Attendance — Punches',
        canActivate: [permissionGuard(...FACE_PUNCH_VIEW_PERMISSIONS)],
        component: FaPunchesPage,
      },
      {
        path: 'locations',
        title: 'Face Attendance — Work locations',
        ...view,
        component: FaLocationsPage,
      },
      {
        path: 'policies',
        title: 'Face Attendance — Policies',
        ...view,
        component: FaPoliciesPage,
      },
    ],
  },
];
