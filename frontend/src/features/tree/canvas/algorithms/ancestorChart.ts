/**
 * Ancestor chart layout — focus person at bottom, ancestors above.
 * Descendant chart layout — focus person at top, descendants below.
 *
 * Both are special-cased dagre layouts with a filtered subgraph.
 * The "ancestor" variant hides descendants; the "descendant" variant hides ancestors.
 *
 * For the ancestor chart:
 *   - BFS upward from focus person
 *   - Include only ancestor persons + their connecting family groups
 *   - Run dagre TB with focus at the bottom (reverse rank order via dummy root)
 *
 * For the descendant chart:
 *   - BFS downward from focus person
 *   - Include only descendant persons + their connecting family groups
 *   - Run dagre TB with focus at the top
 */

import type { ApiTreeGraph, PositionedNode } from '../../types';
import { dagreLayout } from './dagre';
import { transformGraphToFlow } from '../useTreeTransform';

/** IDs of persons/family-groups to include in ancestor chart */
export function ancestorSubgraphIds(
  graph: ApiTreeGraph,
  focusPersonId: string,
  maxGenerations = 100
): Set<string> {
  // Parent lookup: personId → parent personIds
  const parentFamilyGroups = new Map<string, string[]>();
  for (const fg of graph.familyGroups) {
    for (const childId of Object.keys(fg.children)) {
      const existing = parentFamilyGroups.get(childId) ?? [];
      parentFamilyGroups.set(childId, [...existing, fg.id]);
    }
  }

  const fgById = new Map(graph.familyGroups.map((fg) => [fg.id, fg]));
  const included = new Set<string>();
  included.add(focusPersonId);

  let frontier = [focusPersonId];

  for (let gen = 0; gen < maxGenerations && frontier.length > 0; gen++) {
    const nextFrontier: string[] = [];
    for (const personId of frontier) {
      const fgIds = parentFamilyGroups.get(personId) ?? [];
      for (const fgId of fgIds) {
        included.add(fgId);
        const fg = fgById.get(fgId);
        if (!fg) continue;
        for (const parentId of fg.parentIds) {
          if (!included.has(parentId)) {
            included.add(parentId);
            nextFrontier.push(parentId);
          }
        }
      }
    }
    frontier = nextFrontier;
  }

  return included;
}

/** IDs of persons/family-groups to include in descendant chart */
export function descendantSubgraphIds(
  graph: ApiTreeGraph,
  focusPersonId: string,
  maxGenerations = 100
): Set<string> {
  // Child lookup: personId → familyGroupIds where they are a parent
  const childFamilyGroups = new Map<string, string[]>();
  for (const fg of graph.familyGroups) {
    for (const parentId of fg.parentIds) {
      const existing = childFamilyGroups.get(parentId) ?? [];
      childFamilyGroups.set(parentId, [...existing, fg.id]);
    }
  }

  const fgById = new Map(graph.familyGroups.map((fg) => [fg.id, fg]));
  const included = new Set<string>();
  included.add(focusPersonId);

  let frontier = [focusPersonId];

  for (let gen = 0; gen < maxGenerations && frontier.length > 0; gen++) {
    const nextFrontier: string[] = [];
    for (const personId of frontier) {
      const fgIds = childFamilyGroups.get(personId) ?? [];
      for (const fgId of fgIds) {
        included.add(fgId);
        const fg = fgById.get(fgId);
        if (!fg) continue;
        for (const childId of Object.keys(fg.children)) {
          if (!included.has(childId)) {
            included.add(childId);
            nextFrontier.push(childId);
          }
        }
      }
    }
    frontier = nextFrontier;
  }

  return included;
}

/** IDs of persons/family-groups to include in descendant-family chart.
 *  Like descendantSubgraphIds, but also includes the spouse (co-parent) at each level.
 */
export function descendantFamilySubgraphIds(
  graph: ApiTreeGraph,
  focusPersonId: string,
  maxGenerations = 100
): Set<string> {
  // Lookup: personId → family group IDs where they are a parent
  const parentToFGs = new Map<string, string[]>();
  for (const fg of graph.familyGroups) {
    for (const parentId of fg.parentIds) {
      const existing = parentToFGs.get(parentId) ?? [];
      parentToFGs.set(parentId, [...existing, fg.id]);
    }
  }

  const fgById = new Map(graph.familyGroups.map((fg) => [fg.id, fg]));
  const included = new Set<string>();
  included.add(focusPersonId);

  let frontier = [focusPersonId];

  for (let gen = 0; gen < maxGenerations && frontier.length > 0; gen++) {
    const nextFrontier: string[] = [];
    for (const personId of frontier) {
      for (const fgId of parentToFGs.get(personId) ?? []) {
        included.add(fgId);
        const fg = fgById.get(fgId);
        if (!fg) continue;
        // Include co-parents (spouses of descendants)
        for (const parentId of fg.parentIds) {
          included.add(parentId);
        }
        // Include children and queue them for further traversal
        for (const childId of Object.keys(fg.children)) {
          if (!included.has(childId)) {
            included.add(childId);
            nextFrontier.push(childId);
          }
        }
      }
    }
    frontier = nextFrontier;
  }

  return included;
}

/**
 * Layout for ancestor chart (focus at bottom, ancestors rising above).
 * Uses dagre BT (bottom-to-top) direction.
 */
export function ancestorChartLayout(
  graph: ApiTreeGraph,
  focusPersonId: string,
  maxGenerations = 6,
  nodeHGap = 40,
  nodeVGap = 80
): PositionedNode[] {
  const visibleIds = ancestorSubgraphIds(graph, focusPersonId, maxGenerations);
  const filteredGraph: ApiTreeGraph = {
    treeId: graph.treeId,
    persons: graph.persons.filter((p) => visibleIds.has(p.id)),
    familyGroups: graph.familyGroups.filter((fg) => visibleIds.has(fg.id)),
  };

  const { nodes, edges } = transformGraphToFlow(filteredGraph, {
    focusPersonId,
    expandedNodeIds: new Set(filteredGraph.persons.map((p) => p.id)),
  });

  const result = dagreLayout(nodes, edges, {
    direction: 'BT' as 'TB', // dagre supports BT (bottom-to-top)
    nodeHGap,
    nodeVGap,
  });

  return result.nodes;
}

/**
 * Layout for descendant chart (focus at top, descendants going down).
 * Uses dagre TB direction.
 */
export function descendantChartLayout(
  graph: ApiTreeGraph,
  focusPersonId: string,
  maxGenerations = 6,
  nodeHGap = 40,
  nodeVGap = 80
): PositionedNode[] {
  const visibleIds = descendantSubgraphIds(graph, focusPersonId, maxGenerations);
  const filteredGraph: ApiTreeGraph = {
    treeId: graph.treeId,
    persons: graph.persons.filter((p) => visibleIds.has(p.id)),
    familyGroups: graph.familyGroups.filter((fg) => visibleIds.has(fg.id)),
  };

  const { nodes, edges } = transformGraphToFlow(filteredGraph, {
    focusPersonId,
    expandedNodeIds: new Set(filteredGraph.persons.map((p) => p.id)),
  });

  const result = dagreLayout(nodes, edges, {
    direction: 'TB',
    nodeHGap,
    nodeVGap,
  });

  return result.nodes;
}
