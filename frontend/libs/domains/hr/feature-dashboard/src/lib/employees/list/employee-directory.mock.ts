/** Lifecycle cards on the employee directory. Counts come from the employee list API. */
export type DirectoryLifecycle = 'active' | 'probation' | 'notice' | 'exited' | 'archived';

export interface OverviewCard {
  id: DirectoryLifecycle | 'all';
  title: string;
  description: string;
  icon: string;
  tone: 'blue' | 'green' | 'orange' | 'cyan' | 'pink' | 'violet';
}

export const DIRECTORY_OVERVIEW: readonly OverviewCard[] = [
  { id: 'all', title: 'All Employees', description: 'Total workforce', icon: 'groups', tone: 'blue' },
  { id: 'active', title: 'Active', description: 'Currently working', icon: 'check_circle', tone: 'green' },
  { id: 'probation', title: 'Probation', description: 'Under probation', icon: 'hourglass_top', tone: 'orange' },
  { id: 'notice', title: 'Notice Period', description: 'Serving notice', icon: 'event_busy', tone: 'cyan' },
  { id: 'exited', title: 'Exited', description: 'Former employees', icon: 'logout', tone: 'pink' },
  { id: 'archived', title: 'Archived', description: 'Archived records', icon: 'inventory_2', tone: 'violet' },
];
