import React, { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { SEO } from '@shared/components/SEO';
import { OAuthButtons, hasOAuthProviders } from '@features/auth/components/OAuthButtons';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

async function register(body: {
  email: string;
  password: string;
  given_name: string;
  family_name: string;
}) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? 'Registration failed');
  }
}


export default function RegisterPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const oauthError = searchParams.get('error');

  const [givenName,  setGivenName]  = useState('');
  const [familyName, setFamilyName] = useState('');
  const [email,      setEmail]      = useState('');
  const [password,   setPassword]   = useState('');
  const [confirm,    setConfirm]    = useState('');
  const [error,      setError]      = useState('');
  const [loading,    setLoading]    = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      await register({ email, password, given_name: givenName, family_name: familyName });
      navigate('/login?registered=1', { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <SEO
        title="Create Account"
        description="Create your free OurFamRoots account and start building your family tree today. Connect ancestors, add photos, and share your genealogy with family."
        canonical="/register"
        keywords="register, create account, free genealogy, family tree signup, genealogy account"
      />
    <div className="min-h-screen flex items-center justify-center bg-surface-muted px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="text-3xl mb-2">🌳</div>
          <h1 className="text-2xl font-bold text-slate-900">{t('common.appName')}</h1>
          <p className="text-sm text-slate-500 mt-1">{t('auth.createFreeAccount')}</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-7">
          {/* OAuth error banner */}
          {oauthError && (
            <div className="mb-4 px-3 py-2.5 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {oauthError === 'oauth_state_mismatch'
                ? t('auth.oauthExpired')
                : t('auth.oauthError')}
            </div>
          )}

          {/* Social login */}
          {hasOAuthProviders && (
            <>
              <OAuthButtons dividerLabel="" next="/register" />
              <div className="relative flex items-center gap-3 my-5">
                <div className="flex-1 h-px bg-slate-200" />
                <span className="text-xs text-slate-400 font-medium">{t('auth.orSignUpWithEmail')}</span>
                <div className="flex-1 h-px bg-slate-200" />
              </div>
            </>
          )}

          <form
            onSubmit={handleSubmit}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && e.target instanceof HTMLInputElement) {
                e.preventDefault();
                e.currentTarget.requestSubmit();
              }
            }}
            className="space-y-4"
          >
            {/* Name row */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="reg-given-name" className="block text-sm font-medium text-slate-700 mb-1.5">
                  {t('auth.firstName')}
                </label>
                <input
                  id="reg-given-name"
                  type="text"
                  autoComplete="given-name"
                  value={givenName}
                  onChange={(e) => setGivenName(e.target.value)}
                  required
                  className="w-full h-10 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                  placeholder="Alice"
                />
              </div>
              <div>
                <label htmlFor="reg-family-name" className="block text-sm font-medium text-slate-700 mb-1.5">
                  {t('auth.lastName')}
                </label>
                <input
                  id="reg-family-name"
                  type="text"
                  autoComplete="family-name"
                  value={familyName}
                  onChange={(e) => setFamilyName(e.target.value)}
                  required
                  className="w-full h-10 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                  placeholder="Smith"
                />
              </div>
            </div>

            {/* Email */}
            <div>
              <label htmlFor="reg-email" className="block text-sm font-medium text-slate-700 mb-1.5">
                {t('auth.email')}
              </label>
              <input
                id="reg-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full h-10 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                placeholder="alice@example.com"
              />
            </div>

            {/* Password */}
            <div>
              <label htmlFor="reg-password" className="block text-sm font-medium text-slate-700 mb-1.5">
                {t('auth.password')}
              </label>
              <input
                id="reg-password"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                className="w-full h-10 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                placeholder="8+ chars, uppercase & digit"
              />
            </div>

            {/* Confirm password */}
            <div>
              <label htmlFor="reg-confirm" className="block text-sm font-medium text-slate-700 mb-1.5">
                {t('auth.confirmPassword')}
              </label>
              <input
                id="reg-confirm"
                type="password"
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
                className={`w-full h-10 px-3 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent ${
                  confirm && confirm !== password ? 'border-red-400' : 'border-slate-300'
                }`}
                placeholder="Re-enter password"
              />
              {confirm && confirm !== password && (
                <p className="mt-1 text-xs text-red-500">{t('auth.passwordsNoMatch')}</p>
              )}
            </div>

            {error && (
              <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full h-10 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? t('auth.creatingAccount') : t('auth.createAccount')}
            </button>
          </form>
        </div>

        <p className="text-center text-sm text-slate-500 mt-5">
          {t('auth.alreadyHaveAccount')}{' '}
          <Link to="/login" className="text-brand-600 font-medium hover:text-brand-700">
            {t('auth.signIn')}
          </Link>
        </p>
      </div>
    </div>
    </>
  );
}
