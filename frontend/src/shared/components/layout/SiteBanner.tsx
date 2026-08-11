/**
 * SiteBanner — site-wide announcement banner, visible to every user
 * (including logged-out visitors), toggled by a Super Admin from
 * Admin Dashboard → Site Settings, optionally time-bounded.
 *
 * Rendered once at the app root (main.tsx), above <AppRouter/>, so it
 * covers every route — including ones that don't use AppShell (login,
 * landing, public pages, and the full-screen tree canvas).
 *
 * Independent of MaintenanceBanner (AppShell.tsx), which is a Super-Admin-only
 * reminder that maintenance mode (a hard, blocking kill-switch) was left on —
 * this banner is purely informational and never blocks the site.
 */
import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useBannerStore, checkBannerStatus } from '@store/banner.store';

const RECHECK_INTERVAL_MS = 60_000;

// Used whenever no custom color is configured (banner_bg_color/banner_text_color
// are null) — also imported by BannerPanel.tsx to show the true default in the
// admin color pickers rather than leaving them looking unset.
export const DEFAULT_BANNER_BG_COLOR = '#4f46e5';
export const DEFAULT_BANNER_TEXT_COLOR = '#ffffff';

export function SiteBanner() {
  const { t } = useTranslation();
  const active = useBannerStore((s) => s.active);
  const message = useBannerStore((s) => s.message);
  const bgColor = useBannerStore((s) => s.bgColor) ?? DEFAULT_BANNER_BG_COLOR;
  const textColor = useBannerStore((s) => s.textColor) ?? DEFAULT_BANNER_TEXT_COLOR;
  const rootRef = useRef<HTMLDivElement>(null);
  // In-memory only, deliberately not persisted (no sessionStorage/localStorage):
  // dismissing is meant to be a "not right now" for this page load, not
  // "never show me this again" — it resets on the next reload/visit, and a
  // changed message (e.g. admin edits it, or the 60s re-check picks up a
  // different scheduled banner) reappears immediately even without a reload.
  const [dismissedMessage, setDismissedMessage] = useState<string | null>(null);

  // Time-bounded by design — a boot-only check (like maintenance mode's)
  // would leave a stale banner showing/hidden until the user reloads,
  // defeating "for a specific time." Re-check periodically instead.
  useEffect(() => {
    const id = setInterval(() => { checkBannerStatus(); }, RECHECK_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  const visible = active && !!message && message !== dismissedMessage;

  // Publish our rendered height as a CSS variable so full-bleed pages
  // (fixed inset-0 roots, e.g. the tree canvas) can offset themselves —
  // see FamilyTreePage.tsx / DiscoverTreePage.tsx.
  useEffect(() => {
    if (!visible) {
      document.documentElement.style.setProperty('--site-banner-height', '0px');
      return;
    }
    const el = rootRef.current;
    if (!el) return;
    const observer = new ResizeObserver(() => {
      document.documentElement.style.setProperty('--site-banner-height', `${el.offsetHeight}px`);
    });
    observer.observe(el);
    document.documentElement.style.setProperty('--site-banner-height', `${el.offsetHeight}px`);
    return () => {
      observer.disconnect();
      document.documentElement.style.setProperty('--site-banner-height', '0px');
    };
  }, [visible]);

  if (!visible) return null;

  function handleDismiss() {
    setDismissedMessage(message);
  }

  return (
    <div
      ref={rootRef}
      style={{ background: bgColor, color: textColor }}
      className="text-sm py-2 px-4 flex items-center justify-center gap-3 relative"
    >
      <span className="text-center whitespace-pre-line">{message}</span>
      <button
        type="button"
        onClick={handleDismiss}
        aria-label={t('siteBanner.dismiss')}
        style={{ color: textColor }}
        className="absolute right-2 top-1/2 -translate-y-1/2 w-6 h-6 flex items-center justify-center rounded-full opacity-70 hover:opacity-100 transition-opacity"
      >
        ✕
      </button>
    </div>
  );
}
