/**
 * useTreeLayout — orchestrates graph transform + layout algorithm.
 *
 * Pipeline:
 *   ApiTreeGraph
 *     → transformGraphToFlow()   (pure: API → RF nodes/edges)
 *     → filter by expandedNodeIds
 *     → apply layout algorithm   (dagre / fan / ancestor / descendant)
 *     → return positioned ReactFlow nodes + edges
 */

import { useMemo } from 'react';
import type { ApiTreeGraph, TreeNode, TreeEdge, LayoutOptions, LayoutMode, UnionEdgeData } from '../types';
import { transformGraphToFlow } from './useTreeTransform';
import { dagreLayout } from './algorithms/dagre';
import { fanChartLayout, fanChartVisibleIds } from './algorithms/fanChart';
import {
  ancestorChartLayout,
  ancestorSubgraphIds,
  descendantChartLayout,
  descendantFamilySubgraphIds,
} from './algorithms/ancestorChart';
import { familyTreeLayout } from './algorithms/familyTree';
import { pedigreeChartLayout, pedigreeChartVisibleIds } from './algorithms/pedigreeChart';

export interface UseTreeLayoutResult {
  nodes: TreeNode[];
  edges: TreeEdge[];
}

/**
 * Deduplicate family-group nodes: when multiple FGs share the same visible
 * parent set, keep only the one with the most children.  This mirrors the
 * dedup in filterByExpanded() but is applied to subgraph-filtered views
 * (descendant-family, ancestor-family) where filterByExpanded is skipped.
 */
function deduplicateFGNodes(
  nodes: TreeNode[],
  edges: TreeEdge[],
): { nodes: TreeNode[]; edges: TreeEdge[] } {
  const personNodes = nodes.filter((n) => n.type === 'person');
  const fgNodes     = nodes.filter((n) => n.type === 'family-group');
  const visiblePersonIds = new Set(personNodes.map((n) => n.id));

  const childCountOf = (fgId: string) =>
    edges.filter((e) => e.source === fgId && (e.data as any)?.kind === 'parent-child').length;

  const parentKeyToFgId = new Map<string, string>();
  for (const n of fgNodes) {
    const key = [...((n.data as any).parentIds as string[])]
      .filter((pid: string) => visiblePersonIds.has(pid))
      .sort()
      .join('|');
    if (!key) continue;
    const existing = parentKeyToFgId.get(key);
    if (!existing || childCountOf(n.id) > childCountOf(existing)) {
      parentKeyToFgId.set(key, n.id);
    }
  }

  const keptFgIds = new Set(parentKeyToFgId.values());
  const dedupedNodes = [...personNodes, ...fgNodes.filter((n) => keptFgIds.has(n.id))];
  const visibleIds   = new Set(dedupedNodes.map((n) => n.id));
  const dedupedEdges = edges.filter((e) => visibleIds.has(e.source) && visibleIds.has(e.target));

  return { nodes: dedupedNodes, edges: dedupedEdges };
}

/**
 * Recompute union ordinals on a filtered edge set so labels reflect only
 * the visible unions (e.g., "1st Marriage", "2nd Marriage") rather than
 * stale ordinals from the full graph.
 *
 * Only couple FGs (2+ visible parents) participate in ordinal counting —
 * single-parent FGs are data artifacts and shouldn't inflate ordinals.
 */
