/**
 * SearchableCombobox — a typeahead dropdown for picking one item out of a
 * potentially large, server-paginated list (namespaces, users, trees,
 * permission groups, ...). A plain <select> stops being usable once a list
 * has more than a couple dozen entries; this fetches PAGE_SIZE results at a
 * time, loads more as you scroll the list, and re-queries the server as you
 * type — the same interaction pattern everywhere it's used.
 */
import React, { useCallback, useRef, useState } from 'react';

export interface ComboboxItem {
  id: string;
}

export interface ComboboxPage<T> {
  items: T[];
  total_pages: number;
}

interface SearchableComboboxProps<T extends ComboboxItem> {
  /** Fetch one page of results, optionally filtered by a search term. */
  fetchPage: (page: number, pageSize: number, search: string) => Promise<ComboboxPage<T>>;
  /** Content shown for each option in the open dropdown list. */
  renderOption: (item: T) => React.ReactNode;
  selected: T | null;
  onSelect: (item: T | null) => void;
  /** Label for the "clear selection" option, always shown first. */
  emptyLabel: string;
  placeholder?: string;
  /** Text shown in the closed input for the current selection (defaults to a plain-text render of renderOption). */
  getLabel?: (item: T) => string;
  /** How many results to fetch per page/scroll-load. */
  pageSize?: number;
  /** Applied to each freshly-fetched page before it's appended to the list, e.g. to exclude already-selected items. */
  filterItems?: (items: T[]) => T[];
  noResultsLabel?: string;
}

export function SearchableCombobox<T extends ComboboxItem>({
  fetchPage,
  renderOption,
  selected,
  onSelect,
  emptyLabel,
  placeholder = 'Search…',
  getLabel,
  pageSize = 10,
  filterItems,
  noResultsLabel = 'No results found',
}: SearchableComboboxProps<T>) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<T[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const requestIdRef = useRef(0);

  const loadPage = useCallback(async (pageNum: number, searchTerm: string, append: boolean) => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    try {
      const data = await fetchPage(pageNum, pageSize, searchTerm);
      if (requestId !== requestIdRef.current) return;
      const results = filterItems ? filterItems(data.items) : data.items;
      setItems((prev) => (append ? [...prev, ...results] : results));
      setTotalPages(data.total_pages);
      setPage(pageNum);
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, [fetchPage, pageSize, filterItems]);

  function handleOpen() {
    setOpen(true);
    if (items.length === 0) loadPage(1, '', false);
  }

  function handleQueryChange(v: string) {
    setQuery(v);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => loadPage(1, v, false), 250);
  }

  function handleScroll(e: React.UIEvent<HTMLDivElement>) {
    const el = e.currentTarget;
    if (loading || page >= totalPages) return;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 24) {
      loadPage(page + 1, query, true);
    }
  }

  function handleSelect(item: T | null) {
    onSelect(item);
    setQuery('');
    setOpen(false);
  }

  const closedLabel = selected ? (getLabel ? getLabel(selected) : String(renderOption(selected))) : '';

  return (
    <div
      className="relative"
      onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setOpen(false); }}
    >
      <input
        type="text"
        value={open ? query : closedLabel}
        onFocus={handleOpen}
        onChange={(e) => handleQueryChange(e.target.value)}
        placeholder={placeholder}
        className="w-full h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
      />
      {open && (
        <div
          onScroll={handleScroll}
          className="absolute z-10 mt-1 w-full max-h-64 overflow-y-auto bg-white border border-gray-200 rounded-lg shadow-lg py-1"
        >
          <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => handleSelect(null)}
            className="w-full text-left px-3 py-2 text-sm text-gray-600 hover:bg-gray-50">
            {emptyLabel}
          </button>
          {items.map((item) => (
            <button key={item.id} type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => handleSelect(item)}
              className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 ${selected?.id === item.id ? 'bg-brand-50 text-brand-700' : 'text-gray-800'}`}>
              {renderOption(item)}
            </button>
          ))}
          {items.length === 0 && !loading && (
            <p className="px-3 py-2 text-sm text-gray-400">{noResultsLabel}</p>
          )}
          {loading && (
            <div className="flex justify-center py-2">
              <div className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
