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
import { DocumentLibraryApi } from './documents.api';
import {
  DocumentEntityType,
  DocumentLibraryItem,
  DocumentLibraryQuery,
} from './documents.models';

interface DocumentLibraryState {
  query: DocumentLibraryQuery;
  items: DocumentLibraryItem[];
  total: number;
  loading: boolean;
  failed: boolean;
  entityTypes: DocumentEntityType[];
}

const initialState: DocumentLibraryState = {
  query: { page: 1, pageSize: 20, sort: '-uploadedAt' },
  items: [],
  total: 0,
  loading: false,
  failed: false,
  entityTypes: [],
};

/** State of the Administration > Documents page. Provide it in the page component. */
export const DocumentLibraryStore = signalStore(
  withState(initialState),
  withMethods((store, api = inject(DocumentLibraryApi)) => {
    const load = rxMethod<DocumentLibraryQuery>(
      pipe(
        tap(() => patchState(store, { loading: true, failed: false })),
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
              patchState(store, { loading: false, failed: true });
              return EMPTY;
            }),
          ),
        ),
      ),
    );

    const loadEntityTypes = rxMethod<void>(
      pipe(
        switchMap(() =>
          api.entityTypes().pipe(
            tap((entityTypes) => patchState(store, { entityTypes })),
            // The filter just stays empty; the list itself still works.
            catchError(() => EMPTY),
          ),
        ),
      ),
    );

    return {
      /** Filter changes go back to page 1. */
      updateQuery(change: Partial<DocumentLibraryQuery>): void {
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
      loadEntityTypes,
    };
  }),
  withHooks({
    onInit: (store) => {
      store.loadEntityTypes();
      store.reload();
    },
  }),
);
