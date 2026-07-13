/**
 * NamespaceInvitationAcceptPage — handles /namespace-invitations/:token links from email.
 *
 * Accepting transfers the signed-in account into the target namespace and
 * revokes all existing sessions server-side, so the user must sign in again
 * afterwards. The user must already be signed in as the invited account —
 * if they're not, we redirect them to /login with a `next` param.
 */
import React, { useEffect, useState } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@store/auth.store';
import { SEO } from '@shared/components/SEO';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

type State = 'checking' | 'needs-login' | 'accepting' | 'success' | 'error' | 'missing';

export default function NamespaceInvitationAcceptPage() {
  const { token }    = useParams<{ token: string }>();
  const navigate      = useNavigate();
  const accessToken   = useAuthStore((s) => s.accessToken);
  const logout        = useAuthStore((s) => s.logout);

  const [state,   setState]   = useState<State>(token ? 'checking' : 'missing');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!token) return;
    const timer = setTimeout(() => {
      setState(accessToken ? 'accepting' : 'needs-login');
    }, 200);
    return () => clearTimeout(timer);
  }, [token, accessToken]);

  useEffect(() => {
    if (state !== 'accepting' || !token || !accessToken) return;

    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/namespace-invitations/${token}/accept`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${accessToken}` },
          credentials: 'include',
        });
        if (cancelled) return;

        if (res.ok) {
          setState('success');
        } else {
          const err = await res.json().catch(() => ({}));
          setMessage((err as any).detail ?? 'This invitation link is invalid or has expired.');
          setState('error');
        }
      } catch {
        if (!cancelled) {
          setMessage('Could not reach the server. Please try again.');
          setState('error');
        }
      }
    })();

    return () => { cancelled = true; };
  }, [state, token, accessToken]);

  const loginHref = `/login?next=${encodeURIComponent(`/namespace-invitations/${token}`)}`;

  function handleSignInAgain() {
    logout();
    navigate(loginHref, { replace: true });
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-muted px-4">
      <SEO
        title="Namespace invitation"
        description="Accept your invitation to join a namespace on OurFamRoots."
        noIndex
      />
      <div className="w-full max-w-sm text-center">
        <div className="text-4xl mb-4">🏷️</div>
        <h1 className="text-xl font-bold text-slate-900 mb-2">OurFamRoots</h1>

        {(state === 'checking' || state === 'accepting') && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-sm text-slate-600">
              {state === 'checking' ? 'Checking invitation…' : 'Accepting invitation…'}
            </p>
          </div>
        )}

        {state === 'needs-login' && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8">
            <div className="text-4xl mb-3">✉️</div>
            <h2 className="text-lg font-semibold text-slate-900 mb-2">You've been invited</h2>
            <p className="text-sm text-slate-500 mb-6">
              Sign in as the invited account to accept this namespace invitation.
            </p>
            <a
              href={loginHref}
              className="inline-block w-full h-10 leading-10 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 transition-colors"
            >
              Sign in to accept
            </a>
          </div>
        )}

        {state === 'success' && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8">
            <div className="text-4xl mb-3">🎉</div>
            <h2 className="text-lg font-semibold text-slate-900 mb-2">You've joined the namespace</h2>
            <p className="text-sm text-slate-500 mb-6">
              Your account has moved into its new namespace. For security, you've been signed out
              everywhere — please sign in again to continue.
            </p>
            <button
              onClick={handleSignInAgain}
              className="inline-block w-full h-10 leading-10 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 transition-colors"
            >
              Sign in again
            </button>
          </div>
        )}

        {state === 'error' && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8">
            <div className="text-4xl mb-3">⚠️</div>
            <h2 className="text-lg font-semibold text-slate-900 mb-2">Couldn't accept invitation</h2>
            <p className="text-sm text-slate-500 mb-6">{message}</p>
            <Link to="/dashboard" className="text-sm text-brand-600 hover:text-brand-700 font-medium">
              Go to dashboard
            </Link>
          </div>
        )}

        {state === 'missing' && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8">
            <div className="text-4xl mb-3">🔗</div>
            <h2 className="text-lg font-semibold text-slate-900 mb-2">Invalid link</h2>
            <p className="text-sm text-slate-500 mb-6">This invitation link is missing its token.</p>
            <Link to="/dashboard" className="text-sm text-brand-600 hover:text-brand-700 font-medium">
              Go to dashboard
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
