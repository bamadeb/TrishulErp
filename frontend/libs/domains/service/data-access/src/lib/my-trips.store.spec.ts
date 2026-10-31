import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { Component, inject } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideApiConfiguration } from '@trishul/core-api';
import { MyTripsStore } from './my-trips.store';
import { TripListItem } from './trip.models';

function trip(id: number, overrides: Partial<TripListItem> = {}): TripListItem {
  return {
    id,
    employeeId: 5,
    employeeName: 'Ravi Das',
    module: 'SVC',
    activityTitle: 'Call #9001',
    tripType: 'To site',
    status: 'Completed',
    startAt: '2026-10-28T06:35:00Z',
    endAt: '2026-10-28T08:10:00Z',
    gpsDistanceKm: 12,
    adjustedDistanceKm: null,
    isDistanceAdjusted: false,
    effectiveDistanceKm: 12,
    durationMinutes: 95,
    ...overrides,
  };
}

function page(items: TripListItem[]) {
  return { items, total: items.length, page: 1, pageSize: 20 };
}

/** The store is provided per page, so host it in a component like the real page does. */
@Component({ template: '', providers: [MyTripsStore] })
class Host {
  readonly store = inject(MyTripsStore);
}

describe('MyTripsStore', () => {
  let store: InstanceType<typeof MyTripsStore>;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideApiConfiguration('/api'),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    store = TestBed.createComponent(Host).componentInstance.store;
  });

  afterEach(() => http.verify());

  it('loads the own-trips endpoint, newest first, and selects the newest trip', () => {
    const req = http.expectOne((r) => r.url === '/api/trk/trips/mine');
    expect(req.request.params.get('sort')).toBe('-startAt');
    expect(req.request.params.has('employeeId')).toBe(false);
    req.flush(page([trip(2), trip(1)]));

    expect(store.items().map((t) => t.id)).toEqual([2, 1]);
    expect(store.selectedTrip()?.id).toBe(2);
    http.expectOne('/api/trk/trips/2/adjustments').flush([]);
    expect(store.adjustmentsLoading()).toBe(false);
  });

  it('sends the status filter and goes back to page 1', () => {
    http.expectOne((r) => r.url === '/api/trk/trips/mine').flush(page([]));

    store.updateQuery({ page: 3 });
    http.expectOne((r) => r.url === '/api/trk/trips/mine').flush(page([]));

    store.updateQuery({ status: ['Completed'] });
    const req = http.expectOne((r) => r.url === '/api/trk/trips/mine');
    expect(req.request.params.get('status')).toBe('Completed');
    expect(req.request.params.get('page')).toBe('1');
    req.flush(page([]));
    expect(store.selectedTrip()).toBeNull();
  });

  it('shows the adjustment trail of the trip the engineer opens', () => {
    http
      .expectOne((r) => r.url === '/api/trk/trips/mine')
      .flush(page([trip(2), trip(1, { isDistanceAdjusted: true })]));
    http.expectOne('/api/trk/trips/2/adjustments').flush([]);

    store.select(1);
    http.expectOne('/api/trk/trips/1/adjustments').flush([
      {
        id: 40,
        tripId: 1,
        previousDistanceKm: 12,
        newDistanceKm: 18.5,
        gpsDistanceKmAtAdjustment: 12,
        reason: 'GPS under-counted on the hill road',
        adjustedByUserId: 7,
        adjustedByName: 'Team Lead',
        adjustedAt: '2026-10-29T10:00:00Z',
      },
    ]);
    expect(store.adjustments().map((a) => a.newDistanceKm)).toEqual([18.5]);
  });
});
