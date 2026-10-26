import { NavItem } from '@trishul/core-layout';
import { SERVICE_CALL_VIEW_PERMISSIONS } from '@trishul/service-data-access';

/** Side menu. Add each module's entries as its routes are built. Icons are Material Symbols names. */
export const navItems: NavItem[] = [
  { label: 'Dashboard', icon: 'dashboard', route: '/' },
  {
    label: 'Service',
    icon: 'build',
    children: [
      {
        label: 'Service calls',
        route: '/service/calls',
        permissions: [...SERVICE_CALL_VIEW_PERMISSIONS],
      },
    ],
  },
];
