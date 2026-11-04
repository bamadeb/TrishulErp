import { inject } from '@angular/core';
import { patchState, signalStore, withMethods, withState } from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { EMPTY, Observable, catchError, map, pipe, switchMap, tap } from 'rxjs';
import {
  BranchListItem,
  CompanyListItem,
  DepartmentListItem,
  DesignationListItem,
  GradeListItem,
  HierarchyListItem,
} from '@trishul/core-api';
import { OrganizationApi } from './organization.api';
import { OrgCounts, OrgQuery, OrgTabId } from './organization.models';

export type OrgSnapshot =
  | { tab: 'departments'; items: DepartmentListItem[] }
  | { tab: 'designations'; items: DesignationListItem[] }
  | { tab: 'grades'; items: GradeListItem[] }
  | { tab: 'locations'; items: BranchListItem[] }
  | { tab: 'companies'; items: CompanyListItem[] }
  | { tab: 'hierarchy'; items: HierarchyListItem[] };

interface Loaded {
  snapshot: OrgSnapshot;
  total: number;
}

interface OrganizationState {
  snapshot: OrgSnapshot;
  query: OrgQuery;
  total: number;
  counts: OrgCounts;
  loading: boolean;
}

const emptyCounts: OrgCounts = {
  departments: 0,
  designations: 0,
  grades: 0,
  locations: 0,
  hierarchy: 0,
};

const initialQuery: OrgQuery = { page: 1, pageSize: 10, search: '', status: 'active' };

const initialState: OrganizationState = {
  snapshot: { tab: 'departments', items: [] },
  query: initialQuery,
  total: 0,
  counts: emptyCounts,
  loading: false,
};

function emptySnapshot(tab: OrgTabId): OrgSnapshot {
  switch (tab) {
    case 'departments':
      return { tab, items: [] };
    case 'designations':
      return { tab, items: [] };
    case 'grades':
      return { tab, items: [] };
    case 'locations':
      return { tab, items: [] };
    case 'companies':
      return { tab, items: [] };
    case 'hierarchy':
      return { tab, items: [] };
  }
}

function loadTab(api: OrganizationApi, tab: OrgTabId, query: OrgQuery): Observable<Loaded> {
  switch (tab) {
    case 'departments':
      return api.listDepartments(query).pipe(
        map((page) => ({ snapshot: { tab, items: page.items }, total: page.total })),
      );
    case 'designations':
      return api.listDesignations(query).pipe(
        map((page) => ({ snapshot: { tab, items: page.items }, total: page.total })),
      );
    case 'grades':
      return api
        .listGrades(query)
        .pipe(map((page) => ({ snapshot: { tab, items: page.items }, total: page.total })));
    case 'locations':
      return api
        .listBranches(query)
        .pipe(map((page) => ({ snapshot: { tab, items: page.items }, total: page.total })));
    case 'companies':
      return api
        .listCompaniesPage(query)
        .pipe(map((page) => ({ snapshot: { tab, items: page.items }, total: page.total })));
    case 'hierarchy':
      return api
        .listHierarchy(query)
        .pipe(map((page) => ({ snapshot: { tab, items: page.items }, total: page.total })));
  }
}

/** State of the Organization Management page. Provide it on the page component. */
export const OrganizationStore = signalStore(
  withState(initialState),
  withMethods((store, api = inject(OrganizationApi)) => {
    const loadCounts = (): void => {
      api
        .counts()
        .pipe(catchError(() => EMPTY))
        .subscribe((counts) => patchState(store, { counts }));
    };

    const load = rxMethod<{ tab: OrgTabId; query: OrgQuery }>(
      pipe(
        tap(() => patchState(store, { loading: true })),
        switchMap(({ tab, query }) =>
          loadTab(api, tab, query).pipe(
            tap((loaded) =>
              patchState(store, {
                snapshot: loaded.snapshot,
                total: loaded.total,
                loading: false,
              }),
            ),
            catchError(() => {
              patchState(store, {
                loading: false,
                total: 0,
                snapshot: emptySnapshot(tab),
              });
              return EMPTY;
            }),
          ),
        ),
      ),
    );

    return {
      start(): void {
        const query = store.query();
        load({ tab: store.snapshot().tab, query });
        loadCounts();
      },
      selectTab(tab: OrgTabId): void {
        if (tab === store.snapshot().tab) return;
        const query: OrgQuery = { ...store.query(), page: 1, search: '' };
        patchState(store, { snapshot: emptySnapshot(tab), query, total: 0 });
        load({ tab, query });
      },
      /** Filter changes go back to page 1. A page change does not. */
      updateQuery(change: Partial<OrgQuery>): void {
        const query: OrgQuery = {
          ...store.query(),
          ...change,
          ...(change.page === undefined ? { page: 1 } : {}),
        };
        patchState(store, { query });
        load({ tab: store.snapshot().tab, query });
      },
      reload(): void {
        load({ tab: store.snapshot().tab, query: store.query() });
        loadCounts();
      },
    };
  }),
);
