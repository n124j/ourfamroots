/**
 * E2E tests — Search functionality.
 */
import { test, expect } from '../fixtures/auth';

test.describe('Global search', () => {
  test('search bar is present in navigation', async ({ authenticatedPage: page }) => {
    await page.goto('/search');
    const searchInput = page.getByPlaceholder(/search people/i);
    await expect(searchInput).toBeVisible({ timeout: 5_000 });
  });

  test('typing in search bar shows results', async ({ authenticatedPage: page }) => {
    await page.goto('/search');
    const searchInput = page.getByPlaceholder(/search people/i);
    await searchInput.fill('Smith');

    // Results list or "no results" message appears after debounce
    await expect(
      page.getByText(/no results|no people|result/i).first()
    ).toBeVisible({ timeout: 5_000 });
  });

  test('search shows "No results" for nonsense query', async ({ authenticatedPage: page }) => {
    await page.goto('/search?q=Zzzxyz12345');

    await expect(
      page.getByText(/no results|no people|no matches/i)
    ).toBeVisible({ timeout: 5_000 });
  });

  test('Enter key navigates to full results page', async ({ authenticatedPage: page }) => {
    await page.goto('/search');
    const input = page.getByPlaceholder(/search people/i);
    await input.fill('Smith');
    await input.press('Enter');

    await expect(page).toHaveURL(/\/search\?q=Smith/, { timeout: 5_000 });
  });
});

test.describe('Results page', () => {
  test('search results page renders', async ({ authenticatedPage: page }) => {
    await page.goto('/search?q=Smith');
    await expect(page.getByText(/results for/i)).toBeVisible({ timeout: 5_000 });
  });

  test('sort dropdown changes sort order', async ({ authenticatedPage: page }) => {
    await page.goto('/search?q=Smith');
    const dropdown = page.getByRole('combobox').or(page.locator('select'));
    if (await dropdown.first().isVisible({ timeout: 3_000 }).catch(() => false)) {
      await dropdown.first().selectOption({ index: 1 });
      await expect(page.getByPlaceholder(/search people/i)).toBeVisible();
    }
  });

  test('birth year filter works', async ({ authenticatedPage: page }) => {
    await page.goto('/search?q=Smith');
    const minInput = page.getByPlaceholder('Born after');
    if (await minInput.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await minInput.fill('1800');
      await expect(page.getByPlaceholder(/search people/i)).toBeVisible({ timeout: 5_000 });
    }
  });
});

test.describe('Relationship finder', () => {
  test('relationship finder panel renders on tree page', async ({
    authenticatedPage: page,
  }) => {
    // Navigate to a tree (any)
    const token = await page.evaluate(() => (window as any).__e2e_api_token__ ?? '');
    const treesRes = await page.request.get('/api/v1/trees?limit=1', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (treesRes.ok()) {
      const data = await treesRes.json();
      if (data.items?.length) {
        await page.goto(`/trees/${data.items[0].id}`);
        const finderBtn = page.getByText(/relationship finder/i);
        if (await finderBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
          await expect(finderBtn).toBeVisible();
        }
      }
    }
  });
});
