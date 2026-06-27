/**
 * AncestorChainView — vertical timeline of ancestors or descendants
 * grouped by generation depth.
 */
import React, { useState } from 'react';
import { useAncestors, useDescendants } from '../useSearch';
import type { AncestorHit } from '../types';

interface Props {
  treeId: string;
  personId: string;
  mode: 'ancestors' | 'descendants';
  maxDepth?: number;
}

export function AncestorChainView({ treeId, personId, mode, maxDepth = 10 }: Props) {
  const [depth, setDepth] = useState(maxDepth);

  const ancestorQuery    = useAncestors(treeId, personId, depth);
  const descendantQuery  = useDescendants(treeId, personId, depth);

  const query  = mode === 'ancestors' ? ancestorQuery : descendantQuery;
  const items  = query.data?.items ?? [];
  const title  = mode === 'ancestors' ? 'Ancestors' : 'Descendants';

  // Group by depth
  const byDepth = new Map<number, AncestorHit[]>();
  for (const item of items) {
    const bucket = byDepth.get(item.depth) ?? [];
    bucket.push(item);
    byDepth.set(item.depth, bucket);
  }
  const depths = Array.from(byDepth.keys()).sort((a, b) => a - b);

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">
          {title}
          {query.data && (
            <span className="ml-2 text-sm font-normal text-gray-500">
              ({query.data.total})
            </span>
          )}
        </h3>
        <div className="flex items-center gap-2 text-sm">
          <label className="text-gray-500">Generations:</label>
          <select
            value={depth}
            onChange={(e) => setDepth(parseInt(e.target.value))}
            className="rounded border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            {[2, 3, 5, 7, 10, 15, 20].map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </div>
      </div>

      {query.isLoading && <GenerationSkeletons />}
      {query.isError  && <p className="text-sm text-red-500">Failed to load {title.toLowerCase()}.</p>}

      {query.data?.total === 0 && !query.isLoading && (
        <p className="text-sm text-gray-500">No {title.toLowerCase()} found.</p>
      )}

      {/* Generations */}
      <div className="space-y-3">
        {depths.map((d) => (
          <GenerationGroup
            key={d}
            depth={d}
            items={byDepth.get(d)!}
            treeId={treeId}
          />
        ))}
      </div>
    </div>
  );
}

// ── Generation group ───────────────────────────────────────────────────────────

function GenerationGroup({
  depth,
  items,
  treeId,
}: {
  depth: number;
  items: AncestorHit[];
  treeId: string;
}) {
  const label = items[0]?.relationship_label ?? `Generation ${depth}`;

  return (
    <div>
      <div className="mb-1.5 flex items-center gap-2">
        <span className="inline-flex items-center rounded-full bg-indigo-100 px-2.5 py-0.5 text-xs font-medium text-indigo-800">
          {label}
        </span>
        <span className="text-xs text-gray-400">{items.length} person{items.length !== 1 ? 's' : ''}</span>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((item) => (
          <PersonCard key={item.person_id} item={item} treeId={treeId} />
        ))}
      </div>
    </div>
  );
}

function PersonCard({ item, treeId }: { item: AncestorHit; treeId: string }) {
  const fullName = [item.given_name, item.surname].filter(Boolean).join(' ') || 'Unknown';
  const dates    = item.birth_year
    ? item.is_living
      ? `b. ${item.birth_year}`
      : `${item.birth_year ?? '?'} – ${item.death_year ?? '?'}`
    : null;

  return (
    <a
      href={`/trees/${treeId}/persons/${item.person_id}`}
      className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white p-2.5 hover:border-indigo-300 hover:shadow-sm transition-all"
    >
      <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-gray-100 text-xs font-semibold text-gray-600">
        {fullName.split(' ').map((w) => w[0]).join('').slice(0, 2)}
      </div>
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-gray-900">{fullName}</p>
        {dates && <p className="text-xs text-gray-500">{dates}</p>}
      </div>
    </a>
  );
}

function GenerationSkeletons() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => (
        <div key={i}>
          <div className="mb-1.5 h-5 w-24 animate-pulse rounded-full bg-gray-200" />
          <div className="grid grid-cols-2 gap-2">
            {Array.from({ length: 2 }).map((_, j) => (
              <div key={j} className="h-14 animate-pulse rounded-lg bg-gray-100" />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
