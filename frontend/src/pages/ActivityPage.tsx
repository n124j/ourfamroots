/**
 * ActivityPage — tenant-wide activity feed.
 * Visible to ADMIN and AUDITOR roles only.
 * Features: search, sort, filter, pagination, CSV export.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@store/auth.store';
import { SEO } from '@shared/components/SEO';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';
const PAGE_SIZE = 25;

// ── Types ──────────────────────────────────────────────────────────────────────

interface ActivityItem {
  id: string;
  event_source: 'audit' | 'login';
  actor_id: string | null;
  actor_display_name: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  entity_display_name: string | null;
  tree_id: string | null;
  tree_name: string | null;
  ip_address: string | null;
  occurred_at: string;
}

interface ActivityResponse {
  total: number;
  items: ActivityItem[];
  page: number;
  page_size: number;
  total_pages: number;
}

// ── Constants ──────────────────────────────────────────────────────────────────

const ACTION_OPTIONS = [
  { value: '', label: 'All actions' },
  // Auth
  { value: 'LOGIN', label: 'Login' },
  { value: 'LOGOUT', label: 'Logout' },
  { value: 'FAILED_LOGIN', label: 'Failed login' },
  // Admin — user management
  { value: 'ADMIN_CREATE', label: 'Admin: create user' },
  { value: 'ADMIN_VERIFY', label: 'Admin: verify user' },
  { value: 'ADMIN_UNVERIFY', label: 'Admin: unverify user' },
  { value: 'ADMIN_DEACTIVATE', label: 'Admin: deactivate user' },
  { value: 'ADMIN_ACTIVATE', label: 'Admin: activate user' },
  { value: 'ADMIN_UPDATE', label: 'Admin: update user' },
  // Admin — permission groups
  { value: 'PG_CREATE', label: 'Permission group: create' },
  { value: 'PG_UPDATE', label: 'Permission group: update' },
  { value: 'PG_DELETE', label: 'Permission group: delete' },
  { value: 'PG_ADD_TREE', label: 'Permission group: add tree' },
  { value: 'PG_REMOVE_TREE', label: 'Permission group: remove tree' },
  { value: 'PG_ADD_MEMBER', label: 'Permission group: add member' },
  { value: 'PG_REMOVE_MEMBER', label: 'Permission group: remove member' },
  // Broadcast
  { value: 'BROADCAST_SEND', label: 'Broadcast: send email' },
  { value: 'BROADCAST_DEL', label: 'Broadcast: delete log' },
  // Tree content
  { value: 'CREATE_PERSON', label: 'Create person' },
  { value: 'UPDATE_PERSON', label: 'Update person' },
  { value: 'DELETE_PERSON', label: 'Delete person' },
  { value: 'ADD_RELATIONSHIP', label: 'Add relationship' },
  { value: 'REMOVE_RELATIONSHIP', label: 'Remove relationship' },
  { value: 'INVITE_MEMBER', label: 'Invite member' },
  { value: 'REMOVE_MEMBER', label: 'Remove member' },
  { value: 'UPDATE_TREE', label: 'Update tree' },
  { value: 'DELETE_TREE', label: 'Delete tree' },
  { value: 'UPLOAD_MEDIA', label: 'Upload media' },
  { value: 'DELETE_MEDIA', label: 'Delete media' },
];

const ENTITY_OPTIONS = [
  { value: '', label: 'All types' },
  { value: 'LOGIN', label: 'Login' },
  { value: 'PERSON', label: 'Person' },
  { value: 'TREE', label: 'Tree' },
  { value: 'FAMILY_GROUP', label: 'Family group' },
  { value: 'MEMBER', label: 'Member' },
  { value: 'INVITATION', label: 'Invitation' },
  { value: 'MEDIA', label: 'Media' },
];

// ── Helpers ────────────────────────────────────────────────────────────────────

const ADMIN_ACTION_LABELS: Record<string, string> = {
  ADMIN_CREATE:     'Created user',
  ADMIN_VERIFY:     'Verified user',
  ADMIN_UNVERIFY:   'Unverified user',
  ADMIN_DEACTIVATE: 'Deactivated user',
  ADMIN_ACTIVATE:   'Activated user',
  ADMIN_UPDATE:     'Updated user',
  PG_CREATE:        'Created permission group',
  PG_UPDATE:        'Updated permission group',
  PG_DELETE:        'Deleted permission group',
  PG_ADD_TREE:      'Added tree to group',
  PG_REMOVE_TREE:   'Removed tree from group',
  PG_ADD_MEMBER:    'Added member to group',
  PG_REMOVE_MEMBER: 'Removed member from group',
  BROADCAST_SEND:   'Sent broadcast email',
  BROADCAST_DEL:    'Deleted broadcast log',
};

function actionBadge(action: string): string {
  if (action === 'LOGIN') return 'bg-green-100 text-green-800';
  if (action === 'LOGOUT') return 'bg-gray-100 text-gray-700';
  if (action === 'FAILED_LOGIN') return 'bg-red-100 text-red-800';
  if (action.startsWith('ADMIN_') || action.startsWith('PG_') || action.startsWith('BROADCAST_')) return 'bg-purple-100 text-purple-800';
  if (action.startsWith('CREATE') || action.startsWith('ADD') || action.startsWith('UPLOAD') || action.startsWith('INVITE'))
    return 'bg-blue-100 text-blue-800';
  if (action.startsWith('DELETE') || action.startsWith('REMOVE') || action === 'ADMIN_DEACTIVATE')
    return 'bg-red-100 text-red-800';
  if (action.startsWith('UPDATE') || action.startsWith('CHANGE'))
    return 'bg-amber-100 text-amber-800';
  return 'bg-gray-100 text-gray-700';
}

function formatAction(action: string): string {
  if (ADMIN_ACTION_LABELS[action]) return ADMIN_ACTION_LABELS[action];
  return action.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
}

function formatDate(iso: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function ActivityPage() {
  const { t } = useTranslation();
  const accessToken = useAuthStore((s) => s.accessToken);

  const [data, setData]         = useState<ActivityResponse | null>(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');

  const [page, setPage]         = useState(1);
  const [search, setSearch]     = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [action, setAction]     = useState('');
  const [entityType, setEntityType] = useState('');
  const [sort, setSort]         = useState<'desc' | 'asc'>('desc');
  const [exporting, setExporting] = useState(false);

  // Debounce search input
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 350);
    return () => clearTimeout(debounceRef.current);
  }, [search]);

  const fetchActivity = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(PAGE_SIZE),
        sort,
        ...(debouncedSearch ? { search: debouncedSearch } : {}),
        ...(action ? { action } : {}),
        ...(entityType ? { entity_type: entityType } : {}),
      });
      const res = await fetch(`${API_BASE}/activity?${params}`, {
        headers: { Authorization: `Bearer ${accessToken}` },
        credentials: 'include',
      });
      if (!res.ok) throw new Error('Failed to load activity');
      setData(await res.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [accessToken, page, debouncedSearch, action, entityType, sort]);

  useEffect(() => { fetchActivity(); }, [fetchActivity]);

  async function handleExport() {
    if (!accessToken) return;
    setExporting(true);
    try {
      const params = new URLSearchParams({
        sort,
        ...(debouncedSearch ? { search: debouncedSearch } : {}),
        ...(action ? { action } : {}),
        ...(entityType ? { entity_type: entityType } : {}),
      });
      const res = await fetch(`${API_BASE}/activity/export?${params}`, {
        headers: { Authorization: `Bearer ${accessToken}` },
        credentials: 'include',
      });
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `activity-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setExporting(false);
    }
  }

  function toggleSort() {
    setSort((s) => (s === 'desc' ? 'asc' : 'desc'));
    setPage(1);
  }

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto">
      <SEO
        title="Activity Log"
        description="View all actions and login events across your organisation's family trees."
        noIndex
      />
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 md:mb-6">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--portal-text-primary)' }}>{t('activityPage.title')}</h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--portal-text-muted)' }}>
            {t('activityPage.subtitle')}
          </p>
        </div>
        <button
          onClick={handleExport}
          disabled={exporting || loading}
          className="flex items-center gap-2 h-9 px-4 text-sm border border-gray-300 rounded-lg hover:opacity-80 disabled:opacity-50 transition-colors"
          style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)' }}
        >
          {exporting ? (
            <span className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
          ) : (
            <svg className="w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          )}
          {t('activityPage.exportCSV')}
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        {/* Search */}
        <div className="relative flex-1 min-w-48">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
            fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('activityPage.searchPlaceholder')}
            className="w-full h-9 pl-9 pr-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)' }}
          />
        </div>

        {/* Action filter */}
        <select
          value={action}
          onChange={(e) => { setAction(e.target.value); setPage(1); }}
          className="h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)' }}
        >
          {ACTION_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        {/* Entity type filter */}
        <select
          value={entityType}
          onChange={(e) => { setEntityType(e.target.value); setPage(1); }}
          className="h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)' }}
        >
          {ENTITY_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        {/* Sort toggle */}
        <button
          onClick={toggleSort}
          className="h-9 px-3 text-sm border border-gray-300 rounded-lg hover:opacity-80 flex items-center gap-1.5 transition-colors"
          style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)' }}
          title={sort === 'desc' ? t('activityPage.newestFirst') : t('activityPage.oldestFirst')}
        >
          <svg className={`w-4 h-4 text-gray-500 transition-transform ${sort === 'asc' ? 'rotate-180' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12" />
          </svg>
          {sort === 'desc' ? t('activityPage.newestFirst') : t('activityPage.oldestFirst')}
        </button>
      </div>

      {/* Stats bar */}
      {data && (
        <p className="text-xs text-gray-500 mb-3">
          {debouncedSearch || action || entityType
            ? t('activityPage.eventsMatching', { count: data.total })
            : t('activityPage.eventsTotal', { count: data.total })}
          {' · '}{t('activityPage.page')} {data.page} / {data.total_pages}
        </p>
      )}

      {/* Error */}
      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--portal-card-bg)', borderColor: 'var(--portal-border)' }}>
        {loading && !data ? (
          <div className="flex justify-center py-16">
            <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : data?.items.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <p className="text-sm">{t('activityPage.noActivity')}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b" style={{ background: 'var(--portal-main-bg)', borderColor: 'var(--portal-border)' }}>
                  <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider w-44" style={{ color: 'var(--portal-text-muted)' }}>
                    {t('activityPage.colWhen')}
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--portal-text-muted)' }}>
                    {t('activityPage.colActor')}
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--portal-text-muted)' }}>
                    {t('activityPage.colAction')}
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--portal-text-muted)' }}>
                    {t('activityPage.colOn')}
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--portal-text-muted)' }}>
                    {t('activityPage.colTree')}
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider w-32" style={{ color: 'var(--portal-text-muted)' }}>
                    {t('activityPage.colIP')}
                  </th>
                </tr>
              </thead>
              <tbody className={`divide-y divide-gray-50 ${loading ? 'opacity-50' : ''}`}>
                {data?.items.map((item) => (
                  <tr key={item.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                      {formatDate(item.occurred_at)}
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-medium text-gray-800">{item.actor_display_name || '—'}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${actionBadge(item.action)}`}>
                        {formatAction(item.action)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {item.entity_display_name ? (
                        <span>
                          <span className="text-xs text-gray-400 mr-1">{item.entity_type}</span>
                          {item.entity_display_name}
                        </span>
                      ) : item.entity_type ? (
                        <span className="text-xs text-gray-400">{item.entity_type}</span>
                      ) : '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-600 text-xs">
                      {item.tree_name ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-400 font-mono">
                      {item.ip_address ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {data && data.total_pages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1 || loading}
            className="h-8 px-3 text-sm border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50 transition-colors"
          >
            {t('common.previous')}
          </button>

          <div className="flex items-center gap-1">
            {Array.from({ length: Math.min(7, data.total_pages) }, (_, i) => {
              // Show pages around current page
              let p: number;
              const total = data.total_pages;
              if (total <= 7) {
                p = i + 1;
              } else if (page <= 4) {
                p = i + 1;
                if (i === 6) p = total;
                if (i === 5) p = -1; // ellipsis
              } else if (page >= total - 3) {
                p = i === 0 ? 1 : i === 1 ? -1 : total - 6 + i + 1;
              } else {
                const mid = [1, -1, page - 1, page, page + 1, -1, total];
                p = mid[i];
              }
              if (p === -1) return <span key={`e${i}`} className="text-gray-400 px-1">…</span>;
              return (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`w-8 h-8 text-sm rounded-lg transition-colors ${
                    p === page
                      ? 'bg-brand-500 text-white'
                      : 'border border-gray-300 hover:bg-gray-50 text-gray-700'
                  }`}
                >
                  {p}
                </button>
              );
            })}
          </div>

          <button
            onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
            disabled={page === data.total_pages || loading}
            className="h-8 px-3 text-sm border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50 transition-colors"
          >
            {t('common.next')}
          </button>
        </div>
      )}
    </div>
  );
}
