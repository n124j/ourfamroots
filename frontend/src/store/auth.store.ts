/**
 * auth.store — Zustand store for JWT tokens and current user.
 *
 * Security decisions:
 *  - Access token: memory only (never localStorage / sessionStorage → no XSS leak)
 *  - Refresh token: httpOnly cookie managed by the server
 *  - On hard refresh: call POST /auth/refresh (cookie is sent automatically)
 *    to silently recover a new access token before rendering protected routes.
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

export interface AuthUser {
  id: string;
  tenantId: string;
  email: string;
  displayName: string;
  avatarUrl?: string;
  isEmailVerified: boolean;
  appRole: 'SUPER_ADMIN' | 'ADMIN' | 'STANDARD' | 'AUDITOR';
}

interface AuthStore {
  // ── State ──────────────────────────────────────────────────────────────
  accessToken: string | null;
  user: AuthUser | null;
  isInitialised: boolean;   // true once the silent-refresh attempt has completed

  // ── Mutations ──────────────────────────────────────────────────────────
  setAccessToken: (token: string) => void;
  setUser: (user: AuthUser) => void;
  /** Called after successful login / OAuth callback */
  login: (accessToken: string, user: AuthUser) => void;
  /** Clears memory; server must clear the httpOnly refresh cookie */
  logout: () => void;
  setInitialised: () => void;

  // ── Derived ────────────────────────────────────────────────────────────
  isAuthenticated: boolean;
}

export const useAuthStore = create<AuthStore>()(
  devtools(
    (set, get) => ({
      accessToken: null,
      user: null,
      isInitialised: false,
      isAuthenticated: false,

      setAccessToken: (token) =>
        set({ accessToken: token, isAuthenticated: true }),

      setUser: (user) => set({ user }),

      login: (accessToken, user) =>
        set({ accessToken, user, isAuthenticated: true }),

      logout: () =>
        set({ accessToken: null, user: null, isAuthenticated: false }),

      setInitialised: () => set({ isInitialised: true }),
    }),
    { name: 'auth-store' }
  )
);

// ── Silent refresh helper (call once on app boot) ──────────────────────────

const _API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

export async function initAuth(): Promise<void> {
  const store = useAuthStore.getState();
  if (store.isInitialised) return;

  try {
    // Step 1: use the httpOnly refresh cookie to get a new access token
    const refreshRes = await fetch(`${_API_BASE}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    });

    if (!refreshRes.ok) {
      console.warn('[initAuth] refresh failed:', refreshRes.status, await refreshRes.text().catch(() => ''));
      return;
    }

    const { access_token } = await refreshRes.json();
    store.setAccessToken(access_token);

    // Step 2: fetch the user profile with the new access token
    const meRes = await fetch(`${_API_BASE}/users/me`, {
      headers: { Authorization: `Bearer ${access_token}` },
      credentials: 'include',
    });

    if (meRes.ok) {
      const u = await meRes.json();
      store.setUser({
        id: u.id,
        tenantId: u.tenant_id,
        email: u.email,
        displayName: `${u.given_name ?? ''} ${u.family_name ?? ''}`.trim() || u.email,
        avatarUrl: u.avatar_url,
        isEmailVerified: u.email_verified,
        appRole: u.app_role ?? 'STANDARD',
      });
    } else {
      console.warn('[initAuth] /users/me failed:', meRes.status, await meRes.text().catch(() => ''));
    }
  } catch (err) {
    console.error('[initAuth] network error:', err);
  } finally {
    store.setInitialised();
  }
}
