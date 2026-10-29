import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { RouterLink } from '@angular/router';
import { PageHeader } from '@trishul/shared-ui';

/** Labelled stand-in for an HR screen that is not built yet. */
@Component({
  selector: 'trishul-hr-placeholder-page',
  imports: [PageHeader, RouterLink, MatButton],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <trishul-page-header
      [title]="screenTitle()"
      subtitle="Placeholder. This screen has not been built."
    />
    <p>No records are loaded or saved from here.</p>
    <a mat-button routerLink="/hr/dashboard">Back to HR Dashboard</a>
  `,
})
export class HrPlaceholderPage {
  readonly screenTitle = input.required<string>();
}
