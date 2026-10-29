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
import { EmployeesApi } from './employees.api';
import { EmployeeQuery, EmployeeRow } from './employees.models';

interface EmployeeListState {
  query: EmployeeQuery;
  items: EmployeeRow[];
  total: number;
  loading: boolean;
}

const initialState: EmployeeListState = {
  query: { page: 1, pageSize: 20, sort: 'firstName', status: 'active' },
  items: [],
  total: 0,
  loading: false,
};

/** State of the employee list page. Provide it in the page component. */
export const EmployeeListStore = signalStore(
  withState(initialState),
  withMethods((store, api = inject(EmployeesApi)) => {
    const load = rxMethod<EmployeeQuery>(
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
      updateQuery(change: Partial<EmployeeQuery>): void {
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
