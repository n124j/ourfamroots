/**
 * SearchResultList — full results page for name searches.
 * Reads ?q from the URL, supports filter panel, pagination.
 */
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import { useNameSearch } from '../useSearch';
import type { PersonHit, SearchFilters } from '../types';

interface Props {
  treeId?: string;
}

export function SearchResultList({ treeId }: Props) {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();

  const q       = searchParams.get('q') ?? '';
  const page    = parseInt(searchParams.get('page') ?? '1', 10);
  const limit   = 20;
  const offset  = (page - 1) * limit;

  const [filters, setFilters] = useState<SearchFilters>({
    sort: 'relevance',
    fuzzy: true,
  });

  const { data, isFetching, isError } = useNameSearch(q, { ...filters }, treeId);

  const totalPages = data ? Math.ceil(data.total / limit) : 0;

  if (!q) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-gray-400">
        <SearchEmptyIcon />
        <p className="text-sm">{t('searchPage.enterName')}</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">
          {isFetching ? t('searchPage.searching') : t('searchPage.resultsFor', { count: data?.total ?? 0, query: q })}
          {data && (
            <span className="ml-2 text-xs font-normal text-gray-400">
              ({data.took_ms} ms)
            </span>
          )}
        </h2>

        {/* Sort */}
        <select
          value={filters.sort}
          onChange={(e) => setFilters((f) => ({ ...f, sort: e.target.value as SearchFilters['sort'] }))}
          className="rounded border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500"
        >
          <option value="relevance">{t('searchPage.mostRelevant')}</option>
          <option value="name">{t('searchPage.nameAZ')}</option>
          <option value="birth_year">{t('searchPage.birthYear')}</option>
          <option value="updated_at">{t('searchPage.recentlyUpdated')}</option>
        </select>
      </div>

      {/* Filter bar */}
      <FilterBar filters={filters} onChange={setFilters} />

      {/* Results */}
      {isError && (
        <p className="text-sm text-red-500">Search failed. Please try again.</p>
      )}

      {data?.hits.length === 0 && !isFetching && (
        <div className="rounded-lg border border-dashed border-gray-300 py-12 text-center">
          <p className="text-sm text-gray-500">{t('searchPage.noMatchingPeople')} "{q}".</p>
          {!filters.fuzzy && (
            <button
              className="mt-2 text-sm text-indigo-600 hover:underline"
              onClick={() => setFilters((f) => ({ ...f, fuzzy: true }))}
            >
              Try fuzzy matching
            </button>
          )}
        </div>
      )}

      <ul className="divide-y divide-gray-100 rounded-xl border border-gray-200 bg-white shadow-sm">
        {data?.hits.map((hit) => (
          <ResultItem
            key={hit.person_id}
            hit={hit}
            onClick={() => navigate(
              `/trees/${hit.tree_id}/persons/${hit.person_id}`,
              { state: { from: 'search', searchUrl: location.pathname + location.search } },
            )}
          />
        ))}
      </ul>

      {/* Pagination */}
      {totalPages > 1 && (
        <Pagination
          current={page}
          total={totalPages}
          onChange={(p) => setSearchParams({ q, page: String(p) })}
        />
      )}
    </div>
  );
}

// ── Result item ────────────────────────────────────────────────────────────────

function ResultItem({ hit, onClick }: { hit: PersonHit; onClick: () => void }) {
  const fullName = [hit.given_name, hit.surname].filter(Boolean).join(' ') || 'Unknown';
  const dates    = formatLifespan(hit);

  return (
    <li>
      <button
        onClick={onClick}
        className="flex w-full items-start gap-4 px-4 py-3 text-left hover:bg-gray-50 transition-colors"
      >
        <Avatar name={fullName} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-gray-900">{fullName}</span>
            {hit.maiden_name && (
              <span className="text-xs text-gray-500">née {hit.maiden_name}</span>
            )}
          </div>
          <p className="mt-0.5 text-sm text-gray-500">
            {[dates, hit.birth_place].filter(Boolean).join(' · ')}
          </p>
        </div>
        <span className="flex-shrink-0 text-xs text-gray-300">
          {Math.round(hit.score * 100)}%
        </span>
      </button>
    </li>
  );
}

function Avatar({ name }: { name: string }) {
  const initials = name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase();
  return (
    <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-indigo-100 text-sm font-semibold text-indigo-700">
      {initials}
    </div>
  );
}

function formatLifespan(hit: PersonHit): string {
  const b = hit.birth_year;
  const d = hit.death_year;
  if (!b && !d) return '';
  if (hit.is_living) return `b. ${b ?? '?'}`;
  return `${b ?? '?'} – ${d ?? '?'}`;
}

// ── Filter bar ─────────────────────────────────────────────────────────────────

function FilterBar({ filters, onChange }: { filters: SearchFilters; onChange: (f: SearchFilters) => void }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <label className="flex items-center gap-1.5 text-sm text-gray-600">
        <input
          type="checkbox"
          checked={filters.fuzzy ?? true}
          onChange={(e) => onChange({ ...filters, fuzzy: e.target.checked })}
          className="rounded border-gray-300 text-indigo-600"
        />
        Fuzzy match
      </label>
    </div>
  );
}

// ── Pagination ─────────────────────────────────────────────────────────────────

function Pagination({
  current,
  total,
  onChange,
}: {
  current: number;
  total: number;
  onChange: (p: number) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center justify-center gap-2">
      <button
        onClick={() => onChange(current - 1)}
        disabled={current === 1}
        className="rounded border px-3 py-1 text-sm disabled:opacity-40 hover:bg-gray-50"
      >
        {t('common.previous')}
      </button>
      <span className="text-sm text-gray-600">
        Page {current} of {total}
      </span>
      <button
        onClick={() => onChange(current + 1)}
        disabled={current === total}
        className="rounded border px-3 py-1 text-sm disabled:opacity-40 hover:bg-gray-50"
      >
        {t('common.next')}
      </button>
    </div>
  );
}

function SearchEmptyIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  );
}
