/**
 * useExpandCollapse — manages which subtrees are expanded/collapsed.
 *
 * Strategy:
 *  - Start with only the focus person + immediate family expanded.
 *  - On expand: BFS one generation in the requested direction and add to visible set.
 *  - On collapse: BFS and remove the subtree from visible set.
 *  - Visible set is stored in canvas.store for persistence across re-renders.
 */

import { useCallback } from 'react';
import type { ApiTreeGraph } from '../types';
import { useCanvasStore } from '@store/canvas.store';

// ── Graph helpers ──────────────────────────────────────────────────────────

function buildChildrenMap(graph: ApiTreeGraph): Map<string, string[]> {
  const map = new Map<string, string[]>();
  for (const fg of graph.familyGroups) {
    for (const parentId of fg.parentIds) {
      const existing = map.get(parentId) ?? [];
      map.set(parentId, [...existing, ...Object.keys(fg.children)]);
    }
  }
  return map;
}

function buildParentsMap(graph: ApiTreeGraph): Map<string, string[]> {
  const map = new Map<string, string[]>();
  for (const fg of graph.familyGroups) {
    for (const childId of Object.keys(fg.children)) {
      const existing = map.get(childId) ?? [];
      map.set(childId, [...existing, ...fg.parentIds]);
    }
  }
  return map;
}

/** BFS from startId collecting all reachable IDs in the given direction. */
function bfsDescendants(startId: string, childrenMap: Map<string, string[]>): Set<string> {
  const visited = new Set<string>();
  const queue = [startId];
  while (queue.length > 0) {
    const id = queue.shift()!;
    if (visited.has(id)) continue;
    visited.add(id);
    for (const childId of childrenMap.get(id) ?? []) {
      queue.push(childId);
    }
  }
  visited.delete(startId); // don't include the node itself
  return visited;
}

function bfsAncestors(startId: string, parentsMap: Map<string, string[]>): Set<string> {
  const visited = new Set<string>();
  const queue = [startId];
  while (queue.length > 0) {
    const id = queue.shift()!;
    if (visited.has(id)) continue;
    visited.add(id);
    for (const parentId of parentsMap.get(id) ?? []) {
      queue.push(parentId);
    }
  }
  visited.delete(startId);
  return visited;
}

// ── Hook ───────────────────────────────────────────────────────────────────

export interface UseExpandCollapseReturn {
  /** Compute the initial expanded set for a fresh tree load */
  initializeExpanded: (graph: ApiTreeGraph, focusPersonId: string) => void;
  /** Toggle expand/collapse for a person's children or parents */
  toggleExpand: (personId: string, direction: 'children' | 'parents') => void;
  /** Expand all nodes (show entire tree) */
  expandAll: (graph: ApiTreeGraph) => void;
  /** Collapse to focus person only */
  collapseAll: (focusPersonId: string) => void;
  /** Current set of expanded node IDs */
  expandedNodeIds: Set<string>;
}

export function useExpandCollapse(graph: ApiTreeGraph | null): UseExpandCollapseReturn {
  const expandedNodeIds = useCanvasStore((s) => s.expandedNodeIds);
  const setExpandedNodeIds = useCanvasStore((s) => s.setExpandedNodeIds);

  const initializeExpanded = useCallback(
    (g: ApiTreeGraph, focusPersonId: string) => {
      if (!g) return;
      const childrenMap = buildChildrenMap(g);
      const parentsMap = buildParentsMap(g);

      // Start with focus person + immediate parents + immediate children
      const initial = new Set<string>([focusPersonId]);
      for (const parentId of parentsMap.get(focusPersonId) ?? []) {
        initial.add(parentId);
      }
      for (const childId of childrenMap.get(focusPersonId) ?? []) {
        initial.add(childId);
      }
      setExpandedNodeIds(initial);
    },
    [setExpandedNodeIds]
  );

  const toggleExpand = useCallback(
    (personId: string, direction: 'children' | 'parents') => {
      if (!graph) return;

      const childrenMap = buildChildrenMap(graph);
      const parentsMap = buildParentsMap(graph);

      const isExpanded = expandedNodeIds.has(personId);
      const next = new Set(expandedNodeIds);

      if (direction === 'children') {
        if (isExpanded) {
          // Collapse: remove all descendants
          const descendants = bfsDescendants(personId, childrenMap);
          for (const id of descendants) next.delete(id);
          next.delete(personId);
        } else {
          // Expand: add this node + immediate children
          next.add(personId);
          for (const childId of childrenMap.get(personId) ?? []) {
            next.add(childId);
          }
        }
      } else {
        // direction === 'parents'
        if (isExpanded) {
          const ancestors = bfsAncestors(personId, parentsMap);
          for (const id of ancestors) next.delete(id);
        } else {
          next.add(personId);
          for (const parentId of parentsMap.get(personId) ?? []) {
            next.add(parentId);
          }
        }
      }

      setExpandedNodeIds(next);
    },
    [graph, expandedNodeIds, setExpandedNodeIds]
  );

  const expandAll = useCallback(
    (g: ApiTreeGraph) => {
      const all = new Set(g.persons.map((p) => p.id));
      setExpandedNodeIds(all);
    },
    [setExpandedNodeIds]
  );

  const collapseAll = useCallback(
    (focusPersonId: string) => {
      setExpandedNodeIds(new Set([focusPersonId]));
    },
    [setExpandedNodeIds]
  );

  return { initializeExpanded, toggleExpand, expandAll, collapseAll, expandedNodeIds };
}
