/**
 * InvitationAcceptPage — handles /invitations/accept?token=xxx links from email.
 *
 * The user must be signed in to accept. If they're not, we redirect them to
 * /login with a `next` param so they land back here after signing in.
 */
import React, { useEffect, useState } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@store/auth.store';
import { SEO } from '@shared/components/SEO';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

type State = 'checking' | 'needs-login' | 'accepting' | 'success' | 'error' | 'missing';

export default function InvitationAcceptPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const navigate       = useNavigate();
  const token          = searchParams.get('token');
  const accessToken    = useAuthStore((s) => s.accessToken);
  const user           = useAuthStore((s) => s.user);

  const [state,     setState]     = useState<State>(token ? 'checking' : 'missing');
  const [message,   setMessage]   = useState('');
  const [treeName,  setTreeName]  = useState('');

  useEffect(() => {
    if (!token) return;

    // Wait for auth store to hydrate (it may be loading from storage)
    const timer = setTimeout(() => {
      if (!accessToken) {
        setState('needs-login');
      } else {
        setState('accepting');
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [token, accessToken]);

  useEffect(() => {
    if (state !== 'accepting' || !token || !accessToken) return;

    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/invitations/accept`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${accessToken}`,
          },
          credentials: 'include',
          body: JSON.stringify({ token }),
        });

        if (cancelled) return;

        if (res.ok) {
          const data = await res.json();
          setTreeName(data.tree_name ?? '');
          setState('success');
          // Auto-redirect to dashboard after 2.5 s
          setTimeout(() => { if (!cancelled) navigate('/dashboard'); }, 2500);
        } else {
          const err = await res.json().catch(() => ({}));
          setMessage((err as any).detail ?? 'The invitation link is invalid or has expired.');
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

  const loginHref = `/login?next=${encodeURIComponent(`/invitations/accept?token=${token}`)}`;

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-muted px-4">
      <SEO
        title={t('invitationAccept.title')}
        description="Accept your invitation to collaborate on a OurFamRoots family tree."
        noIndex
      />
      <div className="w-full max-w-sm text-center">
        <div className="text-4xl mb-4">🌳</div>
        <h1 className="text-xl font-bold text-slate-900 mb-2">{t('common.appName')}</h1>

        {(state === 'checking' || state === 'accepting') && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-sm text-slate-600">
              {state === 'checking' ? t('invitationAccept.checking') : t('invitationAccept.accepting')}
            </p>
          </div>
        )}

        {state === 'needs-login' && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8">
            <div className="text-4xl mb-3">✉️</div>
            <h2 className="text-lg font-semibold text-slate-900 mb-2">{t('invitationAccept.youveBeenInvited')}</h2>
            <p className="text-sm text-slate-500 mb-6">
              {t('invitationAccept.signInToAccept')}
            </p>
            <a
              href={loginHref}
              className="inline-block w-full h-10 leading-10 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 transition-colors"
            >
              {t('invitationAccept.signInButton')}
            </a>
            <p className="text-xs text-slate-400 mt-4">
              {t('invitationAccept.noAccount')}{' '}
              <a
                href={`/register?next=${encodeURIComponent(`/invitations/accept?token=${token}`)}`}
                className="text-brand-600 hover:text-brand-700 font-medium"
              >
                {t('invitationAccept.register')}
              </a>
            </p>
          </div>
        )}

        {state === 'success' && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8">
            <div className="text-4xl mb-3">🎉</div>
            <h2 className="text-lg font-semibold text-slate-900 mb-2">{t('invitationAccept.welcomeToFamily')}</h2>
            <p className="text-sm text-slate-500 mb-6">
              {t('invitationAccept.successfullyJoined', { treeName: treeName || undefined, firstName: user?.displayName ? user.displayName.split(' ')[0] : undefined })}
              {' '}{t('invitationAccept.redirecting')}
            </p>
            <Link
              to="/dashboard"
              className="inline-block w-full h-10 leading-10 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 transition-colors"
            >
              {t('invitationAccept.goToDashboard')}
            </Link>
          </div>
        )}

        {state === 'error' && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8">
            <div className="text-4xl mb-3">⚠️</div>
            <h2 className="text-lg font-semibold text-slate-900 mb-2">{t('invitationAccept.couldntAccept')}</h2>
            <p className="text-sm text-slate-500 mb-6">{message}</p>
            <Link to="/dashboard" className="text-sm text-brand-600 hover:text-brand-700 font-medium">
              {t('invitationAccept.goToDashboard')}
            </Link>
          </div>
        )}

        {state === 'missing' && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8">
            <div className="text-4xl mb-3">🔗</div>
            <h2 className="text-lg font-semibold text-slate-900 mb-2">{t('verifyEmail.invalidLink')}</h2>
            <p className="text-sm text-slate-500 mb-6">
              {t('verifyEmail.noToken')}
            </p>
            <Link to="/dashboard" className="text-sm text-brand-600 hover:text-brand-700 font-medium">
              {t('invitationAccept.goToDashboard')}
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
