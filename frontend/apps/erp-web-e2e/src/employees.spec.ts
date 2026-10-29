import { Page } from '@playwright/test';
import { expect, test } from './fixtures';
import { signIn } from './sign-in';

// Mock API (mock-employees.ts): EMP0010 Rahul Patil (has a login), EMP0011 Sneha Kulkarni and
// EMP0012 Amit Joshi (no login). Data resets on every page load.

async function openEmployees(page: Page): Promise<void> {
  await page.goto('/admin/employees');
  await signIn(page);
  await expect(page.locator('h1')).toHaveText('Employees');
}

/** Open a form select and choose an option, retrying until the (async-loaded) option appears. */
async function selectFromForm(
  page: Page,
  form: ReturnType<Page['locator']>,
  field: string,
  option: string,
): Promise<void> {
  await expect(async () => {
    await form.getByRole('combobox', { name: field }).click();
    await expect(page.getByRole('option', { name: option })).toBeVisible({
      timeout: 1000,
    });
  }).toPass();
  await page.getByRole('option', { name: option }).click();
}

test('the menu leads to the employee list with details and status', async ({
  page,
}) => {
  await page.goto('/');
  await signIn(page);
  await page.getByRole('link', { name: 'Employees' }).click();
  await expect(page).toHaveURL(/\/admin\/employees$/);
  const rahul = page.getByRole('row', { name: /Rahul Patil/ });
  for (const text of [
    'EMP0010',
    'Rahul Patil',
    '9822000010',
    'Pune',
    'Permanent',
    'Active',
  ]) {
    await expect(rahul).toContainText(text);
  }
});

test('add an employee', async ({ page }) => {
  await openEmployees(page);
  await page.getByRole('link', { name: 'Add employee' }).click();
  await expect(page.locator('h1')).toHaveText('Add employee');

  const form = page.locator('form'); // scope past the toolbar's own Branch picker
  await form.getByLabel('Employee code').fill('EMP0099');
  await form.getByLabel('First name').fill('Test');
  await form.getByLabel('Last name').fill('User');
  // The option lists load asynchronously; reopen until the choice is there.
  await selectFromForm(page, form, 'Company', 'Trishul');
  await selectFromForm(page, form, 'Branch', 'Pune');
  await page.getByRole('button', { name: 'Add employee' }).click();

  await expect(page).toHaveURL(/\/admin\/employees\/\d+$/);
  await expect(page.locator('h1')).toHaveText('Test User');
});

test('a new employee needs a code, name, company and branch', async ({
  page,
}) => {
  await openEmployees(page);
  await page.getByRole('link', { name: 'Add employee' }).click();
  await page.getByRole('button', { name: 'Add employee' }).click();
  await expect(
    page.getByText('A unique employee code is required.'),
  ).toBeVisible();
  await expect(page.getByText('Choose a company.')).toBeVisible();
  await expect(page).toHaveURL(/\/admin\/employees\/new$/);
});

test("change an employee's designation", async ({ page }) => {
  await openEmployees(page);
  await page.getByRole('link', { name: 'Sneha Kulkarni' }).click();
  await expect(page.locator('h1')).toHaveText('Sneha Kulkarni');
  const save = page.getByRole('button', { name: 'Save changes' });
  await expect(save).toBeDisabled();

  await page
    .locator('form')
    .getByRole('combobox', { name: 'Designation' })
    .click();
  await page.getByRole('option', { name: 'Team Lead' }).click();
  await save.click();
  await expect(page.getByText('Changes saved')).toBeVisible();
});

test('deactivating an employee who has a login is refused', async ({
  page,
}) => {
  await openEmployees(page);
  await page.getByRole('button', { name: 'Actions for EMP0010' }).click();
  await page.getByRole('menuitem', { name: 'Deactivate' }).click();
  await page.getByRole('button', { name: 'Deactivate' }).click();
  // The API refuses it, so Rahul stays in the active list.
  await expect(page.getByRole('row', { name: /Rahul Patil/ })).toBeVisible();
});

test('deactivate and reactivate an employee', async ({ page }) => {
  await openEmployees(page);
  await page.getByRole('button', { name: 'Actions for EMP0012' }).click();
  await page.getByRole('menuitem', { name: 'Deactivate' }).click();
  await page.getByRole('button', { name: 'Deactivate' }).click();
  await expect(page.getByText('Amit Joshi deactivated')).toBeVisible();
  await expect(page.getByRole('row', { name: /Amit Joshi/ })).toHaveCount(0);

  await page.getByRole('combobox', { name: 'Status' }).click();
  await page.getByRole('option', { name: 'Inactive' }).click();
  const amit = page.getByRole('row', { name: /Amit Joshi/ });
  await expect(amit).toContainText('Inactive');
  await amit.getByRole('button', { name: /Actions for/ }).click();
  await page.getByRole('menuitem', { name: 'Activate' }).click();
  await expect(page.getByText('Amit Joshi is active again')).toBeVisible();
});
