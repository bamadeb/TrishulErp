import {
  ChangeDetectionStrategy,
  Component,
  computed,
  input,
} from '@angular/core';

export type StatusSeverity =
  'success' | 'info' | 'warn' | 'danger' | 'neutral' | 'contrast';

/** A document status shown as a coloured pill. Each module supplies its status -> severity map. */
@Component({
  selector: 'trishul-status-badge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[class]': '"badge " + severity()' },
  template: `{{ status() }}`,
  styles: `
    :host {
      display: inline-block;
      padding: 0.125rem 0.5rem;
      border-radius: 999px;
      font: var(--mat-sys-label-small);
      font-weight: 600;
      white-space: nowrap;
    }
    :host(.success) {
      color: var(--trishul-success);
      background: var(--trishul-success-container);
    }
    :host(.info) {
      color: var(--trishul-info);
      background: var(--trishul-info-container);
    }
    :host(.warn) {
      color: var(--trishul-warn);
      background: var(--trishul-warn-container);
    }
    :host(.danger) {
      color: var(--trishul-danger);
      background: var(--trishul-danger-container);
    }
    :host(.neutral) {
      color: var(--trishul-neutral);
      background: var(--trishul-neutral-container);
    }
    :host(.contrast) {
      color: var(--mat-sys-inverse-on-surface);
      background: var(--mat-sys-inverse-surface);
    }
  `,
})
export class StatusBadge {
  readonly status = input.required<string>();
  readonly severities = input<Partial<Record<string, StatusSeverity>>>({});

  protected readonly severity = computed(
    () => this.severities()[this.status()] ?? 'neutral',
  );
}
