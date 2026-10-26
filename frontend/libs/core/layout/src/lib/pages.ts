import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'trishul-forbidden-page',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1>Access denied</h1>
    <p>
      You do not have permission to open this page. Ask your administrator for
      access.
    </p>
    <a routerLink="/">Go to dashboard</a>
  `,
})
export class ForbiddenPage {}

@Component({
  selector: 'trishul-not-found-page',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1>Page not found</h1>
    <p>The page you are looking for does not exist.</p>
    <a routerLink="/">Go to dashboard</a>
  `,
})
export class NotFoundPage {}
