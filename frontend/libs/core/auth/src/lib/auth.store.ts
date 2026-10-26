import { computed, inject } from '@angular/core';
import {
  patchState,
  signalStore,
  withComputed,
  withMethods,
  withState,
} from '@ngrx/signals';
import { firstValueFrom } from 'rxjs';
import { ApiClient, me, withoutErrorToast } from '@trishul/core-api';
import { readStorage, writeStorage } from '@trishul/shared-util';
import { CurrentUser } from './auth.models';

const BRANCH_KEY = 'trishul.branchId';
const PRINCIPAL_KEY = 'trishul.principalId';

interface AuthState {
  user: CurrentUser | null;
  /** Branch the user is working in; sent to the API on every call. */
  branchId: number | null;
  /** Selected brand, or null for all brands the user may see. */
  principalId: number | null;
}

export const AuthStore = signalStore(
  { providedIn: 'root' },
  withState<AuthState>({ user: null, branchId: null, principalId: null }),
  withComputed(({ user, branchId, principalId }) => {
    const permissions = computed(() => new Set(user()?.permissions ?? []));
    return {
      isLoggedIn: computed(() => user() !== null),
      permissions,
      currentBranch: computed(
        () => user()?.branches.find((b) => b.id === branchId()) ?? null,
      ),
      currentPrincipal: computed(
        () => user()?.principals.find((p) => p.id === principalId()) ?? null,
      ),
    };
  }),
  withMethods((store, api = inject(ApiClient)) => {
    /** True when the user holds the permission code (or the '*' super-permission). */
    const hasPermission = (code: string): boolean => {
      const granted = store.permissions();
      return granted.has('*') || granted.has(code);
    };

    return {
      hasPermission,

      hasAnyPermission(codes: readonly string[]): boolean {
        return codes.some(hasPermission);
      },

      async loadCurrentUser(): Promise<void> {
        // The login page reports failures itself, so no global error toast.
        const user = await firstValueFrom(
          api.call(me, undefined, withoutErrorToast()),
        );
        const savedBranch = readNumber(BRANCH_KEY);
        const savedPrincipal = readNumber(PRINCIPAL_KEY);
        patchState(store, {
          user,
          branchId: user.branches.some((b) => b.id === savedBranch)
            ? savedBranch
            : (user.defaultBranchId ?? user.branches[0]?.id ?? null),
          principalId: user.principals.some((p) => p.id === savedPrincipal)
            ? savedPrincipal
            : null,
        });
      },

      /** Signed out: forget the user and their branch / brand context. */
      clear(): void {
        patchState(store, { user: null, branchId: null, principalId: null });
      },

      selectBranch(branchId: number): void {
        patchState(store, { branchId });
        writeStorage('local', BRANCH_KEY, String(branchId));
      },

      selectPrincipal(principalId: number | null): void {
        patchState(store, { principalId });
        writeStorage(
          'local',
          PRINCIPAL_KEY,
          principalId === null ? null : String(principalId),
        );
      },
    };
  }),
);

function readNumber(key: string): number | null {
  const value = readStorage('local', key);
  return value ? Number(value) : null;
}
