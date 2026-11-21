import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatAnchor } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { map } from 'rxjs';
import { PageHeader } from '@trishul/shared-ui';

/** Lightweight stub for Attendance submenu screens not yet built. */
@Component({
  selector: 'trishul-attendance-placeholder-page',
  imports: [MatAnchor, MatIcon, PageHeader, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <trishul-page-header [title]="title()" subtitle="This screen is coming soon." />
    <section class="panel">
      <mat-icon>construction</mat-icon>
      <p>{{ title() }} UI will be added in a later iteration.</p>
      <a mat-stroked-button color="primary" routerLink="/hr/attendance/daily">Open Daily Attendance</a>
    </section>
  `,
  styles: `
    .panel {
      display: grid;
      justify-items: start;
      gap: 0.75rem;
      padding: 1.25rem;
      border: 1px solid #e3ebf6;
      border-radius: 12px;
      background: #fff;
      color: #475569;
      font-size: 0.9rem;
    }
    mat-icon {
      color: #0754b8;
    }
  `,
})
export class AttendancePlaceholderPage {
  private readonly route = inject(ActivatedRoute);
  private readonly routeTitle = toSignal(
    this.route.data.pipe(map((data) => String(data['screenTitle'] ?? 'Attendance'))),
    { initialValue: 'Attendance' },
  );
  protected readonly title = computed(() => this.routeTitle());
}
