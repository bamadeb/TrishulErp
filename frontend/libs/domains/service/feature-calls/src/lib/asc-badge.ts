import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
} from '@angular/core';
import { MatIcon } from '@angular/material/icon';
import { RouterLink } from '@angular/router';
import { AuthStore } from '@trishul/core-auth';
import { ASC_VIEW_PERMISSIONS, MachineAsc } from '@trishul/service-data-access';

/** A machine's ASC as calls show it: under ASC (till when, visits used), starting later, expired, or none. */
@Component({
  selector: 'trishul-asc-badge',
  imports: [DatePipe, MatIcon, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @let a = asc();
    <span class="asc" [class]="tone()">
      <mat-icon>{{ icon() }}</mat-icon>
      @if (!a) {
        No ASC
      } @else {
        @switch (a.state) {
          @case ('Active') {
            Under ASC till {{ a.endDate | date: 'dd MMM yyyy' }}
          }
          @case ('Upcoming') {
            ASC starts {{ a.startDate | date: 'dd MMM yyyy' }}
          }
          @default {
            ASC expired {{ a.endDate | date: 'dd MMM yyyy' }} — renewal due
          }
        }
        @if (a.visitsIncluded !== null && a.state === 'Active') {
          <span class="visits"
            >· {{ a.visitsUsed }}/{{ a.visitsIncluded }} visits</span
          >
        }
        @if (canOpen) {
          <a [routerLink]="['/service/asc', a.contractId]">{{ a.contractNo }}</a>
        }
      }
    </span>
  `,
  styles: `
    .asc {
      display: inline-flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.3rem;
      padding: 0.2rem 0.625rem;
      border-radius: 999px;
      font: var(--mat-sys-label-large);
      color: var(--mat-sys-on-surface-variant);
      background: var(--mat-sys-surface-container-high);

      mat-icon {
        width: 18px;
        height: 18px;
        font-size: 18px;
      }
      a {
        color: inherit;
        font-weight: 600;
      }
      .visits {
        font-weight: 400;
      }
    }
    .success {
      color: var(--trishul-success);
      background: var(--trishul-success-container);
    }
    .info {
      color: var(--trishul-info);
      background: var(--trishul-info-container);
    }
    .warn {
      color: var(--trishul-warn);
      background: var(--trishul-warn-container);
    }
  `,
})
export class AscBadge {
  /** null = the machine has never had an ASC. */
  readonly asc = input.required<MachineAsc | null>();

  protected readonly canOpen = inject(AuthStore).hasAnyPermission(
    ASC_VIEW_PERMISSIONS,
  );

  protected readonly tone = computed(() => {
    const state = this.asc()?.state;
    if (state === 'Active') return 'asc success';
    if (state === 'Upcoming') return 'asc info';
    if (state === 'Expired') return 'asc warn';
    return 'asc';
  });

  protected readonly icon = computed(() => {
    const state = this.asc()?.state;
    if (state === 'Active') return 'verified';
    if (state === 'Upcoming') return 'schedule';
    if (state === 'Expired') return 'event_busy';
    return 'remove_moderator';
  });
}
