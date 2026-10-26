import { Page, expect } from '@playwright/test';

/** Signs in through the login page (development sign-in: username only, as in config.json). */
export async function signIn(
  page: Page,
  username = 'demo.admin',
): Promise<void> {
  await expect(page).toHaveURL(/\/login/);
  await page.getByLabel('Username').fill(username);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).not.toHaveURL(/\/login/);
}
