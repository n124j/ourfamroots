/**
 * VerifyNewLoginPage — handles /verify-new-login?token=xxx from the email.
 * Calls POST /auth/verify-new-login, signs out old sessions, and logs the user in.
 */
import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@store/auth.store';
import { SEO } from '@shared/components/SEO';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

type State = 'verifying' | 'success' | 'error' | 'missing';

export default function VerifyNewLoginPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const storeLogin = useAuthStore((s) => s.login);
  const token = searchParams.get('token');

  const [state, setState] = useState<State>(token ? 'verifying' : 'missing');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!token) return;

    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/verify-new-login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ token }),
        });
        if (cancelled) return;
        if (res.ok) {
          const data = await res.json();
          const meRes = await fetch(`${API_BASE}/users/me`, {
            headers: { Authorization: `Bearer ${data.access_token}` },
            credentials: 'include',
          });
          const me = meRes.ok ? await meRes.json() : null;
          storeLogin(data.access_token, {
            id: data.user_id,
            tenantId: data.tenant_id,
            email: me?.email ?? '',
            displayName: me ? `${me.given_name ?? ''} ${me.family_name ?? ''}`.trim() || me.email : '',
            avatarUrl: me?.avatar_url ?? undefined,
            isEmailVerified: true,
            appRole: me?.app_role ?? 'STANDARD',
          });
          setState('success');
          setTimeout(() => navigate('/settings/security', { replace: true }), 3000);
        } else {
          const err = await res.json().catch(() => ({}));
          setMessage((err as any).detail ?? t('verifyNewLogin.invalidToken'));
          setState('error');
        }
      } catch {
        if (!cancelled) {
          setMessage(t('verifyNewLogin.networkError'));
          setState('error');
        }
      }
    })();

    return () => { cancelled = true; };
  }, [token]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-muted px-4">
      <SEO
        title={t('verifyNewLogin.title')}
        description="Verify your new login to OurFamRoots."
        noIndex
      />
      <div className="w-full max-w-sm text-center">
        <div className="text-4xl mb-4">🌳</div>
        <h1 className="text-xl font-bold text-slate-900 mb-2">{t('common.appName')}</h1>

        {state === 'verifying' && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-sm text-slate-600">{t('verifyNewLogin.verifying')}</p>
          </div>
        )}

        {state === 'success' && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8">
            <div className="text-4xl mb-3">✅</div>
            <h2 className="text-lg font-semibold text-slate-900 mb-2">{t('verifyNewLogin.verified')}</h2>
            <p className="text-sm text-slate-500 mb-4">{t('verifyNewLogin.verifiedDesc')}</p>
            <div className="px-3 py-2.5 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800 mb-4">
              <p className="font-medium mb-0.5">{t('verifyNewLogin.changePasswordTitle')}</p>
              <p className="text-xs">{t('verifyNewLogin.changePasswordDesc')}</p>
            </div>
            <p className="text-xs text-slate-400">{t('verifyNewLogin.redirecting')}</p>
          </div>
        )}

        {state === 'error' && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8">
            <div className="text-4xl mb-3">⚠️</div>
            <h2 className="text-lg font-semibold text-slate-900 mb-2">{t('verifyNewLogin.failed')}</h2>
            <p className="text-sm text-slate-500 mb-6">{message}</p>
            <Link to="/login" className="text-sm text-brand-600 hover:text-brand-700 font-medium">
              {t('verifyNewLogin.backToSignIn')}
            </Link>
          </div>
        )}

        {state === 'missing' && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8">
            <div className="text-4xl mb-3">🔗</div>
            <h2 className="text-lg font-semibold text-slate-900 mb-2">{t('verifyNewLogin.invalidLink')}</h2>
            <p className="text-sm text-slate-500 mb-6">{t('verifyNewLogin.noToken')}</p>
            <Link to="/login" className="text-sm text-brand-600 hover:text-brand-700 font-medium">
              {t('verifyNewLogin.backToSignIn')}
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
