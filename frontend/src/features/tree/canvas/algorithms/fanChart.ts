/**
 * Fan Chart layout algorithm.
 *
 * Places ancestors in concentric arcs radiating outward from the focus person.
 *
 *           [ great-grandparents — generation 3 ]
 *        [ grandparents — generation 2 ]
 *     [ parents — generation 1 ]
 *           [ FOCUS — centre ]
 *
 * Each generation n is drawn on a circle of radius = n * generationRadius.
 * The arc for generation n spans the angle range [startAngle, endAngle],
 * divided equally among all persons in that generation.
 *
 * Standard fan chart: 180° upper semi-circle.
 * Full-circle variant: 360° — useful when descendants are also shown.
 */

import type { ApiTreeGraph, PositionedNode } from '../../types';
import { PERSON_NODE_WIDTH, PERSON_NODE_HEIGHT } from '../../types';

export interface FanChartOptions {
  focusPersonId: string;
  /** Maximum number of ancestor generations to show */
  maxGenerations: number;
  /** Starting angle in degrees (0 = right, 90 = top). Default 180 for upper semi-circle. */
  startAngleDeg: number;
  /** Total arc span in degrees. 180 = semi-circle, 360 = full circle. */
  arcSpanDeg: number;
  /** Radius increment per generation (px) */
  generationRadius: number;
}

const DEFAULT_FAN: FanChartOptions = {
  focusPersonId: '',
  maxGenerations: 8,
  startAngleDeg: 180,
  arcSpanDeg: 180,
  generationRadius: 220,
};

function deg2rad(deg: number): number {
  return (deg * Math.PI) / 180;
}

/**
 * Build a map from personId → list of ancestor IDs per generation.
 * generation 0 = focus, 1 = parents, 2 = grandparents, ...
 */
function buildAncestorGenerations(
  graph: ApiTreeGraph,
  focusId: string,
  maxGen: number
): Map<number, string[]> {
  // Build a parent lookup: personId → parentIds
  const parentOf = new Map<string, string[]>();
  for (const fg of graph.familyGroups) {
    for (const childId of Object.keys(fg.children)) {
      const existing = parentOf.get(childId) ?? [];
      parentOf.set(childId, [...existing, ...fg.parentIds]);
    }
  }

  const generations = new Map<number, string[]>();
  generations.set(0, [focusId]);

  let currentGen = [focusId];
  for (let g = 1; g <= maxGen; g++) {
    const nextGen: string[] = [];
    for (const personId of currentGen) {
      const parents = parentOf.get(personId) ?? [];
      nextGen.push(...parents);
    }
    if (nextGen.length === 0) break;
    generations.set(g, nextGen);
    currentGen = nextGen;
  }

  return generations;
}

/**
 * Compute fan chart positions for ancestors of the focus person.
 *
 * @returns Array of positioned nodes (top-left coordinates for React Flow)
 */
export function fanChartLayout(
  graph: ApiTreeGraph,
  options: Partial<FanChartOptions> = {}
): PositionedNode[] {
  const opts = { ...DEFAULT_FAN, ...options };

  if (!opts.focusPersonId) return [];

  const generations = buildAncestorGenerations(
    graph,
    opts.focusPersonId,
    opts.maxGenerations
  );

  const positioned: PositionedNode[] = [];
  const arcRad = deg2rad(opts.arcSpanDeg);
  const startRad = deg2rad(opts.startAngleDeg);

  for (const [gen, personIds] of generations) {
    if (gen === 0) {
      // Focus person at origin
      positioned.push({
        id: opts.focusPersonId,
        x: -PERSON_NODE_WIDTH / 2,
        y: -PERSON_NODE_HEIGHT / 2,
      });
      continue;
    }

    const radius = gen * opts.generationRadius;
    const count = personIds.length;

    // Divide the arc equally
    const sliceRad = count > 1 ? arcRad / count : arcRad;

    for (let i = 0; i < count; i++) {
      // Centre of this person's arc slice
      const angle = startRad + (i + 0.5) * sliceRad;
      // Negate Y because canvas Y increases downward, but we want up
      const cx = Math.cos(angle) * radius;
      const cy = -Math.sin(angle) * radius;

      positioned.push({
        id: personIds[i],
        x: cx - PERSON_NODE_WIDTH / 2,
        y: cy - PERSON_NODE_HEIGHT / 2,
      });
    }
  }

  return positioned;
}

/**
 * Compute which person nodes and family group nodes are visible in fan mode.
 * Fan chart shows person nodes only (no family group junction nodes).
 */
export function fanChartVisibleIds(
  graph: ApiTreeGraph,
  focusPersonId: string,
  maxGenerations: number
): Set<string> {
  const generations = buildAncestorGenerations(graph, focusPersonId, maxGenerations);
  const visible = new Set<string>();
  for (const ids of generations.values()) {
    for (const id of ids) visible.add(id);
  }
  return visible;
}
