import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
} from '@angular/core';
import { MatIcon } from '@angular/material/icon';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthStore } from '@trishul/core-auth';
import {
  FACE_APPROVE_PERMISSION,
  FACE_ATTENDANCE_VIEW_PERMISSIONS,
  FACE_PUNCH_VIEW_PERMISSIONS,
  FACE_REGISTER_PERMISSION,
} from '@trishul/hr-data-access';
import { PageHeader } from '@trishul/shared-ui';

const TABS = [
  {
    label: 'Employees',
    icon: 'badge',
    route: 'employees',
    permissions: FACE_ATTENDANCE_VIEW_PERMISSIONS,
  },
  {
    label: 'Face approvals',
    icon: 'face',
    route: 'faces',
    permissions: [FACE_REGISTER_PERMISSION, FACE_APPROVE_PERMISSION],
  },
  {
    label: 'Punches & review',
    icon: 'fact_check',
    route: 'punches',
    permissions: FACE_PUNCH_VIEW_PERMISSIONS,
  },
  {
    label: 'Work locations',
    icon: 'location_on',
    route: 'locations',
    permissions: FACE_ATTENDANCE_VIEW_PERMISSIONS,
  },
  {
    label: 'Policies',
    icon: 'rule',
    route: 'policies',
    permissions: FACE_ATTENDANCE_VIEW_PERMISSIONS,
  },
] as const;

/** Face Attendance (mobile app check-in with a face check) under /hr/face-attendance. */
@Component({
  selector: 'trishul-face-attendance-shell-page',
  imports: [MatIcon, PageHeader, RouterLink, RouterLinkActive, RouterOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <trishul-page-header
      title="Face Attendance"
      subtitle="Employees check in from the mobile app with a face check. Set them up, approve faces and review doubtful punches."
    />
    <nav class="tabs" aria-label="Face attendance sections">
      @for (tab of tabs(); track tab.route) {
        <a [routerLink]="tab.route" routerLinkActive="active">
          <mat-icon>{{ tab.icon }}</mat-icon>
          {{ tab.label }}
        </a>
      }
    </nav>
    <router-outlet />
  `,
  styleUrl: './face-attendance.shared.scss',
})
export class FaceAttendanceShellPage {
  private readonly auth = inject(AuthStore);
  protected readonly tabs = computed(() =>
    TABS.filter((tab) => this.auth.hasAnyPermission(tab.permissions)),
  );
}
