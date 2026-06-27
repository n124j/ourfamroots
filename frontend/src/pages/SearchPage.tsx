import React, { useState, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { SEO } from '@shared/components/SEO';
import { useQuery } from '@tanstack/react-query';
import { get } from '@api/client';
import { SearchResultList } from '@features/search/components/SearchResultList';
import { RelationshipSearch } from '@features/search/components/RelationshipSearch';

type Tab = 'members' | 'trees' | 'relationship';

interface TreeSummary {
  id: string;
  name: string;
  description: string | null;
  role: string;
  person_count: number;
  member_count: number;
}

export default function SearchPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const urlQ = searchParams.get('q') ?? '';

  const [tab, setTab]               = useState<Tab>('members');
  const [treeFilter, setTreeFilter]   = useState('');
  const [selectedTreeId, setSelectedTreeId] = useState<string>('');

  const { data: trees, isLoading: treesLoading } = useQuery({
    queryKey: ['trees'],
    queryFn:  () => get<TreeSummary[]>('/trees'),
    staleTime: 60_000,
  });

  const filteredTrees = trees?.filter((tr) =>
    tr.name.toLowerCase().includes(treeFilter.toLowerCase())
  );

  const handleQueryChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setSearchParams(e.target.value ? { q: e.target.value } : {});
    },
    [setSearchParams],
  );

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      <SEO
        title="Search"
        description="Search across family members, trees, and relationships in OurFamRoots."
        noIndex
      />
      <h1 className="text-xl md:text-2xl font-bold mb-4 md:mb-6" style={{ color: 'var(--portal-text-primary)' }}>{t('searchPage.title')}</h1>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 mb-6">
        {([
          ['members',      t('searchPage.tabs.members')],
          ['trees',        t('searchPage.tabs.trees')],
          ['relationship', t('searchPage.tabs.relationship')],
        ] as [Tab, string][]).map(([tabKey, label]) => (
          <button
            key={tabKey}
            onClick={() => setTab(tabKey)}
            className={[
              'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
              tab === tabKey
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700',
            ].join(' ')}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Members tab */}
      {tab === 'members' && (
        <>
          <div className="flex flex-col sm:flex-row gap-2 mb-4 md:mb-6">
            <div className="relative flex-1">
              <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
              <input
                type="search"
                value={urlQ}
                onChange={handleQueryChange}
                placeholder={t('searchPage.searchPeople')}
                autoFocus
                autoComplete="off"
                className="w-full rounded-lg border border-gray-300 py-2.5 pl-9 pr-4 text-sm
                           shadow-sm placeholder-gray-400 focus:border-indigo-500 focus:outline-none
                           focus:ring-1 focus:ring-indigo-500"
                style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)' }}
              />
            </div>
            <select
              value={selectedTreeId}
              onChange={(e) => setSelectedTreeId(e.target.value)}
              className="rounded-lg border border-gray-300 px-3 py-2.5 text-sm shadow-sm
                         focus:border-indigo-500 focus:outline-none focus:ring-1
                         focus:ring-indigo-500 sm:min-w-[160px]"
              style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)' }}
            >
              <option value="">{t('searchPage.allTrees')}</option>
              {trees?.map((tr) => (
                <option key={tr.id} value={tr.id}>{tr.name}</option>
              ))}
            </select>
          </div>
          <SearchResultList treeId={selectedTreeId || undefined} />
        </>
      )}

      {/* Trees tab */}
      {tab === 'trees' && (
        <>
          <div className="relative mb-6">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
            <input
              type="search"
              value={treeFilter}
              onChange={(e) => setTreeFilter(e.target.value)}
              placeholder={t('searchPage.filterTrees')}
              autoFocus
              autoComplete="off"
              className="w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-9 pr-4 text-sm
                         shadow-sm placeholder-gray-400 focus:border-indigo-500 focus:outline-none
                         focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          {treesLoading && (
            <div className="flex justify-center py-12">
              <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {!treesLoading && filteredTrees?.length === 0 && (
            <div className="flex flex-col items-center gap-3 py-16 text-gray-400">
              <TreeIcon />
              <p className="text-sm">
                {treeFilter ? t('searchPage.noTreesMatching', { query: treeFilter }) : t('searchPage.noFamilyTreesYet')}
              </p>
            </div>
          )}

          {filteredTrees && filteredTrees.length > 0 && (
            <ul className="divide-y rounded-xl border shadow-sm" style={{ background: 'var(--portal-card-bg)', borderColor: 'var(--portal-border)' }}>
              {filteredTrees.map((tree) => (
                <li key={tree.id}>
                  <Link
                    to={`/trees/${tree.id}`}
                    className="flex items-center gap-4 px-5 py-4 hover:bg-gray-50 transition-colors"
                  >
                    <span className="text-2xl select-none">🌳</span>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate" style={{ color: 'var(--portal-text-primary)' }}>{tree.name}</p>
                      {tree.description && (
                        <p className="text-sm text-gray-500 mt-0.5 truncate">{tree.description}</p>
                      )}
                      <p className="text-xs text-gray-400 mt-0.5">
                        {tree.person_count} {tree.person_count === 1 ? t('searchPage.person') : t('common.people')}
                        {' · '}
                        {tree.member_count} {tree.member_count === 1 ? t('searchPage.collaborator') : t('searchPage.collaborators')}
                        {' · '}
                        {t('roles.' + tree.role, { defaultValue: tree.role })}
                      </p>
                    </div>
                    <ChevronIcon className="h-4 w-4 text-gray-400 flex-shrink-0" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {/* Relationship tab */}
      {tab === 'relationship' && (
        <RelationshipSearch trees={trees ?? []} />
      )}
    </div>
  );
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  );
}

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  );
}

function TreeIcon() {
  return (
    <svg className="h-12 w-12 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
        d="M12 3v18M5 8l7-5 7 5M5 16l7-5 7 5" />
    </svg>
  );
}
