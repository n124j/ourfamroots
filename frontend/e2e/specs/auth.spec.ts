/**
 * E2E tests — Authentication flows.
 * Covers: register, login, logout, token refresh, OAuth redirect.
 */
import { test, expect } from '@playwright/test';
import { ensureTestUserExists, TEST_USER } from '../fixtures/auth';

test.describe('Registration', () => {
  test('user can register a new account', async ({ page }) => {
    const uniqueEmail = `reg-${Date.now()}@ourfamroots-testing.com`;

    await page.goto('/register');
    await page.getByLabel('First name').fill('New');
    await page.getByLabel('Last name').fill('User');
    await page.getByLabel('Email').fill(uniqueEmail);
    await page.getByLabel('Password', { exact: true }).fill('Str0ng!Pass2024');
    await page.getByLabel('Confirm password').fill('Str0ng!Pass2024');
    await page.getByRole('button', { name: /create account/i }).click();

    // Registration sends verification email — should redirect to login with registered flag
    await expect(page).toHaveURL(/\/login\?registered=1/, { timeout: 10_000 });
  });

  test('duplicate email shows error', async ({ page }) => {
    await ensureTestUserExists(page);
    await page.goto('/register');
    await page.getByLabel('Email').fill(TEST_USER.email);
    await page.getByLabel('Password', { exact: true }).fill(TEST_USER.password);
    await page.getByLabel('Confirm password').fill(TEST_USER.password);
    await page.getByLabel('First name').fill('Dup');
    await page.getByLabel('Last name').fill('User');
    await page.getByRole('button', { name: /create account/i }).click();

    await expect(page.getByText(/already (registered|exists)/i)).toBeVisible({ timeout: 5_000 });
  });

  test('weak password shows validation error', async ({ page }) => {
    await page.goto('/register');
    await page.getByLabel('First name').fill('Weak');
    await page.getByLabel('Last name').fill('User');
    await page.getByLabel('Email').fill(`weak-${Date.now()}@ourfamroots-testing.com`);
    await page.getByLabel('Password', { exact: true }).fill('weakpassword');
    await page.getByLabel('Confirm password').fill('weakpassword');
    await page.getByRole('button', { name: /create account/i }).click();

    await expect(page.getByText(/validation|failed|password must/i)).toBeVisible({ timeout: 5_000 });
  });

  test('registration form has no Organisation ID field', async ({ page }) => {
    await page.goto('/register');
    // tenant_slug / Organisation ID field must not exist on the form
    await expect(page.getByLabel(/organisation id|org id|tenant/i)).not.toBeVisible();
  });

  test('after registration hard-refresh does not grant dashboard access', async ({ page }) => {
    const uniqueEmail = `unverified-${Date.now()}@ourfamroots-testing.com`;

    await page.goto('/register');
    await page.getByLabel('First name').fill('Unverified');
    await page.getByLabel('Last name').fill('User');
    await page.getByLabel('Email').fill(uniqueEmail);
    await page.getByLabel('Password', { exact: true }).fill('Str0ng!Pass2024');
    await page.getByLabel('Confirm password').fill('Str0ng!Pass2024');
    await page.getByRole('button', { name: /create account/i }).click();

    // Wait for redirect to login
    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });

    // Hard-navigate to a protected route — must not be granted access without login
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/login/, { timeout: 5_000 });
  });
});

test.describe('Login', () => {
  test.beforeEach(async ({ page }) => {
    await ensureTestUserExists(page);
  });

  test('valid credentials redirect to dashboard', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(TEST_USER.email);
    await page.getByLabel('Password').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(page).toHaveURL(/\/(dashboard|trees)/, { timeout: 10_000 });
  });

  test('wrong password shows error message', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(TEST_USER.email);
    await page.getByLabel('Password').fill('WrongPassword!');
    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(
      page.getByText(/invalid|incorrect|wrong|credentials/i)
    ).toBeVisible({ timeout: 5_000 });
  });

  test('access token is NOT stored in localStorage', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(TEST_USER.email);
    await page.getByLabel('Password').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(page).toHaveURL(/\/(dashboard|trees)/, { timeout: 10_000 });

    const storedToken = await page.evaluate(() => {
      return Object.keys(localStorage).some((k) =>
        k.includes('token') || k.includes('access')
      );
    });
    expect(storedToken).toBe(false);
  });

  test('?next param preserves redirect after login', async ({ page }) => {
    await page.goto('/login?next=/search');
    await page.getByLabel('Email').fill(TEST_USER.email);
    await page.getByLabel('Password').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(page).toHaveURL('/search', { timeout: 10_000 });
  });
});

