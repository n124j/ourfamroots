/**
 * VersionHistoryDrawer — right-side drawer showing a person's edit history.
 *
 * Lists versions newest-first. Each row shows: version number, date,
 * editor name, change summary, and a "View snapshot" / "Restore" action.
 * Restore requires ADMIN+ (PermissionGuard gates the button).
 */

import React, { memo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '@store/auth.store';
import { PermissionGuard } from '@shared/components/PermissionGuard';

interface PersonVersion {
  id: string;
  versionNumber: number;
  changeSummary: string;
  createdById: string;
  createdAt: string;
  snapshot: Record<string, unknown>;
}

// ── API ────────────────────────────────────────────────────────────────────

async function fetchVersions(treeId: string, personId: string): Promise<PersonVersion[]> {
  const token = useAuthStore.getState().accessToken;
  const res = await fetch(
    `/api/v1/trees/${treeId}/persons/${personId}/versions?limit=20`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  if (!res.ok) throw new Error('Failed to load versions');
  return res.json();
}

async function restoreVersion(
  treeId: string, personId: string, versionNumber: number
): Promise<void> {
  const token = useAuthStore.getState().accessToken;
  const res = await fetch(
    `/api/v1/trees/${treeId}/persons/${personId}/versions/${versionNumber}/restore`,
    { method: 'POST', headers: { Authorization: `Bearer ${token}` } }
  );
  if (!res.ok) throw new Error('Failed to restore version');
}

// ── Snapshot modal ─────────────────────────────────────────────────────────

const SnapshotModal = memo(
  ({ version, onClose }: { version: PersonVersion; onClose: () => void }) => {
    const { t } = useTranslation();
    return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-[60] p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
          <div>
            <h3 className="text-sm font-semibold text-slate-800">
              {t('versionHistory.version')} {version.versionNumber}
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              {new Date(version.createdAt).toLocaleString()}
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-slate-100 text-slate-400"
          >
            ✕
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">
          <pre className="text-xs font-mono text-slate-700 bg-slate-50 rounded-lg p-4 whitespace-pre-wrap break-all">
            {JSON.stringify(version.snapshot, null, 2)}
          </pre>
        </div>
      </div>
    </div>
    );
  }
);

// ── Version row ────────────────────────────────────────────────────────────

interface VersionRowProps {
  version: PersonVersion;
  isLatest: boolean;
  treeId: string;
  personId: string;
  onRestored: () => void;
}

const VersionRow = memo(({ version, isLatest, treeId, personId, onRestored }: VersionRowProps) => {
  const { t } = useTranslation();
  const [showSnapshot, setShowSnapshot] = useState(false);
  const [confirmRestore, setConfirmRestore] = useState(false);
  const queryClient = useQueryClient();

  const restoreMutation = useMutation({
    mutationFn: () => restoreVersion(treeId, personId, version.versionNumber),
    onSuccess: () => {
      setConfirmRestore(false);
      queryClient.invalidateQueries({ queryKey: ['person-versions', treeId, personId] });
      onRestored();
    },
  });

  return (
    <>
      <div className="flex items-start gap-3 py-3 border-b border-slate-100 last:border-0">
        {/* Version badge */}
        <div className="flex-shrink-0 mt-0.5">
          <div className={[
            'w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold',
            isLatest
              ? 'bg-brand-500 text-white'
              : 'bg-slate-100 text-slate-500',
          ].join(' ')}>
            v{version.versionNumber}
          </div>
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="text-xs text-slate-700 font-medium">
            {version.changeSummary || 'No description'}
            {isLatest && (
              <span className="ml-2 text-[10px] font-medium text-brand-600 bg-brand-50 px-1.5 py-0.5 rounded">
                Current
              </span>
            )}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            {new Date(version.createdAt).toLocaleString(undefined, {
              dateStyle: 'short', timeStyle: 'short',
            })}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3 mt-1.5">
            <button
              onClick={() => setShowSnapshot(true)}
              className="text-[11px] text-slate-500 hover:text-slate-700 underline underline-offset-2"
            >
              {t('versionHistory.viewSnapshot')}
            </button>

            {!isLatest && (
              <PermissionGuard action="RESTORE_VERSION" treeId={treeId}>
                {confirmRestore ? (
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => restoreMutation.mutate()}
                      disabled={restoreMutation.isPending}
                      className="text-[11px] text-amber-700 font-medium hover:text-amber-800"
                    >
                      {restoreMutation.isPending ? 'Restoring…' : t('versionHistory.restore')}
                    </button>
                    <button
                      onClick={() => setConfirmRestore(false)}
                      className="text-[11px] text-slate-400 hover:text-slate-500"
                    >
                      {t('common.cancel')}
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setConfirmRestore(true)}
                    className="text-[11px] text-amber-600 hover:text-amber-700 font-medium"
                  >
                    {t('versionHistory.restore')}
                  </button>
                )}
              </PermissionGuard>
            )}
          </div>
        </div>
      </div>

      {showSnapshot && (
        <SnapshotModal version={version} onClose={() => setShowSnapshot(false)} />
      )}
    </>
  );
});

// ── Main component ─────────────────────────────────────────────────────────

interface VersionHistoryDrawerProps {
  treeId: string;
  personId: string;
  personName: string;
  onClose: () => void;
}

export const VersionHistoryDrawer = memo(
  ({ treeId, personId, personName, onClose }: VersionHistoryDrawerProps) => {
    const { t } = useTranslation();
    const { data: versions = [], isLoading } = useQuery({
      queryKey: ['person-versions', treeId, personId],
      queryFn: () => fetchVersions(treeId, personId),
      staleTime: 60_000,
    });

    return (
      /* Drawer overlay */
      <div className="fixed inset-0 z-50 flex justify-end">
        {/* Backdrop */}
        <div
          className="absolute inset-0 bg-black/30"
          onClick={onClose}
        />

        {/* Drawer panel */}
        <div className="relative w-full max-w-sm bg-white shadow-2xl flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
            <div>
              <h2 className="text-sm font-semibold text-slate-800">{t('versionHistory.version')}</h2>
              <p className="text-xs text-slate-400 mt-0.5 truncate max-w-[200px]">
                {personName}
              </p>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100 text-slate-400"
            >
              ✕
            </button>
          </div>

          {/* Versions list */}
          <div className="flex-1 overflow-y-auto px-5">
            {isLoading ? (
              <div className="space-y-4 pt-4">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="flex gap-3 animate-pulse">
                    <div className="w-7 h-7 rounded-full bg-slate-200 flex-shrink-0" />
                    <div className="flex-1 space-y-1.5">
                      <div className="h-3 bg-slate-100 rounded w-3/4" />
                      <div className="h-2.5 bg-slate-100 rounded w-1/2" />
                    </div>
                  </div>
                ))}
              </div>
            ) : versions.length === 0 ? (
              <div className="py-12 text-center text-sm text-slate-400">
                No version history yet
              </div>
            ) : (
              <div>
                {versions.map((v, idx) => (
                  <VersionRow
                    key={v.id}
                    version={v}
                    isLatest={idx === 0}
                    treeId={treeId}
                    personId={personId}
                    onRestored={onClose}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Footer note */}
          <div className="px-5 py-3 border-t border-slate-100">
            <p className="text-[10px] text-slate-400">
              Showing last {versions.length} version{versions.length !== 1 ? 's' : ''}.
              Restoring a version creates a new version entry.
            </p>
          </div>
        </div>
      </div>
    );
  }
);
VersionHistoryDrawer.displayName = 'VersionHistoryDrawer';
