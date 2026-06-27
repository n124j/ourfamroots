/**
 * PermissionGuard — conditionally renders children based on the current
 * user's role in the active tree.
 *
 * Usage:
 *   <PermissionGuard action="INVITE_MEMBER" treeId={treeId}>
 *     <InviteButton />
 *   </PermissionGuard>
 *
 *   <PermissionGuard action="DELETE_TREE" treeId={treeId} fallback={<></>}>
 *     <DeleteTreeButton />
 *   </PermissionGuard>
 */

import React, { memo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@queries/keys';
import { useAuthStore } from '@store/auth.store';

// ── Permission matrix (mirrors backend ACTION_MIN_ROLE) ────────────────────

type TreeRole = 'OWNER' | 'ADMIN' | 'EDITOR' | 'VIEWER';

export const ROLE_HIERARCHY: Record<TreeRole, number> = {
  OWNER: 4, ADMIN: 3, EDITOR: 2, VIEWER: 1,
};

export const ACTION_MIN_ROLE: Record<string, TreeRole> = {
  // Owner
  DELETE_TREE:         'OWNER',
  TRANSFER_OWNERSHIP:  'OWNER',
  // Admin
  INVITE_MEMBER:       'ADMIN',
  REMOVE_MEMBER:       'ADMIN',
  CHANGE_MEMBER_ROLE:  'ADMIN',
  UPDATE_TREE:         'ADMIN',
  VIEW_AUDIT_LOG:      'ADMIN',
  RESTORE_VERSION:     'ADMIN',
  // Editor
  CREATE_PERSON:       'EDITOR',
  UPDATE_PERSON:       'EDITOR',
  DELETE_PERSON:       'EDITOR',
  ADD_RELATIONSHIP:    'EDITOR',
  REMOVE_RELATIONSHIP: 'EDITOR',
  CREATE_EVENT:        'EDITOR',
  UPDATE_EVENT:        'EDITOR',
  DELETE_EVENT:        'EDITOR',
  UPLOAD_MEDIA:        'EDITOR',
  DELETE_MEDIA:        'EDITOR',
  GENERATE_REPORT:     'EDITOR',
  EXPORT_GEDCOM:       'EDITOR',
  // Viewer
  VIEW_PERSON:         'VIEWER',
  VIEW_MEMBERS:        'VIEWER',
  VIEW_VERSION:        'VIEWER',
};

export function isPermitted(userRole: TreeRole, action: string): boolean {
  const minRole = ACTION_MIN_ROLE[action];
  if (!minRole) return false;
  return ROLE_HIERARCHY[userRole] >= ROLE_HIERARCHY[minRole];
}

// ── Hook: current user's role in a tree ───────────────────────────────────

interface MemberRecord { userId: string; role: TreeRole }

export function useTreeRole(treeId: string | null): TreeRole | null {
  const userId = useAuthStore((s) => s.user?.id);

  const { data: members } = useQuery<MemberRecord[]>({
    queryKey: queryKeys.trees.members(treeId ?? ''),
    queryFn: async () => {
      const res = await fetch(`/api/v1/trees/${treeId}/members`, {
        headers: { Authorization: `Bearer ${useAuthStore.getState().accessToken}` },
      });
      if (!res.ok) return [];
      return res.json();
    },
    enabled: !!treeId && !!userId,
    staleTime: 5 * 60_000,
  });

  if (!members || !userId) return null;
  const me = members.find((m) => m.userId === userId);
  return me?.role ?? null;
}

// ── Component ──────────────────────────────────────────────────────────────

interface PermissionGuardProps {
  action: string;
  treeId: string | null;
  /** Rendered when the user lacks permission. Defaults to null (render nothing). */
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

export const PermissionGuard = memo(
  ({ action, treeId, fallback = null, children }: PermissionGuardProps) => {
    const role = useTreeRole(treeId);

    if (!role) return <>{fallback}</>;
    if (!isPermitted(role, action)) return <>{fallback}</>;

    return <>{children}</>;
  }
);
PermissionGuard.displayName = 'PermissionGuard';

// ── usePermission hook (imperative) ───────────────────────────────────────

export function usePermission(treeId: string | null, action: string): boolean {
  const role = useTreeRole(treeId);
  if (!role) return false;
  return isPermitted(role, action);
}