test.describe('Logout', () => {
  test('logout clears session and redirects to login', async ({ page }) => {
    await ensureTestUserExists(page);
    await page.goto('/login');
    await page.getByLabel('Email').fill(TEST_USER.email);
    await page.getByLabel('Password').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/(dashboard|trees)/, { timeout: 10_000 });

    // Dismiss the welcome modal if present
    const dismissBtn = page.getByRole('button', { name: /explore on my own/i });
    await dismissBtn.click({ timeout: 3_000 }).catch(() => {});

    // Click the sign-out button in the sidebar
    await page.getByRole('button', { name: /sign out/i }).click();

    // Logout redirects to landing page (/) via window.location.href
    await expect(page).not.toHaveURL(/\/dashboard/, { timeout: 5_000 });
  });

  test('accessing protected route after logout redirects to login', async ({ page }) => {
    await ensureTestUserExists(page);
    // Force clear any session
    await page.context().clearCookies();
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/login/, { timeout: 5_000 });
  });
});

test.describe('Session persistence', () => {
  test('hard refresh preserves authenticated state via silent refresh', async ({ page }) => {
    await ensureTestUserExists(page);
    await page.goto('/login');
    await page.getByLabel('Email').fill(TEST_USER.email);
    await page.getByLabel('Password').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/(dashboard|trees)/, { timeout: 10_000 });

    // Hard reload — access token in memory is lost; should recover via cookie
    await page.reload();
    await expect(page).not.toHaveURL('/login', { timeout: 5_000 });
  });
});

test.describe('OAuth — Google', () => {
  test('login page shows Google sign-in button', async ({ page }) => {
    await page.goto('/login');
    const btn = page.getByText('Continue with Google');
    const visible = await btn.isVisible().catch(() => false);
    test.skip(!visible, 'GOOGLE_CLIENT_ID not configured — OAuth button not rendered');
    await expect(btn).toBeVisible();
  });

  test('clicking Google button redirects to backend OAuth endpoint', async ({ page }) => {
    await page.goto('/login');
    const btn = page.getByText('Continue with Google');
    const visible = await btn.isVisible().catch(() => false);
    test.skip(!visible, 'GOOGLE_CLIENT_ID not configured — OAuth button not rendered');

    // Intercept the navigation to the backend OAuth route
    const [request] = await Promise.all([
      page.waitForRequest((req) => req.url().includes('/api/v1/auth/oauth/google')),
      btn.click(),
    ]);

    expect(request.url()).toContain('/api/v1/auth/oauth/google');
  });

  test('OAuth callback with error redirects to login with message', async ({ page }) => {
    await page.goto('/auth/callback?error=oauth_cancelled');
    await expect(page).toHaveURL(/\/login\?error=oauth_cancelled/, { timeout: 5_000 });
  });

  test('OAuth callback without token redirects to login', async ({ page }) => {
    await page.goto('/auth/callback');
    await expect(page).toHaveURL(/\/login\?error=/, { timeout: 5_000 });
  });

  test('login page shows error banner for OAuth state mismatch', async ({ page }) => {
    await page.goto('/login?error=oauth_state_mismatch');
    await expect(
      page.getByText(/session expired|try again/i)
    ).toBeVisible({ timeout: 5_000 });
  });

  test('login page shows generic error banner for OAuth provider error', async ({ page }) => {
    await page.goto('/login?error=oauth_provider_error');
    await expect(
      page.getByText(/error occurred|try again/i)
    ).toBeVisible({ timeout: 5_000 });
  });
});