function recomputeUnionOrdinals(edges: TreeEdge[], graph: ApiTreeGraph): TreeEdge[] {
  const fgById = new Map(graph.familyGroups.map((fg) => [fg.id, fg]));
  const personById = new Map(graph.persons.map((p) => [p.id, p]));

  const fgDateOrder = (fg: typeof graph.familyGroups[number] | undefined): number => {
    if (!fg) return 9999;
    if (fg.unionDateYear != null) return fg.unionDateYear;
    if (fg.unionDate) {
      const y = parseInt(fg.unionDate.slice(0, 4), 10);
      if (!isNaN(y)) return y;
    }
    const childYears = Object.keys(fg.children)
      .map((cid) => personById.get(cid)?.birthYear)
      .filter((y): y is number => typeof y === 'number');
    return childYears.length > 0 ? Math.min(...childYears) : 9999;
  };

  // Count visible parents per FG (from union edges)
  const fgParentCount = new Map<string, number>();
  for (const e of edges) {
    if ((e.data as any)?.kind !== 'union') continue;
    fgParentCount.set(e.target, (fgParentCount.get(e.target) ?? 0) + 1);
  }

  const perPerson = new Map<string, Array<{ fgId: string; unionType: string }>>();
  for (const e of edges) {
    if ((e.data as any)?.kind !== 'union') continue;
    // Only count couple FGs (2+ visible parents) for ordinal labeling
    if ((fgParentCount.get(e.target) ?? 0) < 2) continue;
    const fg = fgById.get(e.target);
    if (!fg) continue;
    if (!perPerson.has(e.source)) perPerson.set(e.source, []);
    const list = perPerson.get(e.source)!;
    if (!list.some((x) => x.fgId === e.target)) {
      list.push({ fgId: e.target, unionType: fg.unionType });
    }
  }

  for (const fgs of perPerson.values()) {
    fgs.sort((a, b) => fgDateOrder(fgById.get(a.fgId)) - fgDateOrder(fgById.get(b.fgId)));
  }

  const ordinals = new Map<string, number>();
  for (const [personId, fgs] of perPerson) {
    const byType = new Map<string, string[]>();
    for (const { fgId, unionType } of fgs) {
      if (!byType.has(unionType)) byType.set(unionType, []);
      byType.get(unionType)!.push(fgId);
    }
    for (const fgIds of byType.values()) {
      if (fgIds.length >= 2) {
        fgIds.forEach((fgId, idx) => {
          ordinals.set(`${personId}::${fgId}`, idx + 1);
        });
      }
    }
  }

  const fgUnionEdges = new Map<string, TreeEdge[]>();
  for (const e of edges) {
    if ((e.data as any)?.kind !== 'union') continue;
    if (!fgUnionEdges.has(e.target)) fgUnionEdges.set(e.target, []);
    fgUnionEdges.get(e.target)!.push(e);
  }

  const updated = new Map<string, TreeEdge>();
  for (const [fgId, fgEdges] of fgUnionEdges) {
    const fg = fgById.get(fgId);
    let labelIdx = -1;
    let bestCount = 0;
    let bestOrd = 0;
    fgEdges.forEach((e, i) => {
      const pFgs = perPerson.get(e.source);
      const typeCount = pFgs?.filter((f) => f.unionType === fg?.unionType).length ?? 0;
      const ord = ordinals.get(`${e.source}::${fgId}`) ?? 0;
      if (typeCount > bestCount || (typeCount === bestCount && ord > bestOrd)) {
        bestCount = typeCount;
        bestOrd = ord;
        labelIdx = i;
      }
    });
    const customIdx = labelIdx >= 0 ? labelIdx : 0;

    fgEdges.forEach((e, i) => {
      updated.set(e.id, {
        ...e,
        data: {
          ...(e.data as UnionEdgeData),
          unionOrdinal: i === labelIdx ? ordinals.get(`${e.source}::${fgId}`) : undefined,
          customLabel: i === customIdx ? fg?.customLabel : undefined,
        },
      } as TreeEdge);
    });
  }

  return edges.map((e) => updated.get(e.id) ?? e);
}

/**
 * Filter nodes/edges to only those in the expandedNodeIds set.
 * Family group nodes are visible only if at least one of their parent persons is visible.
 */
function filterByExpanded(
  nodes: TreeNode[],
  edges: TreeEdge[],
  expandedNodeIds: Set<string>
): { nodes: TreeNode[]; edges: TreeEdge[] } {
  const visiblePersonIds = new Set(
    nodes
      .filter((n) => n.type === 'person' && expandedNodeIds.has(n.id))
      .map((n) => n.id)
  );

  // A family group is visible if at least one of its parent persons is visible
  const candidateFamilyGroups = nodes.filter(
    (n) =>
      n.type === 'family-group' &&
      (n.data as any).parentIds.some((pid: string) => visiblePersonIds.has(pid))
  );

  // Deduplicate: for each unique set of visible parents, keep only one family group.
  // When there are multiple, prefer the one with the most children (most parent-child edges).
  const childCountOf = (fgId: string) =>
    edges.filter((e) => e.source === fgId && (e.data as any)?.kind === 'parent-child').length;

  const parentKeyToFgId = new Map<string, string>();
  for (const n of candidateFamilyGroups) {
    const key = [...((n.data as any).parentIds as string[])]
      .filter((pid) => visiblePersonIds.has(pid))
      .sort()
      .join('|');
    if (!key) continue;
    const existing = parentKeyToFgId.get(key);
    if (!existing || childCountOf(n.id) > childCountOf(existing)) {
      parentKeyToFgId.set(key, n.id);
    }
  }

  const visibleFamilyGroupIds = new Set(parentKeyToFgId.values());

  const visibleIds = new Set([...visiblePersonIds, ...visibleFamilyGroupIds]);

  const filteredNodes = nodes.filter((n) => visibleIds.has(n.id));
  const filteredEdges = edges.filter(
    (e) => visibleIds.has(e.source) && visibleIds.has(e.target)
  );

  return { nodes: filteredNodes, edges: filteredEdges };
}

