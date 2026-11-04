import { inject } from '@angular/core';
import { patchState, signalStore, withMethods, withState } from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { EMPTY, catchError, pipe, switchMap, tap } from 'rxjs';
import { EmployeesApi } from './employees.api';
import { EmployeeCounts, EmployeeQuery, EmployeeRow } from './employees.models';

interface EmployeeListState {
  query: EmployeeQuery;
  items: EmployeeRow[];
  total: number;
  counts: EmployeeCounts;
  loading: boolean;
}

const emptyCounts: EmployeeCounts = {
  allEmployees: 0,
  active: 0,
  probation: 0,
  notice: 0,
  exited: 0,
  archived: 0,
};

const initialState: EmployeeListState = {
  query: { page: 1, pageSize: 20, sort: 'firstName', status: 'all', lifecycle: 'all' },
  items: [],
  total: 0,
  counts: emptyCounts,
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
                counts: page.counts,
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
      /** Replaces the query and loads the first page of that query. */
      start(query: EmployeeQuery): void {
        patchState(store, { query });
        load(query);
      },
      reload(): void {
        load(store.query());
      },
    };
  }),
);
