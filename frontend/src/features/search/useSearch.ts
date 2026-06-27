/**
 * useSearch — debounced name search hook backed by React Query.
 * Supports both global (cross-tree) and per-tree search modes.
 */
import { useQuery } from '@tanstack/react-query';
import { get } from '@api/client';
import type { NameSearchResponse, SearchFilters } from './types';

const DEBOUNCE_MS = 300;

export const searchKeys = {
  global:      (q: string, filters: SearchFilters) => ['search', 'global', q, filters] as const,
  tree:        (treeId: string, q: string, filters: SearchFilters) => ['search', 'tree', treeId, q, filters] as const,
  ancestors:   (treeId: string, personId: string, depth: number) => ['search', 'ancestors', treeId, personId, depth] as const,
  descendants: (treeId: string, personId: string, depth: number) => ['search', 'descendants', treeId, personId, depth] as const,
  relatives:   (treeId: string, personId: string, hops: number)  => ['search', 'relatives', treeId, personId, hops] as const,
  relationship:(treeId: string, p1: string, p2: string)          => ['search', 'relationship', treeId, p1, p2] as const,
};

export function useNameSearch(
  query: string,
  filters: SearchFilters = {},
  treeId?: string,
) {
  const trimmed = query.trim();
  const enabled = trimmed.length >= 2;

  const queryKey = treeId
    ? searchKeys.tree(treeId, trimmed, filters)
    : searchKeys.global(trimmed, filters);

  const queryFn = () => {
    const params = new URLSearchParams({ q: trimmed, fuzzy: String(filters.fuzzy ?? true) });
    if (filters.birth_year_min) params.set('birth_year_min', String(filters.birth_year_min));
    if (filters.birth_year_max) params.set('birth_year_max', String(filters.birth_year_max));
    if (filters.birth_place)    params.set('birth_place', filters.birth_place);
    if (filters.sort)           params.set('sort', filters.sort);

    const url = treeId
      ? `/trees/${treeId}/search?${params}`
      : `/search?${params}`;
    return get<NameSearchResponse>(url);
  };

  return useQuery({
    queryKey,
    queryFn,
    enabled,
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });
}

export function useAncestors(treeId: string, personId: string, maxDepth = 10) {
  return useQuery({
    queryKey: searchKeys.ancestors(treeId, personId, maxDepth),
    queryFn: () =>
      get<import('./types').GraphSearchResponse>(
        `/trees/${treeId}/persons/${personId}/ancestors?max_depth=${maxDepth}`
      ),
    staleTime: 5 * 60_000,
  });
}

export function useDescendants(treeId: string, personId: string, maxDepth = 10) {
  return useQuery({
    queryKey: searchKeys.descendants(treeId, personId, maxDepth),
    queryFn: () =>
      get<import('./types').GraphSearchResponse>(
        `/trees/${treeId}/persons/${personId}/descendants?max_depth=${maxDepth}`
      ),
    staleTime: 5 * 60_000,
  });
}

export function useRelatives(treeId: string, personId: string, maxHops = 4) {
  return useQuery({
    queryKey: searchKeys.relatives(treeId, personId, maxHops),
    queryFn: () =>
      get<import('./types').GraphSearchResponse>(
        `/trees/${treeId}/persons/${personId}/relatives?max_hops=${maxHops}`
      ),
    staleTime: 5 * 60_000,
  });
}

export function useRelationship(
  treeId: string,
  personId1: string,
  personId2: string,
  enabled = true,
) {
  return useQuery({
    queryKey: searchKeys.relationship(treeId, personId1, personId2),
    queryFn: () =>
      get<import('./types').RelationshipResponse>(
        `/trees/${treeId}/persons/${personId1}/relationship?target=${personId2}`
      ),
    enabled: enabled && !!personId1 && !!personId2 && personId1 !== personId2,
    staleTime: 10 * 60_000,
  });
}
