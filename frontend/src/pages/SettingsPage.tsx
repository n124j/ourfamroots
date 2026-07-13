import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@store/auth.store';
import { SEO } from '@shared/components/SEO';
import { UserAvatar } from '@shared/components/UserAvatar';
import { usePortalThemeStore, PORTAL_PRESETS, PORTAL_PRESET_LABEL, type PortalTheme } from '@store/portalTheme.store';
import { changeLanguage, getCurrentLanguage } from '../i18n';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

type Tab = 'profile' | 'security' | 'appearance' | 'notifications' | 'language';

interface UserProfile {
  given_name: string | null;
  family_name: string | null;
  email: string;
  avatar_url: string | null;
  app_role: 'SUPER_ADMIN' | 'ADMIN' | 'STANDARD' | 'AUDITOR';
  locale: string;
  timezone: string;
  oauth_providers: string[];
}

// ── Appearance Tab (portal-wide theme) ────────────────────────────────────

function PortalColorField({
  label, field, value,
}: { label: string; field: keyof PortalTheme; value: string }) {
  const updateField = usePortalThemeStore((s) => s.updateField);
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-gray-100 last:border-0">
      <label className="text-sm text-gray-700">{label}</label>
      <div className="flex items-center gap-2">
        <div className="w-6 h-6 rounded border border-gray-300" style={{ background: value }} />
        <input
          type="color"
          value={value}
          onChange={(e) => updateField(field, e.target.value)}
          className="w-8 h-8 rounded cursor-pointer border-0 p-0 bg-transparent"
          title={value}
        />
        <span className="text-xs text-gray-400 font-mono w-16">{value}</span>
      </div>
    </div>
  );
}

