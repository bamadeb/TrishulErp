import { Route } from '@angular/router';
import {
  COMPLAINT_MANAGE_ALL_PERMISSION,
  COMPLAINT_MANAGE_PERMISSIONS,
  COMPLAINT_RAISE_PERMISSION,
} from '@trishul/admin-data-access';
import { permissionGuard } from '@trishul/core-auth';
import { ComplaintDetailPage } from './complaint-detail.page';
import { ComplaintIssueTypesPage } from './complaint-issue-types.page';
import { ComplaintRaisePage } from './complaint-raise.page';
import { DepartmentComplaintsPage } from './department-complaints.page';
import { MyComplaintsPage } from './my-complaints.page';

/** Lazy-loaded under /complaints. The API decides what each person may see; the guards only tidy the menu. */
export const complaintRoutes: Route[] = [
  { path: '', pathMatch: 'full', redirectTo: 'mine' },
  {
    path: 'new',
    title: 'Raise a complaint',
    canActivate: [permissionGuard(COMPLAINT_RAISE_PERMISSION)],
    component: ComplaintRaisePage,
  },
  {
    path: 'mine',
    title: 'My complaints',
    canActivate: [permissionGuard(COMPLAINT_RAISE_PERMISSION)],
    component: MyComplaintsPage,
  },
  {
    path: 'department',
    title: 'Department complaints',
    canActivate: [permissionGuard(...COMPLAINT_MANAGE_PERMISSIONS)],
    component: DepartmentComplaintsPage,
  },
  {
    path: 'issue-types',
    title: 'Complaint issue types',
    canActivate: [permissionGuard(COMPLAINT_MANAGE_ALL_PERMISSION)],
    component: ComplaintIssueTypesPage,
  },
  {
    path: ':complaintId',
    title: 'Complaint',
    canActivate: [
      permissionGuard(
        COMPLAINT_RAISE_PERMISSION,
        ...COMPLAINT_MANAGE_PERMISSIONS,
      ),
    ],
    component: ComplaintDetailPage,
  },
];
