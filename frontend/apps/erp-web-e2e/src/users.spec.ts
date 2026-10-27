import { Page } from '@playwright/test';
import { expect, test } from './fixtures';
import { signIn } from './sign-in';

// Mock API (fixtures.ts): demo.admin and rahul.patil@trishul.co (employee EMP0010) exist; employees
// EMP0011 Sneha Kulkarni and EMP0012 Amit Joshi have no user yet. Data resets on every page load.

async function openUsers(page: Page): Promise<void> {
  await page.goto('/admin/users');
  await signIn(page);
  await expect(page.locator('h1')).toHaveText('Users');
}

test('the menu leads to the user list with employee details, roles and status', async ({
  page,
}) => {
  await page.goto('/');
  await signIn(page);
  await page.getByRole('link', { name: 'Users' }).click();
  await expect(page).toHaveURL(/\/admin\/users$/);
  const rahul = page.getByRole('row', { name: /rahul\.patil@trishul\.co/ });
  for (const text of [
    'EMP0010',
    'Rahul',
    'Patil',
    '9876543210',
    'Team Lead',
    'Service Team Lead · Pune',
    'Active',
  ]) {
    await expect(rahul).toContainText(text);
  }
  await expect(page.getByRole('row', { name: /demo\.admin/ })).toContainText(
    'Not linked',
  );
});

test('add a user for an employee and hand over a temporary password', async ({
  page,
}) => {
  await openUsers(page);
  await page.getByRole('link', { name: 'Add user' }).click();
  await expect(page.locator('h1')).toHaveText('Add user');

  await page.getByRole('combobox', { name: 'Employee' }).fill('sneha');
  await page.getByRole('option', { name: /EMP0011 · Sneha Kulkarni/ }).click();
  await expect(page.getByLabel('Email (sign-in name)')).toHaveValue(
    'sneha.k@trishul.co',
  ); // from the employee record
  const role = page.getByRole('combobox', { name: 'Role' });
  await role.click();
  await page.getByRole('option', { name: 'Back office' }).click();
  await expect(role).toContainText('Back office');
  await page.getByText('Show me a temporary password to hand over').click();
  await page.getByRole('button', { name: 'Add user' }).click();

  await expect(page.getByTestId('temporary-password')).toHaveText(
    'Mock#Temp12345',
  );
  await page.getByRole('button', { name: 'Done' }).click();
  await expect(page).toHaveURL(/\/admin\/users\/\d+$/);
  await expect(page.locator('h1')).toHaveText('Sneha Kulkarni');
  const side = page.getByRole('complementary', {
    name: 'Sign-in and employee',
  });
  await expect(side).toContainText('EMP0011');
  await expect(side).toContainText('9822000011'); // no own mobile, so the employee's
  await expect(
    page.getByText('Must set a password at next sign-in'),
  ).toBeVisible();
});

test('an employee who already has a user cannot be picked again', async ({
  page,
}) => {
  await openUsers(page);
  await page.getByRole('link', { name: 'Add user' }).click();
  await page.getByRole('combobox', { name: 'Employee' }).fill('EMP0010');
  await expect(
    page.getByRole('option', { name: /Rahul Patil.*already a user/ }),
  ).toBeDisabled();
});

test('a new user needs a picked employee, at least one role and a valid email', async ({
  page,
}) => {
  await openUsers(page);
  await page.getByRole('link', { name: 'Add user' }).click();
  await page.getByRole('combobox', { name: 'Employee' }).fill('nobody');
  await page.getByLabel('Email (sign-in name)').fill('not-an-email');
  await page.getByRole('button', { name: 'Remove role 1' }).click();
  await page.getByRole('button', { name: 'Add user' }).click();
  await expect(
    page.getByText('Pick an employee from the list, or clear the field.'),
  ).toBeVisible();
  await expect(page.getByText('Enter a valid email address.')).toBeVisible();
  await expect(
    page.getByText('Give the user at least one role.'),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/admin\/users\/new$/);
});

test("change a user's roles", async ({ page }) => {
  await openUsers(page);
  await page.getByRole('link', { name: 'rahul.patil@trishul.co' }).click();
  await expect(page.locator('h1')).toHaveText('Rahul Patil');
  const save = page.getByRole('button', { name: 'Save changes' });
  await expect(save).toBeDisabled(); // nothing changed yet

  await page.getByRole('button', { name: 'Add role' }).click();
  const roles = page.getByRole('combobox', { name: 'Role' });
  await expect(roles).toHaveCount(2); // Rahul's existing role plus the new row
  const newRole = roles.last();
  await newRole.click();
  await page.getByRole('option', { name: 'Back office' }).click();
  await expect(newRole).toContainText('Back office');
  await save.click();
  await expect(page.getByText('Changes saved')).toBeVisible();

  await page.getByRole('link', { name: 'All users' }).click();
  await expect(page.getByRole('row', { name: /Rahul Patil/ })).toContainText(
    'Back office',
  );
});

test('link an existing user to a different employee', async ({ page }) => {
  await openUsers(page);
  await page.getByRole('link', { name: 'rahul.patil@trishul.co' }).click();
  await expect(page.getByRole('combobox', { name: 'Employee' })).toHaveValue(
    'EMP0010 · Rahul Patil · Team Lead',
  );
  await page.getByRole('button', { name: 'Clear employee' }).click();
  await page.getByRole('combobox', { name: 'Employee' }).fill('amit');
  await page.getByRole('option', { name: /EMP0012 · Amit Joshi/ }).click();
  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByText('Changes saved')).toBeVisible();
  await expect(page.locator('h1')).toHaveText('Amit Joshi');

  await page.getByRole('link', { name: 'All users' }).click();
  await expect(
    page.getByRole('row', { name: /rahul\.patil@trishul\.co/ }),
  ).toContainText('EMP0012');
});

test('deactivate after confirming, then activate again', async ({ page }) => {
  await openUsers(page);
  await page
    .getByRole('button', { name: 'Actions for rahul.patil@trishul.co' })
    .click();
  await page.getByRole('menuitem', { name: 'Deactivate' }).click();
  await expect(
    page.getByRole('heading', { name: 'Deactivate user?' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Deactivate' }).click();

  await expect(
    page.getByText('rahul.patil@trishul.co deactivated'),
  ).toBeVisible();
  await expect(page.getByRole('row', { name: /Rahul Patil/ })).toHaveCount(0); // list shows active users

  await page.getByRole('combobox', { name: 'Status' }).click();
  await page.getByRole('option', { name: 'Inactive' }).click();
  const rahul = page.getByRole('row', { name: /Rahul Patil/ });
  await expect(rahul).toContainText('Inactive');
  await rahul.getByRole('button', { name: /Actions for/ }).click();
  await page.getByRole('menuitem', { name: 'Activate' }).click();
  await expect(
    page.getByText('rahul.patil@trishul.co can sign in again'),
  ).toBeVisible();
});

test('reset a password and show a temporary one', async ({ page }) => {
  await openUsers(page);
  await page.getByRole('link', { name: 'rahul.patil@trishul.co' }).click();
  await page.getByRole('button', { name: 'Reset password' }).click();
  await page.getByText('Show me a temporary password to hand over').click();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Reset password' })
    .click();
  await expect(page.getByTestId('temporary-password')).toHaveText(
    'Mock#Reset12345',
  );
  await page.getByRole('button', { name: 'Done' }).click();
  await expect(
    page.getByText('Must set a password at next sign-in'),
  ).toBeVisible();
});
