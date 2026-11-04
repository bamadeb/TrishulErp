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
import { AscApi } from './asc.api';
import { AscQuery, ServiceContractListItem } from './asc.models';

interface AscListState {
  query: AscQuery;
  items: ServiceContractListItem[];
  total: number;
  loading: boolean;
}

const initialState: AscListState = {
  query: { page: 1, pageSize: 20, status: 'live' },
  items: [],
  total: 0,
  loading: false,
};

/** State of the ASC list page. Provide it in the page component. */
export const AscListStore = signalStore(
  withState(initialState),
  withMethods((store, api = inject(AscApi)) => {
    const load = rxMethod<AscQuery>(
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
      updateQuery(change: Partial<AscQuery>): void {
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
  withHooks({ onInit: (store) => store.reload() }),
);
