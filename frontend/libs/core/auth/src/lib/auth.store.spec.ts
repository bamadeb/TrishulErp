import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideApiConfiguration } from '@trishul/core-api';
import { CurrentUser } from './auth.models';
import { AuthStore } from './auth.store';

const user: CurrentUser = {
  id: 7,
  username: 'team.lead',
  displayName: 'Team Lead',
  email: null,
  defaultBranchId: 2,
  permissions: ['svc.call.assign', 'svc.call.close'],
  branches: [
    { id: 1, code: 'PUN', name: 'Pune' },
    { id: 2, code: 'MUM', name: 'Mumbai' },
  ],
  principals: [{ id: 1, code: 'ATLAS_COPCO', name: 'Atlas Copco' }],
};

describe('AuthStore', () => {
  let store: InstanceType<typeof AuthStore>;
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideApiConfiguration('/api'),
      ],
    });
    store = TestBed.inject(AuthStore);
    http = TestBed.inject(HttpTestingController);
  });

  async function signIn(u: CurrentUser): Promise<void> {
    const loading = store.loadCurrentUser();
    http.expectOne('/api/me').flush(u);
    await loading;
  }

  it('grants only the permissions the user holds', async () => {
    await signIn(user);
    expect(store.hasPermission('svc.call.assign')).toBe(true);
    expect(store.hasPermission('sal.invoice.post')).toBe(false);
    expect(store.hasAnyPermission(['sal.invoice.post', 'svc.call.close'])).toBe(
      true,
    );
  });

  it('treats * as every permission', async () => {
    await signIn({ ...user, permissions: ['*'] });
    expect(store.hasPermission('acc.period.lock')).toBe(true);
  });

  it('starts in the default branch with all brands', async () => {
    await signIn(user);
    expect(store.currentBranch()?.code).toBe('MUM');
    expect(store.principalId()).toBeNull();
  });

  it('restores a remembered branch only if the user still has it', async () => {
    store.selectBranch(1);
    await signIn(user);
    expect(store.branchId()).toBe(1);

    store.selectBranch(99);
    await signIn(user);
    expect(store.branchId()).toBe(2);
  });
});