/**
 * Apply the selected layout algorithm and patch node positions.
 */
function applyLayout(
  nodes: TreeNode[],
  edges: TreeEdge[],
  graph: ApiTreeGraph,
  opts: LayoutOptions
): TreeNode[] {
  let positions: Array<{ id: string; x: number; y: number }>;

  switch (opts.mode) {
    case 'generation': {
      const { nodes: positioned } = dagreLayout(nodes, edges, {
        direction: 'TB',
        nodeHGap: opts.nodeHGap ?? 32,
        nodeVGap: opts.nodeVGap ?? 80,
      });
      positions = positioned;
      break;
    }

    case 'compact': {
      // familyTreeLayout with tighter spacing: keeps spouses adjacent and
      // children directly below their family group — no crossing union edges.
      const visiblePersonIds = new Set(
        nodes.filter((n) => n.type === 'person').map((n) => n.id)
      );
      const visibleFGIds = new Set(
        nodes.filter((n) => n.type === 'family-group').map((n) => n.id)
      );
      const filteredGraph: ApiTreeGraph = {
        treeId: graph.treeId,
        persons: graph.persons.filter((p) => visiblePersonIds.has(p.id)),
        familyGroups: graph.familyGroups
          .filter((fg) => visibleFGIds.has(fg.id))
          .map((fg) => ({
            ...fg,
            parentIds: fg.parentIds.filter((pid) => visiblePersonIds.has(pid)),
            children: Object.fromEntries(
              Object.entries(fg.children).filter(([cid]) => visiblePersonIds.has(cid))
            ),
          })),
      };
      positions = familyTreeLayout(filteredGraph, {
        nodeHGap: 20,
        nodeVGap: 60,
      });
      break;
    }

    case 'fan': {
      positions = fanChartLayout(graph, {
        focusPersonId: opts.focusPersonId,
        maxGenerations: 8,
        startAngleDeg: 180,
        arcSpanDeg: 180,
        generationRadius: 240,
      });
      break;
    }

    case 'ancestry-fan': {
      // Rendered as a single custom node in TreeCanvasInner; no positions needed.
      positions = [];
      break;
    }

    case 'pedigree': {
      positions = pedigreeChartLayout(graph, opts.focusPersonId ?? '', 8);
      break;
    }

    case 'ancestor': {
      positions = ancestorChartLayout(
        graph,
        opts.focusPersonId ?? '',
        8,
        opts.nodeHGap,
        opts.nodeVGap
      );
      break;
    }

    case 'descendant': {
      positions = descendantChartLayout(
        graph,
        opts.focusPersonId ?? '',
        8,
        opts.nodeHGap,
        opts.nodeVGap
      );
      break;
    }

    case 'ancestor-family':
    case 'descendant-family': {
      // Use familyTreeLayout so couples are kept adjacent.
      // filteredNodes already contains the correct subgraph (set in the pre-filter step above).
      const visiblePersonIds = new Set(
        nodes.filter((n) => n.type === 'person').map((n) => n.id)
      );
      const visibleFGIds = new Set(
        nodes.filter((n) => n.type === 'family-group').map((n) => n.id)
      );
      const filteredGraph: ApiTreeGraph = {
        treeId: graph.treeId,
        persons: graph.persons.filter((p) => visiblePersonIds.has(p.id)),
        familyGroups: graph.familyGroups
          .filter((fg) => visibleFGIds.has(fg.id))
          .map((fg) => ({
            ...fg,
            parentIds: fg.parentIds.filter((pid) => visiblePersonIds.has(pid)),
            children: Object.fromEntries(
              Object.entries(fg.children).filter(([cid]) => visiblePersonIds.has(cid))
            ),
          })),
      };
      positions = familyTreeLayout(filteredGraph, {
        nodeHGap: opts.nodeHGap,
        nodeVGap: opts.nodeVGap,
      });
      break;
    }

    case 'vertical': {
      // Build a filtered ApiTreeGraph from the already-expanded visible nodes
      // so familyTreeLayout only sees what's on screen.
      const visiblePersonIds = new Set(
        nodes.filter((n) => n.type === 'person').map((n) => n.id)
      );
      const visibleFGIds = new Set(
        nodes.filter((n) => n.type === 'family-group').map((n) => n.id)
      );
      const filteredGraph: ApiTreeGraph = {
        treeId: graph.treeId,
        persons: graph.persons.filter((p) => visiblePersonIds.has(p.id)),
        familyGroups: graph.familyGroups
          .filter((fg) => visibleFGIds.has(fg.id))
          .map((fg) => ({
            ...fg,
            parentIds: fg.parentIds.filter((pid) => visiblePersonIds.has(pid)),
            children: Object.fromEntries(
              Object.entries(fg.children).filter(([cid]) => visiblePersonIds.has(cid))
            ),
          })),
      };
      positions = familyTreeLayout(filteredGraph, {
        nodeHGap: opts.nodeHGap,
        nodeVGap: opts.nodeVGap,
        alignByBirthYear: true,
      });
      break;
    }

    case 'horizontal':
    default: {
      const { nodes: positioned } = dagreLayout(nodes, edges, {
        direction: 'LR',
        nodeHGap: opts.nodeHGap,
        nodeVGap: opts.nodeVGap,
      });
      positions = positioned;
      break;
    }
  }

  const posMap = new Map(positions.map((p) => [p.id, p]));

  return nodes.map((node) => {
    const pos = posMap.get(node.id);
    if (!pos) return node;
    return { ...node, position: { x: pos.x, y: pos.y } };
  });
}

