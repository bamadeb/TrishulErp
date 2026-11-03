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
import { TeamsApi } from './teams.api';
import { TeamQuery, TeamRow } from './teams.models';

interface TeamListState {
  query: TeamQuery;
  items: TeamRow[];
  loading: boolean;
}

const initialState: TeamListState = {
  query: { status: 'active' },
  items: [],
  loading: false,
};

/** State of the team list page (a short list, not paged). Provide it in the page component. */
export const TeamListStore = signalStore(
  withState(initialState),
  withMethods((store, api = inject(TeamsApi)) => {
    const load = rxMethod<TeamQuery>(
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
      updateQuery(change: Partial<TeamQuery>): void {
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
