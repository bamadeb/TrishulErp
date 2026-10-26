import { effect, inject, untracked } from '@angular/core';
import {
  patchState,
  signalStore,
  withHooks,
  withMethods,
  withState,
} from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { EMPTY, catchError, pipe, switchMap, tap } from 'rxjs';
import { AuthStore } from '@trishul/core-auth';
import { ServiceCallApi } from './service-call.api';
import { ServiceCallListItem, ServiceCallQuery } from './service-call.models';

interface ServiceCallListState {
  query: ServiceCallQuery;
  items: ServiceCallListItem[];
  total: number;
  loading: boolean;
}

const initialState: ServiceCallListState = {
  query: { page: 1, pageSize: 20, sort: '-receivedAt' },
  items: [],
  total: 0,
  loading: false,
};

/** State of the call register page. Provide it in the page component, not in root. */
export const ServiceCallListStore = signalStore(
  withState(initialState),
  withMethods((store, api = inject(ServiceCallApi)) => {
    // switchMap drops the response of a superseded query (fast typing, quick paging).
    const load = rxMethod<ServiceCallQuery>(
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
      /** Merge filter / paging changes into the query and reload. Filter changes go back to page 1. */
      updateQuery(change: Partial<ServiceCallQuery>): void {
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
    };
  }),
  withHooks({
    onInit(store, auth = inject(AuthStore)) {
      // Load now, and again whenever the user switches branch or brand.
      effect(() => {
        auth.branchId();
        auth.principalId();
        untracked(() => store.updateQuery({}));
      });
    },
  }),
);
