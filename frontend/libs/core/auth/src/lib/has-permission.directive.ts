import {
  Directive,
  TemplateRef,
  ViewContainerRef,
  effect,
  inject,
  input,
} from '@angular/core';
import { AuthStore } from './auth.store';

/**
 * Renders its content only when the user holds one of the permission codes.
 *
 *   <button *trishulHasPermission="'svc.call.assign'">Assign</button>
 */
@Directive({ selector: '[trishulHasPermission]' })
export class HasPermission {
  readonly trishulHasPermission = input.required<string | readonly string[]>();

  private readonly store = inject(AuthStore);
  private readonly template = inject(TemplateRef);
  private readonly container = inject(ViewContainerRef);
  private shown = false;

  constructor() {
    effect(() => {
      const value = this.trishulHasPermission();
      const allowed = this.store.hasAnyPermission(
        typeof value === 'string' ? [value] : value,
      );
      if (allowed && !this.shown) {
        this.container.createEmbeddedView(this.template);
      } else if (!allowed && this.shown) {
        this.container.clear();
      }
      this.shown = allowed;
    });
  }
}
