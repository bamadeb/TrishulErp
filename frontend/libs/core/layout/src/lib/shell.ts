import { BreakpointObserver } from '@angular/cdk/layout';
import { NgTemplateOutlet } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { MatIconButton } from '@angular/material/button';
import { MatFormField } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import {
  MatListItem,
  MatListItemIcon,
  MatListItemTitle,
  MatListSubheaderCssMatStyler,
  MatNavList,
} from '@angular/material/list';
import { MatOption, MatSelect } from '@angular/material/select';
import {
  MatSidenav,
  MatSidenavContainer,
  MatSidenavContent,
} from '@angular/material/sidenav';
import { MatToolbar } from '@angular/material/toolbar';
import { MatTooltip } from '@angular/material/tooltip';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { map } from 'rxjs';
import { AuthService, AuthStore } from '@trishul/core-auth';
import { NAV_ITEMS, NavItem } from './nav';

/** Application frame: top bar with branch / brand context, permission-aware side menu, page outlet. */
@Component({
  selector: 'trishul-shell',
  imports: [
    NgTemplateOutlet,
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    MatToolbar,
    MatIconButton,
    MatIcon,
    MatTooltip,
    MatFormField,
    MatSelect,
    MatOption,
    MatSidenavContainer,
    MatSidenav,
    MatSidenavContent,
    MatNavList,
    MatListItem,
    MatListItemIcon,
    MatListItemTitle,
    MatListSubheaderCssMatStyler,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './shell.html',
  styleUrl: './shell.scss',
})
export class Shell {
  protected readonly auth = inject(AuthStore);
  private readonly authService = inject(AuthService);
  private readonly navItems = inject(NAV_ITEMS);

  /** Below 900px the menu slides over the page instead of sitting beside it. */
  protected readonly isCompact = toSignal(
    inject(BreakpointObserver)
      .observe('(max-width: 900px)')
      .pipe(map((state) => state.matches)),
    { initialValue: false },
  );
  protected readonly menuOpen = signal(false);

  /** mat-select shows a null value as blank, so "All brands" uses a sentinel id instead. */
  protected readonly ALL_BRANDS = 0;

  protected readonly menu = computed(() => this.filter(this.navItems));

  protected closeMenuOnCompact(): void {
    if (this.isCompact()) this.menuOpen.set(false);
  }

  protected logout(): void {
    void this.authService.signOut();
  }

  private filter(items: NavItem[]): NavItem[] {
    return items
      .filter(
        (item) =>
          !item.permissions || this.auth.hasAnyPermission(item.permissions),
      )
      .map((item) =>
        item.children
          ? { ...item, children: this.filter(item.children) }
          : item,
      )
      .filter((item) => item.route || item.children?.length);
  }
}
