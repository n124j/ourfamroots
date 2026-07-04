/**
 * SharedTreePage — public read-only tree viewer.
 *
 * Route: /shared/:shareToken
 * No authentication required; backend enforces link_sharing === 'ANYONE'.
 */

import React, { useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { TreeCanvas, type TreeCanvasHandle } from '@features/tree/canvas/TreeCanvas';
import type { ApiTreeGraph } from '@features/tree/types';
import { SEO } from '@shared/components/SEO';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';
const BASE_URL = import.meta.env.VITE_FRONTEND_BASE_URL ?? 'https://ourfamroots.com';
const TREE_OG_IMAGE = `${BASE_URL}/og-image-tree.svg`;

async function fetchSharedGraph(shareToken: string): Promise<ApiTreeGraph> {
  const res = await fetch(`${API_BASE}/trees/shared/${shareToken}/graph`);
  if (res.status === 403) throw new Error('private');
  if (!res.ok) throw new Error('not_found');
  return res.json();
}

export default function SharedTreePage() {
  const { shareToken } = useParams<{ shareToken: string }>();
  const canvasRef = useRef<TreeCanvasHandle>(null);

  const { data: graph, isLoading, error } = useQuery<ApiTreeGraph, Error>({
    queryKey: ['shared-tree', shareToken],
    queryFn: () => fetchSharedGraph(shareToken!),
    enabled: !!shareToken,
    retry: false,
  });

  useEffect(() => {
    if (graph) {
      setTimeout(() => canvasRef.current?.refitView(), 300);
    }
  }, [graph]);

  if (isLoading) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-surface-muted">
        <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    const isPrivate = error.message === 'private';
    return (
      <div className="fixed inset-0 flex flex-col items-center justify-center bg-surface-muted gap-4 p-6 text-center">
        <div className="w-14 h-14 rounded-full bg-gray-100 flex items-center justify-center mb-2">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none" stroke="#6b7280" strokeWidth="1.8" strokeLinecap="round">
            <rect x="5" y="13" width="18" height="13" rx="2.5" />
            <path d="M9 13V9a5 5 0 0 1 10 0v4" />
          </svg>
        </div>
        <h1 className="text-xl font-semibold text-gray-900">
          {isPrivate ? 'This tree is private' : 'Tree not found'}
        </h1>
        <p className="text-sm text-gray-500 max-w-xs">
          {isPrivate
            ? 'The owner has not enabled public link sharing for this family tree.'
            : 'This link may have expired or the tree no longer exists.'}
        </p>
        <Link to="/" className="mt-2 text-sm font-medium text-brand-600 hover:underline">
          Go to homepage
        </Link>
      </div>
    );
  }

  if (!graph) return null;

  const treeName = (graph as any).treeName || 'Family Tree';
  const treeDescription = (graph as any).treeDescription as string | null | undefined;
  const personCount = (graph as any).nodes?.length ?? 0;

  return (
    <div className="fixed inset-0 flex flex-col bg-surface-muted">
      <SEO
        title={`${treeName} — Shared Family Tree`}
        description={treeDescription || `Explore the ${treeName} family tree${personCount ? ` with ${personCount} family members` : ''}. View ancestors, descendants, and family connections on OurFamRoots.`}
        keywords={`${treeName}, family tree, shared family tree, ancestry, genealogy, family history`}
        ogType="website"
        ogImage={TREE_OG_IMAGE}
        ogImageAlt={`${treeName} — family tree logo`}
      />
      {/* Minimal top bar */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-white border-b border-gray-200 shrink-0">
        <div className="flex items-center gap-2.5">
          <Link to="/" className="text-brand-600 hover:text-brand-700">
            <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
              <path d="M11 2C7.5 2 4.5 4.8 4.5 8.3c0 5.2 6.5 11.7 6.5 11.7s6.5-6.5 6.5-11.7C17.5 4.8 14.5 2 11 2z" />
              <circle cx="11" cy="8.5" r="2" />
            </svg>
          </Link>
          <h1 className="text-sm font-semibold text-gray-900 truncate max-w-[200px] md:max-w-xs">
            {treeName}
          </h1>
          <span className="hidden sm:inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-500">
            View only
          </span>
        </div>
        <Link
          to="/register"
          className="text-xs font-medium px-3 py-1.5 bg-brand-500 text-white rounded-lg hover:bg-brand-600 transition-colors"
        >
          Sign up to build your own
        </Link>
      </div>

      {/* Canvas */}
      <div className="flex-1 relative min-h-0">
        <TreeCanvas
          ref={canvasRef}
          graph={graph}
        />
      </div>
    </div>
  );
}
