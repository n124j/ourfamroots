/**
 * AuditLogViewer — paginated, filterable audit log table.
 *
 * Columns: timestamp, actor, action, entity, diff (before/after).
 * Filters: entity type, actor.
 * Requires ADMIN+ role (PermissionGuard gates the parent page).
 */

import React, { memo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '@store/auth.store';

interface AuditEntry {
  id: string;
  actorDisplayName: string;
  action: string;
  entityType: string;
  entityId: string | null;
  entityDisplayName: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  occurredAt: string;
}

// ── Action colours ─────────────────────────────────────────────────────────

const ACTION_COLOR: Record<string, string> = {
  CREATE_PERSON:       'bg-emerald-100 text-emerald-800',
  UPDATE_PERSON:       'bg-blue-100 text-blue-800',
  DELETE_PERSON:       'bg-red-100 text-red-800',
  ADD_RELATIONSHIP:    'bg-emerald-100 text-emerald-800',
  REMOVE_RELATIONSHIP: 'bg-red-100 text-red-800',
  INVITE_MEMBER:       'bg-purple-100 text-purple-800',
  REMOVE_MEMBER:       'bg-orange-100 text-orange-800',
  CHANGE_MEMBER_ROLE:  'bg-amber-100 text-amber-800',
  RESTORE_VERSION:     'bg-indigo-100 text-indigo-800',
  UPLOAD_MEDIA:        'bg-teal-100 text-teal-800',
  DELETE_MEDIA:        'bg-red-100 text-red-800',
};

function actionLabel(action: string): string {
  return action.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
}

// ── Diff viewer ────────────────────────────────────────────────────────────

const DiffCell = memo(
  ({ before, after }: { before: Record<string, unknown> | null; after: Record<string, unknown> | null }) => {
    const [open, setOpen] = useState(false);
    if (!before && !after) return <span className="text-slate-300">—</span>;

    return (
      <div>
        <button
          onClick={() => setOpen((o) => !o)}
          className="text-xs text-brand-600 hover:text-brand-700 font-medium"
        >
          {open ? 'Hide diff' : 'View diff'}
        </button>
        {open && (
          <div className="mt-2 grid grid-cols-2 gap-1 text-[10px] font-mono">
            {before && (
              <div className="bg-red-50 rounded p-1.5 text-red-700 whitespace-pre-wrap break-all">
                {JSON.stringify(before, null, 2)}
              </div>
            )}
            {after && (
              <div className="bg-emerald-50 rounded p-1.5 text-emerald-700 whitespace-pre-wrap break-all">
                {JSON.stringify(after, null, 2)}
              </div>
            )}
          </div>
        )}
      </div>
    );
  }
);

// ── Skeleton row ───────────────────────────────────────────────────────────

const SkeletonRow = () => (
  <tr className="animate-pulse">
    {[80, 100, 120, 140, 60].map((w, i) => (
      <td key={i} className="px-4 py-3">
        <div className="h-3 bg-slate-100 rounded" style={{ width: w }} />
      </td>
    ))}
  </tr>
);

// ── Main component ─────────────────────────────────────────────────────────

const PAGE_SIZE = 25;

const ENTITY_TYPES = [
  'All', 'PERSON', 'FAMILY_GROUP', 'EVENT', 'MEDIA', 'MEMBER', 'INVITATION',
];

interface AuditLogViewerProps {
  treeId: string;
}

export const AuditLogViewer = memo(({ treeId }: AuditLogViewerProps) => {
  const [page, setPage]             = useState(0);
  const [entityType, setEntityType] = useState('All');

  const token = useAuthStore((s) => s.accessToken);

  const { data, isLoading, isFetching } = useQuery<AuditEntry[]>({
    queryKey: ['audit-log', treeId, page, entityType],
    queryFn: async () => {
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(page * PAGE_SIZE),
        ...(entityType !== 'All' && { entity_type: entityType }),
      });
      const res = await fetch(`/api/v1/trees/${treeId}/audit-log?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Failed to load audit log');
      return res.json();
    },
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });

  const entries = data ?? [];
  const hasPrev = page > 0;
  const hasNext = entries.length === PAGE_SIZE;

  return (
    <div className="flex flex-col gap-4">
      {/* Filters */}
      <div className="flex items-center gap-3">
        <label className="text-xs font-medium text-slate-500">Filter by:</label>
        <select
          value={entityType}
          onChange={(e) => { setEntityType(e.target.value); setPage(0); }}
          className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 text-slate-700 bg-white focus:ring-1 focus:ring-brand-500 focus:outline-none"
        >
          {ENTITY_TYPES.map((t) => (
            <option key={t} value={t}>{t === 'All' ? 'All entity types' : t}</option>
          ))}
        </select>
        {isFetching && (
          <span className="text-xs text-slate-400 animate-pulse">Refreshing…</span>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50">
              {['Time', 'Actor', 'Action', 'Entity', 'Changes'].map((h) => (
                <th key={h} className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {isLoading
              ? Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} />)
              : entries.length === 0
              ? (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-sm text-slate-400">
                    No audit entries found
                  </td>
                </tr>
              )
              : entries.map((entry) => (
                <tr key={entry.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">
                    {new Date(entry.occurredAt).toLocaleString(undefined, {
                      dateStyle: 'short', timeStyle: 'short',
                    })}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-700 font-medium whitespace-nowrap">
                    {entry.actorDisplayName}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex px-2 py-0.5 rounded text-[11px] font-medium ${ACTION_COLOR[entry.action] ?? 'bg-slate-100 text-slate-700'}`}>
                      {actionLabel(entry.action)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-600">
                    <div className="font-medium">{entry.entityType}</div>
                    {entry.entityDisplayName && (
                      <div className="text-slate-400 truncate max-w-[180px]">
                        {entry.entityDisplayName}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <DiffCell before={entry.before} after={entry.after} />
                  </td>
                </tr>
              ))
            }
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-400">
          Page {page + 1}
        </span>
        <div className="flex gap-2">
          <button
            onClick={() => setPage((p) => p - 1)}
            disabled={!hasPrev}
            className="text-xs px-3 py-1.5 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ← Prev
          </button>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={!hasNext}
            className="text-xs px-3 py-1.5 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  );
});
AuditLogViewer.displayName = 'AuditLogViewer';
