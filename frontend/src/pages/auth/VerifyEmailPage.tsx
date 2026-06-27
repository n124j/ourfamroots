/**
 * VerifyEmailPage — handles the /verify-email?token=xxx link from the email.
 * Calls POST /auth/verify-email, then redirects to login on success.
 */
import React, { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { SEO } from '@shared/components/SEO';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

type State = 'verifying' | 'success' | 'error' | 'missing';

export default function VerifyEmailPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [state,   setState]   = useState<State>(token ? 'verifying' : 'missing');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!token) return;

    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/verify-email`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token }),
        });
        if (cancelled) return;
        if (res.ok) {
          setState('success');
        } else {
          const err = await res.json().catch(() => ({}));
          setMessage((err as any).detail ?? 'The verification link is invalid or has expired.');
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
  }, [token]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-muted px-4">
      <SEO
        title={t('verifyEmail.title')}
        description="Verify your OurFamRoots email address to activate your account."
        noIndex
      />
      <div className="w-full max-w-sm text-center">
        <div className="text-4xl mb-4">🌳</div>
        <h1 className="text-xl font-bold text-slate-900 mb-2">{t('common.appName')}</h1>

        {state === 'verifying' && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-sm text-slate-600">{t('verifyEmail.verifying')}</p>
          </div>
        )}

        {state === 'success' && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8">
            <div className="text-4xl mb-3">✅</div>
            <h2 className="text-lg font-semibold text-slate-900 mb-2">{t('verifyEmail.verified')}</h2>
            <p className="text-sm text-slate-500 mb-6">
              {t('verifyEmail.verifiedDesc')}
            </p>
            <Link
              to="/login"
              className="inline-block w-full h-10 leading-10 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 transition-colors"
            >
              {t('auth.signIn')}
            </Link>
          </div>
        )}

        {state === 'error' && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8">
            <div className="text-4xl mb-3">⚠️</div>
            <h2 className="text-lg font-semibold text-slate-900 mb-2">{t('verifyEmail.failed')}</h2>
            <p className="text-sm text-slate-500 mb-6">{message}</p>
            <Link to="/login" className="text-sm text-brand-600 hover:text-brand-700 font-medium">
              {t('verifyEmail.backToSignIn')}
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
            <Link to="/login" className="text-sm text-brand-600 hover:text-brand-700 font-medium">
              {t('verifyEmail.backToSignIn')}
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
