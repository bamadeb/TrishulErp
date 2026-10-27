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
import { UsersApi } from './users.api';
import { UserQuery, UserRow } from './users.models';

interface UserListState {
  query: UserQuery;
  items: UserRow[];
  total: number;
  loading: boolean;
}

const initialState: UserListState = {
  query: { page: 1, pageSize: 20, sort: 'username', status: 'active' },
  items: [],
  total: 0,
  loading: false,
};

/** State of the user list page. Provide it in the page component. */
export const UserListStore = signalStore(
  withState(initialState),
  withMethods((store, api = inject(UsersApi)) => {
    const load = rxMethod<UserQuery>(
      pipe(
        tap(() => patchState(store, { loading: true })),
        switchMap((query) =>
          api.list(query).pipe(
            tap((page) =>
              patchState(store, {
                items: page.items,
                total: page.total,
                loading: false,
              }),
            ),
            catchError(() => {
              patchState(store, { loading: false });
              return EMPTY;
            }),
          ),
        ),
      ),
    );

    return {
      /** Filter changes go back to page 1. */
      updateQuery(change: Partial<UserQuery>): void {
        const resetPage = !('page' in change);
        patchState(store, {
          query: {
            ...store.query(),
            ...change,
            ...(resetPage ? { page: 1 } : {}),
          },
        });
        load(store.query());
      },
      reload(): void {
        load(store.query());
      },
      /** Show a changed user without reloading the page. */
      replace(user: UserRow): void {
        patchState(store, {
          items: store
            .items()
            .map((item) => (item.id === user.id ? user : item)),
        });
      },
    };
  }),
  withHooks({ onInit: (store) => store.reload() }),
);
