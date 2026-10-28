import { expect, test } from './fixtures';
import { signIn } from './sign-in';

// The mock API (mock-service-import.ts) returns a fixed 3-row result regardless of the file's
// contents, so the upload screen can be exercised without parsing a real .xlsx in the browser.

const dummyXlsx = {
  name: 'STEP_3_CALL_ASSIGNMENT_ListofServiceOrders.xlsx',
  mimeType:
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  buffer: Buffer.from('PK dummy'),
};

test('the menu leads to the BYD import screen', async ({ page }) => {
  await page.goto('/');
  await signIn(page);
  await page.getByRole('link', { name: 'Import calls' }).click();
  await expect(page).toHaveURL(/\/service\/calls\/import$/);
  await expect(page.locator('h1')).toHaveText('Import service calls');
});

test('preview then import a BYD export', async ({ page }) => {
  await page.goto('/service/calls/import');
  await signIn(page);
  await expect(page.locator('h1')).toHaveText('Import service calls');

  await page.setInputFiles('input[type=file]', dummyXlsx);

  await page.getByRole('button', { name: 'Preview' }).click();
  await expect(page.getByText('Preview only')).toBeVisible();
  // The row whose customer is unknown is flagged, and the counts show up.
  await expect(page.getByText('2 new')).toBeVisible();
  const unlinked = page.getByRole('row', { name: /Golap Manjari Rout/ });
  await expect(unlinked).toContainText('Needs linking');

  await page.getByRole('button', { name: 'Import' }).click();
  await expect(page.getByText('Import complete')).toBeVisible();
  await expect(page.getByText('Imported: 2 new')).toBeVisible();
});
