/**
 * Dagre layout algorithm for vertical (TB) and horizontal (LR) tree modes.
 *
 * Uses dagre's layered graph layout, which produces clean generational ranks.
 * Works on the bipartite PersonNode ↔ FamilyGroupNode graph directly.
 */

import dagre from 'dagre';
import type { TreeNode, TreeEdge, LayoutOptions, PositionedNode } from '../../types';
import { PERSON_NODE_WIDTH, PERSON_NODE_HEIGHT, FAMILY_NODE_SIZE } from '../../types';

export interface DagreResult {
  nodes: PositionedNode[];
  /** Total graph dimensions (useful for centering / fitView) */
  width: number;
  height: number;
}

/**
 * Run the dagre layout algorithm.
 *
 * @param nodes  React Flow nodes (unpositioned)
 * @param edges  React Flow edges
 * @param opts   Layout options (direction, gaps)
 * @returns      Array of { id, x, y } positioned nodes
 */
export function dagreLayout(
  nodes: TreeNode[],
  edges: TreeEdge[],
  opts: Pick<LayoutOptions, 'direction' | 'nodeHGap' | 'nodeVGap'>
): DagreResult {
  const g = new dagre.graphlib.Graph();

  g.setDefaultEdgeLabel(() => ({}));

  g.setGraph({
    rankdir: opts.direction,          // 'TB' | 'LR'
    ranksep: opts.nodeVGap,           // gap between generations
    nodesep: opts.nodeHGap,           // gap between siblings
    edgesep: 10,
    marginx: 40,
    marginy: 40,
    acyclicer: 'greedy',              // handle any accidental cycles gracefully
    ranker: 'network-simplex',        // best balance for genealogy graphs
  });

  // Add nodes
  for (const node of nodes) {
    const isPerson = node.type === 'person';
    g.setNode(node.id, {
      width:  isPerson ? PERSON_NODE_WIDTH  : FAMILY_NODE_SIZE,
      height: isPerson ? PERSON_NODE_HEIGHT : FAMILY_NODE_SIZE,
    });
  }

  // Add edges
  for (const edge of edges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  const positioned: PositionedNode[] = [];
  let maxX = 0;
  let maxY = 0;

  for (const node of nodes) {
    const n = g.node(node.id);
    if (!n) continue;

    // dagre returns centre coordinates; React Flow uses top-left
    const x = n.x - n.width / 2;
    const y = n.y - n.height / 2;

    positioned.push({ id: node.id, x, y });
    if (x + n.width  > maxX) maxX = x + n.width;
    if (y + n.height > maxY) maxY = y + n.height;
  }

  return { nodes: positioned, width: maxX, height: maxY };
}
