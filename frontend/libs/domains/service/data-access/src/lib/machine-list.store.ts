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
import { MachineApi } from './machine.api';
import { MachineQuery, MachineRow } from './machine.models';

interface MachineListState {
  query: MachineQuery;
  items: MachineRow[];
  total: number;
  loading: boolean;
}

const initialState: MachineListState = {
  query: { page: 1, pageSize: 20, sort: 'serialNumber', status: 'active' },
  items: [],
  total: 0,
  loading: false,
};

/** State of the machine list page. Provide it in the page component. */
export const MachineListStore = signalStore(
  withState(initialState),
  withMethods((store, api = inject(MachineApi)) => {
    const load = rxMethod<MachineQuery>(
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
      updateQuery(change: Partial<MachineQuery>): void {
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
