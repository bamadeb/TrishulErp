import { test as base } from '@playwright/test';

/** The end-to-end tests run against the mock API with development sign-in, whatever
 * apps/erp-web/public/config.json is set to for local work. */
const E2E_CONFIG = {
  apiBaseUrl: '/api/v1',
  useMockApi: true,
  auth: { mode: 'dev', userPoolId: '', userPoolClientId: '' },
};

export const test = base.extend({
  page: async ({ page }, use) => {
    await page.route('**/config.json', (route) =>
      route.fulfill({ json: E2E_CONFIG }),
    );
    await use(page);
  },
});

export { expect } from '@playwright/test';
