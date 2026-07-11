/**
 * useEntitledFilterKeys — the current user's subscription-entitled filter keys.
 *
 * Backed by GET /subscriptions/my-filters (any verified user). Used to gate
 * which non-builtin tree view extensions (Timeline, Text Pedigree, Family
 * Tree Poster, …) show up in the Extensions dropdown.
 */
import { useQuery } from '@tanstack/react-query';
import { get } from '@api/client';
import { queryKeys } from '@queries/keys';

interface MyFiltersResponse {
  filterKeys: string[];
}

export function useEntitledFilterKeys() {
  const query = useQuery({
    queryKey: queryKeys.subscriptions.myFilters(),
    queryFn: () => get<MyFiltersResponse>('/subscriptions/my-filters'),
    staleTime: 5 * 60_000,
  });

  return {
    entitledKeys: new Set(query.data?.filterKeys ?? []),
    isLoading: query.isLoading,
    isError: query.isError,
  };
}
