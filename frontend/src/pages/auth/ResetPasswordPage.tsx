import React, { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { SEO } from '@shared/components/SEO';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

function StrengthBar({ password, t }: { password: string; t: (key: string) => string }) {
  const hasLength  = password.length >= 8;
  const hasUpper   = /[A-Z]/.test(password);
  const hasDigit   = /[0-9]/.test(password);
  const score      = [hasLength, hasUpper, hasDigit].filter(Boolean).length;
  const colors     = ['', 'bg-red-400', 'bg-amber-400', 'bg-green-500'];
  const labels     = ['', t('resetPasswordPage.weak'), t('resetPasswordPage.almost'), t('resetPasswordPage.strong')];

  if (!password) return null;
  return (
    <div className="mt-1.5 space-y-1">
      <div className="flex gap-1">
        {[1, 2, 3].map((i) => (
          <div key={i} className={`h-1 flex-1 rounded-full transition-colors ${i <= score ? colors[score] : 'bg-slate-200'}`} />
        ))}
      </div>
      <p className={`text-xs ${score < 3 ? 'text-slate-400' : 'text-green-600'}`}>
        {labels[score]}
        {score < 3 && (
          <span className="ml-1 text-slate-400">
            · {t('resetPasswordPage.needs')} {[!hasLength && t('resetPasswordPage.chars8'), !hasUpper && t('resetPasswordPage.uppercase'), !hasDigit && t('resetPasswordPage.aNumber')].filter(Boolean).join(', ')}
          </span>
        )}
      </p>
    </div>
  );
}

export default function ResetPasswordPage() {
  const { t } = useTranslation();
  const [searchParams]  = useSearchParams();
  const navigate        = useNavigate();
  const token           = searchParams.get('token') ?? '';

  const [password,  setPassword]  = useState('');
  const [confirm,   setConfirm]   = useState('');
  const [loading,   setLoading]   = useState(false);
  const [done,      setDone]      = useState(false);
  const [error,     setError]     = useState('');

  const passwordsMatch = confirm === '' || password === confirm;
  const isStrong       = password.length >= 8 && /[A-Z]/.test(password) && /[0-9]/.test(password);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) { setError(t('resetPasswordPage.passwordsNoMatch')); return; }
    if (!isStrong) { setError(t('resetPasswordPage.requirementsNotMet')); return; }
    setError('');
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: password }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const type = String((err as any).type ?? '');
        if (type.includes('token-expired'))
          throw new Error(t('resetPasswordPage.linkExpired'));
        if (type.includes('token-invalid'))
          throw new Error(t('resetPasswordPage.linkInvalid'));
        throw new Error((err as any).detail ?? 'Something went wrong. Please try again.');
      }
      setDone(true);
      setTimeout(() => navigate('/login', { replace: true }), 3000);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-muted px-4">
        <div className="w-full max-w-sm">
          <div className="text-center mb-8">
            <div className="text-3xl mb-2">🌳</div>
            <h1 className="text-2xl font-bold text-slate-900">{t('common.appName')}</h1>
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-7 text-center space-y-3">
            <div className="text-4xl">🔗</div>
            <p className="text-sm font-medium text-slate-800">{t('resetPasswordPage.invalidLink')}</p>
            <p className="text-sm text-slate-500">{t('resetPasswordPage.invalidLinkDesc')}</p>
            <Link to="/forgot-password" className="inline-block text-sm text-brand-600 font-medium hover:text-brand-700">
              {t('resetPasswordPage.requestNewLink')}
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <SEO
        title={t('resetPasswordPage.title')}
        description="Create a new secure password for your OurFamRoots account."
        noIndex
      />
    <div className="min-h-screen flex items-center justify-center bg-surface-muted px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="text-3xl mb-2">🌳</div>
          <h1 className="text-2xl font-bold text-slate-900">{t('common.appName')}</h1>
          <p className="text-sm text-slate-500 mt-1">{t('resetPasswordPage.setNewPassword')}</p>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-7">
          {done ? (
            <div className="text-center space-y-3">
              <div className="text-4xl">✅</div>
              <p className="text-sm font-medium text-slate-800">{t('resetPasswordPage.passwordUpdated')}</p>
              <p className="text-sm text-slate-500">{t('resetPasswordPage.redirecting')}</p>
              <Link to="/login" className="inline-block text-sm text-brand-600 font-medium hover:text-brand-700">
                {t('resetPasswordPage.signInNow')}
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <p className="text-sm text-slate-500">
                {t('resetPasswordPage.chooseStrong')}
              </p>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">{t('resetPasswordPage.newPassword')}</label>
                <input
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  className="w-full h-10 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                  placeholder="8+ chars, uppercase &amp; digit"
                />
                <StrengthBar password={password} t={t} />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">{t('resetPasswordPage.confirmPassword')}</label>
                <input
                  type="password"
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                  className={`w-full h-10 px-3 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent ${
                    !passwordsMatch ? 'border-red-400' : 'border-slate-300'
                  }`}
                  placeholder="Re-enter password"
                />
                {!passwordsMatch && (
                  <p className="mt-1 text-xs text-red-500">{t('resetPasswordPage.passwordsNoMatch')}</p>
                )}
              </div>

              {error && (
                <div className="px-3 py-2.5 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                  {error}
                  {(error.includes('expired') || error.includes('invalid')) && (
                    <span className="block mt-1">
                      <Link to="/forgot-password" className="underline font-medium">{t('resetPasswordPage.requestNewLink')}</Link>
                    </span>
                  )}
                </div>
              )}

              <button
                type="submit"
                disabled={loading || !isStrong || !passwordsMatch || !confirm}
                className="w-full h-10 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? t('resetPasswordPage.updating') : t('resetPasswordPage.setPassword')}
              </button>
            </form>
          )}
        </div>

        <p className="text-center text-sm text-slate-500 mt-5">
          <Link to="/login" className="text-brand-600 font-medium hover:text-brand-700">{t('forgotPasswordPage.backToSignIn')}</Link>
        </p>
      </div>
    </div>
    </>
  );
}
