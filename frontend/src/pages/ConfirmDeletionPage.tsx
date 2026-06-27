import React, { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { SEO } from '@shared/components/SEO';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

type State = 'confirming' | 'success' | 'error' | 'missing';

export default function ConfirmDeletionPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [state,   setState]   = useState<State>(token ? 'confirming' : 'missing');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!token) return;

    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/users/confirm-deletion`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token }),
        });
        if (cancelled) return;
        if (res.ok) {
          setState('success');
        } else {
          const err = await res.json().catch(() => ({}));
          setMessage((err as any).detail ?? 'The confirmation link is invalid or has expired.');
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
        title={t('confirmDeletion.title')}
        description="Confirm deletion of your OurFamRoots account."
        noIndex
      />
      <div className="w-full max-w-sm text-center">
        <div className="text-4xl mb-4">🌳</div>
        <h1 className="text-xl font-bold text-slate-900 mb-2">{t('common.appName')}</h1>

        {state === 'confirming' && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8">
            <div className="w-8 h-8 border-2 border-red-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-sm text-slate-600">{t('confirmDeletion.confirming')}</p>
          </div>
        )}

        {state === 'success' && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8">
            <div className="text-4xl mb-3">✅</div>
            <h2 className="text-lg font-semibold text-slate-900 mb-2">{t('confirmDeletion.deleted')}</h2>
            <p className="text-sm text-slate-500 mb-6">
              {t('confirmDeletion.deletedDesc')}
              {' '}{t('confirmDeletion.sorryToSeeYouGo')}
            </p>
            <Link
              to="/"
              className="inline-block w-full h-10 leading-10 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 transition-colors"
            >
              {t('confirmDeletion.backToHome')}
            </Link>
          </div>
        )}

        {state === 'error' && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8">
            <div className="text-4xl mb-3">⚠️</div>
            <h2 className="text-lg font-semibold text-slate-900 mb-2">{t('confirmDeletion.failed')}</h2>
            <p className="text-sm text-slate-500 mb-6">{message}</p>
            <Link to="/" className="text-sm text-brand-600 hover:text-brand-700 font-medium">
              {t('confirmDeletion.backToHome')}
            </Link>
          </div>
        )}

        {state === 'missing' && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8">
            <div className="text-4xl mb-3">🔗</div>
            <h2 className="text-lg font-semibold text-slate-900 mb-2">{t('confirmDeletion.invalidLink')}</h2>
            <p className="text-sm text-slate-500 mb-6">
              {t('confirmDeletion.noToken')}
            </p>
            <Link to="/" className="text-sm text-brand-600 hover:text-brand-700 font-medium">
              {t('confirmDeletion.backToHome')}
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
