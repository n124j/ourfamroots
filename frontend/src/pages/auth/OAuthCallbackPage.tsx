/**
 * OAuthCallbackPage — /auth/callback
 *
 * The backend redirects here after successful OAuth with:
 *   ?access_token=<jwt>&provider=google|github
 *
 * This page:
 *  1. Reads the token from the URL
 *  2. Fetches the current user with it
 *  3. Stores both in auth.store
 *  4. Replaces the URL (drops the token from history)
 *  5. Navigates to /dashboard
 *
 * If there's an error param, redirects to /login?error=...
 */

import { useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '@store/auth.store';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

async function fetchMe(accessToken: string) {
  const res = await fetch(`${API_BASE}/users/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error('Failed to fetch user');
  return res.json();
}

export default function OAuthCallbackPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const storeLogin = useAuthStore((s) => s.login);
  const called = useRef(false);

  useEffect(() => {
    if (called.current) return;
    called.current = true;

    const accessToken = searchParams.get('access_token');
    const error       = searchParams.get('error');

    if (error || !accessToken) {
      navigate(`/login?error=${error ?? 'oauth_failed'}`, { replace: true });
      return;
    }

    fetchMe(accessToken)
      .then((user) => {
        storeLogin(accessToken, {
          id: user.id,
          tenantId: user.tenant_id,
          email: user.email,
          displayName:
            `${user.given_name ?? ''} ${user.family_name ?? ''}`.trim() ||
            user.email,
          avatarUrl: user.avatar_url,
          isEmailVerified: user.email_verified,
          appRole: user.app_role ?? 'STANDARD',
        });
        // Drop token from URL, go to dashboard
        navigate('/dashboard', { replace: true });
      })
      .catch(() => {
        navigate('/login?error=oauth_user_fetch_failed', { replace: true });
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="fixed inset-0 flex flex-col items-center justify-center bg-white gap-4">
      <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      <p className="text-sm text-slate-500">Completing sign-in…</p>
    </div>
  );
}
