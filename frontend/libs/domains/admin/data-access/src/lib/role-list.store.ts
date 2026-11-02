import { inject } from '@angular/core';
import {
  patchState,
  signalStore,
  withHooks,
  withMethods,
  withState,
} from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { EMPTY, catchError, pipe, switchMap, tap } from 'rxjs';
import { RolesApi } from './roles.api';
import { RoleQuery, RoleRow } from './roles.models';

interface RoleListState {
  query: RoleQuery;
  items: RoleRow[];
  loading: boolean;
}

const initialState: RoleListState = {
  query: { status: 'all' },
  items: [],
  loading: false,
};

/** State of the role list page (a short list, not paged). Provide it in the page component. */
export const RoleListStore = signalStore(
  withState(initialState),
  withMethods((store, api = inject(RolesApi)) => {
    const load = rxMethod<RoleQuery>(
      pipe(
        tap(() => patchState(store, { loading: true })),
        switchMap((query) =>
          api.list(query).pipe(
            tap((items) => patchState(store, { items, loading: false })),
            catchError(() => {
              patchState(store, { loading: false });
              return EMPTY;
            }),
          ),
        ),
      ),
    );

    return {
      updateQuery(change: Partial<RoleQuery>): void {
        patchState(store, { query: { ...store.query(), ...change } });
        load(store.query());
      },
      reload(): void {
        load(store.query());
      },
    };
  }),
  withHooks({ onInit: (store) => store.reload() }),
);
