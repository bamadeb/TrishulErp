import { expect, test } from './fixtures';
import { signIn } from './sign-in';

// Runs against the mock API with development sign-in (see fixtures.ts).

test('dashboard greets the signed-in user', async ({ page }) => {
  await page.goto('/');
  await signIn(page);
  await expect(page.locator('h1')).toContainText('Welcome, Demo Admin');
});

test('call register lists, filters and pages calls', async ({ page }) => {
  await page.goto('/');
  await signIn(page);
  await page.getByRole('link', { name: 'Service calls' }).click();

  await expect(page).toHaveURL(/\/service\/calls$/);
  await expect(page.locator('h1')).toHaveText('Service calls');
  const rows = page.locator('table tr.mat-mdc-row');
  await expect(rows).toHaveCount(20);
  await expect(page.getByText(/1 – 20 of \d+/)).toBeVisible();

  await page.getByRole('button', { name: 'Next page' }).click();
  await expect(page.getByText(/21 – \d+ of \d+/)).toBeVisible();

  await page.getByRole('searchbox', { name: 'Search calls' }).fill('Sahyadri');
  await expect(rows.first()).toContainText('Sahyadri Pharma');
  for (const row of await rows.all()) {
    await expect(row).toContainText('Sahyadri Pharma');
  }
});

test('unknown routes show the not-found page', async ({ page }) => {
  await page.goto('/no-such-page');
  await signIn(page);
  await expect(page.locator('h1')).toHaveText('Page not found');
});
