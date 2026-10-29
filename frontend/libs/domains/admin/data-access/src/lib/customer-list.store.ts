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
import { CustomersApi } from './customers.api';
import { CustomerQuery, CustomerRow } from './customers.models';

interface CustomerListState {
  query: CustomerQuery;
  items: CustomerRow[];
  total: number;
  loading: boolean;
}

const initialState: CustomerListState = {
  query: { page: 1, pageSize: 20, sort: 'name', status: 'active' },
  items: [],
  total: 0,
  loading: false,
};

/** State of the customer list page. Provide it in the page component. */
export const CustomerListStore = signalStore(
  withState(initialState),
  withMethods((store, api = inject(CustomersApi)) => {
    const load = rxMethod<CustomerQuery>(
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
      updateQuery(change: Partial<CustomerQuery>): void {
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
