/**
 * OAuthButtons — Social login buttons shown only when their client ID is configured.
 *
 * Uses the Authorization Code flow initiated by the backend.
 * Clicking redirects to /api/v1/auth/oauth/{provider}, which then
 * redirects to the provider, then back to /auth/callback.
 */

import React, { memo } from 'react';

// ── Provider config ────────────────────────────────────────────────────────

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? '';
const GITHUB_CLIENT_ID = import.meta.env.VITE_GITHUB_CLIENT_ID ?? '';

const GOOGLE_PROVIDER = {
  id: 'google',
  label: 'Continue with Google',
  icon: (
    <svg width="18" height="18" viewBox="0 0 48 48">
      <path fill="#EA4335" d="M24 9.5c3.14 0 5.95 1.08 8.17 2.84l6.08-6.08C34.41 3.04 29.53 1 24 1 14.91 1 7.12 6.44 3.48 14.16l7.11 5.52C12.27 13.57 17.67 9.5 24 9.5z"/>
      <path fill="#4285F4" d="M46.1 24.55c0-1.64-.15-3.23-.41-4.77H24v9.03h12.42c-.54 2.88-2.18 5.32-4.64 6.96l7.11 5.52C43.18 37.28 46.1 31.34 46.1 24.55z"/>
      <path fill="#FBBC05" d="M10.59 28.32A14.5 14.5 0 0 1 9.5 24c0-1.5.26-2.95.71-4.32L3.1 14.16A23.1 23.1 0 0 0 1 24c0 3.72.87 7.24 2.48 10.32l7.11-6z"/>
      <path fill="#34A853" d="M24 47c5.53 0 10.17-1.83 13.56-4.97l-7.11-5.52c-1.84 1.23-4.2 1.99-6.45 1.99-6.33 0-11.73-4.07-13.41-9.68l-7.11 5.52C7.12 41.56 14.91 47 24 47z"/>
    </svg>
  ),
} as const;

const GITHUB_PROVIDER = {
  id: 'github',
  label: 'Continue with GitHub',
  icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
    </svg>
  ),
} as const;

// Build provider list: each button shown only when its client ID is configured
const PROVIDERS = [
  ...(GOOGLE_CLIENT_ID ? [GOOGLE_PROVIDER] : []),
  ...(GITHUB_CLIENT_ID ? [GITHUB_PROVIDER] : []),
];

export const hasOAuthProviders = PROVIDERS.length > 0;

// ── Component ──────────────────────────────────────────────────────────────

interface OAuthButtonsProps {
  /** Shown above the buttons */
  dividerLabel?: string;
  className?: string;
  /**
   * Path (and optional query) to return to if the user cancels OAuth on the
   * provider's screen — e.g. "/login", "/register", or "/?auth=login" for a
   * landing-page popup. Defaults to the current location.
   */
  next?: string;
}

export const OAuthButtons = memo(({ dividerLabel = 'or', className = '', next }: OAuthButtonsProps) => {
  if (PROVIDERS.length === 0) return null;

  function handleOAuth(provider: string) {
    const returnTo = next ?? `${window.location.pathname}${window.location.search}`;
    window.location.href = `${API_BASE}/auth/oauth/${provider}?next=${encodeURIComponent(returnTo)}`;
  }

  return (
    <div className={`space-y-3 ${className}`}>
      {dividerLabel && (
        <div className="relative flex items-center gap-3 my-2">
          <div className="flex-1 h-px bg-slate-200" />
          <span className="text-xs text-slate-400 font-medium">{dividerLabel}</span>
          <div className="flex-1 h-px bg-slate-200" />
        </div>
      )}

      {PROVIDERS.map((p) => (
        <button
          key={p.id}
          onClick={() => handleOAuth(p.id)}
          type="button"
          className="flex items-center justify-center gap-3 w-full h-10 px-4 rounded-lg border border-slate-300 bg-white text-slate-700 text-sm font-medium hover:bg-slate-50 hover:border-slate-400 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
        >
          {p.icon}
          {p.label}
        </button>
      ))}
    </div>
  );
});
OAuthButtons.displayName = 'OAuthButtons';

// ── OAuth callback page helper ─────────────────────────────────────────────
/**
 * After OAuth redirect from backend, the frontend lands on /auth/callback?access_token=...
 * This hook extracts the token and stores it in auth store.
 */
export function useOAuthCallback() {
  const search = new URLSearchParams(window.location.search);
  const accessToken = search.get('access_token');
  const error = search.get('error');
  return { accessToken, error };
}
