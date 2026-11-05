import { describe, expect, it } from 'vitest';
import {
  AscCallVisit,
  ServiceContractDetail,
} from '@trishul/service-data-access';
import { countBlocked } from './asc-call-visits';

const contract = (changes: Partial<ServiceContractDetail> = {}) =>
  ({ state: 'Active', visitsRemaining: 2, ...changes }) as ServiceContractDetail;
const call = (changes: Partial<AscCallVisit> = {}) =>
  ({ visits: 0, countable: true, ...changes }) as AscCallVisit;

describe('countBlocked', () => {
  it('lets a completed call be counted while visits are left', () => {
    expect(countBlocked(contract(), call())).toBeNull();
  });

  it('stops a new count when the ASC has no visits left', () => {
    expect(countBlocked(contract({ visitsRemaining: 0 }), call())).toContain(
      'No visits',
    );
  });

  it('still lets a counted call be lowered when no visits are left', () => {
    expect(
      countBlocked(contract({ visitsRemaining: 0 }), call({ visits: 2 })),
    ).toBeNull();
  });

  it('allows any count when the ASC has no limit', () => {
    expect(countBlocked(contract({ visitsRemaining: null }), call())).toBeNull();
  });

  it('blocks a reopened call and a cancelled ASC', () => {
    expect(countBlocked(contract(), call({ countable: false }))).toContain(
      'Finish',
    );
    expect(countBlocked(contract({ state: 'Cancelled' }), call())).toContain(
      'cancelled',
    );
  });
});
