import { Route } from '@angular/router';
import {
  COMPLAINT_MANAGE_ALL_PERMISSION,
  COMPLAINT_MANAGE_PERMISSIONS,
} from '@trishul/admin-data-access';
import { permissionGuard } from '@trishul/core-auth';
import { ComplaintDetailPage } from './complaint-detail.page';
import { ComplaintIssueTypesPage } from './complaint-issue-types.page';
import { ComplaintRaisePage } from './complaint-raise.page';
import { DepartmentComplaintsPage } from './department-complaints.page';
import { MyComplaintsPage } from './my-complaints.page';

/**
 * Lazy-loaded under /complaints. Raising a complaint, My complaints and opening one's own complaint are for every
 * signed-in user, whatever their role. The API decides what each person may see; the guards only tidy the menu.
 */
export const complaintRoutes: Route[] = [
  { path: '', pathMatch: 'full', redirectTo: 'mine' },
  {
    path: 'new',
    title: 'Raise a complaint',
    component: ComplaintRaisePage,
  },
  {
    path: 'mine',
    title: 'My complaints',
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
    // Their own complaint for everyone; a department's for its leaders (the API answers 404 otherwise).
    path: ':complaintId',
    title: 'Complaint',
    component: ComplaintDetailPage,
  },
];