// ── Hook ───────────────────────────────────────────────────────────────────

export function useTreeLayout(
  graph: ApiTreeGraph | null,
  expandedNodeIds: Set<string>,
  layoutOpts: LayoutOptions
): UseTreeLayoutResult {
  return useMemo(() => {
    if (!graph) return { nodes: [], edges: [] };

    // 1. Transform API graph → RF nodes/edges (positions = 0,0)
    const { nodes: rawNodes, edges: rawEdges } = transformGraphToFlow(graph, {
      focusPersonId: layoutOpts.focusPersonId,
      expandedNodeIds,
    });

    // 2. For fan mode, use a special visible set instead of expandedNodeIds
    let filteredNodes: TreeNode[];
    let filteredEdges: TreeEdge[];

    if (layoutOpts.mode === 'fan' && layoutOpts.focusPersonId) {
      const visibleIds = fanChartVisibleIds(graph, layoutOpts.focusPersonId, 4);
      filteredNodes = rawNodes.filter((n) => n.type === 'person' && visibleIds.has(n.id));
      filteredEdges = []; // fan chart has no edges
    } else if (layoutOpts.mode === 'pedigree' && layoutOpts.focusPersonId) {
      const visibleIds = pedigreeChartVisibleIds(graph, layoutOpts.focusPersonId, 4);
      filteredNodes = rawNodes.filter((n) => visibleIds.has(n.id));
      filteredEdges = rawEdges.filter(
        (e) => visibleIds.has(e.source) && visibleIds.has(e.target),
      );
    } else if (layoutOpts.mode === 'ancestor-family' && layoutOpts.focusPersonId) {
      const visibleIds = ancestorSubgraphIds(graph, layoutOpts.focusPersonId, 100);
      const preNodes = rawNodes.filter((n) => visibleIds.has(n.id));
      const preEdges = rawEdges.filter((e) => visibleIds.has(e.source) && visibleIds.has(e.target));
      const deduped  = deduplicateFGNodes(preNodes, preEdges);
      filteredNodes  = deduped.nodes;
      filteredEdges  = recomputeUnionOrdinals(deduped.edges, graph);
    } else if (layoutOpts.mode === 'descendant-family' && layoutOpts.focusPersonId) {
      const visibleIds = descendantFamilySubgraphIds(graph, layoutOpts.focusPersonId, 100);
      const preNodes = rawNodes.filter((n) => visibleIds.has(n.id));
      const preEdges = rawEdges.filter((e) => visibleIds.has(e.source) && visibleIds.has(e.target));
      const deduped  = deduplicateFGNodes(preNodes, preEdges);
      filteredNodes  = deduped.nodes;
      filteredEdges  = recomputeUnionOrdinals(deduped.edges, graph);
    } else {
      ({ nodes: filteredNodes, edges: filteredEdges } = filterByExpanded(
        rawNodes,
        rawEdges,
        expandedNodeIds
      ));
    }

    // 3. Apply layout algorithm (patches x/y positions)
    const positionedNodes = applyLayout(filteredNodes, filteredEdges, graph, layoutOpts);

    return { nodes: positionedNodes, edges: filteredEdges };
  }, [graph, expandedNodeIds, layoutOpts]);
}
