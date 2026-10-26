import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { AuthStore } from '@trishul/core-auth';
import { PageHeader } from '@trishul/shared-ui';

/** Placeholder until the management dashboard (rpt) is built in Phase 10. */
@Component({
  selector: 'trishul-dashboard-page',
  imports: [PageHeader],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <trishul-page-header
      [title]="'Welcome, ' + (auth.user()?.displayName ?? '')"
      [subtitle]="auth.currentBranch()?.name ?? ''"
    />
    <p>Select a module from the menu.</p>
  `,
})
export class DashboardPage {
  protected readonly auth = inject(AuthStore);
}
