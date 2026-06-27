import React, { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@store/auth.store';
import { SEO } from '@shared/components/SEO';
import { OAuthButtons, hasOAuthProviders } from '@features/auth/components/OAuthButtons';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

// ─── Shared constants (mirrored from tree/types.ts) ───────────────────────────
const MALE_COLOR   = '#3b82f6';
const FEMALE_COLOR = '#ec4899';

type ModalType = 'login' | 'register' | null;

// ─── Login Modal ──────────────────────────────────────────────────────────────

function LoginModal({ onClose, onSwitchToRegister, initialError }: {
  onClose: () => void;
  onSwitchToRegister: () => void;
  initialError?: string | null;
}) {
  const { t } = useTranslation();
  const navigate   = useNavigate();
  const storeLogin = useAuthStore((s) => s.login);

  const [email,      setEmail]      = useState('');
  const [password,   setPassword]   = useState('');
  const [error,      setError]      = useState('');
  const [unverified, setUnverified] = useState(false);
  const [loading,    setLoading]    = useState(false);
  const oauthError = initialError ?? '';

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setUnverified(false);
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        if (res.status === 403 && String((err as any).type ?? '').includes('account-not-verified')) {
          setUnverified(true);
          return;
        }
        throw new Error((err as any).detail ?? 'Invalid email or password');
      }
      const data = await res.json();
      const meRes = await fetch(`${API_BASE}/users/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
        credentials: 'include',
      });
      const me = meRes.ok ? await meRes.json() : null;
      storeLogin(data.access_token, {
        id: data.user_id,
        tenantId: data.tenant_id,
        email,
        displayName: me ? `${me.given_name ?? ''} ${me.family_name ?? ''}`.trim() || email : email,
        avatarUrl: me?.avatar_url ?? undefined,
        isEmailVerified: true,
        appRole: me?.app_role ?? 'STANDARD',
      });
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <ModalShell onClose={onClose}>
      <div className="text-center mb-6">
        <div className="text-3xl mb-2">🌳</div>
        <h2 className="text-xl font-bold text-slate-900">{t('auth.welcomeBack')}</h2>
        <p className="text-sm text-slate-500 mt-1">{t('auth.signInToAccount')}</p>
      </div>

      {oauthError && (
        <div className="mb-4 px-3 py-2.5 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {oauthError === 'oauth_state_mismatch'
            ? t('auth.oauthExpired')
            : t('auth.oauthError')}
        </div>
      )}

      {hasOAuthProviders && (
        <>
          <OAuthButtons dividerLabel="" next="/?auth=login" />
          <div className="relative flex items-center gap-3 my-5">
            <div className="flex-1 h-px bg-slate-200" />
            <span className="text-xs text-slate-400 font-medium">{t('auth.orSignInWithEmail')}</span>
            <div className="flex-1 h-px bg-slate-200" />
          </div>
        </>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">{t('auth.email')}</label>
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoFocus
            className="w-full h-10 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            placeholder="you@example.com"
          />
        </div>

        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-sm font-medium text-slate-700">{t('auth.password')}</label>
            <Link
              to="/forgot-password"
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-brand-600 hover:text-brand-700"
            >
              {t('auth.forgotPassword')}
            </Link>
          </div>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="w-full h-10 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            placeholder={t('auth.passwordPlaceholder')}
          />
        </div>

        {unverified && (
          <div className="px-3 py-2.5 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
            <p className="font-medium mb-0.5">{t('auth.emailNotVerified')}</p>
            <p className="text-xs">{t('auth.checkVerificationLink')}</p>
          </div>
        )}
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
          {loading ? t('auth.signingIn') : t('auth.signIn')}
        </button>
      </form>

      <p className="text-center text-sm text-slate-500 mt-5">
        {t('auth.noAccount')}{' '}
        <button
          onClick={onSwitchToRegister}
          className="text-brand-600 font-medium hover:text-brand-700"
        >
          {t('auth.createOneFree')}
        </button>
      </p>
    </ModalShell>
  );
}

// ─── Register Modal ───────────────────────────────────────────────────────────

function RegisterModal({ onClose, onSwitchToLogin, initialError }: {
  onClose: () => void;
  onSwitchToLogin: () => void;
  initialError?: string | null;
}) {
  const { t } = useTranslation();
  const [givenName,     setGivenName]     = useState('');
  const [familyName,    setFamilyName]    = useState('');
  const [email,         setEmail]         = useState('');
  const [password,      setPassword]      = useState('');
  const [confirm,       setConfirm]       = useState('');
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [error,         setError]         = useState('');
  const [loading,       setLoading]       = useState(false);
  const [success,       setSuccess]       = useState(false);
  const oauthError = initialError ?? '';

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (password !== confirm) { setError('Passwords do not match.'); return; }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password, given_name: givenName, family_name: familyName }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail ?? 'Registration failed');
      }
      setSuccess(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <ModalShell onClose={onClose}>
        <div className="text-center py-4">
          <div className="text-5xl mb-4">📬</div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">{t('auth.checkInbox')}</h2>
          <p className="text-sm text-slate-600 leading-relaxed mb-6"
            dangerouslySetInnerHTML={{ __html: t('auth.verificationSent', { email }) }}
          />
          <button
            onClick={onSwitchToLogin}
            className="w-full h-10 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 transition-colors"
          >
            {t('auth.goToSignIn')}
          </button>
        </div>
      </ModalShell>
    );
  }

  return (
    <ModalShell onClose={onClose}>
      <div className="text-center mb-6">
        <div className="text-3xl mb-2">🌳</div>
        <h2 className="text-xl font-bold text-slate-900">{t('auth.createFreeAccount')}</h2>
        <p className="text-sm text-slate-500 mt-1">{t('auth.freeBeta')}</p>
      </div>

      {oauthError && (
        <div className="mb-4 px-3 py-2.5 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {oauthError === 'oauth_state_mismatch'
            ? t('auth.oauthExpired')
            : t('auth.oauthError')}
        </div>
      )}

      {hasOAuthProviders && (
        <>
          <OAuthButtons dividerLabel="" next="/?auth=register" />
          <div className="relative flex items-center gap-3 my-5">
            <div className="flex-1 h-px bg-slate-200" />
            <span className="text-xs text-slate-400 font-medium">{t('auth.orSignUpWithEmail')}</span>
            <div className="flex-1 h-px bg-slate-200" />
          </div>
        </>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">{t('auth.firstName')}</label>
            <input
              type="text"
              autoComplete="given-name"
              value={givenName}
              onChange={(e) => setGivenName(e.target.value)}
              required
              autoFocus
              className="w-full h-10 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              placeholder="Alice"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">{t('auth.lastName')}</label>
            <input
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

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">{t('auth.email')}</label>
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full h-10 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            placeholder="alice@example.com"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">{t('auth.password')}</label>
          <input
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            className="w-full h-10 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            placeholder={t('auth.passwordHint')}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">{t('auth.confirmPassword')}</label>
          <input
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            className={[
              'w-full h-10 px-3 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent',
              confirm && confirm !== password ? 'border-red-400' : 'border-slate-300',
            ].join(' ')}
            placeholder={t('auth.reenterPassword')}
          />
          {confirm && confirm !== password && (
            <p className="mt-1 text-xs text-red-500">{t('auth.passwordsNoMatch')}</p>
          )}
        </div>

        {/* Terms & Conditions checkbox */}
        <label className="flex items-start gap-2.5 cursor-pointer group">
          <input
            type="checkbox"
            checked={termsAccepted}
            onChange={(e) => setTermsAccepted(e.target.checked)}
            required
            className="mt-0.5 w-4 h-4 rounded border-slate-300 text-brand-500 focus:ring-brand-500 accent-brand-500 cursor-pointer shrink-0"
          />
          <span className="text-sm text-slate-600 leading-snug">
            {t('auth.acceptTerms')}{' '}
            <a
              href="/terms"
              target="_blank"
              rel="noopener noreferrer"
              className="text-brand-600 font-medium hover:text-brand-700 underline underline-offset-2"
              onClick={(e) => e.stopPropagation()}
            >
              {t('auth.termsAndConditions')}
            </a>
          </span>
        </label>

        {error && (
          <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading || !termsAccepted}
          className="w-full h-10 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? t('auth.creatingAccount') : t('auth.createAccount')}
        </button>
      </form>

      <p className="text-center text-sm text-slate-500 mt-5">
        {t('auth.alreadyHaveAccount')}{' '}
        <button
          onClick={onSwitchToLogin}
          className="text-brand-600 font-medium hover:text-brand-700"
        >
          {t('auth.signIn')}
        </button>
      </p>
    </ModalShell>
  );
}

// ─── Modal shell (backdrop + card) ───────────────────────────────────────────

function ModalShell({ onClose, children }: { onClose: () => void; children: React.ReactNode }) {
  const cardRef = useRef<HTMLDivElement>(null);

  // Close on Escape
  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') onClose(); }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Prevent body scroll while open
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        ref={cardRef}
        className="relative w-full max-w-sm bg-white rounded-2xl shadow-xl p-7 max-h-[90vh] overflow-y-auto"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 w-7 h-7 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors text-lg leading-none"
          aria-label="Close"
        >
          ×
        </button>
        {children}
      </div>
    </div>
  );
}

// ─── Nav ──────────────────────────────────────────────────────────────────────

function LandingNav({ onSignIn, onSignUp }: { onSignIn: () => void; onSignUp: () => void }) {
  const { t } = useTranslation();
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const h = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', h, { passive: true });
    return () => window.removeEventListener('scroll', h);
  }, []);

  return (
    <header className={[
      'fixed top-0 inset-x-0 z-50 transition-all duration-300',
      scrolled ? 'bg-white/95 backdrop-blur shadow-sm border-b border-gray-100' : 'bg-transparent',
    ].join(' ')}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 group">
          <span className="text-2xl leading-none">🌳</span>
          <span className={['text-base font-bold tracking-tight transition-colors', scrolled ? 'text-gray-900' : 'text-white'].join(' ')}>
            {t('common.appName')}
          </span>
          <span className={[
            'ml-1 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold border',
            scrolled ? 'bg-brand-50 text-brand-600 border-brand-200' : 'bg-brand-500/20 text-brand-200 border-brand-400/30',
          ].join(' ')}>
            {t('common.beta')}
          </span>
        </Link>

        <div className="flex items-center gap-2">
          <button
            onClick={onSignIn}
            className={[
              'hidden sm:inline-flex px-3 py-1.5 text-sm font-medium rounded-lg transition-colors',
              scrolled ? 'text-gray-600 hover:bg-gray-100' : 'text-white/80 hover:text-white hover:bg-white/10',
            ].join(' ')}
          >
            {t('landing.signIn')}
          </button>
          <button
            onClick={onSignUp}
            className="inline-flex items-center px-4 py-1.5 text-sm font-semibold rounded-lg bg-brand-500 text-white hover:bg-brand-600 shadow-sm transition-colors"
          >
            {t('landing.getStartedFree')}
          </button>
        </div>
      </div>
    </header>
  );
}

// ─── Person card mockup (matches real PersonNode: 200×88, left bar, avatar) ──

interface MockPersonProps {
  name: string;
  years?: string;
  sex: 'MALE' | 'FEMALE';
  initials: string;
  isFocus?: boolean;
  scale?: number;
}

function MockPersonCard({ name, years, sex, initials, isFocus, scale = 1 }: MockPersonProps) {
  const color = sex === 'MALE' ? MALE_COLOR : FEMALE_COLOR;

  return (
    <div style={{
      width: 200 * scale,
      height: 88 * scale,
      background: '#ffffff',
      border: `${2 * scale}px solid ${isFocus ? color : '#e2e8f0'}`,
      borderRadius: 12 * scale,
      boxShadow: isFocus
        ? `0 0 0 ${3 * scale}px ${color}33, 0 4px 12px rgba(0,0,0,0.08)`
        : '0 1px 3px rgba(0,0,0,0.07)',
      display: 'flex',
      alignItems: 'center',
      gap: 12 * scale,
      padding: `0 ${12 * scale}px`,
      position: 'relative',
      overflow: 'hidden',
      flexShrink: 0,
    }}>
      <div style={{
        position: 'absolute', left: 0, top: 8 * scale, bottom: 8 * scale,
        width: 3 * scale, borderRadius: `0 ${2 * scale}px ${2 * scale}px 0`,
        background: color,
      }} />
      <div style={{
        width: 44 * scale, height: 44 * scale, borderRadius: '50%',
        background: color, color: '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontWeight: 700, fontSize: 15 * scale, flexShrink: 0,
      }}>
        {initials}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 13 * scale, color: '#0f172a', overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>
          {name}
        </div>
        {years && (
          <div style={{ fontSize: 11 * scale, color: '#94a3b8', marginTop: 3 * scale }}>{years}</div>
        )}
        {isFocus && (
          <div style={{
            display: 'inline-flex', marginTop: 4 * scale,
            background: `${color}20`, color, fontSize: 9 * scale,
            fontWeight: 600, padding: `${2 * scale}px ${5 * scale}px`, borderRadius: 4 * scale,
          }}>
            Focus
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Canvas mockup ────────────────────────────────────────────────────────────

function CanvasMockup() {
  const S = 0.75;

  return (
    <div style={{
      width: '100%', maxWidth: 560,
      background: '#f8fafc',
      borderRadius: 16,
      border: '1px solid #e2e8f0',
      boxShadow: '0 8px 40px rgba(0,0,0,0.12)',
      overflow: 'hidden',
      position: 'relative',
    }}>
      {/* Window chrome */}
      <div style={{ height: 36, background: '#fff', borderBottom: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', padding: '0 12px', gap: 6 }}>
        <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#ef4444' }} />
        <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#f59e0b' }} />
        <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#22c55e' }} />
        <div style={{ marginLeft: 8, fontSize: 11, color: '#94a3b8', fontWeight: 500, background: '#f1f5f9', borderRadius: 4, padding: '2px 8px' }}>
          The Johnson Family Tree
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
          {['TB', 'LR', 'Fan'].map((l) => (
            <div key={l} style={{ fontSize: 9, padding: '2px 5px', borderRadius: 3, background: l === 'TB' ? '#6366f1' : '#f1f5f9', color: l === 'TB' ? '#fff' : '#94a3b8', fontWeight: 600 }}>{l}</div>
          ))}
        </div>
      </div>

      {/* Canvas area */}
      <div style={{ position: 'relative', height: 340, overflow: 'hidden' }}>
        <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} aria-hidden>
          <defs>
            <pattern id="dots" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
              <circle cx="1" cy="1" r="1" fill="#cbd5e1" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#dots)" />
        </svg>
        <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', overflow: 'visible' }} aria-hidden>
          <line x1="100" y1="88" x2="100" y2="112" stroke="#cbd5e1" strokeWidth="1.5" />
          <line x1="316" y1="88" x2="316" y2="112" stroke="#cbd5e1" strokeWidth="1.5" />
          <line x1="100" y1="112" x2="316" y2="112" stroke="#cbd5e1" strokeWidth="1.5" />
          <line x1="208" y1="112" x2="208" y2="142" stroke="#cbd5e1" strokeWidth="1.5" />
          <line x1="60"  y1="30"  x2="60"  y2="54" stroke="#cbd5e1" strokeWidth="1.5" />
          <line x1="140" y1="30"  x2="140" y2="54" stroke="#cbd5e1" strokeWidth="1.5" />
          <line x1="60"  y1="54"  x2="140" y2="54" stroke="#cbd5e1" strokeWidth="1.5" />
          <line x1="100" y1="54"  x2="100" y2="66" stroke="#cbd5e1" strokeWidth="1.5" />
          <line x1="276" y1="30"  x2="276" y2="54" stroke="#cbd5e1" strokeWidth="1.5" />
          <line x1="356" y1="30"  x2="356" y2="54" stroke="#cbd5e1" strokeWidth="1.5" />
          <line x1="276" y1="54"  x2="356" y2="54" stroke="#cbd5e1" strokeWidth="1.5" />
          <line x1="316" y1="54"  x2="316" y2="66" stroke="#cbd5e1" strokeWidth="1.5" />
          <line x1="208" y1="230" x2="208" y2="256" stroke="#6366f1" strokeWidth="1.5" />
        </svg>

        <div style={{ position: 'absolute', top: 8, left: 12, transform: `scale(${S})`, transformOrigin: 'top left' }}>
          <MockPersonCard name="Margaret H." years="1920 – 2001" sex="FEMALE" initials="MH" scale={S} />
        </div>
        <div style={{ position: 'absolute', top: 8, left: 168, transform: `scale(${S})`, transformOrigin: 'top left' }}>
          <MockPersonCard name="Robert H." years="1918 – 1998" sex="MALE" initials="RH" scale={S} />
        </div>
        <div style={{ position: 'absolute', top: 8, left: 325, transform: `scale(${S})`, transformOrigin: 'top left' }}>
          <MockPersonCard name="Emma J." years="1922 – 2005" sex="FEMALE" initials="EJ" scale={S} />
        </div>
        <div style={{ position: 'absolute', top: 8, right: 8, transform: `scale(${S})`, transformOrigin: 'top right' }}>
          <MockPersonCard name="Thomas J." years="1919 – 2003" sex="MALE" initials="TJ" scale={S} />
        </div>
        <div style={{ position: 'absolute', top: 142, left: 66 }}>
          <MockPersonCard name="Sarah H." years="1950 – 2018" sex="FEMALE" initials="SH" scale={S} />
        </div>
        <div style={{ position: 'absolute', top: 142, right: 66 }}>
          <MockPersonCard name="David J." years="b. 1948" sex="MALE" initials="DJ" scale={S} />
        </div>
        <div style={{ position: 'absolute', top: 232, left: '50%', transform: 'translateX(-50%)' }}>
          <MockPersonCard name="Emily Johnson" years="b. 1975" sex="FEMALE" initials="EJ" isFocus scale={S} />
        </div>

        {/* Floating toolbar */}
        <div style={{ position: 'absolute', top: 8, right: 8, background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8, padding: '6px 8px', display: 'flex', flexDirection: 'column', gap: 4, boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
          {['+', '−', '⊡'].map((icon) => (
            <div key={icon} style={{ width: 24, height: 24, borderRadius: 4, background: '#f8fafc', border: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color: '#64748b' }}>{icon}</div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Hero ─────────────────────────────────────────────────────────────────────

function Hero({ onSignUp, onSignIn }: { onSignUp: () => void; onSignIn: () => void }) {
  const { t } = useTranslation();
  return (
    <section aria-label="Build your family tree online for free" className="relative min-h-[90vh] flex items-center overflow-hidden bg-gradient-to-br from-brand-900 via-brand-800 to-indigo-900 pt-14">
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-32 -right-32 w-96 h-96 rounded-full bg-white/5" />
        <div className="absolute bottom-0 -left-20 w-72 h-72 rounded-full bg-white/5" />
      </div>

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 flex flex-col lg:flex-row items-center gap-10 lg:gap-16">
        <div className="flex-1 text-center lg:text-left">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-400/10 border border-green-400/20 text-green-300 text-xs font-medium mb-5">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            {t('landing.openBetaTag')}
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-white leading-tight tracking-tight mb-5">
            {t('landing.heroTitle')}{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-amber-300 to-orange-300">
              {t('landing.heroHighlight')}
            </span>
          </h1>

          <p className="text-lg text-indigo-200 mb-8 max-w-lg mx-auto lg:mx-0 leading-relaxed">
            {t('landing.heroDesc')}
          </p>

          <div className="flex flex-col sm:flex-row gap-3 justify-center lg:justify-start mb-5">
            <button
              onClick={onSignUp}
              className="inline-flex items-center justify-center gap-2 px-7 py-3 text-sm font-semibold rounded-lg bg-brand-500 text-white hover:bg-brand-400 shadow-md transition-colors"
            >
              {t('landing.startBuilding')}
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </button>
            <button
              onClick={onSignIn}
              className="inline-flex items-center justify-center px-7 py-3 text-sm font-semibold rounded-lg border border-white/25 text-white hover:bg-white/10 transition-colors"
            >
              {t('landing.signIn')}
            </button>
          </div>
          <p className="text-xs text-indigo-400">{t('landing.noPayment')}</p>
        </div>

        <div className="flex-1 flex items-center justify-center w-full">
          <CanvasMockup />
        </div>
      </div>

      <div className="absolute bottom-0 inset-x-0 pointer-events-none">
        <svg viewBox="0 0 1440 60" fill="none" preserveAspectRatio="none" className="w-full h-12">
          <path d="M0 60 L0 30 Q360 0 720 30 Q1080 60 1440 30 L1440 60 Z" fill="white" />
        </svg>
      </div>
    </section>
  );
}

// ─── Beta banner ──────────────────────────────────────────────────────────────

function BetaBanner({ onSignUp }: { onSignUp: () => void }) {
  const { t } = useTranslation();
  return (
    <section className="bg-brand-50 border-b border-brand-100 py-4">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-center gap-3 text-center sm:text-left">
        <span className="text-sm font-semibold text-brand-700">{t('landing.betaBannerTitle')}</span>
        <span className="text-sm text-brand-600">{t('landing.betaBannerDesc')}</span>
        <button onClick={onSignUp} className="shrink-0 text-sm font-semibold text-brand-600 underline underline-offset-2 hover:text-brand-800 transition-colors">
          {t('landing.joinNow')}
        </button>
      </div>
    </section>
  );
}

// ─── Features ─────────────────────────────────────────────────────────────────

const FEATURES = [
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
        <circle cx="12" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/>
        <path strokeLinecap="round" d="M12 7v4m0 0l-5 6m5-6l5 6"/>
      </svg>
    ),
    titleKey: 'landing.features.interactiveCanvas',
    descKey: 'landing.features.interactiveCanvasDesc',
    accent: 'text-brand-600 bg-brand-50',
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
      </svg>
    ),
    titleKey: 'landing.features.ancestryFanChart',
    descKey: 'landing.features.ancestryFanChartDesc',
    accent: 'text-purple-600 bg-purple-50',
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"/>
      </svg>
    ),
    titleKey: 'landing.features.roleBasedCollab',
    descKey: 'landing.features.roleBasedCollabDesc',
    accent: 'text-green-600 bg-green-50',
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/>
      </svg>
    ),
    titleKey: 'landing.features.profilePhotos',
    descKey: 'landing.features.profilePhotosDesc',
    accent: 'text-amber-600 bg-amber-50',
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
      </svg>
    ),
    titleKey: 'landing.features.relationshipFinder',
    descKey: 'landing.features.relationshipFinderDesc',
    accent: 'text-rose-600 bg-rose-50',
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01"/>
      </svg>
    ),
    titleKey: 'landing.features.appearanceThemes',
    descKey: 'landing.features.appearanceThemesDesc',
    accent: 'text-sky-600 bg-sky-50',
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
      </svg>
    ),
    titleKey: 'landing.features.importExport',
    descKey: 'landing.features.importExportDesc',
    accent: 'text-indigo-600 bg-indigo-50',
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
      </svg>
    ),
    titleKey: 'landing.features.reportsStats',
    descKey: 'landing.features.reportsStatsDesc',
    accent: 'text-teal-600 bg-teal-50',
  },
];

function Features() {
  const { t } = useTranslation();
  return (
    <section className="py-20 sm:py-24 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-14">
          <span className="text-xs font-semibold text-brand-600 uppercase tracking-widest">{t('landing.builtForFamilies')}</span>
          <h2 className="mt-2 text-3xl sm:text-4xl font-extrabold text-gray-900">{t('landing.everythingYouNeed')}</h2>
          <p className="mt-3 text-base text-gray-500 max-w-2xl mx-auto">
            {t('landing.featuresSubtitle')}
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {FEATURES.map((f) => (
            <div key={f.titleKey} className="rounded-xl border border-gray-100 bg-white p-5 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200">
              <div className={['w-10 h-10 rounded-xl flex items-center justify-center mb-4', f.accent].join(' ')}>
                {f.icon}
              </div>
              <h3 className="text-sm font-bold text-gray-900 mb-1.5">{t(f.titleKey)}</h3>
              <p className="text-xs text-gray-500 leading-relaxed">{t(f.descKey)}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Dashboard mockup section ─────────────────────────────────────────────────

function DashboardSection() {
  const { t } = useTranslation();
  const trees = [
    { emoji: '🌳', name: 'The Johnson Family',  role: 'Owner',  people: 47, members: 3, roleColor: '#6366f1', roleBg: '#eef2ff' },
    { emoji: '🌲', name: 'Smith Maternal Line', role: 'Editor', people: 21, members: 1, roleColor: '#16a34a', roleBg: '#f0fdf4' },
    { emoji: '📜', name: 'Kowalski Heritage',   role: 'Viewer', people: 89, members: 5, roleColor: '#6b7280', roleBg: '#f3f4f6' },
    { emoji: '🌸', name: 'Chen Family Tree',    role: 'Admin',  people: 34, members: 2, roleColor: '#7c3aed', roleBg: '#f5f3ff' },
  ];

  const dashboardFeatures = t('landing.dashboardFeatures', { returnObjects: true }) as string[];

  return (
    <section className="py-20 sm:py-24 bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col lg:flex-row items-center gap-12">
        <div className="flex-1 max-w-md">
          <span className="text-xs font-semibold text-brand-600 uppercase tracking-widest">{t('landing.dashboardSection')}</span>
          <h2 className="mt-2 text-3xl font-extrabold text-gray-900 mb-4">{t('landing.allTreesOnePlace')}</h2>
          <p className="text-gray-500 text-sm leading-relaxed mb-6">
            {t('landing.dashboardDesc')}
          </p>
          <ul className="space-y-3">
            {dashboardFeatures.map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                <svg className="w-4 h-4 text-brand-500 mt-0.5 shrink-0" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                </svg>
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div className="flex-1 w-full">
          <div className="rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <div>
                <div className="text-sm font-bold text-gray-900">Welcome back, Emily</div>
                <div className="text-xs text-gray-500 mt-0.5">Your family trees</div>
              </div>
              <div className="flex gap-2">
                <div className="px-3 py-1.5 border border-gray-200 rounded-lg text-xs text-gray-600 font-medium">↑ Import</div>
                <div className="px-3 py-1.5 bg-brand-500 rounded-lg text-xs text-white font-medium">+ New tree</div>
              </div>
            </div>
            <div className="p-4 grid grid-cols-2 gap-3">
              {trees.map((t) => (
                <div key={t.name} className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm hover:border-brand-200 transition-colors cursor-default">
                  <div className="flex items-start justify-between mb-3">
                    <span className="text-2xl">{t.emoji}</span>
                    <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full"
                      style={{ background: t.roleBg, color: t.roleColor }}>{t.role}</span>
                  </div>
                  <div className="text-xs font-semibold text-gray-900 truncate mb-1">{t.name}</div>
                  <div className="flex gap-3 pt-2 border-t border-gray-50 text-[10px] text-gray-400">
                    <span><span className="font-semibold text-gray-600">{t.people}</span> people</span>
                    <span><span className="font-semibold text-gray-600">{t.members}</span> members</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Collaboration section ────────────────────────────────────────────────────

function CollabSection() {
  const { t } = useTranslation();
  const roles = [
    { role: 'Owner',  color: '#6366f1', bg: '#eef2ff', descKey: 'landing.roleDescriptions.owner' },
    { role: 'Admin',  color: '#7c3aed', bg: '#f5f3ff', descKey: 'landing.roleDescriptions.admin' },
    { role: 'Editor', color: '#16a34a', bg: '#f0fdf4', descKey: 'landing.roleDescriptions.editor' },
    { role: 'Viewer', color: '#6b7280', bg: '#f3f4f6', descKey: 'landing.roleDescriptions.viewer' },
  ];

  return (
    <section className="py-20 sm:py-24 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col lg:flex-row-reverse items-center gap-12">
        <div className="flex-1 max-w-md">
          <span className="text-xs font-semibold text-brand-600 uppercase tracking-widest">{t('landing.collaboration')}</span>
          <h2 className="mt-2 text-3xl font-extrabold text-gray-900 mb-4">{t('landing.familyResearch')}</h2>
          <p className="text-gray-500 text-sm leading-relaxed mb-4">
            {t('landing.collabDesc1')}
          </p>
          <p className="text-gray-500 text-sm leading-relaxed">
            {t('landing.collabDesc2')}
          </p>
        </div>
        <div className="flex-1 w-full max-w-sm mx-auto lg:mx-0">
          <div className="rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <div className="text-sm font-bold text-gray-900">{t('landing.collabShareTitle')}</div>
              <div className="text-xs text-gray-400 mt-0.5">{t('landing.collabShareSubtitle')}</div>
            </div>
            <div className="p-4 space-y-2">
              {[
                { name: 'Emily Johnson', email: 'emily@example.com', role: 'Owner',  color: '#6366f1', bg: '#eef2ff', initials: 'EJ', ac: '#ec4899' },
                { name: 'David Johnson', email: 'david@example.com', role: 'Admin',  color: '#7c3aed', bg: '#f5f3ff', initials: 'DJ', ac: '#3b82f6' },
                { name: 'Mark Johnson',  email: 'mark@example.com',  role: 'Editor', color: '#16a34a', bg: '#f0fdf4', initials: 'MJ', ac: '#3b82f6' },
              ].map((m) => (
                <div key={m.name} className="flex items-center justify-between px-3 py-2.5 rounded-lg hover:bg-gray-50">
                  <div className="flex items-center gap-2.5">
                    <div style={{ width: 28, height: 28, borderRadius: '50%', background: m.ac, color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700 }}>
                      {m.initials}
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-gray-900">{m.name}</div>
                      <div className="text-[10px] text-gray-400">{m.email}</div>
                    </div>
                  </div>
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                    style={{ background: m.bg, color: m.color }}>{m.role}</span>
                </div>
              ))}
              <div className="pt-2 border-t border-gray-100">
                <div className="flex gap-2">
                  <div className="flex-1 h-8 rounded-lg border border-dashed border-brand-300 bg-brand-50 flex items-center px-2">
                    <span className="text-[10px] text-brand-400">someone@example.com</span>
                  </div>
                  <div className="h-8 px-3 bg-brand-500 text-white text-[10px] font-semibold rounded-lg flex items-center">{t('landing.sendInvite')}</div>
                </div>
              </div>
            </div>
            <div className="px-4 pb-4 grid grid-cols-2 gap-1.5">
              {roles.map((r) => (
                <div key={r.role} className="rounded-lg p-2" style={{ background: r.bg }}>
                  <div className="text-[10px] font-bold mb-0.5" style={{ color: r.color }}>{r.role}</div>
                  <div className="text-[9px] text-gray-500 leading-tight">{t(r.descKey)}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── How it works ─────────────────────────────────────────────────────────────

function HowItWorks() {
  const { t } = useTranslation();
  const steps = [
    { num: '1', emoji: '✉️', titleKey: 'landing.step1Title', descKey: 'landing.step1Desc' },
    { num: '2', emoji: '🌳', titleKey: 'landing.step2Title', descKey: 'landing.step2Desc' },
    { num: '3', emoji: '🤝', titleKey: 'landing.step3Title', descKey: 'landing.step3Desc' },
  ];

  return (
    <section className="py-20 sm:py-24 bg-gray-50">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <span className="text-xs font-semibold text-brand-600 uppercase tracking-widest">{t('landing.gettingStarted')}</span>
          <h2 className="mt-2 text-3xl font-extrabold text-gray-900">{t('landing.upAndRunning')}</h2>
        </div>
        <div className="relative grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="hidden md:block absolute top-12 left-1/3 right-1/3 h-px bg-gradient-to-r from-brand-200 via-brand-300 to-brand-200" />
          {steps.map((step) => (
            <div key={step.num} className="flex flex-col items-center text-center">
              <div className="relative mb-5">
                <div className="w-24 h-24 rounded-2xl bg-white border border-gray-200 shadow-sm flex items-center justify-center text-4xl">
                  {step.emoji}
                </div>
                <div className="absolute -top-2 -right-2 w-6 h-6 rounded-full bg-brand-500 text-white text-xs font-bold flex items-center justify-center shadow">
                  {step.num}
                </div>
              </div>
              <h3 className="text-sm font-bold text-gray-900 mb-2">{t(step.titleKey)}</h3>
              <p className="text-xs text-gray-500 leading-relaxed max-w-56 mx-auto">{t(step.descKey)}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Fan chart teaser ─────────────────────────────────────────────────────────

function FanChartTeaser() {
  const { t } = useTranslation();
  const cx = 300, cy = 240, r0 = 30;
  const gens = [
    { r: 30,  R: 80,  count: 1, color: '#6366f1' },
    { r: 80,  R: 140, count: 2, color: '#818cf8' },
    { r: 140, R: 200, count: 4, color: '#a5b4fc' },
    { r: 200, R: 260, count: 8, color: '#c7d2fe' },
  ];

  function arc(cx: number, cy: number, r: number, R: number, startAngle: number, endAngle: number) {
    const toRad = (d: number) => (d * Math.PI) / 180;
    const s = toRad(startAngle), e = toRad(endAngle);
    return [
      `M ${cx + r * Math.cos(s)} ${cy + r * Math.sin(s)}`,
      `A ${r} ${r} 0 ${e - s > Math.PI ? 1 : 0} 1 ${cx + r * Math.cos(e)} ${cy + r * Math.sin(e)}`,
      `L ${cx + R * Math.cos(e)} ${cy + R * Math.sin(e)}`,
      `A ${R} ${R} 0 ${e - s > Math.PI ? 1 : 0} 0 ${cx + R * Math.cos(s)} ${cy + R * Math.sin(s)}`,
      'Z',
    ].join(' ');
  }

  const slices: React.ReactElement[] = [];
  gens.forEach(({ r, R, count, color }, gi) => {
    for (let i = 0; i < count; i++) {
      const start = 180 + i * (180 / count);
      const end   = 180 + (i + 1) * (180 / count);
      slices.push(<path key={`${gi}-${i}`} d={arc(cx, cy, r + 2, R - 2, start, end)} fill={color} stroke="white" strokeWidth="2" />);
    }
  });

  return (
    <section className="py-20 sm:py-24 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col lg:flex-row items-center gap-12">
        <div className="flex-1 flex items-center justify-center">
          <div className="rounded-2xl border border-gray-200 bg-gray-50 shadow-sm p-6 w-full max-w-md">
            <div className="flex items-center gap-2 mb-4">
              {['TB', 'LR', 'Fan', 'Ancestry Fan'].map((m) => (
                <div key={m} className="px-2 py-1 rounded text-[10px] font-semibold"
                  style={{ background: m === 'Ancestry Fan' ? '#6366f1' : '#f1f5f9', color: m === 'Ancestry Fan' ? '#fff' : '#94a3b8' }}>{m}</div>
              ))}
            </div>
            <svg viewBox="60 0 480 260" className="w-full" style={{ overflow: 'visible' }}>
              <defs>
                <pattern id="fdots" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
                  <circle cx="1" cy="1" r="0.8" fill="#e2e8f0" />
                </pattern>
              </defs>
              <rect x="60" y="0" width="480" height="260" fill="url(#fdots)" />
              {slices}
              <circle cx={cx} cy={cy} r={r0} fill="#6366f1" />
              <text x={cx} y={cy - 5} textAnchor="middle" fill="white" fontSize="9" fontWeight="700">Emily</text>
              <text x={cx} y={cy + 7} textAnchor="middle" fill="white" fontSize="8">Johnson</text>
            </svg>
            <div className="mt-3 flex items-center gap-3 flex-wrap">
              {[{ color: '#6366f1', labelKey: 'landing.fanLegend.you' }, { color: '#818cf8', labelKey: 'landing.fanLegend.parents' }, { color: '#a5b4fc', labelKey: 'landing.fanLegend.grandparents' }, { color: '#c7d2fe', labelKey: 'landing.fanLegend.greatGrandparents' }].map(({ color, labelKey }) => (
                <div key={labelKey} className="flex items-center gap-1.5">
                  <div className="w-3 h-3 rounded-sm" style={{ background: color }} />
                  <span className="text-[10px] text-gray-500">{t(labelKey)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="flex-1 max-w-md">
          <span className="text-xs font-semibold text-brand-600 uppercase tracking-widest">{t('landing.fanChartSection')}</span>
          <h2 className="mt-2 text-3xl font-extrabold text-gray-900 mb-4">{t('landing.fourGenerations')}</h2>
          <p className="text-gray-500 text-sm leading-relaxed mb-4">
            {t('landing.fanChartDesc1')}
          </p>
          <p className="text-gray-500 text-sm leading-relaxed">
            {t('landing.fanChartDesc2')}
          </p>
        </div>
      </div>
    </section>
  );
}

// ─── CTA ──────────────────────────────────────────────────────────────────────

function CTA({ onSignUp }: { onSignUp: () => void }) {
  const { t } = useTranslation();
  return (
    <section className="py-20 sm:py-24 bg-gradient-to-br from-brand-800 to-indigo-900 relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none opacity-10">
        <svg viewBox="0 0 600 300" className="w-full h-full" preserveAspectRatio="xMidYMid slice">
          <circle cx="500" cy="-50" r="250" fill="white" /><circle cx="100" cy="350" r="200" fill="white" />
        </svg>
      </div>
      <div className="relative max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <div className="text-5xl mb-5">🌳</div>
        <h2 className="text-3xl sm:text-4xl font-extrabold text-white mb-3">{t('landing.startYourTree')}</h2>
        <p className="text-indigo-200 text-base mb-2">
          {t('landing.ctaDesc')}
        </p>
        <p className="text-indigo-300 text-sm mb-8">
          {t('landing.ctaDataNote')}
        </p>
        <button
          onClick={onSignUp}
          className="inline-flex items-center gap-2 px-8 py-3.5 text-sm font-bold rounded-lg bg-white text-brand-700 hover:bg-brand-50 shadow-lg transition-all hover:-translate-y-0.5 duration-200"
        >
          {t('landing.createFreeAccount')}
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6"/>
          </svg>
        </button>
      </div>
    </section>
  );
}

// ─── Footer ───────────────────────────────────────────────────────────────────

function LandingFooter() {
  const { t } = useTranslation();
  return (
    <footer className="bg-gray-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="flex flex-col sm:flex-row gap-8 pb-8 border-b border-gray-800">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-2xl leading-none">🌳</span>
              <span className="font-bold text-white">{t('common.appName')}</span>
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-brand-900 text-brand-400 border border-brand-700">{t('common.beta')}</span>
            </div>
            <p className="text-sm text-gray-400 leading-relaxed max-w-xs">
              {t('landing.footerDesc')}
            </p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-8">
            {[
              { headingKey: 'landing.support', links: [{ labelKey: 'landing.help', to: '/help' }, { labelKey: 'landing.contact', to: '/contact' }] },
              { headingKey: 'landing.legal', links: [{ labelKey: 'landing.terms', to: '/terms' }, { labelKey: 'landing.privacy', to: '/privacy' }] },
            ].map(({ headingKey, links }) => (
              <div key={headingKey}>
                <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">{t(headingKey)}</h4>
                <ul className="space-y-2">
                  {links.map(({ labelKey, to }) => (
                    <li key={labelKey}><Link to={to} className="text-sm text-gray-400 hover:text-white transition-colors">{t(labelKey)}</Link></li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
        <div className="pt-6 flex flex-col sm:flex-row items-center justify-between gap-2">
          <p className="text-xs text-gray-500">{t('landing.copyright', { year: new Date().getFullYear() })}</p>
          <p className="text-xs text-gray-600">{t('landing.betaFeedback')}</p>
        </div>
      </div>
    </footer>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isInitialised   = useAuthStore((s) => s.isInitialised);
  const navigate        = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [modal, setModal] = useState<ModalType>(null);
  const [authError, setAuthError] = useState<string | null>(null);

  // Reopen the right popup (and surface the error) after a cancelled OAuth
  // round-trip — the backend redirects back to /?auth=login|register&error=...
  useEffect(() => {
    const auth = searchParams.get('auth');
    const error = searchParams.get('error');
    if (auth === 'login' || auth === 'register') {
      setModal(auth);
      setAuthError(error);
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.delete('auth');
        next.delete('error');
        return next;
      }, { replace: true });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (isInitialised && isAuthenticated) navigate('/dashboard', { replace: true });
  }, [isInitialised, isAuthenticated, navigate]);

  if (!isInitialised || isAuthenticated) return null;

  const openSignIn  = () => { setAuthError(null); setModal('login'); };
  const openSignUp  = () => { setAuthError(null); setModal('register'); };
  const closeModal  = () => { setAuthError(null); setModal(null); };

  return (
    <>
      <SEO
        title="Free Family Tree Builder Online — Genealogy Software"
        description="Build your family tree online for free with OurFamRoots. Interactive ancestry fan charts up to 8 generations, pedigree views, collaborative editing, photo uploads, and relationship mapping. No download required — start tracing your ancestors today."
        canonical="/"
        keywords="free family tree builder, build family tree online, genealogy software free, ancestry chart maker, fan chart genealogy, pedigree chart creator, trace ancestors online, family history tool, collaborative family tree, family tree app free, heritage mapping, ancestor search, genealogy platform"
      />

      {/* Auth modals */}
      {modal === 'login' && (
        <LoginModal onClose={closeModal} onSwitchToRegister={openSignUp} initialError={authError} />
      )}
      {modal === 'register' && (
        <RegisterModal onClose={closeModal} onSwitchToLogin={openSignIn} initialError={authError} />
      )}

      <LandingNav onSignIn={openSignIn} onSignUp={openSignUp} />
      <main>
        <Hero onSignUp={openSignUp} onSignIn={openSignIn} />
        <BetaBanner onSignUp={openSignUp} />
        <Features />
        <DashboardSection />
        <CollabSection />
        <HowItWorks />
        <FanChartTeaser />
        <CTA onSignUp={openSignUp} />
      </main>
      <LandingFooter />
    </>
  );
}
