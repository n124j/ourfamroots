import React, { useEffect, useState, useRef } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@store/auth.store';
import { useMaintenanceStore } from '@store/maintenance.store';
import { usePortalThemeStore } from '@store/portalTheme.store';
import { UserAvatar } from '@shared/components/UserAvatar';
import { Footer } from './Footer';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

interface Notification {
  id: string;
  type: string;
  title: string;
  body: string | null;
  data: Record<string, string>;
  is_read: boolean;
  created_at: string;
}

function NotificationItem({
  n,
  accessToken,
  apiBase,
  onUpdate,
  onRemove,
}: {
  n: Notification;
  accessToken: string | null;
  apiBase: string;
  onUpdate: (id: string, patch: Partial<Notification>) => void;
  onRemove: (id: string) => void;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [accepting, setAccepting] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [declined, setDeclined] = useState(false);

  async function handleAccept() {
    setAccepting(true);
    try {
      const res = await fetch(`${apiBase}/invitations/accept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
        credentials: 'include',
        body: JSON.stringify({ token: n.data.token }),
      });
      if (res.ok) {
        setAccepted(true);
        onUpdate(n.id, { is_read: true });
        await fetch(`${apiBase}/notifications/${n.id}/read`, {
          method: 'PATCH',
          headers: { Authorization: `Bearer ${accessToken}` },
          credentials: 'include',
        });
        if (n.data.tree_id) navigate(`/trees/${n.data.tree_id}`);
      }
    } finally {
      setAccepting(false);
    }
  }

  async function handleDecline() {
    setDeclined(true);
    onUpdate(n.id, { is_read: true });
    await fetch(`${apiBase}/notifications/${n.id}/read`, {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${accessToken}` },
      credentials: 'include',
    });
  }

  return (
    <div className={`px-4 py-3 hover:bg-gray-50 transition-colors ${!n.is_read ? 'bg-blue-50/50' : ''}`}>
      <div className="flex items-start gap-2.5">
        <div className={`mt-0.5 w-2 h-2 rounded-full shrink-0 ${!n.is_read ? 'bg-brand-500' : 'bg-transparent'}`} />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-gray-900 leading-snug">{n.title}</p>
          {n.body && <p className="text-xs text-gray-500 mt-0.5 leading-snug">{n.body}</p>}
          <p className="text-[11px] text-gray-400 mt-1">{new Date(n.created_at).toLocaleString()}</p>

          {/* Actions */}
          {n.type === 'TREE_INVITE' && !accepted && !declined && (
            <div className="flex gap-2 mt-2">
              <button
                onClick={handleAccept}
                disabled={accepting}
                className="px-3 py-1 text-xs font-medium bg-brand-500 text-white rounded-md hover:bg-brand-600 disabled:opacity-50 transition-colors"
              >
                {accepting ? t('notif.accepting') : t('notif.accept')}
              </button>
              <button
                onClick={handleDecline}
                className="px-3 py-1 text-xs font-medium bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors"
              >
                {t('notif.decline')}
              </button>
            </div>
          )}
          {n.type === 'TREE_INVITE' && accepted && (
            <p className="text-xs text-green-600 mt-1 font-medium">{t('notif.acceptedOpening')}</p>
          )}
          {n.type === 'TREE_INVITE' && declined && (
            <p className="text-xs text-gray-400 mt-1">{t('notif.invitationDeclined')}</p>
          )}
          {n.type === 'TREE_SHARED' && n.data.tree_id && (
            <button
              onClick={() => navigate(`/trees/${n.data.tree_id}`)}
              className="mt-2 text-xs font-medium text-brand-600 hover:underline"
            >
              {t('common.viewTreeArrow')}
            </button>
          )}

          {/* Access request — owner can approve/deny */}
          {n.type === 'ACCESS_REQUEST' && !accepted && !declined && (
            <div className="flex gap-2 mt-2">
              <button
                onClick={async () => {
                  setAccepting(true);
                  try {
                    const res = await fetch(`${apiBase}/trees/${n.data.tree_id}/access-requests/${n.data.request_id}`, {
                      method: 'PATCH',
                      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
                      credentials: 'include',
                      body: JSON.stringify({ action: 'approve' }),
                    });
                    if (res.ok) {
                      await fetch(`${apiBase}/notifications/${n.id}/read`, { method: 'PATCH', headers: { Authorization: `Bearer ${accessToken}` }, credentials: 'include' });
                      onRemove(n.id);
                    }
                  } finally { setAccepting(false); }
                }}
                disabled={accepting}
                className="px-3 py-1 text-xs font-medium bg-brand-500 text-white rounded-md hover:bg-brand-600 disabled:opacity-50 transition-colors"
              >
                {accepting ? t('notif.approving') : t('common.approve')}
              </button>
              <button
                onClick={async () => {
                  await fetch(`${apiBase}/trees/${n.data.tree_id}/access-requests/${n.data.request_id}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
                    credentials: 'include',
                    body: JSON.stringify({ action: 'deny' }),
                  });
                  await fetch(`${apiBase}/notifications/${n.id}/read`, { method: 'PATCH', headers: { Authorization: `Bearer ${accessToken}` }, credentials: 'include' });
                  onRemove(n.id);
                }}
                className="px-3 py-1 text-xs font-medium bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors"
              >
                {t('common.deny')}
              </button>
            </div>
          )}

          {/* Merge request — owner can approve/deny */}
          {n.type === 'MERGE_REQUEST' && !accepted && !declined && (
            <div className="flex gap-2 mt-2">
              <button
                onClick={async () => {
                  setAccepting(true);
                  try {
                    const res = await fetch(`${apiBase}/trees/${n.data.tree_id}/merge-requests/${n.data.request_id}`, {
                      method: 'PATCH',
                      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
                      credentials: 'include',
                      body: JSON.stringify({ action: 'approve' }),
                    });
                    if (res.ok) {
                      await fetch(`${apiBase}/notifications/${n.id}/read`, { method: 'PATCH', headers: { Authorization: `Bearer ${accessToken}` }, credentials: 'include' });
                      onRemove(n.id);
                    }
                  } finally { setAccepting(false); }
                }}
                disabled={accepting}
                className="px-3 py-1 text-xs font-medium bg-brand-500 text-white rounded-md hover:bg-brand-600 disabled:opacity-50 transition-colors"
              >
                {accepting ? t('notif.approving') : t('notif.approveMerge')}
              </button>
              <button
                onClick={async () => {
                  await fetch(`${apiBase}/trees/${n.data.tree_id}/merge-requests/${n.data.request_id}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
                    credentials: 'include',
                    body: JSON.stringify({ action: 'deny' }),
                  });
                  await fetch(`${apiBase}/notifications/${n.id}/read`, { method: 'PATCH', headers: { Authorization: `Bearer ${accessToken}` }, credentials: 'include' });
                  onRemove(n.id);
                }}
                className="px-3 py-1 text-xs font-medium bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors"
              >
                {t('common.deny')}
              </button>
            </div>
          )}

          {/* Result notifications — info-only with link */}
          {(n.type === 'ACCESS_APPROVED' || n.type === 'MERGE_APPROVED') && n.data.tree_id && (
            <button
              onClick={() => navigate(`/trees/${n.data.tree_id}`)}
              className="mt-2 text-xs font-medium text-brand-600 hover:underline"
            >
              {t('common.viewTreeArrow')}
            </button>
          )}
          {n.type === 'MERGE_APPROVED' && n.data.merged_tree_id && (
            <button
              onClick={() => navigate(`/trees/${n.data.merged_tree_id}`)}
              className="mt-2 ml-3 text-xs font-medium text-brand-600 hover:underline"
            >
              {t('notif.openMergedTree')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function MaintenanceBanner() {
  const { t } = useTranslation();
  const isMaintenanceMode = useMaintenanceStore((s) => s.isMaintenanceMode);
  const setMaintenance    = useMaintenanceStore((s) => s.setMaintenance);
  const user              = useAuthStore((s) => s.user);
  const accessToken       = useAuthStore((s) => s.accessToken);
  const [disabling, setDisabling] = useState(false);

  if (!isMaintenanceMode || user?.appRole !== 'SUPER_ADMIN') return null;

  async function handleGoLive() {
    if (!accessToken) return;
    setDisabling(true);
    try {
      const res = await fetch(`${API_BASE}/site-settings/maintenance`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
        credentials: 'include',
        body: JSON.stringify({ maintenance_mode: false }),
      });
      if (res.ok) {
        setMaintenance(false, '');
      }
    } catch { /* ignore */ }
    finally { setDisabling(false); }
  }

  return (
    <div className="bg-amber-500 text-white text-sm font-medium py-1.5 px-4 flex items-center justify-center gap-3">
      <span>{t('maintenance.banner')}</span>
      <button
        onClick={handleGoLive}
        disabled={disabling}
        className="px-3 py-0.5 bg-white text-amber-600 text-xs font-semibold rounded-full hover:bg-amber-50 disabled:opacity-50 transition-colors"
      >
        {disabling ? t('maintenance.disabling') : t('maintenance.goLive')}
      </button>
      <a
        href="/admin"
        className="px-3 py-0.5 border border-white/60 text-white text-xs font-semibold rounded-full hover:bg-white/10 transition-colors"
      >
        {t('maintenance.siteSettings')}
      </a>
    </div>
  );
}

export default function AppShell() {
  const navigate     = useNavigate();
  const user         = useAuthStore((s) => s.user);
  const logout       = useAuthStore((s) => s.logout);
  const accessToken  = useAuthStore((s) => s.accessToken);
  const [loggingOut,   setLoggingOut]   = useState(false);
  const [sidebarOpen,  setSidebarOpen]  = useState(false);
  const portalTheme  = usePortalThemeStore((s) => s.theme);

  const [notifOpen,     setNotifOpen]     = useState(false);
  const [unreadCount,   setUnreadCount]   = useState(0);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [notifLoading,  setNotifLoading]  = useState(false);
  const bellRef = useRef<HTMLDivElement>(null);

  // Show a one-time welcome popup for new verified users
  const [showWelcome, setShowWelcome] = useState(false);
  useEffect(() => {
    if (!user?.id || !user.isEmailVerified) return;
    const key = `welcome_seen_${user.id}`;
    if (!localStorage.getItem(key)) setShowWelcome(true);
  }, [user?.id, user?.isEmailVerified]);

  function dismissWelcome() {
    if (user?.id) localStorage.setItem(`welcome_seen_${user.id}`, '1');
    setShowWelcome(false);
  }

  // Inject portal CSS custom properties onto <html> whenever theme changes
  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty('--portal-main-bg',        portalTheme.mainBg);
    root.style.setProperty('--portal-sidebar-bg',     portalTheme.sidebarBg);
    root.style.setProperty('--portal-sidebar-border', portalTheme.sidebarBorder);
    root.style.setProperty('--portal-nav-text',       portalTheme.navText);
    root.style.setProperty('--portal-nav-hover',      portalTheme.navHover);
    root.style.setProperty('--portal-nav-active-bg',  portalTheme.navActiveBg);
    root.style.setProperty('--portal-nav-active-text',portalTheme.navActiveText);
    root.style.setProperty('--portal-logo-text',      portalTheme.logoText);
    root.style.setProperty('--portal-card-bg',        portalTheme.cardBg);
    root.style.setProperty('--portal-text-primary',   portalTheme.textPrimary);
    root.style.setProperty('--portal-text-muted',     portalTheme.textMuted);
    root.style.setProperty('--portal-border',         portalTheme.sidebarBorder);
    document.body.style.setProperty('background', portalTheme.mainBg);
    return () => { document.body.style.removeProperty('background'); };
  }, [portalTheme]);

  // Lock body scroll while mobile sidebar is open
  useEffect(() => {
    document.body.style.overflow = sidebarOpen ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [sidebarOpen]);

  // Register service worker + subscribe to Web Push
  useEffect(() => {
    if (!accessToken || !('serviceWorker' in navigator) || !('PushManager' in window)) return;
    (async () => {
      try {
        const reg = await navigator.serviceWorker.register('/sw.js');
        // Fetch VAPID public key
        const keyRes = await fetch(`${API_BASE}/push/vapid-public-key`);
        if (!keyRes.ok) return;
        const { vapid_public_key } = await keyRes.json();
        if (!vapid_public_key) return;

        // Convert base64url to Uint8Array
        const base64 = vapid_public_key.replace(/-/g, '+').replace(/_/g, '/');
        const raw = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));

        const existing = await reg.pushManager.getSubscription();
        const sub = existing ?? await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: raw,
        });

        const json = sub.toJSON();
        await fetch(`${API_BASE}/push/subscribe`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
          credentials: 'include',
          body: JSON.stringify({
            endpoint: sub.endpoint,
            p256dh: json.keys?.p256dh ?? '',
            auth: json.keys?.auth ?? '',
          }),
        });
      } catch (_) {
        // Push not supported or permission denied — silent fail
      }
    })();
  }, [accessToken]);

  // ── Toast notification system ──────────────────────────────────────────
  interface ToastNotif { id: string; title: string; body: string | null; type: string; treeId?: string; }
  const [toasts, setToasts] = useState<ToastNotif[]>([]);
  const prevCountRef = useRef(-1);

  function dismissToast(id: string) {
    setToasts((p) => p.filter((t) => t.id !== id));
  }

  function pushToast(t: Omit<ToastNotif, 'id'>) {
    const id = Math.random().toString(36).slice(2);
    setToasts((p) => [...p.slice(-2), { ...t, id }]);
    setTimeout(() => dismissToast(id), 6000);
  }

  // Poll every 10 s; show toast when new notifications arrive
  useEffect(() => {
    if (!accessToken) return;
    const fetchCount = async () => {
      try {
        const res = await fetch(`${API_BASE}/notifications/unread-count`, {
          headers: { Authorization: `Bearer ${accessToken}` },
          credentials: 'include',
        });
        if (!res.ok) return;
        const d = await res.json();
        const newCount: number = d.count ?? 0;
        setUnreadCount(newCount);

        // Show toast when count increases (skip the very first fetch)
        if (prevCountRef.current !== -1 && newCount > prevCountRef.current) {
          try {
            const nr = await fetch(`${API_BASE}/notifications?limit=1`, {
              headers: { Authorization: `Bearer ${accessToken}` },
              credentials: 'include',
            });
            if (nr.ok) {
              const items = await nr.json();
              if (items.length > 0) {
                pushToast({
                  title: items[0].title,
                  body: items[0].body,
                  type: items[0].type,
                  treeId: items[0].data?.tree_id,
                });
              }
            }
          } catch {}
        }
        prevCountRef.current = newCount;
      } catch {}
    };
    fetchCount();
    const interval = setInterval(fetchCount, 10_000);
    return () => clearInterval(interval);
  }, [accessToken]);

  // Close notification panel on outside click
  useEffect(() => {
    if (!notifOpen) return;
    function handleClick(e: MouseEvent) {
      if (bellRef.current && !bellRef.current.contains(e.target as Node)) {
        setNotifOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [notifOpen]);

  async function openNotifications() {
    if (notifOpen) { setNotifOpen(false); return; }
    setNotifOpen(true);
    setNotifLoading(true);
    try {
      const res = await fetch(`${API_BASE}/notifications`, {
        headers: { Authorization: `Bearer ${accessToken}` },
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        setNotifications(data);
        // Mark all as read
        if (unreadCount > 0) {
          await fetch(`${API_BASE}/notifications/read-all`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${accessToken}` },
            credentials: 'include',
          });
          setUnreadCount(0);
        }
      }
    } finally {
      setNotifLoading(false);
    }
  }

  const { t } = useTranslation();

  const bellButton = (
    <div ref={bellRef} className="relative">
      <button
        onClick={openNotifications}
        className="relative p-1.5 rounded-lg hover:bg-black/10 transition-colors"
        style={{ color: 'var(--portal-logo-text)' }}
        aria-label="Notifications"
      >
        {/* Bell SVG */}
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 2a5 5 0 0 1 5 5c0 3 1 4 1.5 5h-13C3 11 4 10 4 7a5 5 0 0 1 5-5z" />
          <path d="M7.5 15a1.5 1.5 0 0 0 3 0" />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-0.5 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center leading-none">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {/* Notification dropdown panel */}
      {notifOpen && (
        <div className="absolute left-0 top-full mt-1 w-80 bg-white rounded-xl shadow-xl border border-gray-200 z-[200] overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <span className="text-sm font-semibold text-gray-900">{t('nav.notifications')}</span>
            {notifications.some(n => !n.is_read) && (
              <button
                onClick={async () => {
                  await fetch(`${API_BASE}/notifications/read-all`, {
                    method: 'POST',
                    headers: { Authorization: `Bearer ${accessToken}` },
                    credentials: 'include',
                  });
                  setUnreadCount(0);
                  setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
                }}
                className="text-xs text-brand-600 hover:underline"
              >
                {t('nav.markAllRead')}
              </button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto divide-y divide-gray-50">
            {notifLoading ? (
              <div className="flex justify-center py-8">
                <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : notifications.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-8">{t('nav.noNotificationsYet')}</p>
            ) : (
              notifications.map((n) => (
                <NotificationItem
                  key={n.id}
                  n={n}
                  accessToken={accessToken}
                  apiBase={API_BASE}
                  onUpdate={(id, patch) =>
                    setNotifications((prev) => prev.map((x) => (x.id === id ? { ...x, ...patch } : x)))
                  }
                  onRemove={(id) => {
                    setNotifications((prev) => {
                      const removed = prev.find((x) => x.id === id);
                      if (removed && !removed.is_read) {
                        setUnreadCount((c) => Math.max(0, c - 1));
                      }
                      return prev.filter((x) => x.id !== id);
                    });
                  }}
                />
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );

  const isElevated = user?.appRole === 'ADMIN' || user?.appRole === 'AUDITOR' || user?.appRole === 'SUPER_ADMIN';
  const isAdmin    = user?.appRole === 'ADMIN' || user?.appRole === 'SUPER_ADMIN';

  const nav = [
    { to: '/dashboard', label: t('nav.dashboard') },
    { to: '/search',    label: t('nav.search') },
    { to: '/discover',  label: t('nav.discover') },
    { to: '/reports',   label: t('nav.reports') },
    ...(isElevated ? [{ to: '/activity', label: t('nav.activity') }] : []),
    ...(isAdmin    ? [{ to: '/admin',    label: t('nav.adminDashboard') }] : []),
    { to: '/settings',  label: t('nav.settings') },
  ];

  const sidebarContent = (
    <>
      {/* Logo row */}
      <div
        className="h-14 flex items-center justify-between px-4 border-b shrink-0"
        style={{ borderColor: 'var(--portal-sidebar-border)' }}
      >
        <div className="flex items-center gap-2">
          <span className="text-xl leading-none">🌳</span>
          <span className="font-bold text-lg" style={{ color: 'var(--portal-logo-text)' }}>
            OurFamRoots
          </span>
          {/* Bell — shown on desktop, hidden on mobile (mobile has its own) */}
          <div className="hidden md:block">
            {(unreadCount > 0 || notifOpen) && bellButton}
          </div>
        </div>
        {/* Close button — mobile only */}
        <button
          className="md:hidden -mr-1 p-1.5 rounded-lg hover:bg-black/10 transition-colors"
          onClick={() => setSidebarOpen(false)}
          aria-label="Close menu"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M3 3l10 10M13 3L3 13" />
          </svg>
        </button>
      </div>

      {/* Nav links */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        {nav.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) => `portal-nav-link${isActive ? ' active' : ''}`}
          >
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer: avatar + name/email + sign out */}
      <div className="p-3 border-t shrink-0" style={{ borderColor: 'var(--portal-sidebar-border)' }}>
        <div className="flex items-center gap-2.5 mb-2">
          <UserAvatar
            avatarUrl={user?.avatarUrl}
            displayName={user?.displayName}
            email={user?.email}
            size="sm"
          />
          <div className="min-w-0 flex-1">
            {user?.displayName && user.displayName !== user.email && (
              <p className="text-xs font-medium truncate" style={{ color: 'var(--portal-nav-text)' }}>
                {user.displayName}
              </p>
            )}
            <p className="text-[11px] truncate" style={{ color: 'var(--portal-nav-text)', opacity: 0.7 }}>
              {user?.email}
            </p>
          </div>
        </div>
        <button
          disabled={loggingOut}
          onClick={async () => {
            setLoggingOut(true);
            try {
              await fetch(`${API_BASE}/auth/logout`, {
                method: 'POST',
                credentials: 'include',
                headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
              });
            } finally {
              logout();
              window.location.href = '/';
            }
          }}
          className="w-full text-left text-xs px-2 py-1 rounded disabled:opacity-50 hover:underline"
          style={{ color: 'var(--portal-nav-text)' }}
        >
          {loggingOut ? t('nav.signingOut') : t('nav.signOut')}
        </button>
      </div>
    </>
  );

  return (
    <div className="min-h-screen flex">

      {/* ── Mobile overlay backdrop ── */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40 md:hidden"
          aria-hidden="true"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ── Sidebar ── */}
      {/* On mobile: fixed overlay, slides in from left.  On md+: static flex column. */}
      <aside
        className={[
          'fixed inset-y-0 left-0 z-50 w-64 flex flex-col border-r',
          'transition-transform duration-200 ease-in-out',
          'md:static md:w-56 md:translate-x-0 md:shrink-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full',
        ].join(' ')}
        style={{ background: 'var(--portal-sidebar-bg)', borderColor: 'var(--portal-sidebar-border)' }}
      >
        {sidebarContent}
      </aside>

      {/* ── Main content column ── */}
      <div className="flex-1 flex flex-col min-w-0">

        {/* Mobile-only top bar */}
        <div
          className="md:hidden h-14 flex items-center px-4 border-b shrink-0"
          style={{
            background:   'var(--portal-sidebar-bg)',
            borderColor:  'var(--portal-sidebar-border)',
          }}
        >
          <button
            className="p-1.5 -ml-1 rounded-lg hover:bg-black/10 transition-colors"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open menu"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
              <path d="M3 5h14M3 10h14M3 15h14" />
            </svg>
          </button>
          <span className="text-xl leading-none ml-3">🌳</span>
          <span className="font-bold text-base ml-1" style={{ color: 'var(--portal-logo-text)' }}>
            OurFamRoots
          </span>
          {unreadCount > 0 && <div className="ml-1">{bellButton}</div>}
        </div>

        {/* Page content */}
        <main className="flex-1 flex flex-col overflow-auto" style={{ background: 'var(--portal-main-bg)' }}>
          <MaintenanceBanner />
          <div className="flex-1">
            <Outlet />
          </div>
          <Footer />
        </main>
      </div>

      {/* ── In-app toast notifications ── */}
      {toasts.length > 0 && (
        <div className="fixed bottom-4 right-4 z-[500] flex flex-col gap-2 items-end pointer-events-none">
          {toasts.map((t) => (
            <div
              key={t.id}
              className="pointer-events-auto w-80 bg-white rounded-xl shadow-2xl border border-gray-200 p-4 flex items-start gap-3"
              style={{ animation: 'slideInRight 0.25s ease-out' }}
            >
              <div className="w-8 h-8 rounded-full bg-brand-50 flex items-center justify-center shrink-0 mt-0.5">
                <svg width="16" height="16" viewBox="0 0 18 18" fill="none" stroke="#6366f1" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 2a5 5 0 0 1 5 5c0 3 1 4 1.5 5h-13C3 11 4 10 4 7a5 5 0 0 1 5-5z" />
                  <path d="M7.5 15a1.5 1.5 0 0 0 3 0" />
                </svg>
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-gray-900 leading-snug">{t.title}</p>
                {t.body && <p className="text-xs text-gray-500 mt-0.5 leading-snug">{t.body}</p>}
                {t.treeId && (
                  <button
                    onClick={() => { navigate(`/trees/${t.treeId}`); dismissToast(t.id); }}
                    className="text-xs font-medium text-brand-600 hover:underline mt-1"
                  >
                    View tree →
                  </button>
                )}
              </div>
              <button
                onClick={() => dismissToast(t.id)}
                className="text-gray-300 hover:text-gray-500 text-lg leading-none shrink-0 -mt-0.5"
                aria-label="Dismiss"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {/* ── Welcome popup (first login only) ── */}
      {showWelcome && (
        <div className="fixed inset-0 z-[600] flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8 flex flex-col items-center text-center">
            <div className="w-16 h-16 rounded-full bg-brand-100 flex items-center justify-center mb-5">
              <svg className="w-8 h-8 text-brand-600" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">{t('welcome.title')}</h2>
            <p className="text-gray-500 text-sm leading-relaxed mb-2">
              {t('welcome.body')}
            </p>
            <p className="text-gray-500 text-sm leading-relaxed mb-6"
              dangerouslySetInnerHTML={{ __html: t('welcome.helpHint') }} />
            <div className="flex flex-col sm:flex-row gap-3 w-full">
              <button
                onClick={() => { dismissWelcome(); navigate('/help'); }}
                className="flex-1 px-4 py-2.5 bg-brand-500 text-white text-sm font-semibold rounded-xl hover:bg-brand-600 transition-colors"
              >
                {t('welcome.goToHelp')}
              </button>
              <button
                onClick={dismissWelcome}
                className="flex-1 px-4 py-2.5 bg-gray-100 text-gray-700 text-sm font-semibold rounded-xl hover:bg-gray-200 transition-colors"
              >
                {t('welcome.explore')}
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes slideInRight {
          from { opacity: 0; transform: translateX(20px); }
          to   { opacity: 1; transform: translateX(0); }
        }
      `}</style>
    </div>
  );
}
