/**
 * BannerPanel — Site Settings admin control for the site-wide announcement
 * banner (see SiteBanner.tsx for the user-facing display). Modeled directly
 * on MaintenancePanel's fetch-on-mount/save pattern, in AdminPage.tsx, with
 * the addition of an optional start/end schedule.
 */
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { DEFAULT_BANNER_BG_COLOR, DEFAULT_BANNER_TEXT_COLOR } from '@shared/components/layout/SiteBanner';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

type BannerStatus = 'off' | 'scheduled' | 'active' | 'expired';

function computeStatus(enabled: boolean, startsAt: string, endsAt: string): BannerStatus {
  if (!enabled) return 'off';
  const now = new Date();
  if (startsAt && now < new Date(startsAt)) return 'scheduled';
  if (endsAt && now >= new Date(endsAt)) return 'expired';
  return 'active';
}

const STATUS_STYLE: Record<BannerStatus, string> = {
  off: 'bg-gray-100 text-gray-600',
  scheduled: 'bg-blue-100 text-blue-700',
  active: 'bg-green-100 text-green-700',
  expired: 'bg-amber-100 text-amber-700',
};

/** datetime-local input value ("YYYY-MM-DDTHH:mm", local time) <-> stored UTC ISO string. */
function isoToLocalInput(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function localInputToIso(local: string): string | null {
  if (!local) return null;
  const d = new Date(local);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

export function BannerPanel({ token }: { token: string | null }) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [message, setMessage] = useState('');
  const [startsAt, setStartsAt] = useState('');
  const [endsAt, setEndsAt] = useState('');
  const [bgColor, setBgColor] = useState(DEFAULT_BANNER_BG_COLOR);
  const [textColor, setTextColor] = useState(DEFAULT_BANNER_TEXT_COLOR);
  const [feedback, setFeedback] = useState('');

  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/site-settings/banner/config`, {
          headers: { Authorization: `Bearer ${token}` },
          credentials: 'include',
        });
        if (res.ok) {
          const data = await res.json();
          setEnabled(data.banner_enabled);
          setMessage(data.banner_message ?? '');
          setStartsAt(isoToLocalInput(data.banner_starts_at));
          setEndsAt(isoToLocalInput(data.banner_ends_at));
          setBgColor(data.banner_bg_color ?? DEFAULT_BANNER_BG_COLOR);
          setTextColor(data.banner_text_color ?? DEFAULT_BANNER_TEXT_COLOR);
        }
      } catch { /* ignore */ }
      finally { setLoading(false); }
    })();
  }, [token]);

  async function handleSave() {
    if (!token) return;
    setSaving(true);
    setFeedback('');
    try {
      const res = await fetch(`${API_BASE}/site-settings/banner`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        credentials: 'include',
        body: JSON.stringify({
          banner_enabled: enabled,
          banner_message: message || undefined,
          banner_starts_at: localInputToIso(startsAt),
          banner_ends_at: localInputToIso(endsAt),
          banner_bg_color: bgColor,
          banner_text_color: textColor,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail ?? 'Failed to update');
      }
      const data = await res.json();
      setEnabled(data.banner_enabled);
      setMessage(data.banner_message ?? '');
      setStartsAt(isoToLocalInput(data.banner_starts_at));
      setEndsAt(isoToLocalInput(data.banner_ends_at));
      setBgColor(data.banner_bg_color ?? DEFAULT_BANNER_BG_COLOR);
      setTextColor(data.banner_text_color ?? DEFAULT_BANNER_TEXT_COLOR);
      setFeedback('Banner settings saved');
    } catch (err) {
      setFeedback((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function handleClearSchedule() {
    if (!token) return;
    setSaving(true);
    setFeedback('');
    try {
      const res = await fetch(`${API_BASE}/site-settings/banner`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        credentials: 'include',
        body: JSON.stringify({ clear_schedule: true }),
      });
      if (res.ok) {
        setStartsAt('');
        setEndsAt('');
      }
    } catch { /* ignore */ }
    finally { setSaving(false); }
  }

  async function handleResetColors() {
    if (!token) return;
    setSaving(true);
    setFeedback('');
    try {
      const res = await fetch(`${API_BASE}/site-settings/banner`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        credentials: 'include',
        body: JSON.stringify({ reset_colors: true }),
      });
      if (res.ok) {
        setBgColor(DEFAULT_BANNER_BG_COLOR);
        setTextColor(DEFAULT_BANNER_TEXT_COLOR);
      }
    } catch { /* ignore */ }
    finally { setSaving(false); }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const status = computeStatus(enabled, startsAt, endsAt);

  return (
    <div className="max-w-2xl mt-6">
      <div className="rounded-xl border p-6" style={{ background: 'var(--portal-card-bg)', borderColor: 'var(--portal-card-border)' }}>
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-lg font-semibold" style={{ color: 'var(--portal-text-primary)' }}>
            {t('adminPage.banner')}
          </h2>
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${STATUS_STYLE[status]}`}>
            {t(`adminPage.bannerStatus.${status}`)}
          </span>
        </div>
        <p className="text-sm mb-6" style={{ color: 'var(--portal-text-muted)' }}>
          {t('adminPage.bannerDesc')}
        </p>

        {/* Toggle */}
        <div className="flex items-center gap-3 mb-6">
          <button
            type="button"
            role="switch"
            aria-checked={enabled}
            onClick={() => setEnabled(!enabled)}
            className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
              enabled ? 'bg-indigo-600' : 'bg-gray-300'
            }`}
          >
            <span
              className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition-transform ${
                enabled ? 'translate-x-5' : 'translate-x-0'
              }`}
            />
          </button>
          <span className="text-sm font-medium" style={{ color: 'var(--portal-text-primary)' }}>
            {enabled ? (
              <span className="text-indigo-600 font-semibold">{t('adminPage.enabled')}</span>
            ) : (
              <span className="text-gray-500 font-semibold">{t('adminPage.disabled')}</span>
            )}
          </span>
        </div>

        {/* Message */}
        <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--portal-text-primary)' }}>
          {t('adminPage.bannerMessage')}
        </label>
        <textarea
          rows={3}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder={t('adminPage.bannerMessagePlaceholder')}
          maxLength={2000}
          className="w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 resize-y"
          style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)', borderColor: 'var(--portal-card-border)' }}
        />

        {/* Colors */}
        <div className="flex items-center justify-between mt-5 mb-1.5">
          <label className="block text-sm font-medium" style={{ color: 'var(--portal-text-primary)' }}>
            {t('adminPage.bannerColors')}
          </label>
          <button
            type="button"
            onClick={handleResetColors}
            disabled={saving}
            className="text-xs px-2 py-1 rounded border border-gray-300 hover:bg-gray-100 transition-colors disabled:opacity-50"
            style={{ color: 'var(--portal-text-muted)' }}
          >
            {t('adminPage.resetColors')}
          </button>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--portal-text-muted)' }}>{t('adminPage.bannerBgColor')}</label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={bgColor}
                onChange={(e) => setBgColor(e.target.value)}
                className="w-9 h-9 p-0.5 border rounded-lg cursor-pointer"
                style={{ borderColor: 'var(--portal-card-border)' }}
              />
              <input
                type="text"
                value={bgColor}
                onChange={(e) => setBgColor(e.target.value)}
                pattern="^#[0-9A-Fa-f]{6}$"
                className="w-full px-2 py-1.5 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono"
                style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)', borderColor: 'var(--portal-card-border)' }}
              />
            </div>
          </div>
          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--portal-text-muted)' }}>{t('adminPage.bannerTextColor')}</label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={textColor}
                onChange={(e) => setTextColor(e.target.value)}
                className="w-9 h-9 p-0.5 border rounded-lg cursor-pointer"
                style={{ borderColor: 'var(--portal-card-border)' }}
              />
              <input
                type="text"
                value={textColor}
                onChange={(e) => setTextColor(e.target.value)}
                pattern="^#[0-9A-Fa-f]{6}$"
                className="w-full px-2 py-1.5 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono"
                style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)', borderColor: 'var(--portal-card-border)' }}
              />
            </div>
          </div>
        </div>
        {/* Live preview */}
        <div
          className="mt-3 rounded-lg py-2 px-4 text-sm text-center"
          style={{ background: bgColor, color: textColor }}
        >
          {message || t('adminPage.bannerMessagePlaceholder')}
        </div>

        {/* Schedule */}
        <div className="flex items-center justify-between mt-5 mb-1.5">
          <label className="block text-sm font-medium" style={{ color: 'var(--portal-text-primary)' }}>
            {t('adminPage.bannerSchedule')}
          </label>
          <button
            type="button"
            onClick={handleClearSchedule}
            disabled={saving}
            className="text-xs px-2 py-1 rounded border border-gray-300 hover:bg-gray-100 transition-colors disabled:opacity-50"
            style={{ color: 'var(--portal-text-muted)' }}
          >
            {t('adminPage.clearSchedule')}
          </button>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--portal-text-muted)' }}>{t('adminPage.bannerStartsAt')}</label>
            <input
              type="datetime-local"
              value={startsAt}
              onChange={(e) => setStartsAt(e.target.value)}
              className="w-full px-2 py-1.5 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
              style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)', borderColor: 'var(--portal-card-border)' }}
            />
          </div>
          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--portal-text-muted)' }}>{t('adminPage.bannerEndsAt')}</label>
            <input
              type="datetime-local"
              value={endsAt}
              onChange={(e) => setEndsAt(e.target.value)}
              className="w-full px-2 py-1.5 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
              style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)', borderColor: 'var(--portal-card-border)' }}
            />
          </div>
        </div>
        <p className="text-xs mt-1 mb-4" style={{ color: 'var(--portal-text-muted)' }}>
          {t('adminPage.bannerScheduleDesc')}
        </p>

        {/* Save */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-50 transition-colors"
          >
            {saving ? t('adminPage.saving') : t('adminPage.saveSettings')}
          </button>
          {feedback && (
            <span className="text-sm font-medium" style={{ color: feedback.toLowerCase().includes('fail') ? '#ef4444' : '#22c55e' }}>
              {feedback}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
