import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { SEO } from '@shared/components/SEO';
import { useAuthStore } from '@store/auth.store';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

interface MatchingPerson {
  person_id: string;
  given_name: string | null;
  surname: string | null;
  birth_year: number | null;
}

interface DiscoveryResult {
  tree_id: string;
  tree_name: string;
  tree_description: string | null;
  owner_name: string;
  owner_id: string;
  person_count: number;
  matching_persons: MatchingPerson[];
  is_member: boolean;
  matched_on: string;
}

interface DiscoveryResponse {
  total: number;
  results: DiscoveryResult[];
  took_ms: number;
}

export default function DiscoverPage() {
  const { t } = useTranslation();
  const accessToken = useAuthStore((s) => s.accessToken);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<DiscoveryResult[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [searchError, setSearchError] = useState('');
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setResults([]);
      setTotal(0);
      setSearchError('');
      if (trimmed.length === 0) setSearched(false);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      setSearchError('');
      try {
        const res = await fetch(
          `${API_BASE}/discover/search?q=${encodeURIComponent(trimmed)}&limit=20`,
          {
            headers: { Authorization: `Bearer ${accessToken}` },
            credentials: 'include',
          },
        );
        if (res.ok) {
          const data: DiscoveryResponse = await res.json();
          setResults(data.results);
          setTotal(data.total);
        } else {
          const err = await res.json().catch(() => ({}));
          setSearchError((err as any).detail ?? `Search failed (${res.status})`);
          setResults([]);
          setTotal(0);
        }
      } catch (err) {
        setSearchError('Network error — could not reach the server');
        setResults([]);
        setTotal(0);
      } finally {
        setLoading(false);
        setSearched(true);
      }
    }, 300);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, accessToken]);

  return (
    <>
      <SEO title="Discover" description="Search for family members across public trees" />
      <div className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">{t('discoverPage.title')}</h1>
        <p className="text-sm text-gray-500 mb-6">
          {t('discoverPage.subtitle')}
        </p>

        {/* Search input */}
        <div className="relative mb-8">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
            width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor"
            strokeWidth="2" strokeLinecap="round"
          >
            <circle cx="8" cy="8" r="5.5" />
            <line x1="12" y1="12" x2="16" y2="16" />
          </svg>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('discoverPage.searchPlaceholder')}
            className="w-full pl-10 pr-4 py-3 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 bg-white"
            autoFocus
          />
          {loading && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              <div className="w-4 h-4 border-2 border-gray-300 border-t-brand-500 rounded-full animate-spin" />
            </div>
          )}
        </div>

        {/* Error */}
        {searchError && (
          <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
            {searchError}
          </div>
        )}

        {/* Results */}
        {!searched && !loading && !searchError && (
          <div className="text-center py-16 text-gray-400">
            <svg className="mx-auto mb-4" width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <circle cx="20" cy="20" r="14" />
              <line x1="30" y1="30" x2="42" y2="42" />
            </svg>
            <p className="text-sm">{t('discoverPage.emptyPrompt')}</p>
          </div>
        )}

        {searched && !loading && !searchError && results.length === 0 && (
          <div className="text-center py-16 text-gray-400">
            <p className="text-sm">{t('discoverPage.noResults', { query: query.trim() })}</p>
          </div>
        )}

        {results.length > 0 && (
          <div className="space-y-4">
            <p className="text-xs text-gray-500 mb-2">
              {t('discoverPage.treesFound', { count: total })}
            </p>
            {results.map((tree) => (
              <div
                key={tree.tree_id}
                className="border border-gray-200 rounded-xl p-5 hover:border-gray-300 transition-colors bg-white"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="text-base font-semibold text-gray-900 truncate">
                        {tree.tree_name}
                      </h3>
                      {tree.is_member && (
                        <span className="shrink-0 text-[10px] font-medium px-2 py-0.5 bg-green-50 text-green-700 rounded-full border border-green-200">
                          {t('discoverPage.memberBadge')}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500 mb-1">
                      {t('dashboard.by')} {tree.owner_name} &middot; {tree.person_count} {tree.person_count === 1 ? t('searchPage.person') : t('common.people')}
                    </p>

                    {/* Tree description (shown when tree matched by name/description) */}
                    {tree.tree_description && (tree.matched_on.includes('tree_name') || tree.matched_on.includes('tree_description')) && (
                      <p className="text-xs text-gray-400 mb-2 line-clamp-2">{tree.tree_description}</p>
                    )}

                    {/* Match source badges + matching persons */}
                    <div className="flex flex-wrap gap-2 mt-2">
                      {tree.matched_on.includes('tree_name') && (
                        <span className="inline-flex items-center gap-1 text-[10px] bg-gray-50 text-gray-500 px-2 py-0.5 rounded-full border border-gray-200">
                          {t('discoverPage.matchedTreeName')}
                        </span>
                      )}
                      {tree.matched_on.includes('tree_description') && !tree.matched_on.includes('tree_name') && (
                        <span className="inline-flex items-center gap-1 text-[10px] bg-gray-50 text-gray-500 px-2 py-0.5 rounded-full border border-gray-200">
                          {t('discoverPage.matchedDescription')}
                        </span>
                      )}
                      {tree.matching_persons.map((p) => (
                        <span
                          key={p.person_id}
                          className="inline-flex items-center gap-1 text-xs bg-brand-50 text-brand-700 px-2.5 py-1 rounded-lg border border-brand-100"
                        >
                          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <circle cx="6" cy="4" r="2.5" />
                            <path d="M1.5 11c0-2.5 2-4 4.5-4s4.5 1.5 4.5 4" />
                          </svg>
                          {[p.given_name, p.surname].filter(Boolean).join(' ')}
                          {p.birth_year ? ` (${p.birth_year})` : ''}
                        </span>
                      ))}
                    </div>
                  </div>

                  {tree.is_member ? (
                    <Link
                      to={`/trees/${tree.tree_id}`}
                      className="shrink-0 px-4 py-2 text-xs font-medium text-brand-600 border border-brand-200 rounded-lg hover:bg-brand-50 transition-colors"
                    >
                      {t('discoverPage.openTree')}
                    </Link>
                  ) : (
                    <Link
                      to={`/discover/trees/${tree.tree_id}`}
                      className="shrink-0 px-4 py-2 text-xs font-medium text-white bg-brand-500 rounded-lg hover:bg-brand-600 transition-colors"
                    >
                      {t('discoverPage.viewTree')}
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
