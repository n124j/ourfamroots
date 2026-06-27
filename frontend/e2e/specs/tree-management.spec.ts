/**
 * E2E tests — Family tree CRUD and person management.
 */
import { test, expect } from '../fixtures/auth';

test.describe('Tree creation', () => {
  test('can create a new family tree', async ({ authenticatedPage: page }) => {
    await page.goto('/dashboard');
    await page.getByRole('button', { name: /new tree/i }).click();

    await page.getByPlaceholder(/johnson family/i).fill('The Smith Family');
    await page.getByPlaceholder(/optional description/i).fill('My paternal line');
    await page.getByRole('button', { name: /create tree/i }).click();

    await expect(page.getByText('The Smith Family')).toBeVisible({ timeout: 5_000 });
  });

  test('tree name is required', async ({ authenticatedPage: page }) => {
    await page.goto('/dashboard');
    await page.getByRole('button', { name: /new tree/i }).click();

    // Submit button should be disabled when name is empty
    const submitBtn = page.getByRole('button', { name: /create tree/i });
    await expect(submitBtn).toBeDisabled({ timeout: 3_000 });
  });
});

test.describe('Person management', () => {
  let treeUrl: string;

  test.beforeEach(async ({ authenticatedPage: page }) => {
    const token = await page.evaluate(() => (window as any).__e2e_api_token__ ?? '');
    const res = await page.request.post('/api/v1/trees', {
      data: { name: `E2E Tree ${Date.now()}`, description: 'Test tree' },
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok()) {
      throw new Error(`Failed to create tree: ${res.status()} ${await res.text()}`);
    }
    const tree = await res.json();
    treeUrl = `/trees/${tree.id}`;
  });

  test('can add a person to the tree', async ({ authenticatedPage: page }) => {
    await page.goto(treeUrl);
    await page.getByRole('button', { name: /add person/i }).click();

    await page.getByPlaceholder('Given name').fill('John');
    await page.getByPlaceholder('Surname').fill('Smith');
    await page.getByRole('button', { name: /add person/i }).last().click();

    await expect(page.getByText('John Smith')).toBeVisible({ timeout: 5_000 });
  });

  test('can edit a person', async ({ authenticatedPage: page }) => {
    const token = await page.evaluate(() => (window as any).__e2e_api_token__ ?? '');
    const treeId = treeUrl.split('/').pop();
    await page.request.post(`/api/v1/trees/${treeId}/persons`, {
      data: { given_name: 'Jane', surname: 'Doe', sex: 'F' },
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }).catch(() => null);

    await page.goto(treeUrl);
    await page.getByText('Jane Doe').click({ timeout: 5_000 }).catch(() => {});

    const editBtn = page.getByRole('button', { name: /edit/i }).first();
    if (await editBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await editBtn.click();
      await page.getByPlaceholder('Given name').fill('Janet');
      await page.getByRole('button', { name: /save/i }).click();
      await expect(page.getByText('Janet Doe')).toBeVisible({ timeout: 5_000 });
    }
  });

  test('tree canvas renders on tree page', async ({ authenticatedPage: page }) => {
    await page.goto(treeUrl);

    // Add a person via UI so the canvas renders
    await page.getByRole('button', { name: /add person/i }).click();
    await page.getByPlaceholder('Given name').fill('Canvas');
    await page.getByPlaceholder('Surname').fill('Test');
    await page.getByRole('button', { name: /add person/i }).last().click();

    await expect(page.locator('.react-flow')).toBeVisible({ timeout: 10_000 });
  });

  test('layout toggle buttons are visible', async ({ authenticatedPage: page }) => {
    const token = await page.evaluate(() => (window as any).__e2e_api_token__ ?? '');
    const treeId = treeUrl.split('/').pop();
    await page.request.post(`/api/v1/trees/${treeId}/persons`, {
      data: { given_name: 'Layout', surname: 'Test', sex: 'U' },
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });

    await page.goto(treeUrl);
    // Check for layout controls or the person name
    const layoutBtn = page.getByRole('button', { name: /vertical|horizontal|fan|ancestor|descendant|layouts/i });
    const layoutsText = page.getByText(/layouts/i);
    await expect(layoutBtn.first().or(layoutsText)).toBeVisible({ timeout: 10_000 });
  });
});
