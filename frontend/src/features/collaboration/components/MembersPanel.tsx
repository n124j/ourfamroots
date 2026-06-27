/**
 * MembersPanel — lists current tree members with role management.
 *
 * Shows: avatar, name, email, role badge, change-role dropdown, remove button.
 * Role controls are hidden for VIEWER users (PermissionGuard).
 */

import React, { memo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@queries/keys';
import { PermissionGuard } from '@shared/components/PermissionGuard';
import { useAuthStore } from '@store/auth.store';

type TreeRole = 'OWNER' | 'ADMIN' | 'EDITOR' | 'VIEWER';

interface Member {
  id: string;
  userId: string;
  role: TreeRole;
  joinedAt: string | null;
  // enriched from user profile:
  displayName?: string;
  email?: string;
  avatarUrl?: string;
}

function useRoleLabels(): Record<TreeRole, string> {
  const { t } = useTranslation();
  return { OWNER: t('roles.OWNER'), ADMIN: t('roles.ADMIN'), EDITOR: t('roles.EDITOR'), VIEWER: t('roles.VIEWER') };
}

const ROLE_COLORS: Record<TreeRole, string> = {
  OWNER:  'bg-amber-100 text-amber-800',
  ADMIN:  'bg-purple-100 text-purple-800',
  EDITOR: 'bg-blue-100 text-blue-800',
  VIEWER: 'bg-slate-100 text-slate-600',
};

const ASSIGNABLE_ROLES: TreeRole[] = ['ADMIN', 'EDITOR', 'VIEWER'];

// ── API helpers ────────────────────────────────────────────────────────────

function authHeaders() {
  return { Authorization: `Bearer ${useAuthStore.getState().accessToken}` };
}

async function fetchMembers(treeId: string): Promise<Member[]> {
  const res = await fetch(`/api/v1/trees/${treeId}/members`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Failed to load members');
  return res.json();
}

async function changeRole(treeId: string, userId: string, role: TreeRole): Promise<void> {
  const res = await fetch(`/api/v1/trees/${treeId}/members/${userId}/role`, {
    method: 'PATCH',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ role }),
  });
  if (!res.ok) throw new Error('Failed to change role');
}

async function removeMember(treeId: string, userId: string): Promise<void> {
  const res = await fetch(`/api/v1/trees/${treeId}/members/${userId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error('Failed to remove member');
}

// ── Sub-components ─────────────────────────────────────────────────────────

const RoleBadge = memo(({ role }: { role: TreeRole }) => {
  const labels = useRoleLabels();
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${ROLE_COLORS[role]}`}>
      {labels[role]}
    </span>
  );
});

interface MemberRowProps {
  member: Member;
  treeId: string;
  isCurrentUser: boolean;
  canManage: boolean;
  isOwner: boolean;
}

const MemberRow = memo(({ member, treeId, isCurrentUser, canManage, isOwner }: MemberRowProps) => {
  const { t } = useTranslation();
  const roleLabels = useRoleLabels();
  const queryClient = useQueryClient();
  const [confirmRemove, setConfirmRemove] = useState(false);

  const changeRoleMutation = useMutation({
    mutationFn: (role: TreeRole) => changeRole(treeId, member.userId, role),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.trees.members(treeId) }),
  });

  const removeMutation = useMutation({
    mutationFn: () => removeMember(treeId, member.userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.trees.members(treeId) }),
  });

  const initials = (member.displayName ?? member.email ?? '?')
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="flex items-center gap-3 py-3 border-b border-slate-100 last:border-0">
      {/* Avatar */}
      <div className="w-9 h-9 rounded-full bg-brand-100 flex items-center justify-center text-brand-700 text-sm font-semibold flex-shrink-0">
        {member.avatarUrl ? (
          <img src={member.avatarUrl} alt="" className="w-full h-full rounded-full object-cover" />
        ) : (
          initials
        )}
      </div>

      {/* Name + email */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-800 truncate">
            {member.displayName ?? member.email ?? member.userId.slice(0, 8)}
          </span>
          {isCurrentUser && (
            <span className="text-[10px] text-slate-400">{t('membersPanel.you')}</span>
          )}
        </div>
        {member.email && (
          <div className="text-xs text-slate-500 truncate">{member.email}</div>
        )}
      </div>

      {/* Role */}
      <div className="flex items-center gap-2">
        {canManage && member.role !== 'OWNER' && !isCurrentUser ? (
          <select
            value={member.role}
            onChange={(e) => changeRoleMutation.mutate(e.target.value as TreeRole)}
            disabled={changeRoleMutation.isPending}
            className="text-xs border border-slate-200 rounded px-2 py-1 text-slate-700 bg-white focus:ring-1 focus:ring-brand-500 focus:outline-none"
          >
            {ASSIGNABLE_ROLES.map((r) => (
              <option key={r} value={r}>{roleLabels[r]}</option>
            ))}
            {isOwner && <option value="OWNER">Owner (transfer)</option>}
          </select>
        ) : (
          <RoleBadge role={member.role} />
        )}

        {/* Remove button */}
        {canManage && member.role !== 'OWNER' && !isCurrentUser && (
          confirmRemove ? (
            <div className="flex items-center gap-1">
              <button
                onClick={() => removeMutation.mutate()}
                className="text-xs text-red-600 hover:text-red-700 font-medium px-2 py-1 rounded hover:bg-red-50"
              >
                Confirm
              </button>
              <button
                onClick={() => setConfirmRemove(false)}
                className="text-xs text-slate-400 hover:text-slate-600 px-1 py-1"
              >
                ✕
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmRemove(true)}
              className="text-slate-300 hover:text-red-500 transition-colors p-1 rounded"
              title="Remove member"
            >
              ✕
            </button>
          )
        )}
      </div>
    </div>
  );
});

// ── Main component ─────────────────────────────────────────────────────────

interface MembersPanelProps {
  treeId: string;
  onInviteClick: () => void;
}

export const MembersPanel = memo(({ treeId, onInviteClick }: MembersPanelProps) => {
  const currentUserId = useAuthStore((s) => s.user?.id);

  const { data: members = [], isLoading } = useQuery({
    queryKey: queryKeys.trees.members(treeId),
    queryFn: () => fetchMembers(treeId),
    staleTime: 2 * 60_000,
  });

  const currentMember = members.find((m) => m.userId === currentUserId);
  const canManage = currentMember?.role === 'OWNER' || currentMember?.role === 'ADMIN';
  const isOwner = currentMember?.role === 'OWNER';

  return (
    <div className="flex flex-col gap-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-700">
          Members ({members.length})
        </h3>
        <PermissionGuard action="INVITE_MEMBER" treeId={treeId}>
          <button
            onClick={onInviteClick}
            className="text-xs text-brand-600 font-medium hover:text-brand-700"
          >
            + Invite
          </button>
        </PermissionGuard>
      </div>

      {/* List */}
      {isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex items-center gap-3 animate-pulse">
              <div className="w-9 h-9 rounded-full bg-slate-200" />
              <div className="flex-1">
                <div className="h-3 bg-slate-200 rounded w-3/4 mb-1.5" />
                <div className="h-2.5 bg-slate-100 rounded w-1/2" />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div>
          {members.map((member) => (
            <MemberRow
              key={member.id}
              member={member}
              treeId={treeId}
              isCurrentUser={member.userId === currentUserId}
              canManage={canManage}
              isOwner={isOwner}
            />
          ))}
        </div>
      )}
    </div>
  );
});
MembersPanel.displayName = 'MembersPanel';
