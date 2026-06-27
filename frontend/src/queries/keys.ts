/**
 * Query key factory — single source of truth for all React Query cache keys.
 *
 * Convention: keys are arrays.  Invalidating a parent key invalidates all
 * children (React Query prefix matching).
 *
 * e.g. invalidating queryKeys.trees.all also invalidates
 *      queryKeys.trees.detail('x'), queryKeys.trees.members('x'), etc.
 */

interface SearchParams {
  q?: string;
  treeId?: string;
  sex?: string;
  birthYearMin?: number;
  birthYearMax?: number;
  isLiving?: boolean;
  page?: number;
}

export const queryKeys = {
  // ── Trees ────────────────────────────────────────────────────────────────
  trees: {
    all:         () => ['trees'] as const,
    list:        () => [...queryKeys.trees.all(), 'list'] as const,
    detail:      (id: string) => [...queryKeys.trees.all(), 'detail', id] as const,
    members:     (treeId: string) => [...queryKeys.trees.all(), treeId, 'members'] as const,
    invitations: (treeId: string) => [...queryKeys.trees.all(), treeId, 'invitations'] as const,
    auditLog:    (treeId: string) => [...queryKeys.trees.all(), treeId, 'audit-log'] as const,
  },

  // ── Persons ──────────────────────────────────────────────────────────────
  persons: {
    all:         (treeId: string) => ['persons', treeId] as const,
    detail:      (treeId: string, id: string) => ['persons', treeId, 'detail', id] as const,
    ancestors:   (treeId: string, id: string) => ['persons', treeId, id, 'ancestors'] as const,
    descendants: (treeId: string, id: string) => ['persons', treeId, id, 'descendants'] as const,
    kinship:     (treeId: string, id1: string, id2: string) =>
                   ['persons', treeId, 'kinship', id1, id2] as const,
    versions:    (treeId: string, personId: string) =>
                   ['persons', treeId, personId, 'versions'] as const,
  },

  // ── Search ───────────────────────────────────────────────────────────────
  search: {
    results: (params: SearchParams) => ['search', params] as const,
  },

  // ── Reports ──────────────────────────────────────────────────────────────
  reports: {
    all:    () => ['reports'] as const,
    detail: (id: string) => ['reports', id] as const,
  },

  // ── Current user ─────────────────────────────────────────────────────────
  me: () => ['me'] as const,
};
