/**
 * SearchBar — debounced global search input with an inline dropdown of results.
 * Used in the top navigation bar; pressing Enter navigates to the full results page.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useNameSearch } from '../useSearch';
import type { PersonHit } from '../types';

interface Props {
  treeId?: string;            // if set, search is scoped to this tree
  placeholder?: string;
  onSelect?: (hit: PersonHit) => void;
}

export function SearchBar({ treeId, placeholder, onSelect }: Props) {
  const { t } = useTranslation();
  const [query, setQuery]     = useState('');
  const [open, setOpen]       = useState(false);
  const [debounced, setDebounced] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  // Debounce
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), 300);
    return () => clearTimeout(t);
  }, [query]);

  const { data, isFetching } = useNameSearch(debounced, {}, treeId);

  const handleSelect = useCallback(
    (hit: PersonHit) => {
      setQuery('');
      setOpen(false);
      if (onSelect) {
        onSelect(hit);
      } else {
        navigate(`/trees/${hit.tree_id}/persons/${hit.person_id}`);
      }
    },
    [onSelect, navigate]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && debounced.trim().length >= 2) {
      setOpen(false);
      const base = treeId ? `/trees/${treeId}/search` : '/search';
      navigate(`${base}?q=${encodeURIComponent(debounced.trim())}`);
    }
    if (e.key === 'Escape') {
      setOpen(false);
      inputRef.current?.blur();
    }
  };

  return (
    <div className="relative w-full max-w-lg">
      <div className="relative">
        <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
        <input
          ref={inputRef}
          type="search"
          value={query}
          placeholder={placeholder ?? t('searchComponents.searchPeople')}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onKeyDown={handleKeyDown}
          className="w-full rounded-lg border border-gray-300 bg-white py-2 pl-9 pr-4 text-sm
                     shadow-sm placeholder-gray-400 focus:border-indigo-500 focus:outline-none
                     focus:ring-1 focus:ring-indigo-500"
          autoComplete="off"
        />
        {isFetching && (
          <SpinnerIcon className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 animate-spin" />
        )}
      </div>

      {/* Dropdown */}
      {open && debounced.length >= 2 && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-gray-200 bg-white py-1 shadow-lg">
          {!data || data.hits.length === 0 ? (
            <p className="px-4 py-3 text-sm text-gray-500">
              {isFetching ? t('searchPage.searching') : t('searchComponents.noResults')}
            </p>
          ) : (
            <>
              {data.hits.slice(0, 8).map((hit) => (
                <SearchResultRow
                  key={hit.person_id}
                  hit={hit}
                  onSelect={handleSelect}
                />
              ))}
              {data.total > 8 && (
                <button
                  className="w-full px-4 py-2 text-left text-xs text-indigo-600 hover:bg-indigo-50"
                  onMouseDown={() => {
                    const base = treeId ? `/trees/${treeId}/search` : '/search';
                    navigate(`${base}?q=${encodeURIComponent(debounced)}`);
                  }}
                >
                  View all {data.total} results →
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function SearchResultRow({ hit, onSelect }: { hit: PersonHit; onSelect: (h: PersonHit) => void }) {
  const fullName = [hit.given_name, hit.surname].filter(Boolean).join(' ') || 'Unknown';
  const years = formatYears(hit.birth_year, hit.death_year, hit.is_living);

  return (
    <button
      className="flex w-full items-center gap-3 px-4 py-2 text-left hover:bg-gray-50"
      onMouseDown={() => onSelect(hit)}
    >
      <PersonAvatar name={fullName} />
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-gray-900">{fullName}</p>
        {(years || hit.birth_place) && (
          <p className="truncate text-xs text-gray-500">
            {[years, hit.birth_place].filter(Boolean).join(' · ')}
          </p>
        )}
      </div>
    </button>
  );
}

function PersonAvatar({ name }: { name: string }) {
  const initials = name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase();
  return (
    <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">
      {initials}
    </div>
  );
}

function formatYears(birth?: number | null, death?: number | null, isLiving?: boolean): string {
  if (!birth && !death) return '';
  const b = birth ?? '?';
  if (isLiving) return `b. ${b}`;
  const d = death ?? '?';
  return `${b} – ${d}`;
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className={className} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}