function AppearanceTab() {
  const { t } = useTranslation();
  const { theme, setPreset, reset } = usePortalThemeStore();
  const accessToken = useAuthStore((s) => s.accessToken);
  const storeUser   = useAuthStore((s) => s.user);
  const setUser     = useAuthStore((s) => s.setUser);
  const mounted = useRef(false);

  // Persist to the account (not just this device) whenever the theme changes,
  // however it changed — preset click, individual colour edit, or reset.
  useEffect(() => {
    if (!mounted.current) { mounted.current = true; return; }
    if (!accessToken) return;
    const timer = setTimeout(() => {
      fetch(`${API_BASE}/users/me`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
        credentials: 'include',
        body: JSON.stringify({ theme }),
      })
        .then((res) => {
          if (res.ok && storeUser) setUser({ ...storeUser, theme });
        })
        .catch(() => {});
    }, 500);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [theme, accessToken]);

  return (
    <div className="space-y-6">
      <p className="text-sm text-gray-500">
        {t('settings.appearance.description')}
      </p>

      {/* Presets */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-3">{t('settings.appearance.presets')}</h3>
        <div className="flex flex-wrap gap-2">
          {PORTAL_PRESETS.map((p) => (
            <button
              key={p.preset}
              onClick={() => setPreset(p.preset)}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg border-2 text-sm font-medium transition-colors ${
                theme.preset === p.preset
                  ? 'border-brand-500 bg-brand-50 text-brand-700'
                  : 'border-gray-200 hover:border-gray-300 text-gray-700'
              }`}
            >
              <span className="flex gap-0.5">
                <span className="w-3 h-3 rounded-sm" style={{ background: p.mainBg, border: `1px solid ${p.sidebarBorder}` }} />
                <span className="w-3 h-3 rounded-sm" style={{ background: p.sidebarBg, border: `1px solid ${p.sidebarBorder}` }} />
                <span className="w-3 h-3 rounded-sm" style={{ background: p.navActiveBg }} />
              </span>
              {PORTAL_PRESET_LABEL[p.preset]}
            </button>
          ))}
          {theme.preset === 'custom' && (
            <span className="flex items-center px-3 py-2 rounded-lg border-2 border-brand-500 bg-brand-50 text-sm font-medium text-brand-700">
              {t('settings.appearance.custom')}
            </span>
          )}
        </div>
      </div>

      {/* Background */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-1">{t('settings.appearance.background')}</h3>
        <div className="bg-white rounded-xl border border-gray-200 px-4">
          <PortalColorField label={t('settings.appearance.mainContentBg')} field="mainBg"   value={theme.mainBg} />
          <PortalColorField label={t('settings.appearance.cardPanelBg')} field="cardBg"   value={theme.cardBg} />
        </div>
      </div>

      {/* Sidebar */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-1">{t('settings.appearance.sidebar')}</h3>
        <div className="bg-white rounded-xl border border-gray-200 px-4">
          <PortalColorField label={t('settings.appearance.sidebarBg')} field="sidebarBg"       value={theme.sidebarBg} />
          <PortalColorField label={t('settings.appearance.sidebarBorder')} field="sidebarBorder"   value={theme.sidebarBorder} />
          <PortalColorField label={t('settings.appearance.navLinkText')} field="navText"         value={theme.navText} />
          <PortalColorField label={t('settings.appearance.navLinkHover')} field="navHover"        value={theme.navHover} />
          <PortalColorField label={t('settings.appearance.activeLinkBg')} field="navActiveBg"     value={theme.navActiveBg} />
          <PortalColorField label={t('settings.appearance.activeLinkText')} field="navActiveText"   value={theme.navActiveText} />
          <PortalColorField label={t('settings.appearance.logoText')} field="logoText"        value={theme.logoText} />
        </div>
      </div>

      {/* Text */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-1">{t('settings.appearance.foreground')}</h3>
        <div className="bg-white rounded-xl border border-gray-200 px-4">
          <PortalColorField label={t('settings.appearance.primaryText')} field="textPrimary" value={theme.textPrimary} />
          <PortalColorField label={t('settings.appearance.mutedText')} field="textMuted"   value={theme.textMuted} />
        </div>
      </div>

      {/* Live preview */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-2">{t('settings.appearance.preview')}</h3>
        <div className="rounded-xl overflow-hidden border border-gray-200 flex" style={{ height: 160 }}>
          {/* Sidebar preview */}
          <div className="w-36 flex flex-col p-2 gap-1" style={{ background: theme.sidebarBg, borderRight: `1px solid ${theme.sidebarBorder}` }}>
            <p className="text-xs font-bold px-2 py-1 mb-1" style={{ color: theme.logoText }}>OurFamRoots</p>
            {[t('nav.dashboard'), t('nav.settings')].map((l, i) => (
              <div key={l} className="px-2 py-1 rounded text-xs" style={{
                background: i === 0 ? theme.navActiveBg : 'transparent',
                color: i === 0 ? theme.navActiveText : theme.navText,
              }}>{l}</div>
            ))}
          </div>
          {/* Main preview */}
          <div className="flex-1 p-4 flex flex-col gap-2" style={{ background: theme.mainBg }}>
            <p className="text-sm font-semibold" style={{ color: theme.textPrimary }}>{t('settings.appearance.familyTrees')}</p>
            <div className="rounded-lg p-3 shadow-sm" style={{ background: theme.cardBg, border: `1px solid ${theme.sidebarBorder}` }}>
              <p className="text-xs font-medium" style={{ color: theme.textPrimary }}>The Shah Dynasty</p>
              <p className="text-xs" style={{ color: theme.textMuted }}>24 {t('common.people')} · 3 {t('common.members')}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="flex justify-end">
        <button
          onClick={reset}
          className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          {t('settings.appearance.resetToLight')}
        </button>
      </div>
    </div>
  );
}

// ── Delete account modal ──────────────────────────────────────────────────────

type DeleteStep = 'warn' | 'confirm' | 'sent';

function DeleteAccountModal({
  userEmail,
  accessToken,
  onClose,
}: {
  userEmail: string;
  accessToken: string | null;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const logout    = useAuthStore((s) => s.logout);
  const cardRef   = useRef<HTMLDivElement>(null);
  const [step, setStep]         = useState<DeleteStep>('warn');
  const [emailInput, setEmailInput] = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');

  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') onClose(); }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  async function handleSendConfirmation(e: React.FormEvent) {
    e.preventDefault();
    if (emailInput.trim().toLowerCase() !== userEmail.toLowerCase()) {
      setError(t('settings.deleteModal.emailNoMatch'));
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/users/me/request-deletion`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
        credentials: 'include',
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error((data as any).detail ?? 'Failed to send confirmation email. Please try again.');
      }
      setStep('sent');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleSentClose() {
    logout();
    window.location.href = '/';
  }

  const deleteItems: string[] = t('settings.deleteModal.items', { returnObjects: true }) as any;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        ref={cardRef}
        className="relative w-full max-w-md bg-white rounded-2xl shadow-xl p-7"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 w-7 h-7 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors text-lg leading-none"
          aria-label={t('common.close')}
        >
          ×
        </button>

        {/* Step 1 — Warning */}
        {step === 'warn' && (
          <div>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center text-xl shrink-0">
                ⚠️
              </div>
              <h2 className="text-lg font-bold text-gray-900">{t('settings.deleteModal.title')}</h2>
            </div>

            <p className="text-sm text-gray-600 mb-4" dangerouslySetInnerHTML={{ __html: t('settings.deleteModal.warning') }} />

            <ul className="text-sm text-gray-700 space-y-1.5 mb-5 pl-1">
              {deleteItems.map((item: string) => (
                <li key={item} className="flex items-start gap-2">
                  <span className="text-red-500 mt-0.5 shrink-0">✕</span>
                  {item}
                </li>
              ))}
            </ul>

            <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5 text-xs text-amber-800 mb-6"
              dangerouslySetInnerHTML={{ __html: t('settings.deleteModal.note') }} />

            <div className="flex gap-3 justify-end">
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                {t('settings.deleteModal.cancelKeep')}
              </button>
              <button
                onClick={() => setStep('confirm')}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors"
              >
                {t('settings.deleteModal.understandContinue')}
              </button>
            </div>
          </div>
        )}

        {/* Step 2 — Email confirmation */}
        {step === 'confirm' && (
          <div>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center text-xl shrink-0">
                📧
              </div>
              <h2 className="text-lg font-bold text-gray-900">{t('settings.deleteModal.confirmByEmail')}</h2>
            </div>

            <p className="text-sm text-gray-600 mb-1" dangerouslySetInnerHTML={{ __html: t('settings.deleteModal.confirmDesc') }} />
            <p className="text-xs text-gray-400 mb-5">
              {t('settings.deleteModal.linkExpiry')}
            </p>

            <form onSubmit={handleSendConfirmation} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  {t('settings.deleteModal.typeEmail')}
                </label>
                <input
                  type="email"
                  autoFocus
                  value={emailInput}
                  onChange={(e) => { setEmailInput(e.target.value); setError(''); }}
                  placeholder={userEmail}
                  required
                  className="w-full h-10 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-400 focus:border-transparent"
                />
                <p className="mt-1 text-xs text-gray-400">
                  {t('settings.deleteModal.yourAccountEmail')} <span className="font-medium text-gray-600">{userEmail}</span>
                </p>
              </div>

              {error && (
                <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                  {error}
                </div>
              )}

              <div className="flex gap-3 justify-end pt-1">
                <button
                  type="button"
                  onClick={() => { setStep('warn'); setEmailInput(''); setError(''); }}
                  className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  {t('common.back')}
                </button>
                <button
                  type="submit"
                  disabled={loading || !emailInput.trim()}
                  className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {loading ? t('settings.deleteModal.sending') : t('settings.deleteModal.sendConfirmation')}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Step 3 — Sent */}
        {step === 'sent' && (
          <div className="text-center py-2">
            <div className="text-5xl mb-4">📬</div>
            <h2 className="text-lg font-bold text-gray-900 mb-2">{t('settings.deleteModal.checkInbox')}</h2>
            <p className="text-sm text-gray-600 leading-relaxed mb-2">
              {t('settings.deleteModal.confirmSent')}{' '}
              <span className="font-semibold text-gray-800">{userEmail}</span>.
            </p>
            <p className="text-sm text-gray-600 leading-relaxed mb-6"
              dangerouslySetInnerHTML={{ __html: t('settings.deleteModal.confirmSentDesc') }} />
            <div className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 text-xs text-gray-500 mb-6 text-left">
              <strong className="text-gray-700">{t('settings.deleteModal.didntReceive')}</strong>
              <ul className="mt-1 space-y-0.5 list-disc pl-4">
                <li>{t('settings.deleteModal.checkSpam')}</li>
                <li>{t('settings.deleteModal.checkEmail')} <span className="font-medium">{userEmail}</span></li>
                <li>{t('settings.deleteModal.contactSupport')}</li>
              </ul>
            </div>
            <button
              onClick={handleSentClose}
              className="w-full h-10 bg-gray-800 text-white text-sm font-medium rounded-lg hover:bg-gray-900 transition-colors"
            >
              {t('settings.deleteModal.signOutClose')}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Danger zone card ──────────────────────────────────────────────────────────

function DangerZone({ userEmail, accessToken }: { userEmail: string; accessToken: string | null }) {
  const { t } = useTranslation();
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <>
      {modalOpen && (
        <DeleteAccountModal
          userEmail={userEmail}
          accessToken={accessToken}
          onClose={() => setModalOpen(false)}
        />
      )}

      <div className="mt-10 rounded-xl border-2 border-red-200 bg-red-50 p-5">
        <h3 className="text-sm font-bold text-red-800 mb-1">{t('settings.danger.title')}</h3>
        <p className="text-xs text-red-700 mb-4 leading-relaxed"
          dangerouslySetInnerHTML={{ __html: t('settings.danger.description') }} />
        <button
          onClick={() => setModalOpen(true)}
          className="px-4 py-2 text-sm font-medium text-red-700 border border-red-300 bg-white rounded-lg hover:bg-red-600 hover:text-white hover:border-red-600 transition-colors"
        >
          {t('settings.danger.deleteButton')}
        </button>
      </div>
    </>
  );
}

// ── Notifications Tab ─────────────────────────────────────────────────────────

interface SettingsNotification {
  id: string;
  type: string;
  title: string;
  body: string | null;
  data: Record<string, string>;
  is_read: boolean;
  created_at: string;
}

const ITEMS_PER_PAGE = 15;

function BroadcastSubscriptionToggle({ accessToken }: { accessToken: string | null }) {
  const { t } = useTranslation();
  const [unsubscribed, setUnsubscribed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!accessToken) return;
    fetch(`${API_BASE}/users/me/broadcast-subscription`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      credentials: 'include',
    })
      .then((r) => r.json())
      .then((d) => setUnsubscribed(d.broadcast_unsubscribed))
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, [accessToken]);

  async function toggle() {
    if (!accessToken) return;
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/users/me/broadcast-subscription`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
        credentials: 'include',
        body: JSON.stringify({ unsubscribed: !unsubscribed }),
      });
      if (res.ok) {
        const d = await res.json();
        setUnsubscribed(d.broadcast_unsubscribed);
      }
    } catch { /* ignore */ }
    finally { setSaving(false); }
  }

  if (!loaded) return null;

  return (
    <div className="flex items-center justify-between rounded-lg border p-4 mb-4"
      style={{ background: 'var(--portal-card-bg)', borderColor: 'var(--portal-card-border)' }}>
      <div>
        <p className="text-sm font-medium" style={{ color: 'var(--portal-text-primary)' }}>{t('settings.notifications.broadcastEmails')}</p>
        <p className="text-xs mt-0.5" style={{ color: 'var(--portal-text-muted)' }}>
          {t('settings.notifications.broadcastDesc')}
        </p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={!unsubscribed}
        onClick={toggle}
        disabled={saving}
        className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors disabled:opacity-50 ${
          !unsubscribed ? 'bg-brand-500' : 'bg-gray-300'
        }`}
      >
        <span className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition-transform ${
          !unsubscribed ? 'translate-x-5' : 'translate-x-0'
        }`} />
      </button>
    </div>
  );
}

function useExpiresIn() {
  const { t } = useTranslation();
  return (createdAt: string): string => {
    const expiry = new Date(new Date(createdAt).getTime() + 90 * 24 * 60 * 60 * 1000);
    const days = Math.ceil((expiry.getTime() - Date.now()) / (1000 * 60 * 60 * 24));
    if (days <= 0) return t('settings.notifications.expiringSoon');
    if (days === 1) return t('settings.notifications.expiresTomorrow');
    if (days < 7) return t('settings.notifications.expiresInDays', { days });
    if (days < 30) {
      const weeks = Math.floor(days / 7);
      return t('settings.notifications.expiresInWeeks', { count: weeks });
    }
    const months = Math.floor(days / 30);
    return t('settings.notifications.expiresInMonths', { count: months });
  };
}

function NotificationsTab({ accessToken }: { accessToken: string | null }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const expiresIn = useExpiresIn();
  const [notifications, setNotifications] = useState<SettingsNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [accepting, setAccepting] = useState<string | null>(null);
  const [itemErrors, setItemErrors] = useState<Record<string, string>>({});
  const [page, setPage] = useState(0);

  const TYPE_LABEL: Record<string, string> = {
    TREE_INVITE: t('settings.notifications.typeLabelInvitation'),
    TREE_SHARED: t('settings.notifications.typeLabelAddedToTree'),
  };

  const TYPE_BADGE: Record<string, string> = {
    TREE_INVITE: 'bg-violet-100 text-violet-700',
    TREE_SHARED: 'bg-green-100 text-green-700',
  };

  useEffect(() => {
    if (!accessToken) return;
    fetch(`${API_BASE}/notifications`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      credentials: 'include',
    })
      .then((r) => r.json())
      .then(setNotifications)
      .finally(() => setLoading(false));
  }, [accessToken]);

  async function markAllRead() {
    await fetch(`${API_BASE}/notifications/read-all`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${accessToken}` },
      credentials: 'include',
    });
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
  }

  async function markRead(id: string) {
    await fetch(`${API_BASE}/notifications/${id}/read`, {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${accessToken}` },
      credentials: 'include',
    });
    setNotifications((prev) => prev.map((n) => n.id === id ? { ...n, is_read: true } : n));
    setItemErrors((prev) => { const e = { ...prev }; delete e[id]; return e; });
  }

  async function acceptInvite(n: SettingsNotification) {
    setAccepting(n.id);
    setItemErrors((prev) => { const e = { ...prev }; delete e[n.id]; return e; });
    try {
      const res = await fetch(`${API_BASE}/invitations/accept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
        credentials: 'include',
        body: JSON.stringify({ token: n.data.token }),
      });
      if (res.ok) {
        setNotifications((prev) => prev.map((x) => x.id === n.id ? { ...x, is_read: true } : x));
        await markRead(n.id);
        if (n.data.tree_id) navigate(`/trees/${n.data.tree_id}`);
      } else {
        const body = await res.json().catch(() => ({}));
        const msg = (body as any).detail ?? `Failed (${res.status})`;
        setItemErrors((prev) => ({ ...prev, [n.id]: typeof msg === 'string' ? msg : JSON.stringify(msg) }));
      }
    } catch (err: any) {
      setItemErrors((prev) => ({ ...prev, [n.id]: err.message ?? 'Network error' }));
    } finally {
      setAccepting(null);
    }
  }

  const unreadCount = notifications.filter((n) => !n.is_read).length;
  const totalPages = Math.ceil(notifications.length / ITEMS_PER_PAGE);
  const pageItems = notifications.slice(page * ITEMS_PER_PAGE, (page + 1) * ITEMS_PER_PAGE);

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <BroadcastSubscriptionToggle accessToken={accessToken} />

      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500" dangerouslySetInnerHTML={{ __html: t('settings.notifications.retentionNote') }} />
        {unreadCount > 0 && (
          <button
            onClick={markAllRead}
            className="text-xs font-medium text-brand-600 hover:underline shrink-0"
          >
            {t('nav.markAllRead')}
          </button>
        )}
      </div>

      {notifications.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mb-3">
            <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="#9ca3af" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M11 3a4 4 0 0 1 4 4c0 3 1 4 1.5 5h-11C6 11 7 10 7 7a4 4 0 0 1 4-4z" />
              <path d="M9 17a2 2 0 0 0 4 0" />
            </svg>
          </div>
          <p className="text-sm font-medium text-gray-500">{t('settings.notifications.noNotifications')}</p>
          <p className="text-xs text-gray-400 mt-1">{t('settings.notifications.allCaughtUp')}</p>
        </div>
      ) : (
        <>
        <div className="rounded-xl border border-gray-200 bg-white divide-y divide-gray-100 overflow-hidden">
          {pageItems.map((n) => (
            <div
              key={n.id}
              className={`px-5 py-4 transition-colors ${!n.is_read ? 'bg-blue-50/40' : ''}`}
            >
              <div className="flex items-start gap-3">
                <div className={`mt-1 w-2 h-2 rounded-full shrink-0 ${!n.is_read ? 'bg-brand-500' : 'bg-transparent'}`} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap mb-0.5">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${TYPE_BADGE[n.type] ?? 'bg-gray-100 text-gray-600'}`}>
                      {TYPE_LABEL[n.type] ?? n.type}
                    </span>
                    {!n.is_read && (
                      <span className="text-[11px] font-medium text-brand-600">{t('common.new')}</span>
                    )}
                  </div>
                  <p className="text-sm font-medium text-gray-900 leading-snug">{n.title}</p>
                  {n.body && <p className="text-xs text-gray-500 mt-0.5">{n.body}</p>}
                  <div className="flex items-center gap-3 mt-1.5 flex-wrap">
                    <span className="text-[11px] text-gray-400">{new Date(n.created_at).toLocaleString()}</span>
                    <span className="text-[11px] text-gray-300">·</span>
                    <span className="text-[11px] text-gray-400">{expiresIn(n.created_at)}</span>
                  </div>

                  {itemErrors[n.id] && (
                    <p className="text-xs text-red-600 mt-1.5 bg-red-50 px-2 py-1 rounded">{itemErrors[n.id]}</p>
                  )}

                  {n.type === 'TREE_INVITE' && (
                    <div className="flex gap-2 mt-2.5 flex-wrap">
                      {n.data.token && !n.is_read && (
                        <button
                          onClick={() => acceptInvite(n)}
                          disabled={accepting === n.id}
                          className="px-3 py-1 text-xs font-medium bg-brand-500 text-white rounded-md hover:bg-brand-600 disabled:opacity-50 transition-colors"
                        >
                          {accepting === n.id ? t('notif.accepting') : t('settings.notifications.acceptInvitation')}
                        </button>
                      )}
                      {n.data.tree_id && (
                        <button
                          onClick={() => navigate(`/trees/${n.data.tree_id}`)}
                          className="px-3 py-1 text-xs font-medium bg-gray-100 text-gray-600 rounded-md hover:bg-gray-200 transition-colors"
                        >
                          {t('common.viewTree')}
                        </button>
                      )}
                      {!n.is_read && (
                        <button
                          onClick={() => markRead(n.id)}
                          className="px-3 py-1 text-xs font-medium text-gray-400 hover:text-gray-600 transition-colors"
                        >
                          {t('common.dismiss')}
                        </button>
                      )}
                    </div>
                  )}
                  {n.type === 'TREE_SHARED' && (
                    <div className="flex gap-2 mt-2.5">
                      {n.data.tree_id && (
                        <button
                          onClick={() => { markRead(n.id); navigate(`/trees/${n.data.tree_id}`); }}
                          className="px-3 py-1 text-xs font-medium bg-brand-500 text-white rounded-md hover:bg-brand-600 transition-colors"
                        >
                          {t('common.viewTree')}
                        </button>
                      )}
                      {!n.is_read && (
                        <button
                          onClick={() => markRead(n.id)}
                          className="px-3 py-1 text-xs font-medium text-gray-400 hover:text-gray-600 transition-colors"
                        >
                          {t('common.dismiss')}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-between pt-2">
            <span className="text-xs text-gray-400">
              {page * ITEMS_PER_PAGE + 1}–{Math.min((page + 1) * ITEMS_PER_PAGE, notifications.length)} {t('common.of')} {notifications.length}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-3 py-1.5 text-xs font-medium border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {t('common.previous')}
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="px-3 py-1.5 text-xs font-medium border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {t('common.next')}
              </button>
            </div>
          </div>
        )}
        </>
      )}
    </div>
  );
}

// ── Language Tab ───────────────────────────────────────────────────────────────

function LanguageTab() {
  const { t } = useTranslation();
  const accessToken = useAuthStore((s) => s.accessToken);
  const storeUser   = useAuthStore((s) => s.user);
  const setUser     = useAuthStore((s) => s.setUser);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const currentLng = getCurrentLanguage();

  async function handleChange(lng: string) {
    setError('');
    // Immediate feedback (and the fallback for signed-out visitors).
    changeLanguage(lng);

    if (!accessToken) {
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      return;
    }

    // Signed in: this is an account-level preference, not just this device's.
    try {
      const res = await fetch(`${API_BASE}/users/me`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
        credentials: 'include',
        body: JSON.stringify({ locale: lng }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? 'Failed to save language');
      }
      if (storeUser) setUser({ ...storeUser, language: lng });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const languages = [
    { code: 'en', label: 'English', nativeLabel: 'English', flag: '🇺🇸' },
    { code: 'ne', label: 'Nepali', nativeLabel: 'नेपाली', flag: '🇳🇵' },
  ];

  return (
    <div className="space-y-6">
      <p className="text-sm text-gray-500">
        {t('settings.language.description')}
      </p>

      <div className="space-y-3">
        {languages.map((lang) => (
          <button
            key={lang.code}
            onClick={() => handleChange(lang.code)}
            className={`w-full flex items-center gap-4 p-4 rounded-xl border-2 text-left transition-all ${
              currentLng === lang.code
                ? 'border-brand-500 bg-brand-50 shadow-sm'
                : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
            }`}
          >
            <span className="text-2xl">{lang.flag}</span>
            <div className="flex-1 min-w-0">
              <p className={`text-sm font-semibold ${currentLng === lang.code ? 'text-brand-700' : 'text-gray-900'}`}>
                {lang.nativeLabel}
              </p>
              <p className="text-xs text-gray-500">{lang.label}</p>
            </div>
            {currentLng === lang.code && (
              <div className="w-6 h-6 rounded-full bg-brand-500 flex items-center justify-center shrink-0">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 7l3 3 5-5" />
                </svg>
              </div>
            )}
          </button>
        ))}
      </div>

      {saved && (
        <p className="text-sm text-green-600 font-medium">{t('settings.language.saved')}</p>
      )}
      {error && (
        <p className="text-sm text-red-600 font-medium">{error}</p>
      )}
    </div>
  );
}

function TabLink({ tab, active, label }: { tab: Tab; active: boolean; label: string }) {
  return (
    <Link
      to={`/settings/${tab}`}
      className={`px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors ${
        active
          ? 'border-brand-500 text-brand-600'
          : 'border-transparent text-gray-500 hover:text-gray-700'
      }`}
    >
      {label}
    </Link>
  );
}

export default function SettingsPage() {
  const { t } = useTranslation();
  const { tab } = useParams<{ tab?: string }>();
  const accessToken = useAuthStore((s) => s.accessToken);
  const storeUser   = useAuthStore((s) => s.user);
  const setUser     = useAuthStore((s) => s.setUser);

  const ROLE_LABEL: Record<string, string> = {
    SUPER_ADMIN: t('roles.SUPER_ADMIN'),
    ADMIN:       t('roles.ADMIN'),
    STANDARD:    t('roles.STANDARD'),
    AUDITOR:     t('roles.AUDITOR'),
  };

  const ROLE_BADGE: Record<string, string> = {
    SUPER_ADMIN: 'bg-red-100 text-red-700',
    ADMIN:       'bg-purple-100 text-purple-700',
    STANDARD:    'bg-blue-100 text-blue-700',
    AUDITOR:     'bg-amber-100 text-amber-700',
  };

  const activeTab: Tab =
    tab === 'security' ? 'security' :
    tab === 'appearance' ? 'appearance' :
    tab === 'notifications' ? 'notifications' :
    tab === 'language' ? 'language' :
    'profile';

  const [profile,     setProfile]     = useState<UserProfile | null>(null);
  const [loading,     setLoading]     = useState(true);

  const [givenName,   setGivenName]   = useState('');
  const [familyName,  setFamilyName]  = useState('');
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMsg,  setProfileMsg]  = useState<{ ok: boolean; text: string } | null>(null);

  const [avatarUploading, setAvatarUploading] = useState(false);
  const avatarInputRef = useRef<HTMLInputElement>(null);

  const [currentPw,   setCurrentPw]   = useState('');
  const [newPw,       setNewPw]       = useState('');
  const [confirmPw,   setConfirmPw]   = useState('');
  const [pwSaving,    setPwSaving]    = useState(false);
  const [pwMsg,       setPwMsg]       = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    if (!accessToken) return;
    fetch(`${API_BASE}/users/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      credentials: 'include',
    })
      .then((r) => r.json())
      .then((data: UserProfile) => {
        setProfile(data);
        setGivenName(data.given_name ?? '');
        setFamilyName(data.family_name ?? '');
        if (storeUser && data.avatar_url && !storeUser.avatarUrl) {
          setUser({ ...storeUser, avatarUrl: data.avatar_url });
        }
      })
      .finally(() => setLoading(false));
  }, [accessToken]);

  async function handleProfileSave(e: React.FormEvent) {
    e.preventDefault();
    setProfileSaving(true);
    setProfileMsg(null);
    try {
      const res = await fetch(`${API_BASE}/users/me`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
        credentials: 'include',
        body: JSON.stringify({ given_name: givenName.trim() || null, family_name: familyName.trim() || null }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? 'Failed to save profile');
      }
      const updated: UserProfile = await res.json();
      setProfile(updated);
      if (storeUser) {
        setUser({
          ...storeUser,
          displayName: `${updated.given_name ?? ''} ${updated.family_name ?? ''}`.trim() || storeUser.email,
        });
      }
      setProfileMsg({ ok: true, text: t('settings.profile.profileSaved') });
    } catch (err: any) {
      setProfileMsg({ ok: false, text: err.message });
    } finally {
      setProfileSaving(false);
    }
  }

  async function handleAvatarUpload(file: File) {
    setAvatarUploading(true);
    setProfileMsg(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${API_BASE}/users/me/avatar`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${accessToken}` },
        credentials: 'include',
        body: form,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? 'Failed to upload avatar');
      }
      const { avatar_url } = await res.json();
      setProfile((p) => (p ? { ...p, avatar_url } : p));
      if (storeUser) {
        setUser({ ...storeUser, avatarUrl: avatar_url });
      }
      setProfileMsg({ ok: true, text: t('settings.profile.profilePictureUpdated') });
    } catch (err: any) {
      setProfileMsg({ ok: false, text: err.message });
    } finally {
      setAvatarUploading(false);
    }
  }

  async function handleAvatarRemove() {
    setAvatarUploading(true);
    setProfileMsg(null);
    try {
      const res = await fetch(`${API_BASE}/users/me/avatar`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${accessToken}` },
        credentials: 'include',
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? 'Failed to remove avatar');
      }
      setProfile((p) => (p ? { ...p, avatar_url: null } : p));
      if (storeUser) {
        setUser({ ...storeUser, avatarUrl: undefined });
      }
      setProfileMsg({ ok: true, text: t('settings.profile.profilePictureRemoved') });
    } catch (err: any) {
      setProfileMsg({ ok: false, text: err.message });
    } finally {
      setAvatarUploading(false);
    }
  }

  async function handlePasswordChange(e: React.FormEvent) {
    e.preventDefault();
    if (newPw !== confirmPw) {
      setPwMsg({ ok: false, text: t('settings.security.passwordsNoMatch') });
      return;
    }
    setPwSaving(true);
    setPwMsg(null);
    try {
      const res = await fetch(`${API_BASE}/users/me/change-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
        credentials: 'include',
        body: JSON.stringify({ current_password: currentPw, new_password: newPw }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? 'Failed to change password');
      }
      setPwMsg({ ok: true, text: t('settings.security.passwordChanged') });
      setCurrentPw('');
      setNewPw('');
      setConfirmPw('');
    } catch (err: any) {
      setPwMsg({ ok: false, text: err.message });
    } finally {
      setPwSaving(false);
    }
  }

  return (
    <div className="p-4 md:p-8 max-w-2xl mx-auto">
      <SEO
        title={t('settings.title')}
        description={t('settings.description')}
        noIndex
      />
      <h1 className="text-xl md:text-2xl font-bold text-gray-900 mb-5 md:mb-6">{t('settings.title')}</h1>

      <div className="flex gap-1 mb-8 border-b border-gray-200 overflow-x-auto">
        <TabLink tab="profile"       active={activeTab === 'profile'}       label={t('settings.tabs.profile')} />
        <TabLink tab="security"      active={activeTab === 'security'}      label={t('settings.tabs.security')} />
        <TabLink tab="appearance"    active={activeTab === 'appearance'}    label={t('settings.tabs.appearance')} />
        <TabLink tab="notifications" active={activeTab === 'notifications'} label={t('settings.tabs.notifications')} />
        <TabLink tab="language"      active={activeTab === 'language'}      label={t('settings.tabs.language')} />
      </div>

      {activeTab === 'appearance' && <AppearanceTab />}

      {activeTab === 'notifications' && <NotificationsTab accessToken={accessToken} />}

      {activeTab === 'language' && <LanguageTab />}

      {(activeTab === 'profile' || activeTab === 'security') && (loading ? (
        <div className="flex justify-center py-16">
          <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : activeTab === 'profile' ? (
        <form onSubmit={handleProfileSave} className="space-y-5">
          {/* Profile picture */}
          <div className="flex items-center gap-4 pb-4 border-b border-gray-100">
            <UserAvatar
              avatarUrl={profile?.avatar_url}
              displayName={`${profile?.given_name ?? ''} ${profile?.family_name ?? ''}`.trim()}
              email={profile?.email}
              size="lg"
            />
            <div>
              <p className="text-sm font-medium text-gray-900">{t('settings.profile.profilePicture')}</p>
              {profile?.oauth_providers?.length ? (
                <p className="text-xs text-gray-400 mt-0.5">
                  {t('settings.profile.syncedFrom', { providers: profile.oauth_providers.map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(', ') })}
                </p>
              ) : (
                <div className="flex items-center gap-2 mt-1">
                  <input
                    ref={avatarInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/gif"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) handleAvatarUpload(f);
                      e.target.value = '';
                    }}
                  />
                  <button
                    type="button"
                    disabled={avatarUploading}
                    onClick={() => avatarInputRef.current?.click()}
                    className="text-xs font-medium text-brand-600 hover:text-brand-700 disabled:opacity-50"
                  >
                    {avatarUploading ? t('settings.profile.uploading') : profile?.avatar_url ? t('settings.profile.change') : t('settings.profile.uploadPhoto')}
                  </button>
                  {profile?.avatar_url && (
                    <button
                      type="button"
                      disabled={avatarUploading}
                      onClick={handleAvatarRemove}
                      className="text-xs font-medium text-red-500 hover:text-red-600 disabled:opacity-50"
                    >
                      {t('common.remove')}
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('settings.profile.firstName')}</label>
              <input
                type="text"
                value={givenName}
                onChange={(e) => setGivenName(e.target.value)}
                placeholder={t('settings.profile.givenNamePlaceholder')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('settings.profile.lastName')}</label>
              <input
                type="text"
                value={familyName}
                onChange={(e) => setFamilyName(e.target.value)}
                placeholder={t('settings.profile.familyNamePlaceholder')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('settings.profile.email')}</label>
            <input
              type="email"
              value={profile?.email ?? ''}
              disabled
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm bg-gray-50 text-gray-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('settings.profile.role')}</label>
            <div className="flex items-center gap-2 px-3 py-2 border border-gray-200 rounded-lg bg-gray-50">
              {profile?.app_role && (
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium ${ROLE_BADGE[profile.app_role] ?? ROLE_BADGE.STANDARD}`}>
                  {ROLE_LABEL[profile.app_role] ?? profile.app_role}
                </span>
              )}
              <span className="text-xs text-gray-400">{t('settings.profile.assignedByAdmin')}</span>
            </div>
          </div>
          {profileMsg && (
            <p className={`text-sm ${profileMsg.ok ? 'text-green-600' : 'text-red-600'}`}>{profileMsg.text}</p>
          )}
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={profileSaving}
              className="px-5 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-50 transition-colors"
            >
              {profileSaving ? t('settings.profile.saving') : t('settings.profile.saveChanges')}
            </button>
          </div>
        </form>
      ) : (
        <div>
          <form onSubmit={handlePasswordChange} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('settings.security.currentPassword')}</label>
              <input
                type="password"
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('settings.security.newPassword')}</label>
              <input
                type="password"
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                required
              />
              <p className="text-xs text-gray-400 mt-1">{t('settings.security.passwordHint')}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('settings.security.confirmNewPassword')}</label>
              <input
                type="password"
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                required
              />
            </div>
            {pwMsg && (
              <p className={`text-sm ${pwMsg.ok ? 'text-green-600' : 'text-red-600'}`}>{pwMsg.text}</p>
            )}
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={pwSaving || !currentPw || !newPw || !confirmPw}
                className="px-5 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-50 transition-colors"
              >
                {pwSaving ? t('settings.security.changing') : t('settings.security.changePassword')}
              </button>
            </div>
          </form>

          {profile && (
            <DangerZone userEmail={profile.email} accessToken={accessToken} />
          )}
        </div>
      ))}
    </div>
  );
}
