import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@store/auth.store';
import { SEO } from '@shared/components/SEO';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

type SortField = 'name' | 'role' | 'person_count' | 'member_count';
type SortDir   = 'asc' | 'desc';

interface TreeSummary {
  id: string;
  name: string;
  description: string | null;
  role: string;
  person_count: number;
  member_count: number;
}

const ROLE_ORDER: Record<string, number> = { OWNER: 0, ADMIN: 1, EDITOR: 2, VIEWER: 3 };
const PAGE_SIZES = [10, 20, 50] as const;
type PageSize = typeof PAGE_SIZES[number];

function pageRange(cur: number, total: number): (number | '…')[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages: (number | '…')[] = [1];
  if (cur > 3) pages.push('…');
  for (let p = Math.max(2, cur - 1); p <= Math.min(total - 1, cur + 1); p++) pages.push(p);
  if (cur < total - 2) pages.push('…');
  pages.push(total);
  return pages;
}

export default function ReportsPage() {
  const { t } = useTranslation();
  const accessToken = useAuthStore((s) => s.accessToken);
  const [trees,   setTrees]   = useState<TreeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState('');

  // Controls
  const [search,     setSearch]     = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [sortBy,     setSortBy]     = useState<SortField>('name');
  const [sortDir,    setSortDir]    = useState<SortDir>('asc');
  const [page,       setPage]       = useState(1);
  const [pageSize,   setPageSize]   = useState<PageSize>(10);

  useEffect(() => {
    if (!accessToken) return;
    fetch(`${API_BASE}/trees`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      credentials: 'include',
    })
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load data');
        return r.json();
      })
      .then((data) => { setTrees(data); setPage(1); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [accessToken]);

  // Summary stats always reflect the full dataset
  const totalPeople  = trees.reduce((s, tr) => s + tr.person_count, 0);
  const totalMembers = trees.reduce((s, tr) => s + tr.member_count, 0);

  // Filtered + sorted list (derived — no extra state)
  const filtered = useMemo(() => {
    let list = trees;
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (t) => t.name.toLowerCase().includes(q) || (t.description ?? '').toLowerCase().includes(q),
      );
    }
    if (roleFilter) list = list.filter((t) => t.role === roleFilter);

    return [...list].sort((a, b) => {
      let cmp = 0;
      if      (sortBy === 'name')         cmp = a.name.localeCompare(b.name);
      else if (sortBy === 'role')         cmp = (ROLE_ORDER[a.role] ?? 9) - (ROLE_ORDER[b.role] ?? 9);
      else if (sortBy === 'person_count') cmp = a.person_count - b.person_count;
      else if (sortBy === 'member_count') cmp = a.member_count - b.member_count;
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [trees, search, roleFilter, sortBy, sortDir]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage   = Math.min(page, totalPages);
  const visible    = filtered.slice((safePage - 1) * pageSize, safePage * pageSize);

  function toggleSort(field: SortField) {
    if (sortBy === field) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortBy(field); setSortDir('asc'); }
    setPage(1);
  }

  function clearFilters() { setSearch(''); setRoleFilter(''); setPage(1); }

  function SortIcon({ field }: { field: SortField }) {
    if (sortBy !== field)
      return <span className="ml-1 text-gray-300 text-xs">↕</span>;
    return <span className="ml-1 text-brand-500 text-xs">{sortDir === 'asc' ? '↑' : '↓'}</span>;
  }

  const hasActiveFilter = !!search.trim() || !!roleFilter;

  return (
    <div className="p-4 md:p-8 max-w-5xl mx-auto">
      <SEO
        title="Reports"
        description="View statistics and reports for your family trees on OurFamRoots."
        noIndex
      />
      <h1 className="text-xl md:text-2xl font-bold mb-1" style={{ color: 'var(--portal-text-primary)' }}>{t('reportsPage.title')}</h1>
      <p className="text-sm mb-6 md:mb-8" style={{ color: 'var(--portal-text-muted)' }}>{t('reportsPage.subtitle')}</p>

      {loading && (
        <div className="flex justify-center py-16">
          <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {error && (
        <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 mb-6">
          {error}
        </div>
      )}

      {!loading && !error && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6 md:mb-8">
            {[
              { label: t('reportsPage.familyTrees'),  value: trees.length,  icon: '🌳' },
              { label: t('reportsPage.totalPeople'),  value: totalPeople,   icon: '👤' },
              { label: t('reportsPage.collaborators'), value: totalMembers,  icon: '👥' },
            ].map(({ label, value, icon }) => (
              <div key={label} className="rounded-xl border p-5" style={{ background: 'var(--portal-card-bg)', borderColor: 'var(--portal-border)' }}>
                <div className="text-2xl mb-2">{icon}</div>
                <div className="text-2xl font-bold" style={{ color: 'var(--portal-text-primary)' }}>{value}</div>
                <div className="text-sm mt-0.5" style={{ color: 'var(--portal-text-muted)' }}>{label}</div>
              </div>
            ))}
          </div>

          {trees.length === 0 ? (
            <div className="text-center py-20 text-gray-400">
              <div className="text-5xl mb-4">📊</div>
              <p className="text-lg font-medium text-gray-600">{t('reportsPage.noDataYet')}</p>
              <p className="text-sm mt-1">{t('reportsPage.createTreeToSee')}</p>
            </div>
          ) : (
            <div>
              <h2 className="text-base font-semibold mb-3" style={{ color: 'var(--portal-text-primary)' }}>{t('reportsPage.treeBreakdown')}</h2>

              {/* ── Toolbar ── */}
              <div className="flex flex-col sm:flex-row gap-2 mb-3">
                {/* Search */}
                <div className="relative flex-1">
                  <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none"
                    fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <circle cx="11" cy="11" r="7" />
                    <path d="M21 21l-4.35-4.35" strokeLinecap="round" />
                  </svg>
                  <input
                    type="search"
                    placeholder={t('reportsPage.searchTrees')}
                    value={search}
                    onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                    className="w-full rounded-lg border border-gray-300 py-2 pl-9 pr-4 text-sm
                               shadow-sm placeholder-gray-400 focus:border-brand-500 focus:outline-none
                               focus:ring-1 focus:ring-brand-500"
                  style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)' }}
                  />
                </div>

                {/* Role filter */}
                <select
                  value={roleFilter}
                  onChange={(e) => { setRoleFilter(e.target.value); setPage(1); }}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm
                             focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)' }}
                >
                  <option value="">{t('reportsPage.allRoles')}</option>
                  <option value="OWNER">{t('roles.OWNER')}</option>
                  <option value="ADMIN">{t('roles.ADMIN')}</option>
                  <option value="EDITOR">{t('roles.EDITOR')}</option>
                  <option value="VIEWER">{t('roles.VIEWER')}</option>
                </select>

                {/* Page size */}
                <select
                  value={pageSize}
                  onChange={(e) => { setPageSize(Number(e.target.value) as PageSize); setPage(1); }}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm
                             focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)' }}
                >
                  {PAGE_SIZES.map((s) => (
                    <option key={s} value={s}>{t('reportsPage.perPage', { count: s })}</option>
                  ))}
                </select>
              </div>

              {/* Result count + clear */}
              <div className="flex items-center gap-3 mb-2 min-h-[1.25rem]">
                <p className="text-xs text-gray-400">
                  {hasActiveFilter
                    ? `${filtered.length} / ${trees.length} ${t('common.trees')}`
                    : `${trees.length} ${t('common.trees')}`}
                </p>
                {hasActiveFilter && (
                  <button onClick={clearFilters}
                    className="text-xs text-brand-600 hover:text-brand-700 hover:underline">
                    {t('reportsPage.clearFilters')}
                  </button>
                )}
              </div>

              {/* Table */}
              <div className="rounded-xl border overflow-hidden overflow-x-auto" style={{ background: 'var(--portal-card-bg)', borderColor: 'var(--portal-border)' }}>
                {filtered.length === 0 ? (
                  <div className="text-center py-12 text-gray-400">
                    <p className="text-sm">{t('reportsPage.noTreesMatch')}</p>
                    <button onClick={clearFilters}
                      className="mt-2 text-xs text-brand-600 hover:underline">
                      {t('reportsPage.clearFilters')}
                    </button>
                  </div>
                ) : (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b" style={{ background: 'var(--portal-main-bg)', borderColor: 'var(--portal-border)' }}>
                        <th className="text-left px-5 py-3 font-medium text-gray-600 whitespace-nowrap">
                          <button onClick={() => toggleSort('name')}
                            className="flex items-center gap-0.5 hover:opacity-80 transition-colors" style={{ color: 'var(--portal-text-muted)' }}>
                            {t('reportsPage.colTree')} <SortIcon field="name" />
                          </button>
                        </th>
                        <th className="text-left px-5 py-3 font-medium text-gray-600 whitespace-nowrap">
                          <button onClick={() => toggleSort('role')}
                            className="flex items-center gap-0.5 hover:opacity-80 transition-colors" style={{ color: 'var(--portal-text-muted)' }}>
                            {t('reportsPage.colRole')} <SortIcon field="role" />
                          </button>
                        </th>
                        <th className="text-right px-5 py-3 font-medium text-gray-600 whitespace-nowrap">
                          <button onClick={() => toggleSort('person_count')}
                            className="flex items-center gap-0.5 ml-auto hover:text-gray-900 transition-colors">
                            {t('reportsPage.colPeople')} <SortIcon field="person_count" />
                          </button>
                        </th>
                        <th className="text-right px-5 py-3 font-medium text-gray-600 whitespace-nowrap">
                          <button onClick={() => toggleSort('member_count')}
                            className="flex items-center gap-0.5 ml-auto hover:text-gray-900 transition-colors">
                            {t('reportsPage.colMembers')} <SortIcon field="member_count" />
                          </button>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {visible.map((tree, i) => (
                        <tr key={tree.id}
                          className={`hover:bg-gray-50/60 transition-colors${i < visible.length - 1 ? ' border-b border-gray-100' : ''}`}>
                          <td className="px-5 py-3">
                            <Link to={`/trees/${tree.id}`}
                              className="font-medium text-gray-900 hover:text-brand-600 transition-colors">
                              {tree.name}
                            </Link>
                            {tree.description && (
                              <p className="text-xs text-gray-400 mt-0.5 truncate max-w-xs">{tree.description}</p>
                            )}
                          </td>
                          <td className="px-5 py-3 text-gray-500 whitespace-nowrap">
                            {t('roles.' + tree.role)}
                          </td>
                          <td className="px-5 py-3 text-right font-semibold text-gray-900">{tree.person_count}</td>
                          <td className="px-5 py-3 text-right font-semibold text-gray-900">{tree.member_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex flex-col sm:flex-row items-center justify-between gap-3 mt-4 pt-4 border-t border-gray-100">
                  <p className="text-sm text-gray-500 order-2 sm:order-1">
                    {t('common.showing')} {(safePage - 1) * pageSize + 1}–{Math.min(safePage * pageSize, filtered.length)} {t('common.of')} {filtered.length}
                  </p>
                  <div className="flex items-center gap-1 order-1 sm:order-2">
                    <button
                      onClick={() => setPage((p) => p - 1)}
                      disabled={safePage === 1}
                      className="px-3 py-1.5 text-sm font-medium text-gray-600 rounded-lg hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    >
                      {t('common.prev')}
                    </button>
                    {pageRange(safePage, totalPages).map((p, i) =>
                      p === '…' ? (
                        <span key={`e${i}`} className="w-8 text-center text-gray-400 text-sm select-none">…</span>
                      ) : (
                        <button
                          key={p}
                          onClick={() => setPage(p as number)}
                          className={[
                            'w-8 h-8 text-sm font-medium rounded-lg transition-colors',
                            p === safePage
                              ? 'bg-brand-500 text-white'
                              : 'text-gray-600 hover:bg-gray-100',
                          ].join(' ')}
                        >
                          {p}
                        </button>
                      )
                    )}
                    <button
                      onClick={() => setPage((p) => p + 1)}
                      disabled={safePage === totalPages}
                      className="px-3 py-1.5 text-sm font-medium text-gray-600 rounded-lg hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    >
                      {t('common.next')}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
