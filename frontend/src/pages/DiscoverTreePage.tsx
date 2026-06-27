/**
 * DiscoverTreePage — authenticated read-only tree viewer for searchable trees.
 *
 * Route: /discover/trees/:treeId
 * Requires authentication; backend enforces is_searchable === true.
 */

import React, { useEffect, useRef, useState, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { TreeCanvas, type TreeCanvasHandle } from '@features/tree/canvas/TreeCanvas';
import type { ApiTreeGraph } from '@features/tree/types';
import { SEO } from '@shared/components/SEO';
import { useAuthStore } from '@store/auth.store';
import { AccessRequestModal } from '@features/discovery/components/AccessRequestModal';
import { MergeRequestModal } from '@features/discovery/components/MergeRequestModal';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

async function fetchDiscoveryGraph(treeId: string, token: string): Promise<ApiTreeGraph & { isMember?: boolean }> {
  const res = await fetch(`${API_BASE}/discover/trees/${treeId}/graph`, {
    headers: { Authorization: `Bearer ${token}` },
    credentials: 'include',
  });
  if (res.status === 403) throw new Error('not_searchable');
  if (!res.ok) throw new Error('not_found');
  return res.json();
}

export default function DiscoverTreePage() {
  const { treeId } = useParams<{ treeId: string }>();
  const accessToken = useAuthStore((s) => s.accessToken);
  const canvasRef = useRef<TreeCanvasHandle>(null);

  const [showAccessModal, setShowAccessModal] = useState(false);
  const [showMergeModal, setShowMergeModal] = useState(false);
  const [requestSent, setRequestSent] = useState(false);

  const { data: graph, isLoading, error } = useQuery<ApiTreeGraph & { isMember?: boolean }, Error>({
    queryKey: ['discover-tree', treeId],
    queryFn: () => fetchDiscoveryGraph(treeId!, accessToken!),
    enabled: !!treeId && !!accessToken,
    retry: false,
  });

  useEffect(() => {
    if (graph) {
      setTimeout(() => canvasRef.current?.refitView(), 300);
    }
  }, [graph]);

  const targetPersons = useMemo(() => {
    if (!graph) return [];
    return ((graph as any).persons || []).map((p: any) => ({
      id: p.id,
      displayGivenName: p.displayGivenName || '',
      displaySurname: p.displaySurname || '',
    }));
  }, [graph]);

  if (isLoading) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-surface-muted">
        <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    const isNotSearchable = error.message === 'not_searchable';
    return (
      <div className="fixed inset-0 flex flex-col items-center justify-center bg-surface-muted gap-4 p-6 text-center">
        <div className="w-14 h-14 rounded-full bg-gray-100 flex items-center justify-center mb-2">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none" stroke="#6b7280" strokeWidth="1.8" strokeLinecap="round">
            <rect x="5" y="13" width="18" height="13" rx="2.5" />
            <path d="M9 13V9a5 5 0 0 1 10 0v4" />
          </svg>
        </div>
        <h1 className="text-xl font-semibold text-gray-900">
          {isNotSearchable ? 'This tree is not searchable' : 'Tree not found'}
        </h1>
        <p className="text-sm text-gray-500 max-w-xs">
          {isNotSearchable
            ? 'The owner has not made this tree discoverable.'
            : 'This tree may have been deleted or does not exist.'}
        </p>
        <Link to="/discover" className="mt-2 text-sm font-medium text-brand-600 hover:underline">
          Back to Discover
        </Link>
      </div>
    );
  }

  if (!graph) return null;

  const treeName = (graph as any).treeName || 'Family Tree';
  const isMember = (graph as any).isMember === true;
  const personCount = ((graph as any).persons || []).length;

  return (
    <div className="fixed inset-0 flex flex-col bg-surface-muted">
      <SEO title={`${treeName} — Discover`} description={`Explore the ${treeName} family tree on OurFamRoots.`} />

      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-white border-b border-gray-200 shrink-0">
        <div className="flex items-center gap-2.5">
          <Link to="/discover" className="text-gray-500 hover:text-gray-700">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
              <path d="M12 4l-6 6 6 6" />
            </svg>
          </Link>
          <h1 className="text-sm font-semibold text-gray-900 truncate max-w-[200px] md:max-w-xs">
            {treeName}
          </h1>
          <span className="hidden sm:inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
            Searchable
          </span>
          <span className="hidden sm:inline text-xs text-gray-400">
            {personCount} {personCount === 1 ? 'person' : 'people'}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {isMember ? (
            <Link
              to={`/trees/${treeId}`}
              className="text-xs font-medium px-3 py-1.5 text-brand-600 border border-brand-200 rounded-lg hover:bg-brand-50 transition-colors"
            >
              Open in My Trees
            </Link>
          ) : (
            <>
              <button
                onClick={() => setShowAccessModal(true)}
                disabled={requestSent}
                className="text-xs font-medium px-3 py-1.5 text-brand-600 border border-brand-200 rounded-lg hover:bg-brand-50 disabled:opacity-50 transition-colors"
              >
                {requestSent ? 'Request Sent' : 'Request Access'}
              </button>
              <button
                onClick={() => setShowMergeModal(true)}
                className="text-xs font-medium px-3 py-1.5 text-white bg-brand-500 rounded-lg hover:bg-brand-600 transition-colors"
              >
                Request Merge
              </button>
            </>
          )}
        </div>
      </div>

      {/* Canvas */}
      <div className="flex-1 relative min-h-0">
        <TreeCanvas ref={canvasRef} graph={graph} />
      </div>

      {/* Modals */}
      {showAccessModal && (
        <AccessRequestModal
          treeId={treeId!}
          treeName={treeName}
          onClose={() => setShowAccessModal(false)}
          onSuccess={() => setRequestSent(true)}
        />
      )}
      {showMergeModal && (
        <MergeRequestModal
          treeId={treeId!}
          treeName={treeName}
          targetPersons={targetPersons}
          onClose={() => setShowMergeModal(false)}
          onSuccess={() => {}}
        />
      )}
    </div>
  );
}
