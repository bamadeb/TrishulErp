import { expect, test } from './fixtures';
import { signIn } from './sign-in';

test('signed-out users are sent to the login page', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveURL(/\/login\?returnUrl=%2F$/);
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
});

test('after signing in, the user lands on the page they asked for', async ({
  page,
}) => {
  await page.goto('/service/calls');
  await signIn(page);
  await expect(page).toHaveURL(/\/service\/calls$/);
  await expect(page.locator('h1')).toHaveText('Service calls');
});

test('the session survives a reload in the same tab', async ({ page }) => {
  await page.goto('/');
  await signIn(page);
  await page.reload();
  await expect(page.locator('h1')).toContainText('Welcome, Demo Admin');
});

test('signing out returns to the login page and protects the app again', async ({
  page,
}) => {
  await page.goto('/');
  await signIn(page);
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL(/\/login$/);

  await page.goto('/service/calls');
  await expect(page).toHaveURL(/\/login\?returnUrl=/);
});

test('a signed-in user opening /login goes to the app', async ({ page }) => {
  await page.goto('/');
  await signIn(page);
  await page.goto('/login');
  await expect(page).not.toHaveURL(/\/login/);
});

test('an empty username is rejected on the page', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByText('Enter your username.')).toBeVisible();
  await expect(page).toHaveURL(/\/login/);
});
