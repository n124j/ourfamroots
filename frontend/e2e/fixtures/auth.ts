/**
 * Playwright auth fixture — registers and logs in a test user,
 * stores auth state so it can be reused across test files.
 */
import { test as base, expect, type Page } from '@playwright/test';

export interface AuthFixtures {
  authenticatedPage: Page;
  testUser: { email: string; password: string; displayName: string };
}

export const TEST_USER = {
  email:       'e2e-test@ourfamroots-testing.com',
  password:    'E2eStr0ng!Pass2024',
  givenName:   'E2E',
  surname:     'Tester',
  displayName: 'E2E Tester',
};

/**
 * Log in via the UI and return the page in an authenticated state.
 */
export async function loginViaUI(page: Page): Promise<void> {
  await page.goto('/login');
  await page.getByLabel('Email').fill(TEST_USER.email);
  await page.getByLabel('Password').fill(TEST_USER.password);
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/(dashboard|trees)/, { timeout: 10_000 });
}

/**
 * Register the test user if not already registered.
 * Safe to call multiple times — ignores 409 Conflict.
 */
export async function ensureTestUserExists(page: Page): Promise<void> {
  const res = await page.request.post('/api/v1/auth/register', {
    data: {
      email:       TEST_USER.email,
      password:    TEST_USER.password,
      given_name:  TEST_USER.givenName,
      family_name: TEST_USER.surname,
    },
  });
  // 204 = created, 409 = already exists — both OK
  if (res.status() !== 204 && res.status() !== 409) {
    const body = await res.text().catch(() => '');
    throw new Error(`Unexpected registration response: ${res.status()} ${body}`);
  }
}

export const test = base.extend<AuthFixtures>({
  testUser: async ({}, use) => {
    await use(TEST_USER);
  },

  authenticatedPage: async ({ page, playwright }, use) => {
    await ensureTestUserExists(page);
    await loginViaUI(page);

    // Get API token using a separate request context (avoids leaking cookies into browser)
    let apiToken = '';
    let userId = '';
    const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:5173';
    const apiCtx = await playwright.request.newContext({ baseURL });
    try {
      const loginRes = await apiCtx.post('/api/v1/auth/login', {
        data: { email: TEST_USER.email, password: TEST_USER.password },
      });
      if (loginRes.ok()) {
        const data = await loginRes.json();
        apiToken = data.access_token ?? '';
        userId = data.user_id ?? '';
      }
    } finally {
      await apiCtx.dispose();
    }

    // Set token and suppress welcome modal on the CURRENT page
    await page.evaluate(({ userId, apiToken }) => {
      if (userId) localStorage.setItem(`welcome_seen_${userId}`, '1');
      if (apiToken) (window as any).__e2e_api_token__ = apiToken;
    }, { userId, apiToken });

    // Also set up an init script for FUTURE navigations
    if (userId || apiToken) {
      await page.context().addInitScript(({ userId, apiToken }) => {
        if (userId) localStorage.setItem(`welcome_seen_${userId}`, '1');
        if (apiToken) (window as any).__e2e_api_token__ = apiToken;
      }, { userId, apiToken });
    }

    // Dismiss welcome modal if currently showing
    const dismissBtn = page.getByRole('button', { name: /explore on my own/i });
    await dismissBtn.click({ timeout: 2_000 }).catch(() => {});

    await use(page);
  },
});

export { expect };
